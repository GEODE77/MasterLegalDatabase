"""Tests for bulk CRS ingestion and CRS crosswalk generation."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from geode.connectors.crs_bulk import (
    parse_crs_subject_index,
    run_crs_bulk_pipeline,
    stage_crs_archive,
)
from geode.connectors.crs_crosswalk import rebuild_statute_to_regulation_crosswalk
from geode.utils.file_io import iter_jsonl, load_json


def test_crs_bulk_pipeline_writes_archived_titles(project_root: Path, crs_fixture_path: Path) -> None:
    """Bulk CRS ingestion processes files under the raw CRS archive."""

    archive_input = project_root / "_RAW_ARCHIVE" / "crs" / "crs_title_25_fixture.txt"
    shutil.copyfile(crs_fixture_path, archive_input)

    summary = run_crs_bulk_pipeline(project_root)

    assert summary.discovered_files == 1
    assert summary.parsed_titles == 1
    assert summary.sections_written == 2
    assert summary.failed_files == 0
    assert (project_root / "01_Statutes_CRS" / "crs_title_25.md").exists()
    assert (project_root / "01_Statutes_CRS" / "_meta" / "crs_bulk_summary.json").exists()
    index_rows = list(iter_jsonl(project_root / "01_Statutes_CRS" / "_index.jsonl"))
    assert [row["id"] for row in index_rows] == ["CRS-25-7-109", "CRS-25-7-114"]
    manifest = load_json(project_root / "_CONTROL_PLANE" / "MASTER_MANIFEST.json")
    crs_layer = next(
        layer for layer in manifest["data_layers"] if layer["id"] == "01_Statutes_CRS"
    )
    assert crs_layer["status"] == "ready"


def test_crs_bulk_pipeline_reports_missing_inputs(project_root: Path) -> None:
    """A bulk CRS run with no source package is conclusive and non-destructive."""

    summary = run_crs_bulk_pipeline(project_root)

    assert summary.discovered_files == 0
    assert summary.parsed_titles == 0
    assert summary.sections_written == 0
    assert summary.failed_files == 0


def test_stage_crs_archive_extracts_safe_zip(project_root: Path, tmp_path: Path) -> None:
    """Official CRS zips are copied and safely extracted under the raw archive."""

    zip_path = tmp_path / "CRSDATA20251001.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("TITLES/title25.txt", "source")
        archive.writestr("INDEX/index.txt", "index")

    summary = stage_crs_archive(project_root, zip_path)

    assert summary.extracted_files == 2
    assert (
        project_root / "_RAW_ARCHIVE" / "crs" / "2025-10-01" / "CRSDATA20251001.zip"
    ).exists()
    assert (
        project_root
        / "_RAW_ARCHIVE"
        / "crs"
        / "2025-10-01"
        / "extracted"
        / "TITLES"
        / "title25.txt"
    ).exists()


def test_stage_crs_archive_rejects_unsafe_zip(project_root: Path, tmp_path: Path) -> None:
    """Zip members cannot escape the raw archive extraction directory."""

    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../escape.txt", "bad")

    with pytest.raises(ValueError, match="unsafe CRS zip member path"):
        stage_crs_archive(project_root, zip_path)


def test_stage_crs_archive_refuses_existing_destination(
    project_root: Path,
    tmp_path: Path,
) -> None:
    """Raw archive staging never overwrites an existing dated package."""

    zip_path = tmp_path / "CRSDATA20251001.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("README.txt", "source")
    stage_crs_archive(project_root, zip_path)

    with pytest.raises(FileExistsError):
        stage_crs_archive(project_root, zip_path)


def test_parse_crs_subject_index(project_root: Path) -> None:
    """The official CRS subject index is written as an auxiliary sidecar."""

    index_path = (
        project_root
        / "_RAW_ARCHIVE"
        / "crs"
        / "2025-10-01"
        / "extracted"
        / "INDEX"
        / "index.txt"
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        """
<L1>ABANDONMENT
   <L2>Animals.
      <L3>Cruelty to animals, &sect;&sect;18-9-202, 35-42-109.
      <L3>See PROPERTY.
""",
        encoding="utf-8",
    )

    summary = parse_crs_subject_index(project_root, index_path)

    rows = list(iter_jsonl(project_root / "01_Statutes_CRS" / "_meta" / "crs_subject_index.jsonl"))
    assert summary.records_written == 4
    assert rows[2]["heading_path"] == ["ABANDONMENT", "Animals", "Cruelty to animals"]
    assert rows[2]["cited_sections"] == ["CRS-18-9-202", "CRS-35-42-109"]
    assert rows[3]["see_also"] == "PROPERTY"


def test_rebuild_statute_to_regulation_crosswalk(project_root: Path) -> None:
    """The inverse CRS crosswalk is derived from regulation-to-statute rows."""

    crosswalk_dir = project_root / "_CROSSWALKS"
    source_path = crosswalk_dir / "regulation_to_statute.jsonl"
    rows = [
        {
            "entity_type": "crosswalk_entry",
            "source_id": "5_CCR_1001-9",
            "source_type": "regulation_rule",
            "target_id": "CRS-25-7-109",
            "target_ids": [],
            "target_type": "statute_section",
            "relationship": "cites",
            "confidence": 0.75,
            "source_evidence": "Authority: 25-7-109, C.R.S.",
            "data_retrieved": "2026-06-23",
        },
        {
            "entity_type": "crosswalk_entry",
            "source_id": "5_CCR_1001-9",
            "source_type": "regulation_rule",
            "target_id": "CRS-00-10-23",
            "target_ids": [],
            "target_type": "statute_section",
            "relationship": "cites",
            "confidence": 0.75,
            "source_evidence": "False positive from a tracking number.",
            "data_retrieved": "2026-06-23",
        },
        {
            "entity_type": "crosswalk_entry",
            "source_id": "8_CCR_1203-9",
            "source_type": "regulation_rule",
            "target_id": "CRS-1-30-11",
            "target_ids": [],
            "target_type": "statute_section",
            "relationship": "cites",
            "confidence": 0.75,
            "source_evidence": "Adopted 12-16-10 - Effective 1-30-11. Statutory Authority.",
            "data_retrieved": "2026-06-23",
        },
    ]
    source_path.write_text(
        "\n".join(
            json.dumps(row, separators=(",", ":"))
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )

    summary = rebuild_statute_to_regulation_crosswalk(project_root)

    rows = list(iter_jsonl(crosswalk_dir / "statute_to_regulation.jsonl"))
    assert summary.input_rows == 3
    assert summary.output_rows == 1
    assert summary.skipped_rows == 2
    assert rows[0]["source_id"] == "CRS-25-7-109"
    assert rows[0]["target_id"] == "5_CCR_1001-9"
    assert rows[0]["relationship"] == "implements"


def test_rebuild_statute_to_regulation_crosswalk_skips_invalid_crs_ids(
    project_root: Path,
) -> None:
    """False positive CRS-looking strings are not promoted into inverse rows."""

    crosswalk_dir = project_root / "_CROSSWALKS"
    source_path = crosswalk_dir / "regulation_to_statute.jsonl"
    source_path.write_text(
        json.dumps(
            {
                "entity_type": "crosswalk_entry",
                "source_id": "5_CCR_1001-9",
                "source_type": "regulation_rule",
                "target_id": "CRS-303-205-5600",
                "target_ids": [],
                "target_type": "statute_section",
                "relationship": "cites",
                "confidence": 0.75,
                "source_evidence": "Telephone number false positive.",
                "data_retrieved": "2026-06-23",
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    summary = rebuild_statute_to_regulation_crosswalk(project_root)

    rows = list(iter_jsonl(crosswalk_dir / "statute_to_regulation.jsonl"))
    assert summary.input_rows == 1
    assert summary.output_rows == 0
    assert summary.skipped_rows == 1
    assert rows == []
