"""Validation and integrity tests."""

from __future__ import annotations

import shutil
from pathlib import Path

from geode.schemas import CrosswalkEntry, TimelineEvent
from geode.pipeline.run import run_crs_pipeline
from geode.utils.file_io import atomic_write_jsonl
from geode.validation.checks import validate_project
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
