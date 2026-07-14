"""Pass-through stage stubs for the orchestration scaffold."""

from geode.orchestration.stages.absence_verification import AbsenceVerificationStage
from geode.orchestration.stages.assemble_evidence import AssembleEvidenceStage
from geode.orchestration.stages.ambiguity_check import AmbiguityCheckStage
from geode.orchestration.stages.build_coverage_contract import BuildCoverageContractStage
from geode.orchestration.stages.calibrate_confidence import CalibrateConfidenceStage
from geode.orchestration.stages.check_completeness import CheckCompletenessStage
from geode.orchestration.stages.check_faithfulness import CheckFaithfulnessStage
from geode.orchestration.stages.conflict_detection import ConflictDetectionStage
from geode.orchestration.stages.emit import EmitStage
from geode.orchestration.stages.enforce_grounding import EnforceGroundingStage
from geode.orchestration.stages.escalation_hook import EscalationHookStage
from geode.orchestration.stages.generate_draft import GenerateDraftStage
from geode.orchestration.stages.guardrails import GuardrailsStage
from geode.orchestration.stages.inject_reasoning_policies import InjectReasoningPoliciesStage
from geode.orchestration.stages.parse_intent import ParseIntentStage
from geode.orchestration.stages.plan_retrieval import PlanRetrievalStage
from geode.orchestration.stages.query_normalization import QueryNormalizationStage
from geode.orchestration.stages.resolve_entities import ResolveEntitiesStage
from geode.orchestration.stages.resolve_jurisdiction import ResolveJurisdictionStage
from geode.orchestration.stages.retrieve import RetrieveStage
from geode.orchestration.stages.scope_temporal import ScopeTemporalStage
from geode.orchestration.stages.validate_answer_contract import ValidateAnswerContractStage
from geode.orchestration.stages.verify_citations import VerifyCitationsStage
from geode.orchestration.stages.verify_currency import VerifyCurrencyStage

__all__ = [
    "AbsenceVerificationStage",
    "AssembleEvidenceStage",
    "AmbiguityCheckStage",
    "BuildCoverageContractStage",
    "CalibrateConfidenceStage",
    "CheckCompletenessStage",
    "CheckFaithfulnessStage",
    "ConflictDetectionStage",
    "EmitStage",
    "EnforceGroundingStage",
    "EscalationHookStage",
    "GenerateDraftStage",
    "GuardrailsStage",
    "InjectReasoningPoliciesStage",
    "ParseIntentStage",
    "PlanRetrievalStage",
    "QueryNormalizationStage",
    "ResolveEntitiesStage",
    "ResolveJurisdictionStage",
    "RetrieveStage",
    "ScopeTemporalStage",
    "ValidateAnswerContractStage",
    "VerifyCitationsStage",
    "VerifyCurrencyStage",
]
