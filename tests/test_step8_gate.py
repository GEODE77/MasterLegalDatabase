"""Tests for the Step 8 readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.update_ledger import write_update_ledger
from geode.validation.step8_gate import build_step8_readiness_report, write_step8_readiness_report


def test_step8_gate_passes_with_update_ledger(tmp_path: Path) -> None:
    """Step 8 passes when update ledger artifacts and product access exist."""

    _write_step8_fixture(tmp_path)

    report = write_step8_readiness_report(tmp_path)

    assert report.ready_for_step_8_completion
    assert not report.blockers
    assert any(item.id == "STEP8-FULL-TEXT-DIFF" for item in report.deferred_items)
    assert (tmp_path / "_CONTROL_PLANE" / "STEP8_READINESS_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "STEP8_DEFERRED_QUEUE.json").exists()


def test_step8_gate_blocks_when_ledger_is_missing(tmp_path: Path) -> None:
    """Step 8 blocks when the update ledger has not been generated."""

    _write_step8_fixture(tmp_path, write_ledger=False)

    report = build_step8_readiness_report(tmp_path)

    assert not report.ready_for_step_8_completion
    assert any("Update ledger" in blocker for blocker in report.blockers)


def _write_step8_fixture(root: Path, *, write_ledger: bool = True) -> None:
    """Write a minimal Step 8-ready fixture."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "STEP6_READINESS_REPORT.json").write_text(
        json.dumps({"ready_for_step_6_completion": True}),
        encoding="utf-8",
    )
    _write_ledger_source_fixture(root)
    if write_ledger:
        write_update_ledger(root)
    _write_marker_file(
        root / "geode" / "web" / "src" / "app" / "api" / "product" / "updates" / "route.ts",
        "getUpdateLedger getUpdateLedgerSummary ledger",
    )
    _write_marker_file(
        root / "geode" / "web" / "src" / "app" / "app" / "updates" / "page.tsx",
        "getUpdateLedger Full text diff Update Ledger",
    )


def _write_ledger_source_fixture(root: Path) -> None:
    """Write minimal source files used by the update ledger builder."""

    control = root / "_CONTROL_PLANE"
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps(
            {
                "data_layers": [
                    {
                        "id": "02_Regulations_CCR",
                        "last_ingested": "2026-06-23",
                        "record_count": 1,
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
                "message": "Wrote one record.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (control / "MASTER_TIMELINE_INDEX.jsonl").write_text(
        json.dumps(
            {
                "id": "TE-1",
                "date": "2026-06-23",
                "event_type": "rule_effective",
                "description": "Rule event.",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_marker_file(path: Path, content: str) -> None:
    """Write one marker file for Step 8 gate tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
