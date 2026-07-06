"""Tests for Colorado Register/eDocket normalization."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from geode.connectors.register_pipeline import (
    extract_register_notices,
    write_rulemaking_dataset,
)
from geode.utils.file_io import iter_jsonl
from geode.utils.hashing import sha256_file


REGISTER_URL = "https://www.sos.state.co.us/pubs/CCR/register_2026-06-10.html"


def test_extract_register_notice_with_edocket_and_future_hearing() -> None:
    """Register notices preserve eDocket references and future hearing dates."""

    text = (
        "NOTICE: proposed | CCR: 5 CCR 1001-9 | Agency: CDPHE_AQCC | "
        "Publication: 2026-06-10 | Hearing: 2026-08-01 | "
        "Effective: 2026-09-15 | eDocket: 2026-00421 | "
        "Summary: Proposed air quality emission reporting rulemaking."
    )

    records = extract_register_notices(text, REGISTER_URL)

    assert len(records) == 1
    assert records[0].id == "RM-2026-2026-00421"
    assert records[0].ccr_rule_affected == "5_CCR_1001-9"
    assert records[0].edocket_tracking_number == "2026-00421"
    assert "air_quality" in records[0].subject_tags
    assert "rulemaking" in records[0].subject_tags


def test_extract_register_table_notice_includes_provenance() -> None:
    """Table-based Register notices carry source evidence and field confidence."""

    text = """
    <html><body>
      <h2 class="pagehead">Notice of Proposed Rulemaking</h2>
      <table>
        <tr>
          <td>Department of Public Health and Environment</td>
          <td>Air Quality Control Commission</td>
          <td>5 CCR 1001-9</td>
          <td>Emission reporting rulemaking</td>
          <td><a href="/CCR/eDocketDetails.do?trackingNum=2026-00421">eDocket</a></td>
          <td>08/01/2026</td>
        </tr>
      </table>
    </body></html>
    """

    records = extract_register_notices(text, REGISTER_URL, publication_date="2026-06-10")

    assert len(records) == 1
    assert records[0].extraction_method == "register_table_row"
    assert records[0].source_section_heading == "Notice of Proposed Rulemaking"
    assert records[0].source_row_number == 1
    assert records[0].notice_type_source == "register_section_heading"
    assert records[0].field_confidence["ccr_rule_affected"] == 0.95


def test_write_rulemaking_dataset_is_idempotent(project_root: Path) -> None:
    """Register archive normalization writes stable outputs without duplicates."""

    raw_dir = project_root / "_RAW_ARCHIVE" / "register"
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_file = raw_dir / "register_2026-06-10.html"
    source_file.write_text(
        (
            "<html><body>"
            "NOTICE: adopted | CCR: 5 CCR 1001-9 | Agency: CDPHE_AQCC | "
            "Publication: 2026-06-10 | Effective: 2026-08-30 | "
            "Summary: Adopted air quality reporting rule. "
            "<a href=\"/CCR/eDocketDetails.do?trackingNum=2026-00421\">2026-00421</a>"
            "</body></html>"
        ),
        encoding="utf-8",
    )
    _write_register_manifest(raw_dir, source_file)

    first = write_rulemaking_dataset(project_root)
    second = write_rulemaking_dataset(project_root)

    dataset_rows = list(iter_jsonl(project_root / "04_Rulemaking" / "_dataset" / "rulemaking_notices.jsonl"))
    year_rows = list(iter_jsonl(project_root / "04_Rulemaking" / "2026" / "register_2026_Q2.jsonl"))
    index_rows = list(iter_jsonl(project_root / "04_Rulemaking" / "_index.jsonl"))
    crosswalk_rows = list(iter_jsonl(project_root / "_CROSSWALKS" / "rulemaking_to_regulation.jsonl"))
    summary = json.loads(
        (project_root / "04_Rulemaking" / "_dataset" / "rulemaking_summary.json").read_text(
            encoding="utf-8"
        )
    )
    quality = json.loads(
        (project_root / "04_Rulemaking" / "_quality" / "register_extraction_quality.json").read_text(
            encoding="utf-8"
        )
    )
    master_manifest = json.loads(
        (project_root / "_CONTROL_PLANE" / "MASTER_MANIFEST.json").read_text(encoding="utf-8")
    )
    rulemaking_layer = next(
        layer for layer in master_manifest["data_layers"] if layer["id"] == "04_Rulemaking"
    )

    assert first.records_total == 1
    assert second.records_total == 1
    assert len(dataset_rows) == 1
    assert len(year_rows) == 1
    assert len(index_rows) == 1
    assert len(crosswalk_rows) == 1
    assert dataset_rows[0]["id"] == "RM-2026-2026-00421"
    assert dataset_rows[0]["edocket_url"] == (
        "https://www.sos.state.co.us/CCR/eDocketDetails.do?trackingNum=2026-00421"
    )
    assert crosswalk_rows[0]["source_id"] == "RM-2026-2026-00421"
    assert crosswalk_rows[0]["target_id"] == "5_CCR_1001-9"
    assert summary["records_total"] == 1
    assert summary["edocket_references_total"] == 1
    assert quality["records_total"] == 1
    assert quality["gap_rows_total"] == 0
    assert rulemaking_layer["record_count"] == 1
    assert rulemaking_layer["status"] == "ready"


def test_write_rulemaking_dataset_reports_extraction_gaps(project_root: Path) -> None:
    """Publications with rulemaking signals but no extracted notices are quarantined."""

    raw_dir = project_root / "_RAW_ARCHIVE" / "register"
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_file = raw_dir / "register_2026-06-10.html"
    source_file.write_text(
        "<html><body>Reference list: 5 CCR 1001-9 and trackingNum=2026-00421.</body></html>",
        encoding="utf-8",
    )
    _write_register_manifest(raw_dir, source_file)

    summary = write_rulemaking_dataset(project_root)

    gaps = list(iter_jsonl(project_root / "04_Rulemaking" / "_quality" / "register_extraction_gaps.jsonl"))
    quarantine = list(
        iter_jsonl(project_root / "04_Rulemaking" / "_quality" / "register_extraction_quarantine.jsonl")
    )

    assert summary.records_total == 0
    assert summary.gap_rows_total == 1
    assert summary.quarantine_rows_total == 1
    assert gaps[0]["reason"] == "no_rulemaking_notice_extracted"
    assert quarantine[0]["reason"] == "source_contains_rulemaking_signals_but_no_notice_was_extracted"


def test_write_rulemaking_dataset_handles_missing_manifest(project_root: Path) -> None:
    """Missing raw Register manifests produce empty auditable outputs."""

    summary = write_rulemaking_dataset(project_root)

    assert summary.records_total == 0
    assert summary.source_publications_total == 0
    assert "missing manifest" in summary.warnings[0]
    assert (project_root / "04_Rulemaking" / "_dataset" / "rulemaking_notices.jsonl").exists()
    assert (project_root / "04_Rulemaking" / "_quality" / "register_extraction_quality.json").exists()


def _write_register_manifest(raw_dir: Path, source_file: Path) -> None:
    """Write one valid Register raw manifest row."""

    payload = {
        "jurisdiction": "Colorado",
        "source_type": "colorado_register_publication",
        "document_id": "2026-06-10",
        "document_name": "Colorado Register 2026-06-10",
        "publication": {
            "title": "Colorado Register 2026-06-10",
            "publication_date": "2026-06-10",
            "url": REGISTER_URL,
        },
        "source_url": REGISTER_URL,
        "source_format": "html",
        "publication_date": "2026-06-10",
        "archive_path": source_file.as_posix(),
        "sha256": sha256_file(source_file),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "missing_metadata": [],
    }
    (raw_dir / "download_manifest.jsonl").write_text(
        json.dumps(payload, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
