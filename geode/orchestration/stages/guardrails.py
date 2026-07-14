"""Config-driven output guardrails."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.output_control import apply_guardrails
from geode.orchestration.stages._stub import PassThroughStage


class GuardrailsStage(PassThroughStage):
    """Attach required disclaimers and UPL-risk language."""

    def __call__(self, state: QueryState) -> QueryState:
        """Apply config-driven guardrails."""

        apply_guardrails(state)
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Output guardrails applied.",
                completed_at=datetime.now(timezone.utc),
                details={"disclaimers": state.final_answer.disclaimers if state.final_answer else []},
            )
        )
        return state
