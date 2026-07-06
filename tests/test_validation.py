"""Validation and integrity tests."""

from __future__ import annotations

import shutil
from pathlib import Path

from geode.schemas import CrosswalkEntry, TimelineEvent
from geode.pipeline.run import run_crs_pipeline
from geode.utils.file_io import atomic_write_jsonl
from geode.validation.checks import run_all_checks, validate_project
from geode.validation.integrity import run_integrity_checks


def test_validation_passes_after_fixture_ingestion(
    project_root: Path,
    crs_fixture_path: Path,
) -> None:
    """Validation succeeds after CRS fixture ingestion."""

    archive_input = project_root / "_RAW_ARCHIVE" / "crs" / "crs_title_25_fixture.txt"
    shutil.copyfile(crs_fixture_path, archive_input)
    run_crs_pipeline(project_root, archive_input, "25", 2025)

    result = validate_project(project_root, "01_Statutes_CRS")
    assert result.valid, result.issues


def test_integrity_checks_pass_after_fixture_ingestion(
    project_root: Path,
    crs_fixture_path: Path,
) -> None:
    """Integrity checks agree that index and metadata IDs match."""

    archive_input = project_root / "_RAW_ARCHIVE" / "crs" / "crs_title_25_fixture.txt"
    shutil.copyfile(crs_fixture_path, archive_input)
    run_crs_pipeline(project_root, archive_input, "25", 2025)

    result = run_integrity_checks(project_root)
    assert result.valid, result.issues


def test_crosswalk_and_timeline_validation_accepts_design_records(project_root: Path) -> None:
    """Validation covers crosswalk and timeline JSONL records."""

    crosswalk = CrosswalkEntry(
        source_id="5_CCR_1001-9",
        source_type="regulation_rule",
        target_id="CRS-25-7-109",
        target_type="statute_section",
        relationship="authorized_by",
        confidence=0.95,
        source_evidence="Promulgated pursuant to section 25-7-109, C.R.S.",
        data_retrieved="2026-06-12",
    )
    timeline = TimelineEvent(
        id="TE-2023-07-01-001",
        date="2023-07-01",
        event_type="bill_signed",
        entity_id="SB23-016",
        entity_type="bill",
        description="SB23-016 signed.",
        affects=["CRS-25-7-109"],
        layer="03_Legislation",
        file_path="03_Legislation/_index.jsonl",
    )
    atomic_write_jsonl(
        project_root / "_CROSSWALKS" / "regulation_to_statute.jsonl",
        [crosswalk],
        project_root,
    )
    atomic_write_jsonl(
        project_root / "_CONTROL_PLANE" / "MASTER_TIMELINE_INDEX.jsonl",
        [timeline],
        project_root,
    )

    result = validate_project(project_root, "all")
    assert result.valid, result.issues


def test_crosswalk_validation_accepts_agency_and_amendment_history_shapes() -> None:
    """Crosswalk validation accepts current relationship-engine row shapes."""

    agency_crosswalk = CrosswalkEntry(
        source_id="AGENCY-DEPARTMENT_OF_AGRICULTURE_ANIMAL_HEALTH_DIVISION",
        source_type="agency",
        target_id="CRS-35-50-105",
        target_type="statute_section",
        relationship="has_rule_citing_statute",
        confidence=0.68,
        source_evidence="Animal Health Division is tied to 8_CCR_1201-1.",
        data_retrieved="2026-07-01",
        agency_name="Animal Health Division",
        department_name="Department of Agriculture",
        supporting_regulation_id="8_CCR_1201-1",
    )
    amendment = CrosswalkEntry.model_validate(
        {
            "entity_type": "amendment_history_entry",
            "statute_id": "CRS-18-1-901",
            "event_id": "AH-CRS_18_1_901-SB23_034",
            "event_type": "amends",
            "event_date": "2023-06-02",
            "bill_id": "SB23-034",
            "bill_title": "Definition Of Serious Bodily Injury",
            "bill_status": "in_committee",
            "source_url": "https://legiscan.com/CO/bill/SB034/2023",
            "source_evidence": "Definition Of Serious Bodily Injury",
            "confidence": 0.9,
            "data_retrieved": "2026-07-01",
        }
    )

    assert agency_crosswalk.relationship == "has_rule_citing_statute"
    assert amendment.source_id == "SB23-034"
    assert amendment.target_id == "CRS-18-1-901"
    assert amendment.relationship == "amends"


def test_regulation_rule_future_effective_date_passes_prewrite_checks(
    project_root: Path,
) -> None:
    """Writer validation permits explicitly future-effective CCR rules."""

    result = run_all_checks(
        {
            "entity_type": "regulation_rule",
            "id": "1_CCR_212-3",
            "ccr_number": "1 CCR 212-3",
            "title": "Future effective regulation",
            "department": "Department of Personnel and Administration",
            "department_code": "5",
            "agency": "Division of Human Resources",
            "agency_code": "CDPHE_DEPT",
            "enabling_statutes": [],
            "effective_date": "2026-12-31",
            "status": "active",
            "full_text": "Effective December 31, 2026.",
            "chunk_level_3_summary": "Future effective CCR rule.",
            "subject_tags": [],
            "industry_tags": [],
            "compliance_keywords": [],
            "source_url": "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo",
            "source_format": "pdf",
            "extraction_method": "fixture",
            "confidence": {"overall": 0.9},
        },
        project_root,
        allow_existing=True,
    )

    assert result.valid, result.issues
