"""Tests for controlled manual source intake."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from geode.pipeline.manual_source_intake import (
    MANUAL_INTAKE_LEDGER_PATH,
    MANUAL_INTAKE_MANIFEST_PATH,
    MANUAL_INTAKE_POLICY_PATH,
    archive_manual_source,
    write_manual_source_intake_policy,
)
from geode.utils.file_io import iter_jsonl


def test_manual_source_intake_archives_official_artifact(tmp_path: Path) -> None:
    """Manual intake preserves a submitted source and writes custody records."""

    source = tmp_path / "official-eo.pdf"
    source.write_bytes(b"%PDF-1.7 official executive order")

    record = archive_manual_source(
        tmp_path,
        _request(source),
        timestamp=datetime(2026, 7, 2, 20, 0, tzinfo=timezone.utc),
    )

    archive_path = tmp_path / record.archive_path
    assert archive_path.exists()
    assert archive_path.read_bytes() == source.read_bytes()
    assert record.status == "archived_pending_pipeline"
    assert record.source_format == "pdf"
    assert list(iter_jsonl(tmp_path / MANUAL_INTAKE_MANIFEST_PATH))[0]["record_id"] == "EO-2019-007"
    assert list(iter_jsonl(tmp_path / MANUAL_INTAKE_LEDGER_PATH))[0]["sha256"] == record.sha256
    assert (tmp_path / "_CONTROL_PLANE" / "MANUAL_SOURCE_INTAKE_REPORT.json").exists()


def test_manual_source_intake_dry_run_does_not_write(tmp_path: Path) -> None:
    """Dry runs validate metadata and calculate the target without archiving."""

    source = tmp_path / "official-eo.pdf"
    source.write_bytes(b"%PDF-1.7 official executive order")

    record = archive_manual_source(tmp_path, _request(source), dry_run=True)

    assert record.status == "dry_run_pending_archive"
    assert not (tmp_path / record.archive_path).exists()
    assert not (tmp_path / MANUAL_INTAKE_LEDGER_PATH).exists()


def test_manual_source_intake_rejects_duplicate_digest(tmp_path: Path) -> None:
    """The same source file cannot be archived twice for the same record by default."""

    source = tmp_path / "official-eo.pdf"
    source.write_bytes(b"%PDF-1.7 official executive order")
    archive_manual_source(tmp_path, _request(source))

    with pytest.raises(ValueError, match="already archived"):
        archive_manual_source(tmp_path, _request(source))


def test_manual_source_intake_updates_blocked_queue(tmp_path: Path) -> None:
    """Matching blocked downloads are annotated but not marked fully resolved."""

    source = tmp_path / "official-eo.pdf"
    source.write_bytes(b"%PDF-1.7 official executive order")
    control = tmp_path / "_CONTROL_PLANE"
    control.mkdir()
    (control / "BLOCKED_DOWNLOAD_QUEUE.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "record_id": "EO-2019-007",
                        "status": "queued",
                        "block_reason": "official download blocked",
                        "next_action": "Request official copy.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    record = archive_manual_source(tmp_path, _request(source))
    queue = json.loads((control / "BLOCKED_DOWNLOAD_QUEUE.json").read_text(encoding="utf-8"))

    item = queue["items"][0]
    assert record.blocked_queue_match
    assert item["status"] == "manual_source_archived_pending_pipeline"
    assert item["manual_intake_archive_path"] == record.archive_path
    assert item["manual_intake_sha256"] == record.sha256


def test_manual_source_intake_rejects_unofficial_url(tmp_path: Path) -> None:
    """Manual intake still requires approved source hosts when a URL is provided."""

    source = tmp_path / "official-eo.pdf"
    source.write_bytes(b"%PDF-1.7 official executive order")
    payload = _request(source)
    payload["official_source_url"] = "https://example.com/not-official.pdf"

    with pytest.raises(ValueError, match="unauthorized source host"):
        archive_manual_source(tmp_path, payload, dry_run=True)


def test_manual_source_intake_policy_writer(tmp_path: Path) -> None:
    """The policy artifact documents boundaries and required metadata."""

    policy = write_manual_source_intake_policy(tmp_path)

    assert "Overwriting an existing raw archive artifact." in policy["not_allowed"]
    assert (tmp_path / MANUAL_INTAKE_POLICY_PATH).exists()


def _request(source: Path) -> dict[str, object]:
    """Return a valid manual intake request."""

    return {
        "record_id": "EO-2019-007",
        "layer_id": "05_Executive_Orders",
        "source_file": source.as_posix(),
        "official_source_name": "Colorado Governor's Office",
        "official_source_url": "https://www.colorado.gov/governor/2019-executive-orders",
        "acquisition_method": "state_archives_request",
        "received_from": "Colorado State Archives",
        "reviewer_name": "Source reviewer",
        "reviewer_email": "source.reviewer@example.com",
        "custody_note": "Received as an official replacement source artifact for EO-2019-007.",
    }
