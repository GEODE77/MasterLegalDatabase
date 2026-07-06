"""Tests for the modern LegiScan repair queue."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.modern_legiscan_repair_queue import (
    build_modern_legiscan_repair_queue,
    write_modern_legiscan_repair_queue,
)


def test_modern_legiscan_queue_filters_current_permanent_failures(tmp_path: Path) -> None:
    """Only modern permanent failures should enter the focused queue."""

    _write_bill_documents(
        tmp_path,
        [
            _row("HB17-1001_texts_1", "HB17-1001", "2017", "failed_permanent"),
            _row("HB23-1001_texts_2", "HB23-1001", "2023", "downloaded"),
            _row("HB23-1002_texts_3", "HB23-1002", "2023", "failed_permanent"),
            _row("SB26-0001_supplements_4", "SB26-0001", "2026", "failed_permanent"),
        ],
    )

    queue = build_modern_legiscan_repair_queue(tmp_path)

    assert queue.item_count == 2
    assert queue.status == "active"
    assert queue.year_counts == {"2023": 1, "2026": 1}
    assert [item.bill_id for item in queue.items] == ["SB26-0001", "HB23-1002"]
    assert all(item.status == "open" for item in queue.items)


def test_write_modern_legiscan_queue_outputs_artifacts(tmp_path: Path) -> None:
    """The queue writer should create machine and human-readable artifacts."""

    _write_bill_documents(
        tmp_path,
        [_row("HB23-1002_texts_3", "HB23-1002", "2023", "failed_permanent")],
    )

    queue = write_modern_legiscan_repair_queue(tmp_path)

    assert queue.item_count == 1
    assert (tmp_path / "_CONTROL_PLANE" / "MODERN_LEGISCAN_REPAIR_QUEUE.json").exists()
    assert (
        tmp_path / "docs" / "audits" / "MODERN_LEGISCAN_REPAIR_QUEUE_2026-07-06.md"
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
