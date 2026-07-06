"""Tests for operations readiness reporting."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.operations_readiness import build_operations_readiness, write_operations_readiness


def test_operations_readiness_keeps_human_work_queued(tmp_path: Path) -> None:
    """Operations report should keep human review work queued when unfinished."""

    _write_operations_fixture(tmp_path)

    report, queue = build_operations_readiness(tmp_path)

    assert report.system_controls_present
    assert "not_implied" in report.boundary
    assert report.warnings
    assert queue.open_items >= 2
    assert {item.id for item in queue.items} >= {"HUMAN-REVIEWERS", "HUMAN-PACKET-REVIEW"}


def test_write_operations_readiness_outputs_reports(tmp_path: Path) -> None:
    """Writer should create production readiness and remaining work reports."""

    _write_operations_fixture(tmp_path)

    report, queue = write_operations_readiness(tmp_path)

    assert report.system_controls_present
    assert queue.open_items >= 1
    assert (tmp_path / "_CONTROL_PLANE" / "PRODUCTION_READINESS_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "REMAINING_WORK_QUEUE.json").exists()


def test_operations_readiness_includes_blocked_download_queue(tmp_path: Path) -> None:
    """Blocked downloads remain visible after operations reports rebuild."""

    _write_operations_fixture(tmp_path)
    (tmp_path / "_CONTROL_PLANE" / "BLOCKED_DOWNLOAD_QUEUE.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "record_id": "EO-2019-007",
                        "status": "queued",
                        "block_reason": "Official download returns a sign-in page.",
                        "next_action": "Request a valid official copy.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    _, queue = build_operations_readiness(tmp_path)

    assert "BLOCKED-DOWNLOAD-EO-2019-007" in {item.id for item in queue.items}


def _write_operations_fixture(root: Path) -> None:
    """Write minimal operations readiness inputs."""

    control = root / "_CONTROL_PLANE"
    meta = root / "02_Regulations_CCR" / "_meta"
    utils = root / "geode" / "utils"
    control.mkdir(parents=True)
    meta.mkdir(parents=True)
    utils.mkdir(parents=True)
    (utils / "file_io.py").write_text("def ensure_not_raw_archive(): pass\n", encoding="utf-8")
    (control / "STEP9_READINESS_REPORT.json").write_text(
        json.dumps({"ready_for_step_9_completion": True}),
        encoding="utf-8",
    )
    (control / "REVIEWER_OPERATIONS_SUMMARY.json").write_text(
        json.dumps({"unassigned_roles": 3}),
        encoding="utf-8",
    )
    (meta / "rule_units_review_packets_summary.json").write_text(
        json.dumps({"pending": 10}),
        encoding="utf-8",
    )
    (control / "FULL_TEXT_DIFF_SUMMARY.json").write_text(
        json.dumps({"diff_ready": True, "files_checked": 1}),
        encoding="utf-8",
    )
    (control / "SOURCE_FRESHNESS_REPORT.json").write_text(
        json.dumps({"stale_layers": 0, "unknown_layers": 0}),
        encoding="utf-8",
    )
    (control / "RETRIEVAL_CATALOG_SUMMARY.json").write_text(
        json.dumps({"records_written": 1}),
        encoding="utf-8",
    )
