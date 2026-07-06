"""Tests for the LegiScan source finder checklist."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.legiscan_source_finder_checklist import (
    build_source_finder_checklist,
    write_source_finder_checklist,
)


def test_source_finder_checklist_builds_review_steps(tmp_path: Path) -> None:
    """The checklist should give each open item a repeatable source-finding workflow."""

    _write_bill_documents(
        tmp_path,
        [_row("HB23-1002_texts_3", "HB23-1002", "2023", "failed_permanent")],
    )

    checklist = build_source_finder_checklist(tmp_path)

    assert checklist.item_count == 1
    assert checklist.status == "active"
    assert checklist.open_by_year == {"2023": 1}
    assert checklist.items[0].queue_id == "LEGISCAN-MODERN-HB23-1002_texts_3"
    assert "leg.colorado.gov" in checklist.items[0].official_source_hosts
    assert any("guarded LegiScan repair intake" in step for step in checklist.items[0].confirmation_checklist)
    assert "--queue-id LEGISCAN-MODERN-HB23-1002_texts_3" in checklist.items[0].intake_command_shape


def test_write_source_finder_checklist_outputs_artifacts(tmp_path: Path) -> None:
    """The checklist writer should create machine and readable reports."""

    _write_bill_documents(
        tmp_path,
        [_row("HB23-1002_texts_3", "HB23-1002", "2023", "failed_permanent")],
    )

    checklist = write_source_finder_checklist(tmp_path)

    assert checklist.item_count == 1
    assert (tmp_path / "_CONTROL_PLANE" / "LEGISCAN_SOURCE_FINDER_CHECKLIST.json").exists()
    assert (
        tmp_path / "docs" / "audits" / "LEGISCAN_SOURCE_FINDER_CHECKLIST_2026-07-06.md"
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
