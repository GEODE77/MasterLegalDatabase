"""Tests for the LegiScan repair progress dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from geode.pipeline.legiscan_repair_intake import repair_modern_legiscan_item
from geode.pipeline.legiscan_repair_progress_dashboard import (
    build_legiscan_repair_progress_dashboard,
    write_legiscan_repair_progress_dashboard,
)
from geode.pipeline.modern_legiscan_repair_queue import write_modern_legiscan_repair_queue
from geode.utils.file_io import load_json


def test_repair_progress_dashboard_tracks_open_items_without_ledger(tmp_path: Path) -> None:
    """The dashboard should show open items even before any repair intake exists."""

    _write_bill_documents(
        tmp_path,
        [
            _row("HB23-1002_texts_3", "HB23-1002", "2023", "failed_permanent"),
            _row("HB23-1003_texts_4", "HB23-1003", "2023", "failed_permanent"),
        ],
    )

    dashboard = build_legiscan_repair_progress_dashboard(tmp_path)

    assert dashboard.original_scope_items == 2
    assert dashboard.repaired_count == 0
    assert dashboard.open_count == 2
    assert dashboard.percent_repaired == 0.0
    assert dashboard.reviewers == {}
    assert all(item.needed_action == "needs verified official replacement file" for item in dashboard.open_items)


def test_repair_progress_dashboard_tracks_reviewer_after_intake(tmp_path: Path) -> None:
    """The dashboard should include reviewer progress after one item is repaired."""

    _write_bill_documents(
        tmp_path,
        [
            _row("HB23-1002_texts_3", "HB23-1002", "2023", "failed_permanent"),
            _row("HB23-1003_texts_4", "HB23-1003", "2023", "failed_permanent"),
        ],
    )
    queue = write_modern_legiscan_repair_queue(tmp_path)
    source = tmp_path / "verified.pdf"
    source.write_bytes(b"%PDF-1.7 verified official source")

    repair_modern_legiscan_item(
        tmp_path,
        {
            "queue_id": queue.items[0].queue_id,
            "source_file": source.as_posix(),
            "official_source_url": "https://leg.colorado.gov/verified/HB23-1002.pdf",
            "reviewer_name": "Reviewer One",
            "custody_note": "Verified against the official Colorado General Assembly source page.",
        },
        timestamp=datetime(2026, 7, 6, tzinfo=timezone.utc),
    )
    dashboard = write_legiscan_repair_progress_dashboard(tmp_path)
    payload = load_json(tmp_path / "_CONTROL_PLANE" / "LEGISCAN_REPAIR_PROGRESS_DASHBOARD.json")

    assert dashboard.original_scope_items == 2
    assert dashboard.repaired_count == 1
    assert dashboard.open_count == 1
    assert dashboard.percent_repaired == 50.0
    assert dashboard.reviewers == {"Reviewer One": 1}
    assert dashboard.repaired_items[0].reviewer_name == "Reviewer One"
    assert payload["repaired_count"] == 1
    assert (
        tmp_path / "docs" / "audits" / "LEGISCAN_REPAIR_PROGRESS_DASHBOARD_2026-07-06.md"
    ).exists()


def _write_bill_documents(root: Path, rows: list[dict[str, object]]) -> None:
    documents_dir = root / "03_Legislation" / "_documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    (documents_dir / "bill_documents.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _row(document_id: str, bill_id: str, session: str, status: str) -> dict[str, object]:
    return {
        "document_id": document_id,
        "bill_id": bill_id,
        "session": session,
        "bill_number": bill_id.split("-")[-1],
        "title": "Example Bill",
        "category": document_id.split("_")[1],
        "document_type": "Introduced",
        "document_date": f"{session}-01-01",
        "source_url": f"https://legiscan.com/CO/text/{bill_id}/id/1",
        "state_link": f"https://leg.colorado.gov/{document_id}.pdf",
        "preferred_url": f"https://leg.colorado.gov/{document_id}.pdf",
        "archive_path": f"_RAW_ARCHIVE/legiscan_documents/{session}/{document_id}.pdf",
        "status": status,
        "content_type": None,
        "size_bytes": 0,
        "sha256": None,
        "error": "GET failed with status 404 (non-retryable source/client failure)",
        "downloaded_at": "2026-07-06T00:00:00Z",
    }
