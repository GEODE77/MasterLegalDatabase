"""Tests for local change tracking reports."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.change_tracking import build_full_text_diff, build_source_freshness_report, write_change_tracking
from geode.utils.file_io import iter_jsonl


def test_full_text_diff_detects_snapshot_changes(tmp_path: Path) -> None:
    """Text diff should compare current text to the latest local snapshot."""

    current = tmp_path / "01_Statutes_CRS" / "crs_title_01.md"
    snapshot = tmp_path / "_SNAPSHOTS" / "snapshot_2026-01-01T000000Z" / "01_Statutes_CRS" / "crs_title_01.md"
    current.parent.mkdir(parents=True)
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("old line\nsame line\n", encoding="utf-8")
    current.write_text("new line\nsame line\n", encoding="utf-8")

    records, summary = build_full_text_diff(tmp_path)

    assert summary.files_checked == 1
    assert summary.files_with_prior_snapshot == 1
    assert summary.files_changed == 1
    assert records[0].added_lines == 1
    assert records[0].removed_lines == 1


def test_source_freshness_uses_manifest_dates(tmp_path: Path) -> None:
    """Freshness report should be based on local manifest dates."""

    control = tmp_path / "_CONTROL_PLANE"
    control.mkdir()
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps(
            {
                "data_layers": [
                    {
                        "id": "02_Regulations_CCR",
                        "record_count": 1,
                        "status": "ready",
                        "last_checked": "2026-06-30",
                        "source": "ccr",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_source_freshness_report(tmp_path)

    assert report.layers_checked == 1
    assert report.layers[0].layer_id == "02_Regulations_CCR"
    assert report.network_refresh_performed is False


def test_write_change_tracking_outputs_reports(tmp_path: Path) -> None:
    """Change tracking should write diff, summary, and freshness files."""

    current = tmp_path / "02_Regulations_CCR" / "_rules" / "1_CCR_101-1.md"
    current.parent.mkdir(parents=True)
    current.write_text("current text\n", encoding="utf-8")
    control = tmp_path / "_CONTROL_PLANE"
    control.mkdir()
    (control / "MASTER_MANIFEST.json").write_text(json.dumps({"data_layers": []}), encoding="utf-8")

    diff_summary, freshness = write_change_tracking(tmp_path)

    assert diff_summary.files_checked == 1
    assert freshness.layers_checked == 0
    assert len(list(iter_jsonl(tmp_path / "_CONTROL_PLANE" / "FULL_TEXT_DIFF.jsonl"))) == 1
    assert (tmp_path / "_CONTROL_PLANE" / "FULL_TEXT_DIFF_SUMMARY.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "SOURCE_FRESHNESS_REPORT.json").exists()
