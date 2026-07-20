"""Tests for systematic retries of failed linked county documents."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from geode.connectors import local_sources
from geode.connectors.local_sources import retry_failed_linked_sources
from geode.connectors.local_sources import _linked_documents
from geode.utils.file_io import iter_jsonl


def test_retry_failed_linked_sources_preserves_each_attempt(tmp_path: Path, monkeypatch) -> None:
    """A failed linked record gets one durable retry result and raw evidence."""

    manifest = tmp_path / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"
    manifest.parent.mkdir(parents=True)
    raw_dir = tmp_path / "_RAW_ARCHIVE" / "local" / "county" / "county_test"
    raw_dir.mkdir(parents=True)
    prior = {
        "source_id": "county_test_homepage",
        "authority_id": "CO-COUNTY-TEST",
        "authority_level": "county",
        "source_url": "https://www.colorado.gov/county/test",
        "requested_url": "https://www.colorado.gov/county/test/ordinance.pdf",
        "raw_path": (raw_dir / "FAILED").as_posix(),
        "status": "failed",
        "retrieved_at": "2026-07-20T00:00:00Z",
        "failure_class": "network_or_transport_failure",
        "message": "previous failure",
    }
    manifest.write_text(json.dumps(prior) + "\n", encoding="utf-8")

    response = SimpleNamespace(
        status_code=200,
        headers={"Content-Type": "application/pdf"},
        content=b"%PDF-1.7 official county document",
    )
    monkeypatch.setattr(local_sources, "_fetch", lambda *args, **kwargs: response)

    summary = retry_failed_linked_sources(tmp_path, max_retries=0)

    assert summary.attempted == 1
    assert summary.downloaded == 1
    rows = list(iter_jsonl(manifest))
    assert len(rows) == 2
    assert rows[-1]["status"] == "downloaded"
    assert Path(rows[-1]["raw_path"]).exists()


def test_linked_documents_normalize_double_encoded_official_paths() -> None:
    """Official links with one extra encoding layer resolve to their published path."""

    html = '<a href="/files/County%2520Code.pdf">County Code</a>'

    assert _linked_documents("https://www.colorado.gov/county", html, 5) == [
        "https://www.colorado.gov/files/County%20Code.pdf"
    ]
