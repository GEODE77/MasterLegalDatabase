"""Core Pydantic models for query orchestration."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import ConfigDict, Field, HttpUrl

from geode.schemas.models import GeodeModel


class StrictOrchestrationModel(GeodeModel):
    """Base model for strict orchestration contracts."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        strict=True,
    )


class QuestionType(StrEnum):
    """Supported high-level question categories."""

    EXACT_CITATION = "exact_citation"
    COMPLIANCE_CHECK = "compliance_check"
    COMPLIANCE_SURVEY = "compliance_survey"
    LEGISLATIVE_HISTORY = "legislative_history"
    OVERLAP_DETECTION = "overlap_detection"
    BROAD_DISCOVERY = "broad_discovery"
    UNKNOWN = "unknown"


class AuthorityLevel(StrEnum):
    """Legal authority level covered by a query or evidence item."""

    STATE = "state"
    COUNTY = "county"
    MUNICIPAL = "municipal"
    FEDERAL = "federal"


class CoverageRequirement(StrEnum):
    """Whether a coverage item is required or conditional."""

    REQUIRED = "required"
    CONDITIONAL = "conditional"


class CoverageStatus(StrEnum):
    """Coverage result status for an expected category."""

    PENDING = "pending"
    FOUND = "found"
    EMPTY = "empty"
    CONDITIONAL = "conditional"


class RetrievalStrategyType(StrEnum):
    """Supported retrieval strategy families."""

    BROAD_AUTHORITY_SWEEP = "broad_authority_sweep"
    EXACT_CITATION_LOOKUP = "exact_citation_lookup"
    TIMELINE_SWEEP = "timeline_sweep"
    RELATIONSHIP_TRAVERSAL = "relationship_traversal"
    DISCOVERY_SWEEP = "discovery_sweep"


class StageStatus(StrEnum):
    """Lifecycle status for a pipeline stage."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    HALTED = "halted"
    SKIPPED = "skipped"


class EntityStatus(StrEnum):
    """Resolution status for an entity mention."""

    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"


class VerificationStatus(StrEnum):
    """Verification outcome for an answer."""

    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class GateAction(StrEnum):
    """Action selected by a hard accuracy gate."""

    PASS = "pass"
    STRIP = "strip"
    DOWNGRADE = "downgrade"
    HALT = "halt"
    REGENERATE = "regenerate"


class CurrencyStatus(StrEnum):
    """Currency status for legal authority evidence."""

    CURRENT = "current"
    AMENDED = "amended"
    REPEALED = "repealed"
    UNKNOWN = "unknown"


class ConflictStatus(StrEnum):
    """Conflict handling status."""

    RESOLVED_BY_HIERARCHY = "resolved_by_hierarchy"
    UNRESOLVED = "unresolved"


class ConfidenceLevel(StrEnum):
    """Human-readable confidence level derived from computed score."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CacheStatus(StrEnum):
    """Cache lookup result."""

    HIT = "hit"
    MISS = "miss"
    STALE = "stale"


class Topic(StrEnum):
    """Broad subject area for a query."""

    ENVIRONMENTAL = "environmental"
    LABOR = "labor"
    TAX = "tax"
    GENERAL = "general"
    UNKNOWN = "unknown"


class Industry(StrEnum):
    """Industry sectors recognized at interpretation time."""

    MANUFACTURING = "manufacturing"
    UNKNOWN = "unknown"


class AnswerShape(StrEnum):
    """Expected answer structure for the writer."""

    COMPLIANCE_SURVEY = "compliance_survey"
    DIRECT_ANSWER = "direct_answer"
    TIMELINE = "timeline"
    COMPARISON = "comparison"
    GENERAL_SUMMARY = "general_summary"


class AssumptionType(StrEnum):
    """Disclosed assumption categories."""

    EXPANSION = "expansion"
    DEFAULT = "default"
    NORMALIZATION = "normalization"


class Intent(StrictOrchestrationModel):
    """Parsed user intent before retrieval begins."""

    question_type: QuestionType = QuestionType.UNKNOWN
    raw_query: str = Field(min_length=1)
    normalized_query: str | None = None
    topic: Topic = Topic.UNKNOWN
    sub_topic: str | None = None
    industry: Industry = Industry.UNKNOWN
    answer_shape: AnswerShape = AnswerShape.GENERAL_SUMMARY
    requested_output: str | None = None


class Entity(StrictOrchestrationModel):
    """Entity mention or resolved Geode entity."""

    name: str = Field(min_length=1)
    entity_type: str | None = None
    geode_id: str | None = None
    canonical_id: str | None = None
    canonical_label: str | None = None
    normalized_terms: list[str] = Field(default_factory=list)
    status: EntityStatus = EntityStatus.UNRESOLVED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class Jurisdiction(StrictOrchestrationModel):
    """Jurisdiction scope for the query."""

    authority_level: AuthorityLevel = AuthorityLevel.STATE
    authority_levels: list[AuthorityLevel] = Field(default_factory=lambda: [AuthorityLevel.STATE])
    state: str = "CO"
    county: str | None = None
    municipality: str | None = None


class JurisdictionCoverage(StrictOrchestrationModel):
    """One authority level included in the expanded query scope."""

    authority_level: AuthorityLevel
    requirement: CoverageRequirement
    label: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class TemporalScope(StrictOrchestrationModel):
    """Time window requested by the query."""

    start_date: date | None = None
    end_date: date | None = None
    as_of_date: date | None = None
    mode: str = "current"
    description: str | None = None


class DisclosedAssumption(StrictOrchestrationModel):
    """Expansion, normalization, or default disclosed to the user."""

    assumption_type: AssumptionType
    field: str = Field(min_length=1)
    original: str | None = None
    applied_value: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class CoverageContract(StrictOrchestrationModel):
    """Explicit statement of what the engine must cover."""

    required_authority_levels: list[AuthorityLevel] = Field(default_factory=list)
    jurisdiction_coverage: list[JurisdictionCoverage] = Field(default_factory=list)
    expected_categories: list["ExpectedCategory"] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    required_entity_ids: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    completeness_standard: str = "source-backed"
    completeness_rule: str = (
        "Each non-conditional category must return candidate sources or be explicitly reported empty."
    )


class ExpectedCategory(StrictOrchestrationModel):
    """One category that retrieval must attempt to cover."""

    category_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    authority_level: AuthorityLevel
    requirement: CoverageRequirement
    retrieval_targets: list[str] = Field(default_factory=list)
    status: CoverageStatus = CoverageStatus.PENDING
    reason: str = Field(min_length=1)


class Provenance(StrictOrchestrationModel):
    """Source location metadata for evidence."""

    source_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    retrieved_at: datetime | None = None
    source_hash: str | None = None
    chain: list[str] = Field(default_factory=list)


class CurrencyMetadata(StrictOrchestrationModel):
    """Currency details for one evidence item."""

    effective_date: date | None = None
    status: CurrencyStatus = CurrencyStatus.UNKNOWN
    amendment_status: str | None = None
    repeal_status: str | None = None
    as_of_date: date | None = None


class Citation(StrictOrchestrationModel):
    """Citation attached to evidence or an answer."""

    citation_text: str = Field(min_length=1)
    canonical_id: str | None = None
    authority_level: AuthorityLevel
    provenance: Provenance | None = None


class Evidence(StrictOrchestrationModel):
    """Verified evidence available to the writer."""

    evidence_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    citation: Citation
    provenance: Provenance
    confidence: float = Field(ge=0.0, le=1.0)
    category_id: str | None = None
    is_candidate: bool = True
    relationship_path: list[str] = Field(default_factory=list)
    enabling_statute: str | None = None
    currency: CurrencyMetadata = Field(default_factory=CurrencyMetadata)
    jurisdiction: Jurisdiction | None = None
    authority_level: AuthorityLevel | None = None
    assembled: bool = False
    conflict_group: str | None = None


class ConflictReport(StrictOrchestrationModel):
    """Detected contradiction between evidence items."""

    conflict_id: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    category_id: str | None = None
    description: str = Field(min_length=1)
    status: ConflictStatus
    resolution: str | None = None
    disclosure_required: bool = True


class PromptPacket(StrictOrchestrationModel):
    """Model-facing prompt assembled from policies and evidence."""

    policies: dict[str, str] = Field(default_factory=dict)
    rendered_prompt: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class DraftRequest(StrictOrchestrationModel):
    """Facts and advisory policies passed to the writer model."""

    prompt: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    conflicts: list[ConflictReport] = Field(default_factory=list)


class GraphLink(StrictOrchestrationModel):
    """Relationship between two candidate sources."""

    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relationship: str = Field(min_length=1)


class RetrievalStep(StrictOrchestrationModel):
    """One deterministic retrieval action selected by the engine."""

    step_id: str = Field(min_length=1)
    category_id: str = Field(min_length=1)
    strategy: RetrievalStrategyType
    authority_level: AuthorityLevel
    targets: list[str] = Field(default_factory=list)
    follow_relationships: list[str] = Field(default_factory=list)


class RetrievalPlan(StrictOrchestrationModel):
    """Ordered retrieval plan chosen by the engine."""

    strategy: RetrievalStrategyType
    steps: list[RetrievalStep] = Field(default_factory=list)
    source_order: list[str] = Field(default_factory=list)
    graph_traversal_enabled: bool = False


class Answer(StrictOrchestrationModel):
    """Structured answer emitted by the writer and checked by gates."""

    answer_text: str = ""
    citations: list[Citation] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AtomicClaim(StrictOrchestrationModel):
    """One extracted answer claim used by hard validators."""

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    citation_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    supported: bool = False


class GateResult(StrictOrchestrationModel):
    """Structured result from one hard validator."""

    gate_name: str = Field(min_length=1)
    action: GateAction
    passed: bool
    checked_claim_ids: list[str] = Field(default_factory=list)
    stripped_claim_ids: list[str] = Field(default_factory=list)
    stripped_citations: list[str] = Field(default_factory=list)
    flagged_evidence_ids: list[str] = Field(default_factory=list)
    missing_categories: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)


class ConfidenceReport(StrictOrchestrationModel):
    """Deterministic confidence computation details."""

    score: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel
    factors: dict[str, float] = Field(default_factory=dict)
    explanation: list[str] = Field(default_factory=list)


class VerificationReport(StrictOrchestrationModel):
    """Validation results for a draft or final answer."""

    status: VerificationStatus = VerificationStatus.NOT_RUN
    checks_run: list[str] = Field(default_factory=list)
    gate_results: list[GateResult] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RequirementItem(StrictOrchestrationModel):
    """One structured requirement in the final answer."""

    requirement_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    jurisdiction: str | None = None


class FinalAnswer(StrictOrchestrationModel):
    """Strict final answer schema emitted by orchestration."""

    summary: str = Field(min_length=1)
    requirements: list[RequirementItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    confidence: ConfidenceReport
    uncertainties: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
    escalation_required: bool = False
    escalation_reason: str | None = None


class EmittedAnswer(StrictOrchestrationModel):
    """Final emitted payload with full audit trace."""

    answer: FinalAnswer
    trace: list[StageLog]
    verification_report: VerificationReport | None = None


class ModelRouteDecision(StrictOrchestrationModel):
    """Selected model provider details."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    estimated_cost: float = Field(ge=0.0)
    estimated_latency_ms: int = Field(ge=0)
    fallback_used: bool = False


class ContextBudgetReport(StrictOrchestrationModel):
    """Context budgeting result."""

    token_limit: int = Field(ge=1)
    estimated_tokens: int = Field(ge=0)
    kept_evidence_ids: list[str] = Field(default_factory=list)
    dropped_evidence_ids: list[str] = Field(default_factory=list)
    preserved_high_authority_ids: list[str] = Field(default_factory=list)


class CacheEvent(StrictOrchestrationModel):
    """Cache hit, miss, or stale event."""

    key: str = Field(min_length=1)
    status: CacheStatus
    corpus_version: str = Field(min_length=1)
    reason: str | None = None


class FreshnessResult(StrictOrchestrationModel):
    """Freshness status for cached orchestration results."""

    corpus_version: str = Field(min_length=1)
    cached_version: str | None = None
    stale: bool = False
    reason: str | None = None


class AuditEvent(StrictOrchestrationModel):
    """Replayable JSON audit event."""

    query_id: str = Field(min_length=1)
    stage_name: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StageLog(StrictOrchestrationModel):
    """Audit log entry for one pipeline stage."""

    stage_name: str = Field(min_length=1)
    status: StageStatus
    message: str = Field(min_length=1)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class QueryState(StrictOrchestrationModel):
    """Single state object that flows through every orchestration stage."""

    query_id: str = Field(default_factory=lambda: f"Q-{uuid4().hex}")
    intent: Intent
    entities: list[Entity] = Field(default_factory=list)
    jurisdiction: Jurisdiction | None = None
    jurisdiction_coverage: list[JurisdictionCoverage] = Field(default_factory=list)
    temporal: TemporalScope | None = None
    temporal_scope: TemporalScope | None = None
    coverage_contract: CoverageContract | None = None
    retrieval_plan: RetrievalPlan | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    empty_expected_categories: list[str] = Field(default_factory=list)
    conflicts: list[ConflictReport] = Field(default_factory=list)
    prompt_packet: PromptPacket | None = None
    draft_request: DraftRequest | None = None
    answer: Answer | None = None
    verification_report: VerificationReport | None = None
    confidence_report: ConfidenceReport | None = None
    final_answer: FinalAnswer | None = None
    emitted_answer: EmittedAnswer | None = None
    model_route: ModelRouteDecision | None = None
    context_budget: ContextBudgetReport | None = None
    cache_events: list[CacheEvent] = Field(default_factory=list)
    freshness: FreshnessResult | None = None
    audit_log_path: str | None = None
    escalation_required: bool = False
    escalation_reason: str | None = None
    extracted_claims: list[AtomicClaim] = Field(default_factory=list)
    regeneration_requested: bool = False
    regeneration_reason: str | None = None
    assumptions: list[DisclosedAssumption] = Field(default_factory=list)
    clarification_offered: bool = False
    trace: list[StageLog] = Field(default_factory=list)
    halted: bool = False
    halt_reason: str | None = None


EmittedAnswer.model_rebuild()
