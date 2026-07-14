"""Strict final answer contract validation stage."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.output_control import repair_final_answer
from geode.orchestration.stages._stub import PassThroughStage


class ValidateAnswerContractStage(PassThroughStage):
    """Repair draft output into the strict final answer schema."""

    def __call__(self, state: QueryState) -> QueryState:
        """Validate and repair final answer structure."""

        state.final_answer = repair_final_answer(state)
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Final answer contract validated and repaired where needed.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "requirement_count": len(state.final_answer.requirements),
                    "coverage_gap_count": len(state.final_answer.coverage_gaps),
                },
            )
        )
        return state
