"""Tests for LegiScan bill document attachment downloads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from geode.connectors.legiscan_documents import (
    discover_document_items,
    run_legiscan_document_safe_bulk,
    run_legiscan_document_pipeline,
    write_document_dataset,
)
from geode.net.http_client import GeodeHttpError
from geode.utils.file_io import iter_jsonl


def test_discover_document_items_from_archived_bill(
    project_root: Path,
    legiscan_fixture_path: Path,
) -> None:
    """Archived LegiScan records produce deterministic document work items."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/example.pdf",
            "text_size": 123,
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    items = discover_document_items(project_root)

    assert len(items) == 1
    assert items[0].document_id == "SB23-016_texts_111"
    assert items[0].bill_id == "SB23-016"
    assert items[0].category == "texts"
    assert items[0].preferred_url == "https://leg.colorado.gov/example.pdf"


def test_write_document_dataset_reports_pending(
    project_root: Path,
    legiscan_fixture_path: Path,
) -> None:
    """Document dataset writer records discovered-but-not-downloaded items."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/example.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")
    items = discover_document_items(project_root)

    summary = write_document_dataset(project_root, items, discovery_only=True)
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.discovered_total == 1
    assert summary.pending == 1
    assert rows[0]["status"] == "discovered"


def test_document_pipeline_downloads_with_injected_http(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """Document pipeline downloads one file when the HTTP client is mocked."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/example.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}
        content = b"%PDF-1.4\nexample\n"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_pipeline(project_root, max_documents=1, delay=0)

    assert summary.downloaded == 1
    assert summary.run_downloaded == 1
    assert summary.pending == 0
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))
    assert rows[0]["status"] == "downloaded"
    assert Path(rows[0]["archive_path"]).exists()


def test_document_pipeline_reports_resume_skips(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """A second run reports completed files as skipped instead of redownloading."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/example.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}
        content = b"%PDF-1.4\nexample\n"

    class FakeClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs) -> FakeResponse:
            self.__class__.calls += 1
            return FakeResponse()

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    first = run_legiscan_document_pipeline(project_root, max_documents=1, delay=0)
    raw_bill.unlink()
    second = run_legiscan_document_pipeline(project_root, max_documents=1, delay=0)

    assert first.run_downloaded == 1
    assert second.run_downloaded == 0
    assert second.run_skipped_existing == 1
    assert second.downloaded == 1
    assert FakeClient.calls == 1


def test_document_pipeline_stops_on_rate_limit(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """A 429 is tracked as pending retry and stops the run."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/example-1.pdf",
        },
        {
            "doc_id": 222,
            "type": "Engrossed",
            "date": "2023-01-02",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/222",
            "state_link": "https://leg.colorado.gov/example-2.pdf",
        },
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs):
            self.__class__.calls += 1
            raise GeodeHttpError(
                "rate limited",
                url="https://leg.colorado.gov/example-1.pdf",
                status_code=429,
            )

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_pipeline(project_root, max_documents=2, delay=0)
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.run_attempted == 1
    assert summary.run_downloaded == 0
    assert summary.run_pending_retry == 1
    assert summary.pending_retry == 1
    assert summary.failed == 0
    assert [row["status"] for row in rows] == ["pending_retry", "discovered"]
    assert FakeClient.calls == 1


def test_document_pipeline_marks_404_permanent(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """A 404 is tracked as a permanent source gap, not a retryable failure."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/missing.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs):
            raise GeodeHttpError(
                "missing",
                url="https://leg.colorado.gov/missing.pdf",
                status_code=404,
            )

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_pipeline(project_root, max_documents=1, delay=0)
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.run_failed == 0
    assert summary.run_failed_permanent == 1
    assert summary.failed == 0
    assert summary.failed_permanent == 1
    assert rows[0]["status"] == "failed_permanent"


def test_document_pipeline_marks_500_pending_retry(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """A transient 500 is tracked as retryable, not as a hard pipeline failure."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/transient.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs):
            raise GeodeHttpError(
                "server error",
                url="https://leg.colorado.gov/transient.pdf",
                status_code=500,
            )

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_pipeline(project_root, max_documents=1, delay=0)
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.run_failed == 0
    assert summary.run_pending_retry == 1
    assert summary.failed == 0
    assert summary.pending_retry == 1
    assert rows[0]["status"] == "pending_retry"


def test_document_pipeline_marks_legacy_403_permanent(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """A legacy Colorado archive document URL is tracked as permanent."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    legacy_url = "http://www.leg.state.co.us/clics/example/$FILE/example.pdf"
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": legacy_url,
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs):
            self.__class__.calls += 1
            raise GeodeHttpError("blocked", url=legacy_url, status_code=403)

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_pipeline(project_root, max_documents=1, delay=0)
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.run_failed == 0
    assert summary.run_failed_permanent == 1
    assert rows[0]["status"] == "failed_permanent"
    assert FakeClient.calls == 0


def test_document_pipeline_marks_legacy_html_wrapper_permanent(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """A legacy archive HTML wrapper URL is not requested as a PDF download."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    legacy_url = "http://www.leg.state.co.us/clics/example/$FILE/example.pdf"
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": legacy_url,
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=UTF-8"}
        content = b"<title>Colorado Legislative - Archived Content</title>"

    class FakeClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs) -> FakeResponse:
            self.__class__.calls += 1
            return FakeResponse()

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_pipeline(project_root, max_documents=1, delay=0)
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.run_downloaded == 0
    assert summary.run_failed == 0
    assert summary.run_failed_permanent == 1
    assert rows[0]["status"] == "failed_permanent"
    assert "plain HTTP" in rows[0]["error"]
    assert not Path(rows[0]["archive_path"]).exists()
    assert FakeClient.calls == 0


def test_document_pipeline_marks_unexpected_html_wrapper_permanent(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """An HTML archive wrapper response is not accepted as a PDF download."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/example.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=UTF-8"}
        content = b"<title>Colorado Legislative - Archived Content</title>"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_pipeline(project_root, max_documents=1, delay=0)
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.run_downloaded == 0
    assert summary.run_failed == 0
    assert summary.run_failed_permanent == 1
    assert rows[0]["status"] == "failed_permanent"
    assert "HTML wrapper" in rows[0]["error"]
    assert not Path(rows[0]["archive_path"]).exists()


def test_document_dataset_reclassifies_stale_legacy_html_download(
    project_root: Path,
    legiscan_fixture_path: Path,
) -> None:
    """Existing manifest rows for legacy HTML wrappers are reconciled as permanent gaps."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    legacy_url = "http://www.leg.state.co.us/clics/example/$FILE/example.pdf"
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": legacy_url,
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")
    items = discover_document_items(project_root)
    archive_path = Path(items[0].archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archived_html = b"<html><title>Colorado Legislative - Archived Content</title></html>"
    archive_path.write_bytes(archived_html)
    manifest_path = project_root / "_RAW_ARCHIVE" / "legiscan_documents" / "download_manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "document_id": items[0].document_id,
                "bill_id": items[0].bill_id,
                "category": items[0].category,
                "preferred_url": items[0].preferred_url,
                "archive_path": items[0].archive_path,
                "status": "downloaded",
                "status_code": 200,
                "content_type": "text/html",
                "size_bytes": len(archived_html),
                "sha256": hashlib.sha256(archived_html).hexdigest(),
                "downloaded_at": "2026-06-22T00:00:00Z",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = write_document_dataset(project_root, items)
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.downloaded == 0
    assert summary.failed_permanent == 1
    assert rows[0]["status"] == "failed_permanent"
    assert "HTML wrapper" in rows[0]["error"]


def test_category_download_keeps_full_dataset(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """Downloading one category still writes a full document dataset."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/text.pdf",
        }
    ]
    payload["bill"]["amendments"] = [
        {
            "amendment_id": 222,
            "type": "Amendment",
            "date": "2023-01-02",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/amendment/SB16/id/222",
            "state_link": "https://leg.colorado.gov/amendment.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}
        content = b"%PDF-1.4\nexample\n"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_pipeline(
        project_root,
        max_documents=1,
        category="texts",
        delay=0,
    )
    rows = list(iter_jsonl(project_root / "03_Legislation" / "_documents" / "bill_documents.jsonl"))

    assert summary.records_total == 2
    assert {row["category"] for row in rows} == {"texts", "amendments"}
    assert {row["status"] for row in rows} == {"downloaded", "discovered"}


def test_safe_bulk_writes_batch_report(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """Safe bulk mode downloads in phases and writes batch reports."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/text.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}
        content = b"%PDF-1.4\nexample\n"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_safe_bulk(
        project_root,
        batch_size=1,
        delay=0,
        phase_order=["texts"],
    )

    batches = project_root / "03_Legislation" / "_documents" / "safe_bulk_batches.jsonl"
    assert summary.status == "completed"
    assert summary.run_downloaded == 1
    assert summary.final_downloaded == 1
    assert batches.exists()
    assert len(list(iter_jsonl(batches))) == 1


def test_safe_bulk_can_stop_after_max_batches(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """Safe bulk supports a bounded validation run without changing default behavior."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/text-1.pdf",
        },
        {
            "doc_id": 222,
            "type": "Engrossed",
            "date": "2023-01-02",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/222",
            "state_link": "https://leg.colorado.gov/text-2.pdf",
        },
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}
        content = b"%PDF-1.4\nexample\n"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_safe_bulk(
        project_root,
        batch_size=1,
        delay=0,
        max_batches=1,
        phase_order=["texts"],
    )

    assert summary.status == "paused"
    assert summary.stopped_reason == "max batches reached"
    assert summary.batches_attempted == 1
    assert summary.run_downloaded == 1
    assert summary.final_downloaded == 1
    assert summary.final_pending == 1


def test_safe_bulk_cools_down_after_rate_limit(
    project_root: Path,
    legiscan_fixture_path: Path,
    monkeypatch,
) -> None:
    """Safe bulk can pause after a 429 and retry the same item."""

    raw_bill = project_root / "_RAW_ARCHIVE" / "legiscan" / "2023" / "12345.json"
    raw_bill.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(legiscan_fixture_path.read_text(encoding="utf-8"))
    payload["bill"]["texts"] = [
        {
            "doc_id": 111,
            "type": "Introduced",
            "date": "2023-01-01",
            "mime": "application/pdf",
            "url": "https://legiscan.com/CO/text/SB16/id/111",
            "state_link": "https://leg.colorado.gov/text.pdf",
        }
    ]
    raw_bill.write_text(json.dumps(payload), encoding="utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}
        content = b"%PDF-1.4\nexample\n"

    class FakeClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs):
            self.__class__.calls += 1
            if self.__class__.calls == 1:
                raise GeodeHttpError(
                    "rate limited",
                    url="https://leg.colorado.gov/text.pdf",
                    status_code=429,
                )
            return FakeResponse()

    monkeypatch.setattr("geode.connectors.legiscan_documents.GeodeHttpClient", FakeClient)

    summary = run_legiscan_document_safe_bulk(
        project_root,
        batch_size=1,
        delay=0,
        cooldown_seconds=0,
        max_rate_limit_pauses=1,
        phase_order=["texts"],
    )

    assert summary.status == "completed"
    assert summary.rate_limit_pauses == 1
    assert summary.run_pending_retry == 1
    assert summary.run_downloaded == 1
    assert summary.final_downloaded == 1
