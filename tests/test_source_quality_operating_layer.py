"""Tests for the source quality operating layer."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.source_quality_operating_layer import build_source_quality_operating_layer
from geode.utils.file_io import iter_jsonl, load_json


def test_source_quality_operating_layer_writes_readiness_artifacts(tmp_path: Path) -> None:
    """The operating layer should score sources and preserve reliance boundaries."""

    _write_fixture(tmp_path)

    report = build_source_quality_operating_layer(tmp_path)

    assert report["local_system_usable"] is True
    assert report["external_reliance_ready"] is False
    assert "named_reviewer_assignments_missing" in report["blockers"]
    assert (tmp_path / "_CONTROL_PLANE" / "SOURCE_STRENGTH_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "SOURCE_REPAIR_DASHBOARD.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "MASTER_READINESS_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "GOLDEN_SAMPLE_REVIEW_SET.jsonl").exists()

    strength_rows = list(
        iter_jsonl(tmp_path / "_CONTROL_PLANE" / "SOURCE_STRENGTH_INDEX.jsonl")
    )
    assert strength_rows[0]["source_strength_level"] == "direct_full_text_source"
    assert strength_rows[0]["reliance_label"] == "source-backed"

    repair = load_json(tmp_path / "_CONTROL_PLANE" / "SOURCE_REPAIR_DASHBOARD.json")
    assert repair["open_items"] >= 3


def test_source_quality_marks_crs_refresh_complete_with_confirmation(tmp_path: Path) -> None:
    """CRS freshness clears only when rebuild and official confirmation are present."""

    _write_fixture(tmp_path)
    control = tmp_path / "_CONTROL_PLANE"
    crs_meta = tmp_path / "01_Statutes_CRS" / "_meta"
    crs_meta.mkdir(parents=True)
    _write_json(
        control / "MASTER_MANIFEST.json",
        {
            "data_layers": [
                {
                    "id": "01_Statutes_CRS",
                    "index_file": "01_Statutes_CRS/_index.jsonl",
                    "last_checked": "2026-07-02",
                }
            ]
        },
    )
    _write_json(
        control / "SOURCE_FRESHNESS_REPORT.json",
        {
            "layers": [
                {
                    "layer_id": "01_Statutes_CRS",
                    "freshness_status": "fresh",
                    "last_checked": "2026-07-02",
                }
            ]
        },
    )
    _write_json(
        crs_meta / "crs_bulk_summary.json",
        {
            "generated_at": "2026-07-02T00:00:00Z",
            "failed_files": 0,
            "parsed_titles": 46,
            "sections_written": 34717,
        },
    )
    _write_json(
        control / "CRS_OFFICIAL_REFRESH_CONFIRMATION.json",
        {
            "generated_at": "2026-07-02T00:00:00Z",
            "status": "confirmed_current_publication",
        },
    )

    report = build_source_quality_operating_layer(tmp_path)
    queue = load_json(control / "FRESHNESS_VERIFICATION_QUEUE.json")

    assert report["freshness"]["items"] == 0
    assert queue["refreshed_sources"] == ["01_Statutes_CRS"]


def _write_fixture(root: Path) -> None:
    control = root / "_CONTROL_PLANE"
    layer = root / "05_Executive_Orders"
    raw = root / "_RAW_ARCHIVE" / "exec_orders"
    crosswalk = root / "_CROSSWALKS"
    docs = root / "docs" / "audits"
    for directory in (control, layer, raw, crosswalk, docs):
        directory.mkdir(parents=True, exist_ok=True)

    _write_json(
        control / "MASTER_MANIFEST.json",
        {
            "data_layers": [
                {
                    "id": "05_Executive_Orders",
                    "index_file": "05_Executive_Orders/_index.jsonl",
                }
            ]
        },
    )
    _write_json(
        control / "SOURCE_FRESHNESS_REPORT.json",
        {
            "layers": [
                {
                    "layer_id": "05_Executive_Orders",
                    "freshness_status": "needs_live_check",
                }
            ]
        },
    )
    _write_json(
        control / "REVIEWER_ASSIGNMENTS.json",
        {
            "assignments": [
                {
                    "role_id": "legal_reviewer",
                    "assignment_status": "unassigned",
                }
            ]
        },
    )
    _write_jsonl(
        control / "SOURCE_TO_OUTPUT_ACCURACY_RECORDS.jsonl",
        [
            {
                "record_id": "EO-2025-001",
                "accuracy_level": "high",
                "source_path": str(raw / "EO-2025-001.pdf"),
            }
        ],
    )
    (raw / "EO-2025-001.pdf").write_text("Executive Order 2025 001", encoding="utf-8")
    _write_jsonl(
        layer / "_index.jsonl",
        [
            {
                "id": "EO-2025-001",
                "citation": "EO 2025-001",
                "title": "Executive Order 2025-001",
                "source_path": "_RAW_ARCHIVE/exec_orders/EO-2025-001.pdf",
            }
        ],
    )
    _write_jsonl(
        crosswalk / "amendment_history.jsonl",
        [
            {
                "source_id": "EO-2025-001",
                "target_id": "EO-2025-001",
                "relationship": "self_reference_fixture",
                "confidence": 1.0,
                "source_evidence": "fixture evidence",
            }
        ],
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
