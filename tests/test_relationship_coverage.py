"""Tests for relationship coverage reporting."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.relationship_coverage import (
    build_relationship_coverage,
    write_relationship_coverage,
)
from geode.utils.file_io import iter_jsonl


def test_relationship_coverage_measures_crosswalk_health(tmp_path: Path) -> None:
    """Relationship coverage should measure populated and empty crosswalks."""

    _write_relationship_fixture(tmp_path)

    records, summary_records, report = build_relationship_coverage(tmp_path)

    assert len(records) == 4
    assert len(summary_records) == 6
    assert report.total_relationships == 4
    assert report.ccr_regulations_total == 3
    assert report.ccr_regulations_with_relationships == 2
    assert report.structured_relationship_panel_ready
    assert report.visual_graph_ready is False
    assert any(record.coverage_status == "empty" for record in summary_records)


def test_write_relationship_coverage_outputs_jsonl_and_report(tmp_path: Path) -> None:
    """Writing relationship coverage creates matching control-plane artifacts."""

    _write_relationship_fixture(tmp_path)

    report = write_relationship_coverage(tmp_path)

    rows = list(iter_jsonl(tmp_path / "_CONTROL_PLANE" / "RELATIONSHIP_COVERAGE.jsonl"))
    summary_rows = list(iter_jsonl(tmp_path / "_CONTROL_PLANE" / "RELATIONSHIP_COVERAGE_SUMMARY.jsonl"))
    assert len(rows) == report.total_relationships
    assert len(summary_rows) == report.crosswalk_files_checked
    assert (tmp_path / "_CONTROL_PLANE" / "RELATIONSHIP_COVERAGE_REPORT.json").exists()


def _write_relationship_fixture(root: Path) -> None:
    """Write a minimal corpus and crosswalk fixture."""

    control = root / "_CONTROL_PLANE"
    crosswalks = root / "_CROSSWALKS"
    layer = root / "02_Regulations_CCR"
    control.mkdir(parents=True)
    crosswalks.mkdir(parents=True)
    layer.mkdir(parents=True)
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps(
            {
                "data_layers": [
                    {
                        "id": "02_Regulations_CCR",
                        "index_file": "02_Regulations_CCR/_index.jsonl",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (layer / "_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"id": "1_CCR_101-1"}),
                json.dumps({"id": "1_CCR_101-2"}),
                json.dumps({"id": "1_CCR_101-3"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        crosswalks / "regulation_to_statute.jsonl",
        [
            {
                "source_id": "1_CCR_101-1",
                "source_type": "regulation_rule",
                "target_id": "CRS-1-1-101",
                "target_type": "statute_section",
                "relationship": "cites",
                "confidence": 0.75,
                "source_evidence": "Authority cites CRS 1-1-101.",
            },
            {
                "source_id": "1_CCR_101-1",
                "target_id": "CRS-1-1-101",
                "relationship": "cites",
                "confidence": 0.75,
                "source_evidence": "Duplicate edge.",
            },
        ],
    )
    _write_jsonl(
        crosswalks / "statute_to_regulation.jsonl",
        [
            {
                "source_id": "CRS-1-1-102",
                "source_type": "statute_section",
                "target_id": "1_CCR_101-2",
                "target_type": "regulation_rule",
                "relationship": "implements",
                "confidence": 0.4,
                "source_evidence": "",
            }
        ],
    )
    _write_jsonl(
        crosswalks / "rulemaking_to_regulation.jsonl",
        [
            {
                "source_id": "RM-1",
                "target_id": "1_CCR_101-2",
                "relationship": "modified_by",
                "confidence": 0.9,
                "source_evidence": "Notice names the regulation.",
            }
        ],
    )
    for name in ["bill_to_statute.jsonl", "agency_to_statute.jsonl", "amendment_history.jsonl"]:
        (crosswalks / name).write_text("", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL test rows."""

    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
