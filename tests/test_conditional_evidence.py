"""Tests for conditionally citable local evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path

from geode.orchestration.contracts import (
    Answer,
    AuthorityLevel,
    Citation,
    Evidence,
    Intent,
    PassageLocation,
    Provenance,
    QueryState,
)
from geode.orchestration.gates import enforce_grounding
from geode.orchestration.services.retrieval import LocalKnowledgeRetrievalBackend
from geode.orchestration.contracts import RetrievalStep, RetrievalStrategyType
from geode.pipeline.retrieval_catalog import write_retrieval_catalog
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl


HASH = "a" * 64


def _queue_row() -> tuple[dict[str, object], dict[str, object]]:
    """Build one conditional candidate and its identity mapping."""

    candidate_id = "LOCAL-RULE-CO-COUNTY-TEST_RU_0001"
    parent = "LOCAL-RULE-CO-COUNTY-TEST"
    candidate = {
        "id": candidate_id,
        "parent_regulation_id": parent,
        "source_section": "Section 1",
        "action_required": "Owners of facilities shall obtain a permit.",
        "regulated_entity": "Owners of facilities",
        "confidence": {"overall": 0.6},
    }
    return (
        {
            "review_id": "REVIEW-1",
            "review_disposition": "manual_entity_confirmation",
            "parent_rule_id": parent,
            "authority_id": "CO-COUNTY-TEST",
            "authority_name": "Test County",
            "source_category": "county_codes",
            "source_path": "_RAW_ARCHIVE/local/test.pdf",
            "source_url": "https://county.example.gov/rules.pdf",
            "source_hash": HASH,
            "candidate_rule_unit": candidate,
        },
        {
            "review_id": "REVIEW-1",
            "candidate_rule_unit_id": candidate_id,
            "permanent_rule_unit_id": f"{parent}-UNIT-0001",
            "parent_regulation_id": parent,
            "source_hash": HASH,
            "source_section": "Section 1",
            "mapping_status": "planned_new",
            "mapping_reason": "test",
        },
    )


def test_conditional_candidates_enter_retrieval_catalog_and_search(tmp_path: Path) -> None:
    """Quarantined candidates are searchable as conditional evidence."""

    queue_row, mapping_row = _queue_row()
    atomic_write_json(tmp_path / "_CONTROL_PLANE" / "MASTER_MANIFEST.json", {"data_layers": []}, tmp_path)
    atomic_write_jsonl(
        tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl",
        [queue_row],
        tmp_path,
    )
    atomic_write_jsonl(
        tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_CANDIDATE_MAP.jsonl",
        [mapping_row],
        tmp_path,
    )
    write_retrieval_catalog(tmp_path)
    state = QueryState(intent=Intent(raw_query="permit owners facilities"))
    results = LocalKnowledgeRetrievalBackend(tmp_path).search(
        state,
        RetrievalStep(
            step_id="local-1",
            category_id="county_rules",
            strategy=RetrievalStrategyType.DISCOVERY_SWEEP,
            authority_level=AuthorityLevel.COUNTY,
            targets=["rule_unit"],
        ),
    )

    assert len(results) == 1
    assert results[0].answer_mode == "conditional"
    assert not results[0].answer_safe
    assert results[0].content_type.value == "conditional"


def _conditional_evidence() -> Evidence:
    """Build one exact conditional evidence item."""

    text = "Owners of facilities shall obtain a permit."
    text_hash = hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()
    return Evidence(
        evidence_id="conditional-1",
        text=text,
        citation=Citation(
            citation_text="Test County — Section 1",
            canonical_id="conditional-1",
            authority_level=AuthorityLevel.COUNTY,
        ),
        provenance=Provenance(
            source_id="conditional-1",
            source_path="_CONTROL_PLANE/COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl",
            passage=PassageLocation(section="Section 1", text_hash=text_hash),
        ),
        confidence=0.6,
        semantic_status="needs_review",
        answer_mode="conditional",
        answer_safe=False,
    )


def test_conditional_evidence_cannot_support_unqualified_legal_claim() -> None:
    """A conditional source cannot support a definite legal conclusion."""

    evidence = _conditional_evidence()
    state = QueryState(
        intent=Intent(raw_query="What is required?"),
        evidence=[evidence],
        answer=Answer(
            answer_text="Owners of facilities must obtain a permit.",
            citations=[evidence.citation],
            evidence_ids=[evidence.evidence_id],
            confidence=0.6,
        ),
    )

    state, result = enforce_grounding(state)

    assert result.passed is False
    assert state.answer is not None
    assert state.answer.answer_text == ""


def test_conditional_evidence_supports_attributed_source_statement() -> None:
    """A conditional source can support a clearly attributed source statement."""

    evidence = _conditional_evidence()
    state = QueryState(
        intent=Intent(raw_query="What does the source say?"),
        evidence=[evidence],
        answer=Answer(
            answer_text="The source states that owners of facilities shall obtain a permit.",
            citations=[evidence.citation],
            evidence_ids=[evidence.evidence_id],
            confidence=0.6,
        ),
    )

    state, result = enforce_grounding(state)

    assert result.passed is True
    assert state.extracted_claims
