"""Offline contracts for the 8-layer Geode enhancement pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from geode.schemas.models import ConfidenceScores, GeodeModel
from geode.schemas.ontology import (
    COMPLIANCE_KEYWORDS,
    INDUSTRY_TAGS,
    RULE_TYPES,
    SUBJECT_TAGS,
    require_known_values,
)

PipelineRoute = Literal["AUTO_ACCEPT", "FLAG_ACCEPT", "QUARANTINE", "REJECT"]
PipelineLayer = Literal[
    "deterministic_extraction",
    "source_fingerprinting",
    "llm_semantic_extraction",
    "ensemble_voting",
    "constitutional_critique",
    "deterministic_validation",
    "confidence_scoring",
    "adversarial_spot_check",
]


class StructureNode(GeodeModel):
    """One node in a deterministic document structure tree."""

    node_type: Literal["title", "article", "part", "section", "subsection"]
    label: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    text: str = ""
    children: list["StructureNode"] = Field(default_factory=list)


class CitationFinding(GeodeModel):
    """Citation found by regex or an offline LLM contract implementation."""

    canonical_form: str = Field(min_length=1)
    as_written: str = Field(min_length=1)
    location: str = Field(min_length=1)
    found_by: Literal["regex", "llm", "ensemble", "human"]


class RuleUnitDraft(GeodeModel):
    """Draft atomic rule unit emitted by semantic extraction."""

    rule_id: str = Field(min_length=1)
    rule_type: str
    regulated_entity: str = Field(min_length=1)
    action_required: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    enabling_statute: list[str] = Field(default_factory=list)
    temporal: str | None = None
    penalties: list[str] = Field(default_factory=list)
    plain_english_summary: str = Field(min_length=1)

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, value: str) -> str:
        """Require controlled rule types."""

        return require_known_values([value], RULE_TYPES, "rule_type")[0]


class DeterministicExtractionResult(GeodeModel):
    """Layer 1 deterministic extraction output."""

    source_path: str = Field(min_length=1)
    structure: list[StructureNode]
    citations: list[CitationFinding] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    needs_llm: bool = False


class SourceFingerprint(GeodeModel):
    """Layer 2 source preservation and hash metadata."""

    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    converted_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_token_count: int = Field(ge=0)
    converted_token_count: int = Field(ge=0)
    preservation_score: float = Field(ge=0.0, le=1.0)

    @property
    def is_preserved(self) -> bool:
        """Return whether the conversion meets the design threshold."""

        return self.preservation_score >= 0.95


class LLMExtractionRequest(GeodeModel):
    """Offline provider-neutral contract for semantic extraction."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    source_markdown: str = Field(min_length=1)
    deterministic_result: DeterministicExtractionResult
    ontology_version: str = Field(min_length=1)
    constitution_version: str = "AGENTS.md A5"


class LLMExtractionResponse(GeodeModel):
    """Provider-neutral semantic extraction response."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    corrected_structure: list[StructureNode]
    citations: list[CitationFinding] = Field(default_factory=list)
    rule_units: list[RuleUnitDraft] = Field(default_factory=list)
    subject_tags: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    compliance_keywords: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    confidence: ConfidenceScores

    @field_validator("subject_tags")
    @classmethod
    def validate_subject_tags(cls, value: list[str]) -> list[str]:
        """Require controlled subject tags."""

        return require_known_values(value, SUBJECT_TAGS, "subject_tags")

    @field_validator("industry_tags")
    @classmethod
    def validate_industry_tags(cls, value: list[str]) -> list[str]:
        """Require controlled industry tags."""

        return require_known_values(value, INDUSTRY_TAGS, "industry_tags")

    @field_validator("compliance_keywords")
    @classmethod
    def validate_compliance_keywords(cls, value: list[str]) -> list[str]:
        """Require controlled compliance keywords."""

        return require_known_values(value, COMPLIANCE_KEYWORDS, "compliance_keywords")


class EnsembleFieldDecision(GeodeModel):
    """Layer 4 field-level ensemble decision."""

    field_name: str = Field(min_length=1)
    strategy: Literal["exact_match", "regex_preferred", "semantic_match", "verified_union"]
    accepted_value: object
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class EnsembleResult(GeodeModel):
    """Layer 4 ensemble result."""

    decisions: list[EnsembleFieldDecision]
    route_hint: PipelineRoute
    confidence: ConfidenceScores


class CritiqueDimensionScore(GeodeModel):
    """One constitutional critique dimension score."""

    dimension: str = Field(pattern=r"^[MDR]\d+$")
    score: int = Field(ge=1, le=5)
    notes: str = ""


class CritiqueScorecard(GeodeModel):
    """Layer 5 constitutional critique scorecard."""

    scores: list[CritiqueDimensionScore]
    repair_cycle: int = Field(default=0, ge=0, le=3)

    @property
    def passes(self) -> bool:
        """Return whether every dimension meets the pass threshold."""

        return all(score.score >= 4 for score in self.scores)

    @property
    def has_hallucination_reject(self) -> bool:
        """Return whether R9 requires rejection."""

        return any(score.dimension == "R9" and score.score < 5 for score in self.scores)


class ValidationGateResult(GeodeModel):
    """Layer 6 deterministic validation result for routing."""

    schema_passed: bool
    id_unique: bool
    referential_integrity_passed: bool
    date_logic_passed: bool
    text_integrity_passed: bool
    cross_record_consistency_passed: bool
    warnings: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return whether all hard validation checks passed."""

        return (
            self.schema_passed
            and self.id_unique
            and self.date_logic_passed
            and self.text_integrity_passed
        )


class PipelineRoutingDecision(GeodeModel):
    """Layer 7 confidence routing decision."""

    route: PipelineRoute
    composite_confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_route_threshold(self) -> "PipelineRoutingDecision":
        """Keep route labels aligned with design thresholds."""

        if self.route == "AUTO_ACCEPT" and self.composite_confidence < 0.85:
            raise ValueError("AUTO_ACCEPT requires confidence >= 0.85")
        if self.route == "FLAG_ACCEPT" and not 0.60 <= self.composite_confidence < 0.85:
            raise ValueError("FLAG_ACCEPT requires confidence from 0.60 to 0.84")
        if self.route == "QUARANTINE" and self.composite_confidence >= 0.60:
            raise ValueError("QUARANTINE requires confidence < 0.60")
        return self


class PipelineStepResult(GeodeModel):
    """Generic result wrapper for an offline pipeline layer."""

    layer: PipelineLayer
    route: PipelineRoute | None = None
    confidence: ConfidenceScores | None = None
    messages: list[str] = Field(default_factory=list)

