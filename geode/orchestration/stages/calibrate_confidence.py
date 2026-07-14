"""Deterministic confidence calibration stage."""

from datetime import datetime, timezone

from geode.orchestration.contracts import QueryState, StageLog, StageStatus
from geode.orchestration.output_control import compute_confidence
from geode.orchestration.stages._stub import PassThroughStage


class CalibrateConfidenceStage(PassThroughStage):
    """Compute confidence from evidence and gate outcomes."""

    def __call__(self, state: QueryState) -> QueryState:
        """Calibrate confidence deterministically."""

        state.confidence_report = compute_confidence(state)
        if state.answer is not None:
            state.answer = state.answer.model_copy(update={"confidence": state.confidence_report.score})
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Confidence computed from evidence factors.",
                completed_at=datetime.now(timezone.utc),
                details=state.confidence_report.model_dump(mode="json"),
            )
        )
        return state
