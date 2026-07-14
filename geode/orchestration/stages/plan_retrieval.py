"""Create deterministic retrieval plans."""

from __future__ import annotations

from datetime import datetime, timezone

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import (
    CoverageRequirement,
    QueryState,
    RetrievalPlan,
    RetrievalStep,
    RetrievalStrategyType,
    StageLog,
    StageStatus,
)
from geode.orchestration.stages._stub import PassThroughStage


class PlanRetrievalStage(PassThroughStage):
    """Select retrieval strategy and ordered source plan."""

    def __call__(self, state: QueryState) -> QueryState:
        """Populate a retrieval plan based on question type and coverage."""

        if state.coverage_contract is None:
            raise ValueError("coverage_contract is required before retrieval planning")
        strategies = load_orchestration_config()["retrieval"]["retrieval_strategies"]
        strategy_config = strategies.get(state.intent.question_type.value) or strategies[
            "compliance_survey"
        ]
        strategy = RetrievalStrategyType(str(strategy_config["strategy"]))
        follow_relationships = [
            str(item) for item in strategy_config.get("follow_relationships", [])
        ]
        steps = [
            RetrievalStep(
                step_id=f"step-{index:03d}",
                category_id=category.category_id,
                strategy=strategy,
                authority_level=category.authority_level,
                targets=category.retrieval_targets,
                follow_relationships=[] if category.requirement == CoverageRequirement.CONDITIONAL else follow_relationships,
            )
            for index, category in enumerate(
                state.coverage_contract.expected_categories,
                start=1,
            )
        ]
        state.retrieval_plan = RetrievalPlan(
            strategy=strategy,
            steps=steps,
            source_order=[str(item) for item in strategy_config.get("source_order", [])],
            graph_traversal_enabled=bool(strategy_config.get("graph_traversal_enabled", False)),
        )
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Retrieval plan selected by the engine.",
                completed_at=datetime.now(timezone.utc),
                details=state.retrieval_plan.model_dump(mode="json"),
            )
        )
        return state
