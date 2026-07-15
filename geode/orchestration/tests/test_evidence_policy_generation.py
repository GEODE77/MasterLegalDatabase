"""Tests for evidence assembly, policy injection, and draft generation."""

from __future__ import annotations

from datetime import date

from geode.orchestration.contracts import (
    AuthorityLevel,
    Citation,
    ConflictStatus,
    CurrencyMetadata,
    CurrencyStatus,
    Evidence,
    Intent,
    Jurisdiction,
    Provenance,
    QueryState,
)
from geode.orchestration.pipeline import Pipeline
from geode.orchestration.stages import (
    AssembleEvidenceStage,
    ConflictDetectionStage,
    GenerateDraftStage,
    InjectReasoningPoliciesStage,
)


def test_assemble_evidence_adds_provenance_currency_and_jurisdiction() -> None:
    """Assembled evidence carries provenance chain and currency metadata."""

    state = QueryState(
        intent=Intent(raw_query="What applies?"),
        jurisdiction=Jurisdiction(),
        evidence=[
            _candidate(
                "ev-reg",
                "5_CCR_1001-9",
                "Colorado regulation requires reporting for emissions.",
                AuthorityLevel.STATE,
                category_id="reporting_rules",
                relationship_path=["CRS-25-7-109", "5_CCR_1001-9"],
            )
        ],
    )

    result = AssembleEvidenceStage("assemble_evidence")(state)

    evidence = result.evidence[0]
    assert evidence.assembled is True
    assert evidence.is_candidate is False
    assert evidence.authority_level == AuthorityLevel.STATE
    assert evidence.enabling_statute == "CRS-25-7-109"
    assert evidence.jurisdiction is not None
    assert evidence.currency.status == CurrencyStatus.UNKNOWN
    assert evidence.currency.repeal_status == "not_verified"
    assert evidence.currency.as_of_date is None
    assert evidence.provenance.chain[:3] == ["claim:pending", result.query_id, "reporting_rules"]
    assert "5_CCR_1001-9" in evidence.provenance.chain


def test_conflict_detection_marks_hierarchy_resolution_and_unresolved_conflicts() -> None:
    """Seeded conflicts are resolved by hierarchy or flagged unresolved."""

    federal = _assembled(
        "ev-fed",
        "40_CFR_98",
        "Facilities must report greenhouse gas emissions.",
        AuthorityLevel.FEDERAL,
        conflict_group="reporting",
    )
    state = _state_with_evidence(
        [
            federal,
            _assembled(
                "ev-state",
                "5_CCR_1001-9",
                "Facilities are not required to report greenhouse gas emissions.",
                AuthorityLevel.STATE,
                conflict_group="reporting",
            ),
            _assembled(
                "ev-state-a",
                "5_CCR_1001-10",
                "Facilities shall obtain an emissions permit.",
                AuthorityLevel.STATE,
                conflict_group="permit",
            ),
            _assembled(
                "ev-state-b",
                "5_CCR_1001-11",
                "Facilities are exempt from an emissions permit.",
                AuthorityLevel.STATE,
                conflict_group="permit",
            ),
        ]
    )

    result = ConflictDetectionStage("conflict_detection")(state)

    statuses = {item.category_id: item.status for item in result.conflicts}
    assert statuses["reporting"] == ConflictStatus.RESOLVED_BY_HIERARCHY
    assert statuses["permit"] == ConflictStatus.UNRESOLVED
    assert all(item.disclosure_required for item in result.conflicts)
    assert result.conflicts[0].resolution is not None


def test_prompt_assembly_is_deterministic_snapshot() -> None:
    """Prompt packet rendering is deterministic and model-facing."""

    result = Pipeline([InjectReasoningPoliciesStage("inject_reasoning_policies")]).run(
        _state_with_evidence([
            _assembled(
                "ev-fed",
                "40_CFR_98",
                "Facilities must report greenhouse gas emissions.",
                AuthorityLevel.FEDERAL,
            )
        ])
    )

    assert result.prompt_packet is not None
    assert result.prompt_packet.evidence_ids == ["ev-fed"]
    expected = """# Geode Draft Answer Packet

## Advisory Policies

### authority_hierarchy.md
# Authority Hierarchy

Use the authority hierarchy supplied by Geode. Federal authority outranks state authority where both directly govern the same issue. State authority outranks county and municipal authority. Local authority remains relevant when it adds location-specific requirements and is not preempted.


### grounding_policy.md
# Grounding Policy

Evidence objects are the only facts available to the writer. Policy text is advisory and must not be treated as legal authority.


### interpretation_rules.md
# Interpretation Rules

Write only from the assembled evidence. Do not infer legal meaning beyond the source-backed evidence. Preserve uncertainty, exceptions, and unresolved conflicts for disclosure.


### no_claim_without_evidence.md
# No Claim Without Evidence

Every claim must cite one or more evidence IDs. If evidence is missing, state that the category was searched and returned no candidate source rather than filling the gap.


## User Intent
- Question type: unknown
- Topic: unknown
- Sub-topic: not specified
- Industry: unknown

## Evidence

- ev-fed | 40_CFR_98 | authority=federal | answer_safe=True | semantic_status=not_reported | applicability=not_reported | passage=not_reported page=not_reported lines=not_reported-not_reported hash=not_reported | why= | Facilities must report greenhouse gas emissions.


## Conflicts

- none


## Empty Expected Categories

- none
""".rstrip()
    assert result.prompt_packet.rendered_prompt == expected


def test_generate_draft_uses_evidence_not_raw_query_text() -> None:
    """Draft answer is produced from assembled evidence only."""

    state = _state_with_evidence([
        _assembled(
            "ev-fed",
            "40_CFR_98",
            "Facilities must report greenhouse gas emissions.",
            AuthorityLevel.FEDERAL,
        )
    ])

    result = Pipeline(
        [
            InjectReasoningPoliciesStage("inject_reasoning_policies"),
            GenerateDraftStage("generate_draft"),
        ]
    ).run(state)

    assert result.answer is not None
    assert result.answer.evidence_ids == ["ev-fed"]
    assert "Facilities must report greenhouse gas emissions." in result.answer.answer_text
    assert "raw secret text outside evidence" not in result.answer.answer_text


def _state_with_evidence(evidence: list[Evidence]) -> QueryState:
    """Build a state with assembled evidence."""

    return QueryState(
        intent=Intent(raw_query="raw secret text outside evidence"),
        jurisdiction=Jurisdiction(),
        evidence=evidence,
    )


def _candidate(
    evidence_id: str,
    source_id: str,
    text: str,
    authority_level: AuthorityLevel,
    category_id: str | None = None,
    relationship_path: list[str] | None = None,
) -> Evidence:
    """Build candidate evidence."""

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
        category_id=category_id,
        relationship_path=relationship_path or [],
    )


def _assembled(
    evidence_id: str,
    source_id: str,
    text: str,
    authority_level: AuthorityLevel,
    conflict_group: str | None = None,
) -> Evidence:
    """Build assembled evidence."""

    return _candidate(evidence_id, source_id, text, authority_level).model_copy(
        update={
            "is_candidate": False,
            "assembled": True,
            "authority_level": authority_level,
            "jurisdiction": Jurisdiction(),
            "currency": CurrencyMetadata(
                effective_date=date(2026, 1, 1),
                status=CurrencyStatus.CURRENT,
                amendment_status="not_reported",
                repeal_status="not_reported",
                as_of_date=date(2026, 7, 14),
            ),
            "conflict_group": conflict_group,
        }
    )
