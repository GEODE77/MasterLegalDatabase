"""Tests for guarded LegiScan repair intake."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from geode.pipeline.legiscan_repair_intake import repair_modern_legiscan_item
from geode.pipeline.modern_legiscan_repair_queue import write_modern_legiscan_repair_queue
from geode.utils.file_io import iter_jsonl, load_json


def test_repair_intake_archives_file_and_removes_item_from_queue(tmp_path: Path) -> None:
    """A verified source file should repair one open modern queue item."""

    _write_bill_documents(
        tmp_path,
        [_row("HB23-1002_texts_3", "HB23-1002", "2023", "failed_permanent")],
    )
    queue = write_modern_legiscan_repair_queue(tmp_path)
    source = tmp_path / "verified.pdf"
    source.write_bytes(b"%PDF-1.7 verified official source")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    record = repair_modern_legiscan_item(
        tmp_path,
        {
            "queue_id": queue.items[0].queue_id,
            "source_file": source.as_posix(),
            "official_source_url": "https://leg.colorado.gov/verified/HB23-1002.pdf",
            "reviewer_name": "Reviewer One",
            "custody_note": "Verified against the official Colorado General Assembly source page.",
            "expected_sha256": digest,
        },
        timestamp=datetime(2026, 7, 6, tzinfo=timezone.utc),
    )

    repaired_rows = list(iter_jsonl(tmp_path / "03_Legislation" / "_documents" / "bill_documents.jsonl"))
    refreshed_queue = load_json(tmp_path / "_CONTROL_PLANE" / "MODERN_LEGISCAN_REPAIR_QUEUE.json")
    summary = load_json(tmp_path / "03_Legislation" / "_documents" / "bill_document_summary.json")

    assert record.dataset_status_after == "downloaded"
    assert record.remaining_modern_queue_items == 0
    assert (tmp_path / record.archive_path).read_bytes() == source.read_bytes()
    assert repaired_rows[0]["status"] == "downloaded"
    assert repaired_rows[0]["sha256"] == digest
    assert repaired_rows[0]["error"] is None
    assert summary["downloaded"] == 1
    assert summary["failed_permanent"] == 0
    assert refreshed_queue["item_count"] == 0
    assert (tmp_path / "_CONTROL_PLANE" / "LEGISCAN_REPAIR_INTAKE_LEDGER.jsonl").exists()


def test_repair_intake_rejects_non_queue_item(tmp_path: Path) -> None:
    """The intake command should only repair currently open queue items."""

    _write_bill_documents(
        tmp_path,
        [_row("HB23-1002_texts_3", "HB23-1002", "2023", "downloaded")],
    )
    write_modern_legiscan_repair_queue(tmp_path)
    source = tmp_path / "verified.pdf"
    source.write_bytes(b"%PDF-1.7 verified official source")

    with pytest.raises(ValueError, match="not open"):
        repair_modern_legiscan_item(
            tmp_path,
            {
                "queue_id": "LEGISCAN-MODERN-HB23-1002_texts_3",
                "source_file": source.as_posix(),
                "official_source_url": "https://leg.colorado.gov/verified/HB23-1002.pdf",
                "reviewer_name": "Reviewer One",
                "custody_note": "Verified against the official Colorado General Assembly source page.",
            },
        )


def test_repair_intake_rejects_existing_archive_without_override(tmp_path: Path) -> None:
    """The repair command should not overwrite an existing raw archive file."""

    row = _row("HB23-1002_texts_3", "HB23-1002", "2023", "failed_permanent")
    _write_bill_documents(tmp_path, [row])
    queue = write_modern_legiscan_repair_queue(tmp_path)
    existing = tmp_path / str(row["archive_path"])
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"existing raw source")
    source = tmp_path / "verified.pdf"
    source.write_bytes(b"%PDF-1.7 verified official source")

    with pytest.raises(ValueError, match="will not be overwritten"):
        repair_modern_legiscan_item(
            tmp_path,
            {
                "queue_id": queue.items[0].queue_id,
                "source_file": source.as_posix(),
                "official_source_url": "https://leg.colorado.gov/verified/HB23-1002.pdf",
                "reviewer_name": "Reviewer One",
                "custody_note": "Verified against the official Colorado General Assembly source page.",
            },
        )


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
