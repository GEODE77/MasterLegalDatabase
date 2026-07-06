"""Tests for source-to-output accuracy auditing."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.source_output_accuracy_audit import (
    build_source_output_accuracy_audit,
    write_source_output_accuracy_audit,
)


def test_source_output_accuracy_audit_matches_raw_source(tmp_path: Path) -> None:
    """The audit should mark records high when source evidence matches output."""

    _write_fixture(tmp_path, raw_text="1 CCR 101-1 Division of Finance and Procurement")

    audit, records, queue = build_source_output_accuracy_audit(tmp_path)

    assert audit.total_records_checked == 1
    assert audit.high_accuracy == 1
    assert records[0].source_relation == "raw_archive_source"
    assert records[0].evidence_terms_matched >= 2
    assert queue["open_groups"] == 0


def test_source_output_accuracy_audit_flags_low_evidence(tmp_path: Path) -> None:
    """The audit should flag records when output terms do not appear in source."""

    _write_fixture(tmp_path, raw_text="unrelated source text")

    audit, records, queue = build_source_output_accuracy_audit(tmp_path)

    assert audit.low_accuracy == 1
    assert records[0].accuracy_level == "low"
    assert "low" in queue["groups"]


def test_write_source_output_accuracy_audit_outputs_artifacts(tmp_path: Path) -> None:
    """The writer should create machine and human reports."""

    _write_fixture(tmp_path, raw_text="1 CCR 101-1 Division of Finance and Procurement")

    audit = write_source_output_accuracy_audit(tmp_path)

    assert audit.total_records_checked == 1
    assert (tmp_path / "_CONTROL_PLANE" / "SOURCE_TO_OUTPUT_ACCURACY_AUDIT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "SOURCE_TO_OUTPUT_ACCURACY_RECORDS.jsonl").exists()
    assert (
        tmp_path / "_CONTROL_PLANE" / "SOURCE_TO_OUTPUT_ACCURACY_REPAIR_QUEUE.json"
    ).exists()
    assert (tmp_path / "docs" / "audits" / "SOURCE_TO_OUTPUT_ACCURACY_AUDIT_2026-07-01.md").exists()


def _write_fixture(root: Path, raw_text: str) -> None:
    control = root / "_CONTROL_PLANE"
    layer = root / "02_Regulations_CCR"
    raw = root / "_RAW_ARCHIVE" / "ccr"
    docs = root / "docs" / "audits"
    control.mkdir(parents=True)
    layer.mkdir(parents=True)
    raw.mkdir(parents=True)
    docs.mkdir(parents=True)
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
    (raw / "1_CCR_101-1.txt").write_text(raw_text, encoding="utf-8")
    (layer / "record.json").write_text(
        json.dumps(
            {
                "id": "1_CCR_101-1",
                "ccr_citation": "1 CCR 101-1",
                "agency_normalized": "Division of Finance and Procurement",
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        layer / "_index.jsonl",
        [
            {
                "id": "1_CCR_101-1",
                "layer": "02_Regulations_CCR",
                "entity_type": "regulation_rule",
                "title": "1 CCR 101-1",
                "citation": "1 CCR 101-1",
                "path": "02_Regulations_CCR/record.json",
                "source_path": "_RAW_ARCHIVE/ccr/1_CCR_101-1.txt",
            }
        ],
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
