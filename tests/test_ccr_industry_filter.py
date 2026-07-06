"""Tests for deterministic CCR industry filtering."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from geode.connectors.ccr_industry_filter import (
    CCRFilterCriteria,
    load_default_taxonomy,
    record_matches_filter,
    tag_ccr_record,
    write_ccr_industry_tags,
)
from geode.utils.file_io import iter_jsonl


def test_tag_ccr_record_uses_agency_and_citation_rules() -> None:
    """Air-quality CCR metadata receives manufacturing and environmental tags."""

    tagged = tag_ccr_record(_air_quality_row(), load_default_taxonomy())

    assert "manufacturing" in tagged.industry_tags
    assert "air_quality" in tagged.topic_tags
    assert "environmental_air" in tagged.domain_tags
    assert "general_manufacturing" in tagged.domain_tags
    assert tagged.coorstek_relevance == "high"
    assert tagged.tag_confidence_label == "high"
    assert "agency" in {match.source for match in tagged.tag_rule_sources}
    assert "agency_air_quality" in {match.rule_id for match in tagged.tag_rule_sources}


def test_write_ccr_industry_tags_outputs_full_filtered_and_summary(tmp_path: Path) -> None:
    """The filter writer emits full tagged outputs, filtered outputs, and counts."""

    dataset_dir = tmp_path / "02_Regulations_CCR" / "_dataset"
    dataset_dir.mkdir(parents=True)
    _write_jsonl(
        dataset_dir / "ccr_items.jsonl",
        [_air_quality_row(), _labor_row(), _unrelated_row()],
    )

    summary = write_ccr_industry_tags(
        tmp_path,
        criteria=CCRFilterCriteria(
            include_industries=["manufacturing"],
            include_domains=["environmental"],
            match_mode="all",
        ),
        filtered_prefix="ccr_items_manufacturing_environmental",
    )
    tagged_rows = list(iter_jsonl(Path(summary.tagged_jsonl_path)))
    filtered_rows = list(iter_jsonl(Path(summary.filtered_jsonl_path or "")))
    csv_rows = list(csv.DictReader(Path(summary.tagged_csv_path).open(encoding="utf-8")))

    assert summary.records_total == 3
    assert summary.tagged_total == 2
    assert summary.untagged_total == 1
    assert summary.filtered_total == 1
    assert summary.industry_counts["manufacturing"] == 2
    assert summary.domain_counts["environmental_air"] == 1
    assert summary.domain_counts["general_manufacturing"] == 2
    assert summary.topic_counts["labor_employment"] == 1
    assert summary.rule_match_counts["agency_air_quality"] == 1
    assert summary.rule_match_counts["agency_labor_standards"] == 1
    assert [row["record_id"] for row in filtered_rows] == ["5_CCR_1001-9"]
    assert len(tagged_rows) == 3
    assert len(csv_rows) == 3
    assert json.loads(csv_rows[0]["industry_tags"])


def test_tag_ccr_record_supports_keyword_multi_tag_and_untagged_rows() -> None:
    """Keyword rules can add multiple domains while unrelated rows stay unforced."""

    tagged = tag_ccr_record(_chemical_waste_row(), load_default_taxonomy())
    untagged = tag_ccr_record(_unrelated_row(), load_default_taxonomy())

    assert "environmental_waste" in tagged.domain_tags
    assert "chemicals_exposure" in tagged.domain_tags
    assert "general_manufacturing" in tagged.domain_tags
    assert {"keyword_waste_hazmat", "keyword_exposure_controls"}.issubset(
        {match.rule_id for match in tagged.tag_rule_sources}
    )
    assert untagged.industry_tags == []
    assert untagged.domain_tags == []
    assert untagged.tag_confidence_label == "none"
    assert untagged.tag_notes == "no deterministic CCR metadata rule matched"


def test_record_matches_filter_honors_exclusions() -> None:
    """Exclusion filters remove otherwise matching tagged CCR records."""

    tagged = tag_ccr_record(_labor_row(), load_default_taxonomy())

    assert record_matches_filter(
        tagged,
        CCRFilterCriteria(include_industries=["manufacturing"]),
    )
    assert not record_matches_filter(
        tagged,
        CCRFilterCriteria(
            include_industries=["manufacturing"],
            exclude_topics=["labor_employment"],
        ),
    )
    assert record_matches_filter(
        tagged,
        CCRFilterCriteria(
            include_industries=["manufacturing"],
            include_domains=["labor"],
            match_mode="all",
        ),
    )
    assert not record_matches_filter(
        tagged,
        CCRFilterCriteria(
            include_domains=["environmental"],
        ),
    )


def _air_quality_row() -> dict[str, object]:
    """Return one normalized CCR air-quality fixture row."""

    return {
        "record_id": "5_CCR_1001-9",
        "title": "5 CCR 1001-9",
        "rule_name": None,
        "department": "1000 Department of Public Health and Environment",
        "department_normalized": "Department of Public Health and Environment",
        "agency": "1001 Air Quality Control Commission",
        "agency_normalized": "Air Quality Control Commission",
        "division_board_program": "Air Quality Control Commission",
        "ccr_citation": "5 CCR 1001-9",
        "department_number": "5",
        "chapter": "1001",
        "rule_number": "9",
        "source_page_url": "https://www.sos.state.co.us/CCR/DisplayRule.do",
        "document_url": "https://www.sos.state.co.us/CCR/GenerateRulePdf.do",
        "file_path": None,
        "content_type": "application/pdf",
        "source_format": "pdf",
        "download_status": "resolved",
        "discovery_timestamp": "2026-06-22T10:00:00Z",
        "retrieval_timestamp": None,
        "checksum_sha256": None,
        "size_bytes": None,
        "text_extraction_status": "not_attempted",
        "raw_file_exists": False,
        "notes": None,
        "error": None,
    }


def _labor_row() -> dict[str, object]:
    """Return one normalized CCR labor fixture row."""

    row = _air_quality_row()
    row.update(
        {
            "record_id": "7_CCR_1103-1",
            "title": "Colorado Overtime and Minimum Pay Standards",
            "department": "1100 Department of Labor and Employment",
            "department_normalized": "Department of Labor and Employment",
            "agency": "1103 Division of Labor Standards and Statistics",
            "agency_normalized": "Division of Labor Standards and Statistics",
            "division_board_program": "Division of Labor Standards and Statistics",
            "ccr_citation": "7 CCR 1103-1",
            "department_number": "7",
            "chapter": "1103",
            "rule_number": "1",
        }
    )
    return row


def _unrelated_row() -> dict[str, object]:
    """Return one normalized CCR row that should not receive target tags."""

    row = _air_quality_row()
    row.update(
        {
            "record_id": "1_CCR_101-1",
            "title": "1 CCR 101-1",
            "department": "100 Department of Personnel and Administration",
            "department_normalized": "Department of Personnel and Administration",
            "agency": "101 Division of Finance and Procurement",
            "agency_normalized": "Division of Finance and Procurement",
            "division_board_program": "Division of Finance and Procurement",
            "ccr_citation": "1 CCR 101-1",
            "department_number": "1",
            "chapter": "101",
            "rule_number": "1",
        }
    )
    return row


def _chemical_waste_row() -> dict[str, object]:
    """Return one normalized CCR row with keyword-driven chemical/waste relevance."""

    row = _air_quality_row()
    row.update(
        {
            "record_id": "5_CCR_1007-3",
            "title": "Hazardous Waste Chemical Exposure And Cleanup Standards",
            "department": "1000 Department of Public Health and Environment",
            "department_normalized": "Department of Public Health and Environment",
            "agency": "1007 Hazardous Materials and Waste Management Division",
            "agency_normalized": "Hazardous Materials and Waste Management Division",
            "division_board_program": "Hazardous Materials and Waste Management Division",
            "ccr_citation": "5 CCR 1007-3",
            "department_number": "5",
            "chapter": "1007",
            "rule_number": "3",
        }
    )
    return row


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write fixture JSONL records."""

    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
