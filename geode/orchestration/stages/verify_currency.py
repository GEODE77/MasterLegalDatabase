"""Hard currency verification gate."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.gates import append_gate_result, verify_currency
from geode.orchestration.stages._stub import PassThroughStage


class VerifyCurrencyStage(PassThroughStage):
    """Flag cited provisions that are not current."""

    def __call__(self, state: QueryState) -> QueryState:
        """Run currency verification."""

        state, result = verify_currency(state)
        append_gate_result(state, result)
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Currency verification gate executed.",
                completed_at=datetime.now(timezone.utc),
                details=result.model_dump(mode="json"),
            )
        )
        return state
