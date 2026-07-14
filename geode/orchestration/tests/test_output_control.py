"""Tests for output shaping and control."""

from __future__ import annotations

from datetime import date

from geode.orchestration.contracts import (
    Answer,
    AuthorityLevel,
    Citation,
    ConfidenceLevel,
    CoverageContract,
    CoverageRequirement,
    CoverageStatus,
    CurrencyMetadata,
    CurrencyStatus,
    EmittedAnswer,
    Evidence,
    ExpectedCategory,
    FinalAnswer,
    Intent,
    Provenance,
    QueryState,
)
from geode.orchestration.pipeline import Pipeline
from geode.orchestration.stages import (
    CalibrateConfidenceStage,
    EmitStage,
    EscalationHookStage,
    GuardrailsStage,
    ValidateAnswerContractStage,
)


def test_confidence_is_reproducible_from_evidence_inputs() -> None:
    """Confidence is computed, not taken from the draft answer."""

    state_a = _state(answer_confidence=0.1)
    state_b = _state(answer_confidence=0.99)

    result_a = CalibrateConfidenceStage("calibrate_confidence")(state_a)
    result_b = CalibrateConfidenceStage("calibrate_confidence")(state_b)

    assert result_a.confidence_report is not None
    assert result_b.confidence_report is not None
    assert result_a.confidence_report.score == result_b.confidence_report.score
    assert result_a.answer is not None
    assert result_a.answer.confidence == result_a.confidence_report.score


def test_nonconforming_model_output_is_repaired_to_final_schema() -> None:
    """Raw draft answer is repaired into the strict final answer contract."""

    result = Pipeline(
        [
            CalibrateConfidenceStage("calibrate_confidence"),
            ValidateAnswerContractStage("validate_answer_contract"),
            GuardrailsStage("guardrails"),
        ]
    ).run(_state(answer_text="Facilities must report emissions."))

    assert result.final_answer is not None
    assert result.final_answer.summary == "Facilities must report emissions."
    assert result.final_answer.requirements[0].text == "Facilities must report emissions."
    assert result.final_answer.citations[0].canonical_id == "CRS-25-7-109"
    assert result.final_answer.disclaimers


def test_low_confidence_sample_triggers_escalation_flag() -> None:
    """Low-confidence final output is flagged for human review."""

    state = _state(
        evidence=[
            _evidence(
                "ev-low",
                "CRS-25-7-109",
                "Facilities must report emissions.",
                AuthorityLevel.MUNICIPAL,
                CurrencyStatus.REPEALED,
            )
        ],
        categories=[
            ExpectedCategory(
                category_id="colorado_regulations",
                label="Colorado regulations",
                authority_level=AuthorityLevel.STATE,
                requirement=CoverageRequirement.REQUIRED,
                status=CoverageStatus.EMPTY,
                reason="Required.",
            )
        ],
    )

    result = Pipeline(
        [
            CalibrateConfidenceStage("calibrate_confidence"),
            ValidateAnswerContractStage("validate_answer_contract"),
            GuardrailsStage("guardrails"),
            EscalationHookStage("escalation_hook"),
        ]
    ).run(state)

    assert result.final_answer is not None
    assert result.final_answer.confidence.level == ConfidenceLevel.LOW
    assert result.escalation_required is True
    assert result.final_answer.escalation_required is True


def test_emit_produces_final_answer_validating_against_json_schema() -> None:
    """Final emitted answer validates against the answer JSON Schema."""

    result = Pipeline(
        [
            CalibrateConfidenceStage("calibrate_confidence"),
            ValidateAnswerContractStage("validate_answer_contract"),
            GuardrailsStage("guardrails"),
            EscalationHookStage("escalation_hook"),
            EmitStage("emit"),
        ]
    ).run(_state())

    assert result.emitted_answer is not None
    payload = result.emitted_answer.model_dump_json()
    round_tripped = EmittedAnswer.model_validate_json(payload)
    assert round_tripped.answer == result.final_answer
    schema = FinalAnswer.model_json_schema()
    assert schema["type"] == "object"
    assert set(schema["properties"]) >= {
        "summary",
        "requirements",
        "citations",
        "jurisdictions",
        "confidence",
        "uncertainties",
        "coverage_gaps",
    }


def _state(
    answer_text: str = "Facilities must report emissions.",
    answer_confidence: float = 0.2,
    evidence: list[Evidence] | None = None,
    categories: list[ExpectedCategory] | None = None,
) -> QueryState:
    """Build a state for output-control tests."""

    evidence_items = evidence or [
        _evidence(
            "ev-reporting",
            "CRS-25-7-109",
            "Facilities must report emissions.",
            AuthorityLevel.STATE,
            CurrencyStatus.CURRENT,
        )
    ]
    category_items = categories or [
        ExpectedCategory(
            category_id="colorado_regulations",
            label="Colorado regulations",
            authority_level=AuthorityLevel.STATE,
            requirement=CoverageRequirement.REQUIRED,
            status=CoverageStatus.FOUND,
            reason="Required.",
        )
    ]
    return QueryState(
        intent=Intent(raw_query="What applies?"),
        evidence=evidence_items,
        coverage_contract=CoverageContract(expected_categories=category_items),
        answer=Answer(
            answer_text=answer_text,
            citations=[evidence_items[0].citation],
            evidence_ids=[evidence_items[0].evidence_id],
            confidence=answer_confidence,
        ),
    )


def _evidence(
    evidence_id: str,
    source_id: str,
    text: str,
    authority_level: AuthorityLevel,
    currency_status: CurrencyStatus,
) -> Evidence:
    """Create assembled evidence."""

    return Evidence(
        evidence_id=evidence_id,
        text=text,
        citation=Citation(
            citation_text=source_id,
            canonical_id=source_id,
            authority_level=authority_level,
        ),
        provenance=Provenance(source_id=source_id, source_path=f"_fixture/{source_id}.json"),
        confidence=0.9,
        is_candidate=False,
        assembled=True,
        authority_level=authority_level,
        currency=CurrencyMetadata(
            effective_date=date(2026, 1, 1),
            status=currency_status,
            amendment_status="not_reported",
            repeal_status="not_reported",
            as_of_date=date(2026, 7, 14),
        ),
    )
