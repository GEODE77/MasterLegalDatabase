"""Package-local scaffold tests."""

from __future__ import annotations

from typing import TypeAlias

from pydantic import BaseModel, HttpUrl, TypeAdapter

from geode.orchestration.contracts import (
    Answer,
    AssumptionType,
    AuthorityLevel,
    Citation,
    CoverageContract,
    DisclosedAssumption,
    Entity,
    Evidence,
    Intent,
    Jurisdiction,
    Provenance,
    QueryState,
    QuestionType,
    StageLog,
    StageStatus,
    TemporalScope,
    VerificationReport,
)
from geode.orchestration.pipeline import Pipeline
from geode.orchestration.pipeline.base import StageBase
from geode.orchestration.services import FixtureRetrievalBackend
from geode.orchestration.stages import (
    AssembleEvidenceStage,
    AbsenceVerificationStage,
    AmbiguityCheckStage,
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
    QueryNormalizationStage,
    ResolveEntitiesStage,
    ResolveJurisdictionStage,
    RetrieveStage,
    ScopeTemporalStage,
    ValidateAnswerContractStage,
    VerifyCitationsStage,
    VerifyCurrencyStage,
)

Contract: TypeAlias = type[BaseModel]
HTTP_URL_ADAPTER: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)


def test_pipeline_runs_all_stubs_end_to_end() -> None:
    """Pipeline executes every scaffold stage and appends trace logs."""

    state = QueryState(intent=Intent(raw_query="What applies to air permits?"))
    stages = [
        QueryNormalizationStage("query_normalization"),
        ParseIntentStage("parse_intent"),
        ResolveEntitiesStage("resolve_entities"),
        ScopeTemporalStage("scope_temporal"),
        AmbiguityCheckStage("ambiguity_check"),
        ResolveJurisdictionStage("resolve_jurisdiction"),
        BuildCoverageContractStage("build_coverage_contract"),
        PlanRetrievalStage("plan_retrieval"),
        RetrieveStage("retrieve", backend=FixtureRetrievalBackend([])),
        AssembleEvidenceStage("assemble_evidence"),
        ConflictDetectionStage("conflict_detection"),
        InjectReasoningPoliciesStage("inject_reasoning_policies"),
        GenerateDraftStage("generate_draft"),
        EnforceGroundingStage("enforce_grounding"),
        VerifyCitationsStage("verify_citations"),
        VerifyCurrencyStage("verify_currency"),
        CheckCompletenessStage("check_completeness"),
        CheckFaithfulnessStage("check_faithfulness"),
        AbsenceVerificationStage("absence_verification"),
        CalibrateConfidenceStage("calibrate_confidence"),
        ValidateAnswerContractStage("validate_answer_contract"),
        GuardrailsStage("guardrails"),
        EscalationHookStage("escalation_hook"),
        EmitStage("emit"),
    ]

    result = Pipeline(stages).run(state)

    assert result.halted is False
    completed_logs = [entry for entry in result.trace if entry.message.startswith("Stage ")]
    assert len(completed_logs) == len(stages)
    assert [entry.stage_name for entry in completed_logs] == [stage.name for stage in stages]
    assert {entry.status for entry in completed_logs} == {StageStatus.PASSED}


def test_contracts_round_trip_and_export_json_schema() -> None:
    """Every core contract validates, serializes, and exports JSON Schema."""

    for model in _contract_instances():
        payload = model.model_dump_json()
        round_tripped = model.__class__.model_validate_json(payload)
        assert round_tripped == model
        schema = model.__class__.model_json_schema()
        assert schema["type"] == "object"


def test_pipeline_short_circuits_after_halt() -> None:
    """Pipeline stops when a gate marks the state as halted."""

    class HaltStage(StageBase):
        """Test stage that halts the query."""

        def __call__(self, state: QueryState) -> QueryState:
            """Mark state as halted."""

            state.halted = True
            state.halt_reason = "test_gate"
            return state

    state = QueryState(intent=Intent(raw_query="What applies?"))
    result = Pipeline([HaltStage("halt"), ParseIntentStage("not_run")]).run(state)

    assert result.halted is True
    assert result.halt_reason == "test_gate"
    assert [entry.stage_name for entry in result.trace] == ["halt"]
    assert result.trace[0].status == StageStatus.HALTED


def _contract_instances() -> list[BaseModel]:
    """Return one valid instance for each scaffold contract."""

    provenance = Provenance(
        source_id="CRS-25-7-109",
        source_path="01_Statutes_CRS/crs_title_25.md",
        source_url=HTTP_URL_ADAPTER.validate_python(
            "https://leg.colorado.gov/colorado-revised-statutes"
        ),
    )
    citation = Citation(
        citation_text="CRS 25-7-109",
        canonical_id="CRS-25-7-109",
        authority_level=AuthorityLevel.STATE,
        provenance=provenance,
    )
    evidence = Evidence(
        evidence_id="EV-1",
        text="The commission has rulemaking authority.",
        citation=citation,
        provenance=provenance,
        confidence=0.9,
    )
    return [
        Intent(
            question_type=QuestionType.COMPLIANCE_CHECK,
            raw_query="What permits apply?",
            normalized_query="what permits apply?",
        ),
        Entity(name="Air Quality Control Commission", entity_type="agency", confidence=0.8),
        Jurisdiction(authority_level=AuthorityLevel.STATE),
        TemporalScope(description="current law"),
        CoverageContract(required_authority_levels=[AuthorityLevel.STATE]),
        DisclosedAssumption(
            assumption_type=AssumptionType.DEFAULT,
            field="jurisdiction",
            applied_value="state",
            reason="No narrower jurisdiction was stated.",
        ),
        provenance,
        citation,
        evidence,
        Answer(answer_text="Answer text.", citations=[citation], evidence_ids=["EV-1"], confidence=0.8),
        VerificationReport(),
        StageLog(stage_name="parse_intent", status=StageStatus.PASSED, message="done"),
        QueryState(
            intent=Intent(raw_query="What permits apply?"),
            jurisdiction=Jurisdiction(),
            evidence=[evidence],
            answer=Answer(
                answer_text="Answer text.",
                citations=[citation],
                evidence_ids=["EV-1"],
                confidence=0.8,
            ),
            verification_report=VerificationReport(),
        ),
    ]
