"""Tests for update ledger generation."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.update_ledger import build_update_ledger, write_update_ledger
from geode.utils.file_io import iter_jsonl


def test_update_ledger_builds_source_backed_events(tmp_path: Path) -> None:
    """The ledger should combine manifest, log, timeline, and gate evidence."""

    _write_update_ledger_fixture(tmp_path)

    events = build_update_ledger(tmp_path)

    assert {event.source for event in events} == {
        "manifest",
        "step_gate",
        "timeline",
        "update_log",
    }
    assert all(event.full_text_diff_available is False for event in events)
    assert any(event.requires_full_diff for event in events)


def test_write_update_ledger_writes_summary_and_jsonl(tmp_path: Path) -> None:
    """Writing the ledger creates matching control-plane artifacts."""

    _write_update_ledger_fixture(tmp_path)

    summary = write_update_ledger(tmp_path)

    rows = list(iter_jsonl(tmp_path / "_CONTROL_PLANE" / "UPDATE_LEDGER.jsonl"))
    assert summary.events_written == len(rows)
    assert summary.full_diff_ready is False
    assert (tmp_path / "_CONTROL_PLANE" / "UPDATE_LEDGER_SUMMARY.json").exists()


def _write_update_ledger_fixture(root: Path) -> None:
    """Write minimal control-plane evidence for update ledger tests."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps(
            {
                "data_layers": [
                    {
                        "id": "02_Regulations_CCR",
                        "last_ingested": "2026-06-23",
                        "known_gaps": ["needs full diff"],
                        "record_count": 2,
                        "status": "ready",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (control / "UPDATE_LOG.jsonl").write_text(
        json.dumps(
            {
                "event_id": "UL-1",
                "timestamp": "2026-06-23T00:00:00Z",
                "event_type": "record_written",
                "layer": "02_Regulations_CCR",
                "entity_id": "1_CCR_101-1",
                "action": "write_record",
                "source_path": "_RAW_ARCHIVE/ccr/example.pdf",
                "message": "Wrote one regulation.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (control / "MASTER_TIMELINE_INDEX.jsonl").write_text(
        json.dumps(
            {
                "id": "TE-2026-06-23-001",
                "date": "2026-06-23",
                "event_type": "rule_effective",
                "entity_id": "1_CCR_101-1",
                "description": "Rule effective date recorded.",
                "layer": "02_Regulations_CCR",
                "file_path": "02_Regulations_CCR/_rules/1_CCR_101-1.md",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (control / "STEP6_READINESS_REPORT.json").write_text(
        json.dumps({"generated_at": "2026-06-24T00:00:00Z", "ready_for_step_6_completion": True}),
        encoding="utf-8",
    )
