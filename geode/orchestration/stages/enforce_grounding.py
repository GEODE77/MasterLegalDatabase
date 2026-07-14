"""Hard grounding gate."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.gates import append_gate_result, enforce_grounding
from geode.orchestration.stages._stub import PassThroughStage


class EnforceGroundingStage(PassThroughStage):
    """Strip draft claims that lack supporting evidence."""

    def __call__(self, state: QueryState) -> QueryState:
        """Run the grounding gate."""

        state, result = enforce_grounding(state)
        append_gate_result(state, result)
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Grounding gate executed.",
                completed_at=datetime.now(timezone.utc),
                details=result.model_dump(mode="json"),
            )
        )
        return state
