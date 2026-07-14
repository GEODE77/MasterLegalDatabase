"""Structured JSON audit logging."""

from __future__ import annotations

from pathlib import Path

from geode.orchestration.contracts import AuditEvent, QueryState, StageLog


class OrchestrationLogger:
    """Write replayable JSONL audit events."""

    def __init__(self, audit_path: Path | None = None) -> None:
        """Create a logger."""

        self.audit_path = audit_path
        self.events: list[AuditEvent] = []
        if self.audit_path is not None:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, log: StageLog, state: QueryState) -> None:
        """Write one stage log as a replayable audit event."""

        event = AuditEvent(
            query_id=state.query_id,
            stage_name=log.stage_name,
            event_type="stage_decision",
            payload={
                "status": log.status.value,
                "message": log.message,
                "details": log.details,
                "verification_report": state.verification_report.model_dump(mode="json")
                if state.verification_report
                else None,
                "cache_events": [item.model_dump(mode="json") for item in state.cache_events],
            },
        )
        self.events.append(event)
        if self.audit_path is not None:
            with self.audit_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(event.model_dump_json() + "\n")
            state.audit_log_path = self.audit_path.as_posix()
