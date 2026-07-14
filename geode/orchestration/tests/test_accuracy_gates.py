"""Tests for hard accuracy gates."""

from __future__ import annotations

from datetime import date

from geode.orchestration.contracts import (
    Answer,
    AuthorityLevel,
    Citation,
    CoverageContract,
    CoverageRequirement,
    CoverageStatus,
    CurrencyMetadata,
    CurrencyStatus,
    Evidence,
    ExpectedCategory,
    GateAction,
    Intent,
    Provenance,
    QueryState,
    VerificationStatus,
)
from geode.orchestration.pipeline import Pipeline
from geode.orchestration.stages import (
    AbsenceVerificationStage,
    CheckCompletenessStage,
    CheckFaithfulnessStage,
    EnforceGroundingStage,
    VerifyCitationsStage,
    VerifyCurrencyStage,
)


def test_fabricated_citation_is_stripped_and_claim_does_not_survive() -> None:
    """Citation gate strips claims whose citations are absent from evidence."""

    state = QueryState(
        intent=Intent(raw_query="What applies?"),
        evidence=[_evidence("ev-real", "CRS-25-7-109", "Facilities must report emissions.")],
        answer=Answer(
            answer_text="FAKE-999 says facilities must register.",
            citations=[
                Citation(
                    citation_text="FAKE-999",
                    canonical_id="FAKE-999",
                    authority_level=AuthorityLevel.STATE,
                )
            ],
            evidence_ids=["ev-real"],
            confidence=0.9,
        ),
    )

    result = VerifyCitationsStage("verify_citations")(state)

    assert result.answer is not None
    assert result.answer.answer_text == ""
    assert result.answer.citations == []
    gate = result.verification_report.gate_results[0] if result.verification_report else None
    assert gate is not None
    assert gate.action == GateAction.STRIP
    assert gate.stripped_citations == ["FAKE-999"]


def test_repealed_provision_is_flagged_by_currency_gate() -> None:
    """Currency gate flags repealed current-law evidence."""

    evidence = _evidence(
        "ev-repealed",
        "CRS-25-7-109",
        "Facilities must report emissions.",
        currency=CurrencyMetadata(
            effective_date=date(2020, 1, 1),
            status=CurrencyStatus.REPEALED,
            repeal_status="repealed",
            as_of_date=date(2026, 7, 14),
        ),
    )
    state = QueryState(
        intent=Intent(raw_query="What applies now?"),
        evidence=[evidence],
        answer=_answer("CRS-25-7-109 requires reporting.", evidence),
    )

    result = VerifyCurrencyStage("verify_currency")(state)

    assert result.answer is not None
    assert result.answer.confidence == 0.5
    gate = result.verification_report.gate_results[0] if result.verification_report else None
    assert gate is not None
    assert gate.action == GateAction.DOWNGRADE
    assert gate.flagged_evidence_ids == ["ev-repealed"]


def test_missing_category_is_flagged_by_completeness_gate() -> None:
    """Completeness gate flags omitted required categories."""

    state = QueryState(
        intent=Intent(raw_query="What applies?"),
        coverage_contract=CoverageContract(
            expected_categories=[
                ExpectedCategory(
                    category_id="colorado_regulations",
                    label="Colorado regulations",
                    authority_level=AuthorityLevel.STATE,
                    requirement=CoverageRequirement.REQUIRED,
                    status=CoverageStatus.EMPTY,
                    reason="Required for compliance survey.",
                )
            ]
        ),
        answer=Answer(answer_text="Available sources were reviewed.", confidence=0.8),
    )

    result = CheckCompletenessStage("check_completeness")(state)

    assert "colorado_regulations" in result.empty_expected_categories
    assert result.answer is not None
    assert "Retrieval gaps: colorado_regulations." in result.answer.answer_text
    gate = result.verification_report.gate_results[0] if result.verification_report else None
    assert gate is not None
    assert gate.missing_categories == ["colorado_regulations"]


def test_unsupported_sentence_is_removed_by_faithfulness_gate() -> None:
    """Faithfulness gate removes sentences not entailed by evidence."""

    evidence = _evidence("ev-real", "CRS-25-7-109", "Facilities must report emissions.")
    state = QueryState(
        intent=Intent(raw_query="What applies?"),
        evidence=[evidence],
        answer=Answer(
            answer_text="Facilities must report emissions. They must install scrubbers.",
            citations=[evidence.citation],
            evidence_ids=["ev-real"],
            confidence=0.9,
        ),
    )

    result = CheckFaithfulnessStage("check_faithfulness")(state)

    assert result.answer is not None
    assert "Facilities must report emissions." in result.answer.answer_text
    assert "scrubbers" not in result.answer.answer_text
    gate = result.verification_report.gate_results[0] if result.verification_report else None
    assert gate is not None
    assert gate.action == GateAction.STRIP


def test_absence_verification_rewrites_retrieval_limit_as_not_verified_absence() -> None:
    """Absence gate does not allow none-found wording to become verified absence."""

    state = QueryState(
        intent=Intent(raw_query="What applies?"),
        answer=Answer(answer_text="No such requirement exists.", confidence=0.7),
    )

    result = AbsenceVerificationStage("absence_verification")(state)

    assert result.answer is not None
    assert "no candidate source was found" in result.answer.answer_text
    gate = result.verification_report.gate_results[0] if result.verification_report else None
    assert gate is not None
    assert gate.action == GateAction.STRIP


def test_gate_outcomes_are_recorded_in_report_and_trace() -> None:
    """Every gate writes a structured report result and trace event."""

    evidence = _evidence("ev-real", "CRS-25-7-109", "Facilities must report emissions.")
    state = QueryState(
        intent=Intent(raw_query="What applies?"),
        evidence=[evidence],
        answer=_answer("Facilities must report emissions.", evidence),
    )

    result = Pipeline(
        [
            EnforceGroundingStage("enforce_grounding"),
            VerifyCitationsStage("verify_citations"),
            VerifyCurrencyStage("verify_currency"),
            CheckFaithfulnessStage("check_faithfulness"),
            AbsenceVerificationStage("absence_verification"),
        ]
    ).run(state)

    assert result.verification_report is not None
    assert result.verification_report.status == VerificationStatus.PASSED
    assert result.verification_report.checks_run == [
        "enforce_grounding",
        "verify_citations",
        "verify_currency",
        "check_faithfulness",
        "absence_verification",
    ]
    trace_names = [entry.stage_name for entry in result.trace]
    for gate_name in result.verification_report.checks_run:
        assert gate_name in trace_names


def _evidence(
    evidence_id: str,
    source_id: str,
    text: str,
    currency: CurrencyMetadata | None = None,
) -> Evidence:
    """Create assembled evidence for gate tests."""

    return Evidence(
        evidence_id=evidence_id,
        text=text,
        citation=Citation(
            citation_text=source_id,
            canonical_id=source_id,
            authority_level=AuthorityLevel.STATE,
        ),
        provenance=Provenance(source_id=source_id, source_path=f"_fixture/{source_id}.json"),
        confidence=0.9,
        is_candidate=False,
        assembled=True,
        authority_level=AuthorityLevel.STATE,
        currency=currency
        or CurrencyMetadata(
            effective_date=date(2026, 1, 1),
            status=CurrencyStatus.CURRENT,
            amendment_status="not_reported",
            repeal_status="not_reported",
            as_of_date=date(2026, 7, 14),
        ),
    )


def _answer(text: str, evidence: Evidence) -> Answer:
    """Create an answer citing one evidence item."""

    return Answer(
        answer_text=text,
        citations=[evidence.citation],
        evidence_ids=[evidence.evidence_id],
        confidence=0.9,
    )
