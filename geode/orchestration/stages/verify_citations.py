"""Hard citation verification gate."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.gates import append_gate_result, verify_citations
from geode.orchestration.stages._stub import PassThroughStage


class VerifyCitationsStage(PassThroughStage):
    """Strip citations that fail evidence checks."""

    def __call__(self, state: QueryState) -> QueryState:
        """Run citation verification."""

        state, result = verify_citations(state)
        append_gate_result(state, result)
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Citation verification gate executed.",
                completed_at=datetime.now(timezone.utc),
                details=result.model_dump(mode="json"),
            )
        )
        return state
