"""Tests for the LegiScan-to-legislation normalization pipeline."""

from __future__ import annotations

import shutil
from pathlib import Path

from geode.connectors.legiscan_pipeline import write_legislation_dataset
from geode.connectors.legiscan_transformer import transform_bill
from geode.utils.file_io import iter_jsonl, load_json


def test_write_legislation_dataset_from_archived_legiscan_json(
    project_root: Path,
    legiscan_fixture_path: Path,
) -> None:
    """Archived LegiScan JSON becomes legislation records, index, and crosswalks."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(legiscan_fixture_path, raw_bill)

    summary = write_legislation_dataset(project_root)

    dataset_rows = list(iter_jsonl(project_root / "03_Legislation" / "_dataset" / "bills.jsonl"))
    year_rows = list(iter_jsonl(project_root / "03_Legislation" / "2023" / "bills_2023.jsonl"))
    index_rows = list(iter_jsonl(project_root / "03_Legislation" / "_index.jsonl"))
    crosswalk_rows = list(iter_jsonl(project_root / "_CROSSWALKS" / "bill_to_statute.jsonl"))

    assert summary.raw_files_total == 1
    assert summary.records_total == 1
    assert summary.failed_files == 0
    assert summary.bill_to_statute_rows_total == 1
    assert dataset_rows[0]["id"] == "SB23-016"
    assert year_rows[0]["id"] == "SB23-016"
    assert index_rows[0]["id"] == "SB23-016"
    assert crosswalk_rows[0]["source_id"] == "SB23-016"
    assert crosswalk_rows[0]["target_id"] == "CRS-25-7-109"
    assert crosswalk_rows[0]["relationship"] == "amends"


def test_write_legislation_dataset_handles_empty_archive(project_root: Path) -> None:
    """Empty LegiScan archives produce empty but auditable outputs."""

    summary = write_legislation_dataset(project_root)

    assert summary.raw_files_total == 0
    assert summary.records_total == 0
    assert summary.failed_files == 0
    assert (project_root / "03_Legislation" / "_dataset" / "bills.jsonl").exists()
    assert (project_root / "03_Legislation" / "_dataset" / "legislation_summary.json").exists()


def test_transform_bill_uses_current_ontology_tags(project_root: Path) -> None:
    """Bill transformer emits current controlled tags and avoids invented tags."""

    ontology = load_json(project_root / "_CONTROL_PLANE" / "ONTOLOGY.json")
    raw_bill = {
        "bill": {
            "bill_id": 99,
            "number": "HB 99",
            "session": {"year_start": 2026, "year_end": 2026},
            "title": "Labor and Employment Tax Administration",
            "description": "Concerning labor employment and tax administration.",
            "body": "The bill amends 8-4-101, C.R.S.",
            "status": "Introduced",
            "status_date": "2026-01-15",
            "introduced_date": "2026-01-15",
            "url": "https://legiscan.com/CO/bill/HB99/2026",
            "subjects": ["Labor", "Employment", "Tax"],
        }
    }

    record = transform_bill(raw_bill, ontology)

    assert "labor_employment" in record["subject_tags"]
    assert "taxes" not in record["subject_tags"]
