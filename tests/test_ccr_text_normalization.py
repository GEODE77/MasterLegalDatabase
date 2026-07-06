"""Tests for CCR raw archive to regulation-rule text normalization."""

from __future__ import annotations

import json
from pathlib import Path

from geode.extractors.converter import ConversionResult
from geode.extractors.fingerprint import PreservationReport, fingerprint_source
from geode.pipeline.ccr_text import (
    build_regulation_rule_record,
    normalize_ccr_text_records,
)
from geode.schemas import RegulationRule
from geode.utils.file_io import iter_jsonl

SOURCE_PAGE_URL = (
    "https://www.sos.state.co.us/CCR/DisplayRule.do?"
    "action=ruleinfo&ruleId=1&deptID=16&agencyID=7"
)
PDF_URL = "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?rule=5%20CCR%201001-9"


def test_build_regulation_rule_record_extracts_text_metadata(tmp_path: Path) -> None:
    """A downloaded CCR dataset row becomes a schema-valid RegulationRule payload."""

    raw_file = tmp_path / "5_CCR_1001-9.pdf"
    raw_file.write_bytes(b"%PDF-1.7\nfixture")
    record = _dataset_record(raw_file)
    conversion = _conversion(raw_file)

    payload = build_regulation_rule_record(record, conversion, tmp_path)
    model = RegulationRule.model_validate(
        {
            key: value
            for key, value in payload.items()
            if key not in {"crosswalks", "timeline_events", "source_path"}
        }
    )

    assert model.id == "5_CCR_1001-9"
    assert model.effective_date.isoformat() == "2024-01-01"
    assert model.enabling_statutes == ["CRS-25-7-109"]
    assert "air_quality" in model.subject_tags
    assert "manufacturing" in model.industry_tags
    assert "permit_required" in model.compliance_keywords
    assert payload["crosswalks"][0]["record"]["target_id"] == "CRS-25-7-109"
    assert payload["timeline_events"][0]["event_type"] == "rule_effective"


def test_build_regulation_rule_record_skips_future_timeline_event(tmp_path: Path) -> None:
    """Future CCR effective dates stay on the rule but not the timeline."""

    raw_file = tmp_path / "5_CCR_1001-9.pdf"
    raw_file.write_bytes(b"%PDF-1.7\nfixture")
    record = _dataset_record(raw_file)
    conversion = _conversion(raw_file)
    conversion.markdown_text = conversion.markdown_text.replace(
        "Effective January 1, 2024",
        "Effective December 31, 2026",
    )

    payload = build_regulation_rule_record(record, conversion, tmp_path)
    model = RegulationRule.model_validate(
        {
            key: value
            for key, value in payload.items()
            if key not in {"crosswalks", "timeline_events", "source_path"}
        }
    )

    assert model.effective_date.isoformat() == "2026-12-31"
    assert payload["timeline_events"] == []


def test_normalize_ccr_text_records_writes_rule_outputs(project_root: Path) -> None:
    """Bulk text normalization writes rule Markdown, metadata, crosswalks, and summary."""

    raw_file = _write_acquisition_artifacts(project_root)

    summary = normalize_ccr_text_records(
        project_root,
        converter=lambda path: _conversion(path),
    )
    index_rows = list(iter_jsonl(project_root / "02_Regulations_CCR" / "_index.jsonl"))
    meta_rows = list(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "ccr_rules_meta.jsonl")
    )
    crosswalk_rows = list(iter_jsonl(project_root / "_CROSSWALKS" / "regulation_to_statute.jsonl"))
    rule_path = project_root / "02_Regulations_CCR" / "_rules" / "5_CCR_1001-9.md"
    department_files = list((project_root / "02_Regulations_CCR").glob("ccr_dept_*.md"))

    assert raw_file.exists()
    assert summary.records_considered == 1
    assert summary.converted == 1
    assert summary.written == 1
    assert summary.failed == 0
    assert summary.skipped == 0
    assert rule_path.exists()
    assert "permit required" in rule_path.read_text(encoding="utf-8")
    assert meta_rows[0]["entity_type"] == "regulation_rule"
    assert index_rows[0]["entity_type"] == "regulation_rule"
    assert crosswalk_rows[0]["target_id"] == "CRS-25-7-109"
    assert department_files
    assert Path(summary.summary_path).exists()


def test_normalize_ccr_text_records_skips_pending_rows(project_root: Path) -> None:
    """Rows without downloaded raw files stay skipped instead of fabricated."""

    archive_dir = project_root / "_RAW_ARCHIVE" / "ccr"
    archive_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        archive_dir / "ccr_bulk_queue.jsonl",
        [_queue_row(sequence=0, status="resolved", archive_path=None)],
    )

    summary = normalize_ccr_text_records(project_root)

    assert summary.records_considered == 1
    assert summary.skipped == 1
    assert summary.written == 0
    assert summary.skipped_ids == ["5_CCR_1001-9"]


def _write_acquisition_artifacts(project_root: Path) -> Path:
    """Write one downloaded CCR acquisition fixture."""

    archive_dir = project_root / "_RAW_ARCHIVE" / "ccr"
    archive_dir.mkdir(parents=True, exist_ok=True)
    raw_file = archive_dir / "5_CCR_1001-9.pdf"
    raw_file.write_bytes(b"%PDF-1.7\nfixture")
    _write_jsonl(
        archive_dir / "ccr_bulk_queue.jsonl",
        [
            _queue_row(sequence=0, status="discovered", archive_path=None),
            _queue_row(sequence=1, status="resolved", archive_path=raw_file),
            _queue_row(sequence=2, status="downloaded", archive_path=raw_file),
        ],
    )
    _write_jsonl(
        archive_dir / "download_manifest.jsonl",
        [
            {
                "jurisdiction": "Colorado",
                "source_type": "regulation_rule",
                "document_id": "5_CCR_1001-9",
                "document_name": "5 CCR 1001-9",
                "ccr_number": "5 CCR 1001-9",
                "department": "1000 Department of Public Health and Environment",
                "agency": "1001 Air Quality Control Commission",
                "source_url": PDF_URL,
                "source_page_url": SOURCE_PAGE_URL,
                "source_format": "pdf",
                "archive_path": raw_file.as_posix(),
                "sha256": "a" * 64,
                "size_bytes": raw_file.stat().st_size,
                "downloaded_at": "2026-06-22T10:02:00+00:00",
                "effective_date": None,
                "publication_date": None,
                "status": "downloaded",
                "error": None,
                "missing_metadata": ["effective_date", "publication_date"],
            }
        ],
    )
    return raw_file


def _queue_row(
    *,
    sequence: int,
    status: str,
    archive_path: Path | None,
) -> dict[str, object]:
    """Return one CCR bulk queue fixture row."""

    return {
        "sequence": sequence,
        "timestamp": "2026-06-22T10:00:00+00:00",
        "item_id": "5_CCR_1001-9",
        "status": status,
        "phase": "content_retrieval" if status == "downloaded" else "detail_resolution",
        "ccr_number": "5 CCR 1001-9",
        "department": "1000 Department of Public Health and Environment",
        "agency": "1001 Air Quality Control Commission",
        "source_page_url": SOURCE_PAGE_URL,
        "pdf_url": PDF_URL,
        "docx_url": None,
        "preferred_url": PDF_URL,
        "archive_path": archive_path.as_posix() if archive_path else None,
        "error": None,
    }


def _dataset_record(raw_file: Path):
    """Return one validated CCR dataset record."""

    from geode.connectors.ccr_dataset import CCRDatasetRecord

    return CCRDatasetRecord(
        record_id="5_CCR_1001-9",
        title="5 CCR 1001-9",
        department="1000 Department of Public Health and Environment",
        department_normalized="Department of Public Health and Environment",
        agency="1001 Air Quality Control Commission",
        agency_normalized="Air Quality Control Commission",
        division_board_program="Air Quality Control Commission",
        ccr_citation="5 CCR 1001-9",
        department_number="5",
        chapter="1001",
        rule_number="9",
        source_page_url=SOURCE_PAGE_URL,
        document_url=PDF_URL,
        file_path=raw_file.as_posix(),
        content_type="application/pdf",
        source_format="pdf",
        download_status="downloaded",
        raw_file_exists=True,
    )


def _conversion(path: Path) -> ConversionResult:
    """Return a deterministic fake conversion result for a raw file."""

    markdown = """# Air Quality Control Commission Regulation 9

Effective January 1, 2024

The commission cites 25-7-109, C.R.S. A permit required by this rule must be
reported and records must be kept for inspection.
"""
    return ConversionResult(
        markdown_text=markdown,
        conversion_path="path_2_pdf_markitdown",
        tool_used="fixture",
        preservation_score=PreservationReport(
            source_tokens=0,
            output_tokens=len(markdown.split()),
            shared_tokens=0,
            preservation_score=0.0,
            passed=False,
        ),
        fingerprint=fingerprint_source(path, PDF_URL),
        warnings=[],
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write fixture JSONL records."""

    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
