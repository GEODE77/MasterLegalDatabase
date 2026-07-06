"""Build a control-plane update ledger before full text diffing exists."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl, load_json

UPDATE_LEDGER_PATH = Path(CONTROL_PLANE_DIR) / "UPDATE_LEDGER.jsonl"
UPDATE_LEDGER_SUMMARY_PATH = Path(CONTROL_PLANE_DIR) / "UPDATE_LEDGER_SUMMARY.json"

LedgerSource = Literal["manifest", "update_log", "timeline", "step_gate"]


class UpdateLedgerEvent(BaseModel):
    """One source-backed update event."""

    event_id: str
    event_date: str
    event_type: str
    source: LedgerSource
    title: str
    description: str
    layer_id: str | None = None
    entity_id: str | None = None
    status: str | None = None
    source_path: str
    evidence_id: str | None = None
    full_text_diff_available: bool = False
    requires_full_diff: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


class UpdateLedgerSummary(BaseModel):
    """Summary of the generated update ledger."""

    generated_at: datetime
    ledger_path: str
    events_written: int = Field(ge=0)
    manifest_layer_events: int = Field(ge=0)
    update_log_events: int = Field(ge=0)
    timeline_events: int = Field(ge=0)
    step_gate_events: int = Field(ge=0)
    full_diff_ready: bool = False
    diff_status: str
    next_action: str


def build_update_ledger(root: Path) -> list[UpdateLedgerEvent]:
    """Build update events from existing control-plane evidence."""

    resolved_root = root.resolve()
    events: list[UpdateLedgerEvent] = []
    events.extend(_manifest_events(resolved_root))
    events.extend(_update_log_events(resolved_root))
    events.extend(_timeline_events(resolved_root))
    events.extend(_step_gate_events(resolved_root))
    return sorted(events, key=lambda event: (event.event_date, event.event_id), reverse=True)


def build_update_ledger_summary(events: list[UpdateLedgerEvent]) -> UpdateLedgerSummary:
    """Build a summary for a ledger event list."""

    return UpdateLedgerSummary(
        generated_at=datetime.now(timezone.utc),
        ledger_path=UPDATE_LEDGER_PATH.as_posix(),
        events_written=len(events),
        manifest_layer_events=sum(event.source == "manifest" for event in events),
        update_log_events=sum(event.source == "update_log" for event in events),
        timeline_events=sum(event.source == "timeline" for event in events),
        step_gate_events=sum(event.source == "step_gate" for event in events),
        full_diff_ready=False,
        diff_status="not_started",
        next_action=(
            "Use this ledger for update awareness now; add full text diff after stable "
            "source snapshots are available."
        ),
    )


def write_update_ledger(root: Path) -> UpdateLedgerSummary:
    """Write the update ledger and summary to the control plane."""

    resolved_root = root.resolve()
    events = build_update_ledger(resolved_root)
    summary = build_update_ledger_summary(events)
    atomic_write_jsonl(resolved_root / UPDATE_LEDGER_PATH, events, resolved_root)
    atomic_write_json(resolved_root / UPDATE_LEDGER_SUMMARY_PATH, summary, resolved_root)
    return summary


def _manifest_events(root: Path) -> list[UpdateLedgerEvent]:
    """Build one event per manifest layer."""

    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    manifest = _load_dict(manifest_path)
    layers = manifest.get("data_layers") if isinstance(manifest.get("data_layers"), list) else []
    events: list[UpdateLedgerEvent] = []
    for index, layer in enumerate(layers, start=1):
        if not isinstance(layer, dict):
            continue
        layer_id = _as_str(layer.get("id"), "unknown_layer")
        record_count = int(layer.get("record_count") or 0)
        status = _as_str(layer.get("status"), "unknown")
        event_date = _as_str(
            layer.get("last_ingested") or layer.get("last_checked"),
            _fallback_date(),
        )
        events.append(
            UpdateLedgerEvent(
                event_id=f"LEDGER-MANIFEST-{index:03d}-{_slug(layer_id)}",
                event_date=event_date,
                event_type="layer_status",
                source="manifest",
                title=f"{layer_id} status",
                description=f"{record_count:,} records are marked {status}.",
                layer_id=layer_id,
                status=status,
                source_path=f"{CONTROL_PLANE_DIR}/MASTER_MANIFEST.json",
                evidence_id=layer_id,
                requires_full_diff=bool(layer.get("known_gaps")),
                confidence=1.0,
            )
        )
    return events


def _update_log_events(root: Path) -> list[UpdateLedgerEvent]:
    """Build ledger events from the append-only update log."""

    path = root / CONTROL_PLANE_DIR / "UPDATE_LOG.jsonl"
    if not path.exists():
        return []
    events: list[UpdateLedgerEvent] = []
    for index, row in enumerate(iter_jsonl(path), start=1):
        event_id = _as_str(row.get("event_id"), f"LEDGER-UPDATE-LOG-{index:06d}")
        layer_id = _optional_str(row.get("layer"))
        entity_id = _optional_str(row.get("entity_id"))
        event_type = _as_str(row.get("event_type"), "update_log_event")
        timestamp = _as_str(row.get("timestamp"), _fallback_date())
        message = _as_str(row.get("message"), event_type)
        source_path = _optional_str(row.get("source_path")) or f"{CONTROL_PLANE_DIR}/UPDATE_LOG.jsonl"
        events.append(
            UpdateLedgerEvent(
                event_id=f"LEDGER-LOG-{_slug(event_id)}",
                event_date=timestamp,
                event_type=event_type,
                source="update_log",
                title=_title_from_log(row, event_type),
                description=message,
                layer_id=layer_id,
                entity_id=entity_id,
                status=_optional_str(row.get("action")),
                source_path=source_path,
                evidence_id=event_id,
                requires_full_diff=event_type in {"record_written", "record_updated"},
                confidence=1.0,
            )
        )
    return events


def _timeline_events(root: Path) -> list[UpdateLedgerEvent]:
    """Build ledger events from the master timeline."""

    path = root / CONTROL_PLANE_DIR / "MASTER_TIMELINE_INDEX.jsonl"
    if not path.exists():
        return []
    events: list[UpdateLedgerEvent] = []
    for index, row in enumerate(iter_jsonl(path), start=1):
        event_id = _as_str(row.get("id"), f"LEDGER-TIMELINE-{index:06d}")
        layer_id = _optional_str(row.get("layer"))
        entity_id = _optional_str(row.get("entity_id"))
        event_type = _as_str(row.get("event_type"), "timeline_event")
        source_path = _optional_str(row.get("file_path")) or (
            f"{CONTROL_PLANE_DIR}/MASTER_TIMELINE_INDEX.jsonl"
        )
        events.append(
            UpdateLedgerEvent(
                event_id=f"LEDGER-TIMELINE-{_slug(event_id)}",
                event_date=_as_str(row.get("date"), _fallback_date()),
                event_type=event_type,
                source="timeline",
                title=f"{event_type.replace('_', ' ').title()} for {entity_id or 'corpus item'}",
                description=_as_str(row.get("description"), event_type),
                layer_id=layer_id,
                entity_id=entity_id,
                status="timeline_recorded",
                source_path=source_path,
                evidence_id=event_id,
                requires_full_diff=False,
                confidence=0.9,
            )
        )
    return events


def _step_gate_events(root: Path) -> list[UpdateLedgerEvent]:
    """Build one ledger event for each completed readiness gate report."""

    control = root / CONTROL_PLANE_DIR
    events: list[UpdateLedgerEvent] = []
    for path in sorted(control.glob("STEP*_READINESS_REPORT.json")):
        payload = _load_dict(path)
        ready_keys = [key for key in payload if key.startswith("ready_for_")]
        ready = any(bool(payload.get(key)) for key in ready_keys)
        step_name = path.stem.replace("_READINESS_REPORT", "")
        blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
        events.append(
            UpdateLedgerEvent(
                event_id=f"LEDGER-GATE-{step_name}",
                event_date=_as_str(payload.get("generated_at"), _fallback_date()),
                event_type="step_gate",
                source="step_gate",
                title=f"{step_name} readiness",
                description=(
                    f"{step_name} is ready with {len(blockers)} blockers."
                    if ready
                    else f"{step_name} is not ready; {len(blockers)} blockers remain."
                ),
                layer_id=None,
                status="ready" if ready else "blocked",
                source_path=f"{CONTROL_PLANE_DIR}/{path.name}",
                evidence_id=step_name,
                requires_full_diff=False,
                confidence=1.0,
            )
        )
    return events


def _title_from_log(row: dict[str, Any], event_type: str) -> str:
    """Build a compact update-log title."""

    entity_id = _optional_str(row.get("entity_id"))
    layer_id = _optional_str(row.get("layer"))
    if entity_id:
        return f"{event_type.replace('_', ' ').title()}: {entity_id}"
    if layer_id:
        return f"{event_type.replace('_', ' ').title()}: {layer_id}"
    return event_type.replace("_", " ").title()


def _load_dict(path: Path) -> dict[str, Any]:
    """Load a JSON object, returning an empty object if absent."""

    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _as_str(value: object, fallback: str) -> str:
    """Convert a value to a non-empty string."""

    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _optional_str(value: object) -> str | None:
    """Convert a value to a non-empty optional string."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _fallback_date() -> str:
    """Return a stable fallback date for generated evidence."""

    return datetime.now(timezone.utc).date().isoformat()


def _slug(value: str) -> str:
    """Return a compact identifier-safe slug."""

    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "UNKNOWN"


def main() -> None:
    """Build or write the update ledger."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    if args.write:
        summary = write_update_ledger(root)
    else:
        events = build_update_ledger(root)
        summary = build_update_ledger_summary(events)
    if args.json:
        print(summary.model_dump_json(indent=2))
        return
    print(f"Update ledger events: {summary.events_written}")


if __name__ == "__main__":
    main()
