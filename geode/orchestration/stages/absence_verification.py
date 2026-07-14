"""Hard absence-verification gate."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.gates import absence_verification, append_gate_result
from geode.orchestration.stages._stub import PassThroughStage


class AbsenceVerificationStage(PassThroughStage):
    """Prevent retrieval limits from being stated as verified absence."""

    def __call__(self, state: QueryState) -> QueryState:
        """Run absence verification."""

        state, result = absence_verification(state)
        append_gate_result(state, result)
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Absence verification gate executed.",
                completed_at=datetime.now(timezone.utc),
                details=result.model_dump(mode="json"),
            )
        )
        return state
