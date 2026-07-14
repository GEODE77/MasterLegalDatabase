"""Emit final structured answer."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.output_control import emit_final_answer
from geode.orchestration.stages._stub import PassThroughStage


class EmitStage(PassThroughStage):
    """Produce the final structured output with trace."""

    def __call__(self, state: QueryState) -> QueryState:
        """Emit final answer and full audit trace."""

        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Final structured answer emitted.",
                completed_at=datetime.now(timezone.utc),
            )
        )
        emit_final_answer(state)
        return state
