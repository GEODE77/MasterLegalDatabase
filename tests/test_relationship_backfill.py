"""Tests for relationship backfill outputs."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.relationship_backfill import build_relationship_backfill, write_relationship_backfill
from geode.utils.file_io import iter_jsonl


def test_relationship_backfill_derives_agency_and_amendment_rows(tmp_path: Path) -> None:
    """Backfill should derive rows only from existing crosswalk evidence."""

    _write_backfill_fixture(tmp_path)

    agency_rows, amendment_rows = build_relationship_backfill(tmp_path)

    assert len(agency_rows) == 1
    assert agency_rows[0].target_id == "CRS-1-1-101"
    assert agency_rows[0].supporting_regulation_id == "1_CCR_101-1"
    assert "Division of Test Rules" in agency_rows[0].source_evidence
    assert len(amendment_rows) == 1
    assert amendment_rows[0].statute_id == "CRS-1-1-101"
    assert amendment_rows[0].bill_title == "Test Bill"


def test_write_relationship_backfill_writes_crosswalk_files(tmp_path: Path) -> None:
    """Backfill writes agency, amendment, and summary files."""

    _write_backfill_fixture(tmp_path)

    summary = write_relationship_backfill(tmp_path)

    assert summary.agency_to_statute_rows == 1
    assert summary.amendment_history_rows == 1
    assert len(list(iter_jsonl(tmp_path / "_CROSSWALKS" / "agency_to_statute.jsonl"))) == 1
    assert len(list(iter_jsonl(tmp_path / "_CROSSWALKS" / "amendment_history.jsonl"))) == 1
    assert (tmp_path / "_CONTROL_PLANE" / "RELATIONSHIP_BACKFILL_SUMMARY.json").exists()


def _write_backfill_fixture(root: Path) -> None:
    """Write minimal inputs for relationship backfill tests."""

    ccr_meta = root / "02_Regulations_CCR" / "_meta"
    crosswalks = root / "_CROSSWALKS"
    bills = root / "03_Legislation" / "2026"
    ccr_meta.mkdir(parents=True)
    crosswalks.mkdir(parents=True)
    bills.mkdir(parents=True)
    (ccr_meta / "ccr_normalized_meta.jsonl").write_text(
        json.dumps(
            {
                "id": "1_CCR_101-1",
                "agency_normalized": "Division of Test Rules",
                "department_normalized": "Department of Tests",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (crosswalks / "regulation_to_statute.jsonl").write_text(
        json.dumps(
            {
                "source_id": "1_CCR_101-1",
                "target_id": "CRS-1-1-101",
                "relationship": "cites",
                "confidence": 0.75,
                "source_evidence": "Rule cites CRS 1-1-101.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (crosswalks / "bill_to_statute.jsonl").write_text(
        json.dumps(
            {
                "source_id": "HB26-1001",
                "target_id": "CRS-1-1-101",
                "relationship": "amends",
                "confidence": 0.9,
                "source_evidence": "Test bill amends CRS 1-1-101.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (bills / "bills_2026.jsonl").write_text(
        json.dumps(
            {
                "id": "HB26-1001",
                "title": "Test Bill",
                "status": "passed",
                "status_date": "2026-05-01",
                "source_url": "https://legiscan.com/CO/bill/HB1001/2026",
            }
        )
        + "\n",
        encoding="utf-8",
    )
