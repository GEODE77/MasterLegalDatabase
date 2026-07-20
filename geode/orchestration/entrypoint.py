"""Public entrypoint for the integrated orchestration pipeline."""

from __future__ import annotations

from pathlib import Path

from geode.orchestration.contracts import Intent, QueryState
from geode.orchestration.pipeline import Pipeline, Stage
from geode.orchestration.services import (
    AccessControlService,
    ContextBudgetManager,
    EvidenceStore,
    FreshnessMonitor,
    ModelRouter,
    OrchestrationCache,
    OrchestrationLogger,
    RetrievalBackend,
)
from geode.orchestration.stages import (
    AssembleEvidenceStage,
    BuildCoverageContractStage,
    CalibrateConfidenceStage,
    CheckCompletenessStage,
    CheckFaithfulnessStage,
    ConflictDetectionStage,
    EmitStage,
    EnforceGroundingStage,
    EscalationHookStage,
    GenerateDraftStage,
    GuardrailsStage,
    InjectReasoningPoliciesStage,
    ParseIntentStage,
    PlanRetrievalStage,
    ResolveEntitiesStage,
    ResolveJurisdictionStage,
    RetrieveStage,
    ScopeTemporalStage,
    ValidateAnswerContractStage,
    VerifyCitationsStage,
    VerifyCurrencyStage,
)

DEFAULT_STAGE_ORDER = [
    "parse_intent",
    "resolve_entities",
    "scope_temporal",
    "resolve_jurisdiction",
    "build_coverage_contract",
    "plan_retrieval",
    "retrieve",
    "assemble_evidence",
    "conflict_detection",
    "inject_reasoning_policies",
    "generate_draft",
    "enforce_grounding",
    "verify_citations",
    "verify_currency",
    "check_completeness",
    "check_faithfulness",
    "calibrate_confidence",
    "validate_answer_contract",
    "guardrails",
    "escalation_hook",
    "emit",
]

DEFAULT_EVIDENCE_STORE_PATH = Path(".geode_runtime/evidence_store.sqlite")


def build_default_stages(
    *,
    retrieval_backend: RetrievalBackend | None = None,
    model_router: ModelRouter | None = None,
    context_budget_manager: ContextBudgetManager | None = None,
) -> list[Stage]:
    """Build the canonical stage order for the orchestration engine."""

    return [
        ParseIntentStage("parse_intent"),
        ResolveEntitiesStage("resolve_entities"),
        ScopeTemporalStage("scope_temporal"),
        ResolveJurisdictionStage("resolve_jurisdiction"),
        BuildCoverageContractStage("build_coverage_contract"),
        PlanRetrievalStage("plan_retrieval"),
        RetrieveStage("retrieve", backend=retrieval_backend),
        AssembleEvidenceStage("assemble_evidence"),
        ConflictDetectionStage("conflict_detection"),
        InjectReasoningPoliciesStage("inject_reasoning_policies"),
        GenerateDraftStage(
            "generate_draft",
            router=model_router,
            budget_manager=context_budget_manager,
        ),
        EnforceGroundingStage("enforce_grounding"),
        VerifyCitationsStage("verify_citations"),
        VerifyCurrencyStage("verify_currency"),
        CheckCompletenessStage("check_completeness"),
        CheckFaithfulnessStage("check_faithfulness"),
        CalibrateConfidenceStage("calibrate_confidence"),
        ValidateAnswerContractStage("validate_answer_contract"),
        GuardrailsStage("guardrails"),
        EscalationHookStage("escalation_hook"),
        EmitStage("emit"),
    ]


def build_default_pipeline(
    *,
    retrieval_backend: RetrievalBackend | None = None,
    model_router: ModelRouter | None = None,
    context_budget_manager: ContextBudgetManager | None = None,
    cache: OrchestrationCache | None = None,
    logger: OrchestrationLogger | None = None,
    freshness_monitor: FreshnessMonitor | None = None,
    access_control: AccessControlService | None = None,
    corpus_version: str = "unknown",
    evidence_store_path: Path = DEFAULT_EVIDENCE_STORE_PATH,
) -> Pipeline:
    """Create the fully integrated pipeline with durable evidence storage."""

    if context_budget_manager is None:
        context_budget_manager = ContextBudgetManager(
            evidence_store=EvidenceStore(evidence_store_path),
            corpus_version=corpus_version,
        )

    return Pipeline(
        build_default_stages(
            retrieval_backend=retrieval_backend,
            model_router=model_router,
            context_budget_manager=context_budget_manager,
        ),
        cache=cache,
        logger=logger,
        freshness_monitor=freshness_monitor,
        access_control=access_control,
        corpus_version=corpus_version,
    )


def run_orchestration(
    raw_query: str,
    *,
    retrieval_backend: RetrievalBackend | None = None,
    model_router: ModelRouter | None = None,
    context_budget_manager: ContextBudgetManager | None = None,
    cache: OrchestrationCache | None = None,
    audit_log_path: Path | None = None,
    corpus_version: str = "unknown",
    evidence_store_path: Path = DEFAULT_EVIDENCE_STORE_PATH,
) -> QueryState:
    """Run a raw query through the integrated pipeline."""

    logger = OrchestrationLogger(audit_log_path) if audit_log_path is not None else None
    pipeline = build_default_pipeline(
        retrieval_backend=retrieval_backend,
        model_router=model_router,
        context_budget_manager=context_budget_manager,
        cache=cache,
        logger=logger,
        freshness_monitor=FreshnessMonitor(corpus_version=corpus_version),
        access_control=AccessControlService(),
        corpus_version=corpus_version,
        evidence_store_path=evidence_store_path,
    )
    return pipeline.run(QueryState(intent=Intent(raw_query=raw_query)))
