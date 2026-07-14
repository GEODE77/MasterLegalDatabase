"""Human-review escalation hook."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.output_control import apply_escalation
from geode.orchestration.stages._stub import PassThroughStage


class EscalationHookStage(PassThroughStage):
    """Flag low-confidence or high-stakes outputs for human review."""

    def __call__(self, state: QueryState) -> QueryState:
        """Apply escalation rules."""

        apply_escalation(state)
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Escalation hook evaluated.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "escalation_required": state.escalation_required,
                    "escalation_reason": state.escalation_reason,
                },
            )
        )
        return state
