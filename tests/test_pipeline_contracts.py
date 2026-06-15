"""Offline 8-layer pipeline contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from geode.pipeline.contracts import (
    CritiqueDimensionScore,
    CritiqueScorecard,
    DeterministicExtractionResult,
    LLMExtractionRequest,
    LLMExtractionResponse,
    RuleUnitDraft,
    SourceFingerprint,
    StructureNode,
)


def test_offline_llm_contract_accepts_fake_provider_response() -> None:
    """Provider-neutral LLM contracts validate without network calls or SDKs."""

    structure = [StructureNode(node_type="section", label="25-7-109", heading="Commission")]
    deterministic = DeterministicExtractionResult(
        source_path="_RAW_ARCHIVE/crs/title25.txt",
        structure=structure,
        needs_llm=True,
    )
    request = LLMExtractionRequest(
        provider="fake",
        model="offline-test",
        source_markdown="#### 25-7-109. Commission\n\nText.",
        deterministic_result=deterministic,
        ontology_version="1.0",
    )
    response = LLMExtractionResponse(
        provider=request.provider,
        model=request.model,
        corrected_structure=structure,
        rule_units=[
            RuleUnitDraft(
                rule_id="draft-1",
                rule_type="obligation",
                regulated_entity="The commission",
                action_required="Must promulgate rules",
                plain_english_summary="The commission must promulgate rules.",
            )
        ],
        subject_tags=["air_quality"],
        industry_tags=["manufacturing"],
        compliance_keywords=["permit_required"],
        summary="The section describes commission duties.",
        confidence={"overall": 0.9},
    )
    assert response.provider == "fake"


def test_source_fingerprint_threshold() -> None:
    """Fingerprint preservation threshold follows the design."""

    fingerprint = SourceFingerprint(
        source_sha256="a" * 64,
        converted_sha256="b" * 64,
        source_token_count=100,
        converted_token_count=98,
        preservation_score=0.98,
    )
    assert fingerprint.is_preserved


def test_critique_scorecard_detects_hallucination_reject() -> None:
    """R9 below 5 marks the record for rejection."""

    scorecard = CritiqueScorecard(
        scores=[CritiqueDimensionScore(dimension="R9", score=4, notes="Needs repair")]
    )
    assert scorecard.passes
    assert scorecard.has_hallucination_reject


def test_llm_contract_rejects_invented_tags() -> None:
    """Offline LLM responses cannot invent ontology tags."""

    with pytest.raises(ValidationError):
        LLMExtractionResponse(
            provider="fake",
            model="offline-test",
            corrected_structure=[StructureNode(node_type="section", label="x", heading="x")],
            subject_tags=["not_real"],
            industry_tags=[],
            compliance_keywords=[],
            summary="Bad tag.",
            confidence={"overall": 0.9},
        )
