"""Tests for normalized CCR acquisition dataset writing."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from geode.connectors.ccr_dataset import write_ccr_dataset
from geode.utils.file_io import iter_jsonl

SOURCE_PAGE_URL = (
    "https://www.sos.state.co.us/CCR/DisplayRule.do?"
    "action=ruleinfo&ruleId=1&deptID=16&agencyID=7"
)
PDF_URL = "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?rule=5%20CCR%201001-9"


def test_ccr_dataset_writer_collapses_duplicate_artifact_rows(tmp_path: Path) -> None:
    """Dataset writer collapses append-only queue and manifest rows to one record."""

    archive_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    archive_dir.mkdir(parents=True)
    raw_file = archive_dir / "5_CCR_1001-9.pdf"
    raw_file.write_bytes(b"%PDF-1.7\nfixture")
    _write_jsonl(
        archive_dir / "ccr_bulk_queue.jsonl",
        [
            _queue_row(sequence=0, status="indexed", timestamp="2026-06-22T10:00:00+00:00"),
            _queue_row(
                sequence=1,
                status="resolved",
                timestamp="2026-06-22T10:01:00+00:00",
                archive_path=raw_file,
            ),
            _queue_row(
                sequence=2,
                status="downloaded",
                timestamp="2026-06-22T10:02:00+00:00",
                archive_path=raw_file,
            ),
        ],
    )
    _write_jsonl(
        archive_dir / "download_manifest.jsonl",
        [
            _manifest_row(
                status="failed",
                archive_path=raw_file,
                sha256=None,
                downloaded_at="2026-06-22T10:01:30+00:00",
                error="temporary reset",
            ),
            _manifest_row(
                status="downloaded",
                archive_path=raw_file,
                sha256="a" * 64,
                downloaded_at="2026-06-22T10:02:00+00:00",
            ),
        ],
    )

    summary = write_ccr_dataset(tmp_path)
    rows = list(iter_jsonl(Path(summary.metadata_jsonl_path)))
    csv_rows = list(csv.DictReader(Path(summary.metadata_csv_path).open(encoding="utf-8")))
    normalized_rows = list(
        iter_jsonl(
            tmp_path / "02_Regulations_CCR" / "_normalized" / "ccr_normalized_records.jsonl"
        )
    )
    meta_rows = list(
        iter_jsonl(tmp_path / "02_Regulations_CCR" / "_meta" / "ccr_normalized_meta.jsonl")
    )
    index_rows = list(iter_jsonl(tmp_path / "02_Regulations_CCR" / "_index.jsonl"))
    normalized_record_path = tmp_path / normalized_rows[0]["normalized_output_path"]

    assert summary.records_total == 1
    assert summary.downloaded == 1
    assert summary.normalized_records_total == 1
    assert summary.normalized_index_path is not None
    assert Path(summary.normalized_index_path).exists()
    assert summary.queue_events_total == 3
    assert summary.manifest_rows_total == 2
    assert summary.duplicate_queue_events_collapsed == 2
    assert summary.duplicate_manifest_rows_collapsed == 1
    assert len(rows) == 1
    assert len(csv_rows) == 1
    assert rows[0]["record_id"] == "5_CCR_1001-9"
    assert rows[0]["department_normalized"] == "Department of Public Health and Environment"
    assert rows[0]["agency_normalized"] == "Air Quality Control Commission"
    assert rows[0]["division_board_program"] == "Air Quality Control Commission"
    assert rows[0]["ccr_citation"] == "5 CCR 1001-9"
    assert rows[0]["chapter"] == "1001"
    assert rows[0]["rule_number"] == "9"
    assert rows[0]["content_type"] == "application/pdf"
    assert rows[0]["checksum_sha256"] == "a" * 64
    assert rows[0]["raw_file_exists"] is True
    assert csv_rows[0]["download_status"] == "downloaded"
    assert normalized_record_path.exists()
    assert normalized_rows == meta_rows
    assert len(index_rows) == 1
    assert index_rows[0]["id"] == "5_CCR_1001-9"
    assert index_rows[0]["path"] == normalized_rows[0]["normalized_output_path"]
    assert index_rows[0]["meta_path"] == "02_Regulations_CCR/_meta/ccr_normalized_meta.jsonl"
    assert normalized_rows[0]["entity_type"] == "regulation_rule_acquisition"
    assert normalized_rows[0]["archive_raw_file_path"] == raw_file.as_posix()
    assert normalized_rows[0]["status"] == "downloaded"
    assert normalized_rows[0]["normalization_timestamp"]


def test_ccr_dataset_writer_updates_cleanly_after_resume(tmp_path: Path) -> None:
    """Dataset regeneration updates an existing row instead of appending a duplicate."""

    archive_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    archive_dir.mkdir(parents=True)
    raw_file = archive_dir / "5_CCR_1001-9.pdf"
    queue_path = archive_dir / "ccr_bulk_queue.jsonl"
    manifest_path = archive_dir / "download_manifest.jsonl"
    _write_jsonl(
        queue_path,
        [
            _queue_row(sequence=0, status="indexed", timestamp="2026-06-22T10:00:00+00:00"),
            _queue_row(
                sequence=1,
                status="resolved",
                timestamp="2026-06-22T10:01:00+00:00",
                archive_path=raw_file,
            ),
        ],
    )

    first_summary = write_ccr_dataset(tmp_path)
    first_rows = list(iter_jsonl(Path(first_summary.metadata_jsonl_path)))
    first_index_rows = list(iter_jsonl(tmp_path / "02_Regulations_CCR" / "_index.jsonl"))
    raw_file.write_bytes(b"%PDF-1.7\nfixture")
    _write_jsonl(
        manifest_path,
        [
            _manifest_row(
                status="downloaded",
                archive_path=raw_file,
                sha256="b" * 64,
                downloaded_at="2026-06-22T11:00:00+00:00",
            )
        ],
    )
    second_summary = write_ccr_dataset(tmp_path)
    second_rows = list(iter_jsonl(Path(second_summary.metadata_jsonl_path)))
    second_index_rows = list(iter_jsonl(tmp_path / "02_Regulations_CCR" / "_index.jsonl"))
    second_meta_rows = list(
        iter_jsonl(tmp_path / "02_Regulations_CCR" / "_meta" / "ccr_normalized_meta.jsonl")
    )

    assert first_summary.records_total == 1
    assert first_summary.normalized_records_total == 1
    assert first_rows[0]["download_status"] == "resolved"
    assert first_rows[0]["notes"] == "document content not yet retrieved"
    assert len(first_index_rows) == 1
    assert first_index_rows[0]["id"] == "5_CCR_1001-9"
    assert second_summary.records_total == 1
    assert second_summary.normalized_records_total == 1
    assert second_summary.downloaded == 1
    assert len(second_rows) == 1
    assert len(second_index_rows) == 1
    assert len(second_meta_rows) == 1
    assert second_rows[0]["download_status"] == "downloaded"
    assert second_rows[0]["checksum_sha256"] == "b" * 64
    assert second_rows[0]["discovery_timestamp"] == "2026-06-22T10:00:00Z"
    assert second_meta_rows[0]["status"] == "downloaded"
    assert second_meta_rows[0]["checksum_sha256"] == "b" * 64


def _queue_row(
    *,
    sequence: int,
    status: str,
    timestamp: str,
    archive_path: Path | None = None,
) -> dict[str, object]:
    """Return one CCR bulk queue fixture row."""

    return {
        "sequence": sequence,
        "timestamp": timestamp,
        "item_id": "5_CCR_1001-9",
        "status": status,
        "phase": "content_retrieval" if status == "downloaded" else "detail_resolution",
        "ccr_number": "5 CCR 1001-9",
        "department": "100,800 Department of Public Health and Environment",
        "agency": "1001 Air Quality Control Commission",
        "source_page_url": SOURCE_PAGE_URL,
        "pdf_url": PDF_URL,
        "docx_url": None,
        "preferred_url": PDF_URL,
        "archive_path": archive_path.as_posix() if archive_path else None,
        "error": None,
    }


def _manifest_row(
    *,
    status: str,
    archive_path: Path,
    sha256: str | None,
    downloaded_at: str,
    error: str | None = None,
) -> dict[str, object]:
    """Return one CCR download manifest fixture row."""

    return {
        "jurisdiction": "Colorado",
        "source_type": "regulation_rule",
        "document_id": "5_CCR_1001-9",
        "document_name": "5 CCR 1001-9",
        "ccr_number": "5 CCR 1001-9",
        "department": "100,800 Department of Public Health and Environment",
        "agency": "1001 Air Quality Control Commission",
        "source_url": PDF_URL,
        "source_page_url": SOURCE_PAGE_URL,
        "source_format": "pdf",
        "archive_path": archive_path.as_posix(),
        "sha256": sha256,
        "size_bytes": archive_path.stat().st_size if archive_path.exists() else 0,
        "downloaded_at": downloaded_at,
        "effective_date": None,
        "publication_date": None,
        "status": status,
        "error": error,
        "missing_metadata": ["effective_date", "publication_date"],
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write fixture JSONL without invoking production artifact writers."""

    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
