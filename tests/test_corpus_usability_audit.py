"""Tests for full corpus usability auditing."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.corpus_usability_audit import (
    build_corpus_usability_audit,
    write_corpus_usability_audit,
)


def test_corpus_usability_audit_checks_retrieval_and_content(tmp_path: Path) -> None:
    """The audit should flag records that cannot be found or used."""

    _write_fixture(tmp_path)

    audit, issues, queue = build_corpus_usability_audit(tmp_path)

    assert audit.total_index_records_checked == 2
    assert audit.total_retrievable_records == 1
    assert audit.total_crosswalk_rows_checked == 1
    assert audit.error_count >= 1
    assert any(issue.category == "missing_retrieval_catalog_entry" for issue in issues)
    assert any(issue.category == "missing_content_anchor" for issue in issues)
    assert queue["open_items"] == len(issues)


def test_write_corpus_usability_audit_outputs_reports(tmp_path: Path) -> None:
    """The writer should create machine and human audit artifacts."""

    _write_fixture(tmp_path)

    audit = write_corpus_usability_audit(tmp_path)

    assert audit.issue_count > 0
    assert (tmp_path / "_CONTROL_PLANE" / "CORPUS_USABILITY_AUDIT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "CORPUS_USABILITY_ISSUES.jsonl").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "CORPUS_USABILITY_REPAIR_QUEUE.json").exists()
    assert (tmp_path / "docs" / "audits" / "CORPUS_USABILITY_AUDIT_2026-07-01.md").exists()


def test_corpus_usability_audit_skips_snapshots_and_generated_runtime_data(
    tmp_path: Path,
) -> None:
    """The audit should stay focused on the current legal corpus."""

    _write_fixture(tmp_path)
    snapshot = tmp_path / "_SNAPSHOTS" / "snapshot_2026-01-01" / "bad.jsonl"
    generated_runtime = tmp_path / "data" / "structured_output" / "runtime" / "bad.jsonl"
    snapshot.parent.mkdir(parents=True)
    generated_runtime.parent.mkdir(parents=True)
    snapshot.write_text("{bad json\n", encoding="utf-8")
    generated_runtime.write_text("{bad json\n", encoding="utf-8")

    audit, issues, _queue = build_corpus_usability_audit(tmp_path)

    assert audit.total_jsonl_files_checked == 8
    assert not any(issue.path == "_SNAPSHOTS/snapshot_2026-01-01/bad.jsonl" for issue in issues)
    assert not any(issue.path == "data/structured_output/runtime/bad.jsonl" for issue in issues)


def _write_fixture(root: Path) -> None:
    control = root / "_CONTROL_PLANE"
    layer = root / "01_Statutes_CRS"
    crosswalks = root / "_CROSSWALKS"
    docs = root / "docs" / "audits"
    control.mkdir(parents=True)
    layer.mkdir(parents=True)
    crosswalks.mkdir(parents=True)
    docs.mkdir(parents=True)
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps(
            {
                "data_layers": [
                    {
                        "id": "01_Statutes_CRS",
                        "index_file": "01_Statutes_CRS/_index.jsonl",
                        "record_count": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        control / "RETRIEVAL_CATALOG.jsonl",
        [
            {
                "id": "CRS-1-1-101",
                "layer": "01_Statutes_CRS",
                "retrieval_text": "CRS-1-1-101",
            }
        ],
    )
    (layer / "crs_title_01.md").write_text("#### CRS-1-1-101\nSource text.\n", encoding="utf-8")
    _write_jsonl(
        layer / "_index.jsonl",
        [
            _index_row("CRS-1-1-101", "01_Statutes_CRS/crs_title_01.md"),
            _index_row("CRS-1-1-102", "01_Statutes_CRS/missing.md"),
        ],
    )
    for name in [
        "regulation_to_statute.jsonl",
        "statute_to_regulation.jsonl",
        "bill_to_statute.jsonl",
        "rulemaking_to_regulation.jsonl",
        "agency_to_statute.jsonl",
        "amendment_history.jsonl",
    ]:
        rows = [
            {
                "source_id": "1_CCR_101-1",
                "target_id": "CRS-1-1-101",
                "relationship": "cites",
                "source_evidence": "Authority cites CRS-1-1-101.",
            }
        ] if name == "regulation_to_statute.jsonl" else []
        _write_jsonl(crosswalks / name, rows)


def _index_row(record_id: str, path: str) -> dict[str, object]:
    return {
        "id": record_id,
        "layer": "01_Statutes_CRS",
        "entity_type": "statute_section",
        "title": record_id,
        "citation": record_id,
        "path": path,
        "source_url": "https://leg.colorado.gov/colorado-revised-statutes",
        "source_path": path,
        "last_updated": "2026-07-01T00:00:00Z",
        "sha256": "a" * 64,
        "confidence": 1.0,
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
