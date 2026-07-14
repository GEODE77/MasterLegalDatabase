"""Remaining connector and orchestrator tests."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pytest

from geode.connectors.crs_parser import parse_crs_sgml, write_crs_sgml_title
from geode.connectors.exec_orders_scraper import (
    _invalid_executive_order_content_reason,
    download_all_executive_orders,
    discover_executive_orders,
    download_executive_order,
    extract_order_metadata,
    ingest_archived_executive_orders,
)
from geode.connectors.orchestrator import run_full_download
from geode.connectors.quality import build_bulk_download_quality_report
from geode.connectors.register_scraper import (
    download_all_publications,
    discover_publications,
    download_publication,
    extract_rulemaking_notices,
)
from geode.net.http_client import GeodeBlockedError
from geode.schemas.validators import validate_record
from geode.utils.file_io import iter_jsonl, load_json


class FakeResponse:
    """Fake HTTP response."""

    def __init__(self, text: str = "", content: bytes = b"", status_code: int = 200) -> None:
        """Create fake response."""

        self.text = text
        self.content = content or text.encode("utf-8")
        self.status_code = status_code

    def raise_for_status(self) -> None:
        """Raise on fake HTTP errors."""

        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    """URL mapping fake client."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        """Create fake client."""

        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> FakeResponse:
        """Return mapped response."""

        self.calls.append(url)
        return self.responses[url]


def test_register_scraper_processes_sample(tmp_path: Path) -> None:
    """Register connector discovers, downloads, and extracts notices."""

    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    pub_url = "https://www.sos.state.co.us/pubs/CCR/register_2024-01-10.html"
    html = f'<a href="{pub_url}">Colorado Register 2024-01-10</a>'
    notice_text = (
        "NOTICE: adopted | CCR: 5 CCR 1001-9 | Agency: CDPHE_DEPT | "
        "Publication: 2024-01-10 | Hearing: 2023-12-01 | "
        "Effective: 2024-01-15 | Summary: Amendments to air quality permits."
    )
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pub_url: FakeResponse(text=notice_text),
        }
    )
    publications = discover_publications(client=client, index_url=index_url)
    assert len(publications) == 1
    download = download_publication(publications[0], tmp_path, client=client)
    assert Path(download.archive_path).exists()
    rows = list(iter_jsonl(tmp_path / "download_manifest.jsonl"))
    assert rows[0]["jurisdiction"] == "Colorado"
    assert rows[0]["source_type"] == "colorado_register_publication"
    assert rows[0]["document_id"] == "2024-01-10"
    assert rows[0]["document_name"] == "Colorado Register 2024-01-10"
    assert rows[0]["source_url"] == pub_url
    assert rows[0]["source_format"] == "html"
    assert rows[0]["publication_date"] == "2024-01-10"
    assert rows[0]["missing_metadata"] == []
    notices = extract_rulemaking_notices(notice_text, pub_url)
    valid, errors = validate_record(notices[0])
    assert valid, errors
    assert notices[0]["hearing_date"] == "2023-12-01"


def test_register_bulk_download_resumes_from_manifest(tmp_path: Path) -> None:
    """Register bulk downloads skip already fingerprinted publications."""

    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    pub_url = "https://www.sos.state.co.us/pubs/CCR/register_2024-01-10.html"
    html = f'<a href="{pub_url}">Colorado Register 2024-01-10</a>'
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pub_url: FakeResponse(text="register body"),
        }
    )

    first = download_all_publications(tmp_path, delay=0, client=client, index_url=index_url)
    before = client.calls.count(pub_url)
    second = download_all_publications(tmp_path, delay=0, client=client, index_url=index_url)
    after = client.calls.count(pub_url)

    assert first.downloaded == 1
    assert first.failed == 0
    assert second.skipped == 1
    assert after == before
    assert len(list(iter_jsonl(tmp_path / "download_manifest.jsonl"))) == 1


def test_register_discovery_parses_register_contents_links() -> None:
    """Register discovery supports the live RegisterHome.do link shape."""

    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    href = (
        "/CCR/RegisterContents.do?publicationDay=01/10/2026&Volume=49"
        "&yearPublishNumber=1&Month=1&Year=2026"
    )
    html = f'<a href="{href}"><span>HTML</span></a>'
    client = FakeClient({index_url: FakeResponse(text=html)})

    publications = discover_publications(client=client, index_url=index_url)

    assert len(publications) == 1
    assert publications[0].publication_date == "2026-01-10"
    assert publications[0].title == "Colorado Register 2026-01-10"
    assert str(publications[0].url).startswith(
        "https://www.sos.state.co.us/CCR/RegisterContents.do"
    )


def test_register_discovery_supports_year_ranges() -> None:
    """Register discovery can traverse explicit back-issue years."""

    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    url_2025 = f"{index_url}?pyear=2025"
    url_2026 = f"{index_url}?pyear=2026"
    html_2025 = (
        '<a href="/CCR/RegisterContents.do?publicationDay=01/10/2025&Volume=48">'
        "<span>HTML</span></a>"
    )
    html_2026 = (
        '<a href="/CCR/RegisterContents.do?publicationDay=01/10/2026&Volume=49">'
        "<span>HTML</span></a>"
    )
    client = FakeClient(
        {
            url_2025: FakeResponse(text=html_2025),
            url_2026: FakeResponse(text=html_2026),
        }
    )

    publications = discover_publications(client=client, index_url=index_url, years=[2025, 2026])

    assert [publication.publication_date for publication in publications] == [
        "2025-01-10",
        "2026-01-10",
    ]
    assert client.calls == [url_2025, url_2026]


def test_register_bulk_download_does_not_sleep_for_skipped_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Manifest-complete reruns do not burn pacing delay on skipped items."""

    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    pub_url = "https://www.sos.state.co.us/pubs/CCR/register_2024-01-10.html"
    html = f'<a href="{pub_url}">Colorado Register 2024-01-10</a>'
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pub_url: FakeResponse(text="register body"),
        }
    )
    sleeps: list[float] = []

    first = download_all_publications(tmp_path, delay=0, client=client, index_url=index_url)
    monkeypatch.setattr("geode.connectors.register_scraper.time.sleep", sleeps.append)
    second = download_all_publications(tmp_path, delay=99, client=client, index_url=index_url)

    assert first.downloaded == 1
    assert second.skipped == 1
    assert sleeps == []


def test_register_bulk_download_max_downloads_caps_network_attempts(
    tmp_path: Path,
) -> None:
    """A capped run pauses after non-skipped downloads and resumes later."""

    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    pub_one = "https://www.sos.state.co.us/pubs/CCR/register_2024-01-10.html"
    pub_two = "https://www.sos.state.co.us/pubs/CCR/register_2024-02-10.html"
    html = (
        f'<a href="{pub_one}">Colorado Register 2024-01-10</a>'
        f'<a href="{pub_two}">Colorado Register 2024-02-10</a>'
    )
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pub_one: FakeResponse(text="register body one"),
            pub_two: FakeResponse(text="register body two"),
        }
    )

    first = download_all_publications(
        tmp_path,
        delay=0,
        client=client,
        index_url=index_url,
        max_downloads=1,
    )
    quality = build_bulk_download_quality_report(
        tmp_path,
        [
            {
                "connector": "colorado_register",
                "raw_dir": tmp_path.as_posix(),
                "status": "completed",
                "summary": first.model_dump(mode="json"),
            }
        ],
    )
    second = download_all_publications(
        tmp_path,
        delay=0,
        client=client,
        index_url=index_url,
        max_downloads=1,
    )

    assert first.discovered == 2
    assert first.attempted == 1
    assert first.downloaded == 1
    assert client.calls.count(pub_two) == 1
    assert second.attempted == 2
    assert second.skipped == 1
    assert second.downloaded == 1
    assert quality.valid is True
    assert {issue.code for issue in quality.issues} == {"partial_run"}


def test_register_bulk_download_records_failed_items(tmp_path: Path, caplog) -> None:
    """Register publication failures are persisted for later review."""

    caplog.set_level(logging.WARNING)
    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    pub_url = "https://www.sos.state.co.us/pubs/CCR/register_2024-01-10.html"
    html = f'<a href="{pub_url}">Colorado Register 2024-01-10</a>'
    client = FakeClient({index_url: FakeResponse(text=html)})

    report = download_all_publications(tmp_path, delay=0, client=client, index_url=index_url)
    rows = list(iter_jsonl(tmp_path / "download_failures.jsonl"))

    assert report.downloaded == 0
    assert report.failed == 1
    assert rows[0]["publication"]["url"] == pub_url
    assert rows[0]["error"]
    assert rows[0]["jurisdiction"] == "Colorado"
    assert rows[0]["source_type"] == "colorado_register_publication"
    assert rows[0]["document_name"] == "Colorado Register 2024-01-10"
    log_messages = "\n".join(record.getMessage() for record in caplog.records)
    assert f"source_url={pub_url}" in log_messages
    assert "archive_path=" in log_messages


def test_register_discovery_rejects_challenge_page() -> None:
    """Blocked Register index pages cannot masquerade as empty discovery."""

    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    client = FakeClient(
        {
            index_url: FakeResponse(
                text="<html><title>Attention Required! | Cloudflare</title><div id='cf-wrapper'>"
            )
        }
    )

    with pytest.raises(GeodeBlockedError):
        discover_publications(client=client, index_url=index_url)


def test_crs_sgml_parser_outputs_markdown_and_metadata(project_root: Path) -> None:
    """CRS SGML parser writes title Markdown and JSONL metadata."""

    sgml_path = project_root / "_RAW_ARCHIVE" / "crs" / "title25.sgml"
    sgml_path.write_text(
        """
        <TITLE number="25" name="Public Health and Environment">
          <ARTICLE number="7" name="Air Quality">
            <PART number="1" name="General">
              <SECTION number="109" heading="Commission">
                The commission has authority under 25-7-109, C.R.S.
              </SECTION>
            </PART>
          </ARTICLE>
        </TITLE>
        """,
        encoding="utf-8",
    )
    document = parse_crs_sgml(sgml_path, "25", 2025)
    assert document.sections[0].id == "CRS-25-7-109"
    outputs = write_crs_sgml_title(project_root, sgml_path, "25", 2025)
    assert project_root / "01_Statutes_CRS" / "crs_title_25.md" in outputs


def test_exec_order_scraper_processes_sample(tmp_path: Path) -> None:
    """Executive order connector discovers, downloads, and extracts metadata."""

    index_url = "https://www.colorado.gov/governor/executive-orders"
    pdf_url = "https://www.colorado.gov/governor/eo/D2024001.pdf"
    html = f'<a href="{pdf_url}">D 2024 001 Emergency Order 2024-01-10</a>'
    client = FakeClient({index_url: FakeResponse(text=html), pdf_url: FakeResponse(content=b"pdf")})
    entries = discover_executive_orders(client=client, index_url=index_url)
    assert entries[0].entity_id == "EO-2024-001"
    download = download_executive_order(entries[0], tmp_path, client=client)
    assert Path(download.archive_path).exists()
    rows = list(iter_jsonl(tmp_path / "download_manifest.jsonl"))
    assert rows[0]["jurisdiction"] == "Colorado"
    assert rows[0]["source_type"] == "executive_order"
    assert rows[0]["document_id"] == "EO-2024-001"
    assert rows[0]["document_name"] == "D 2024 001 Emergency Order 2024-01-10"
    assert rows[0]["source_url"] == pdf_url
    assert rows[0]["source_format"] == "pdf"
    assert rows[0]["signed_date"] == "2024-01-10"
    assert rows[0]["missing_metadata"] == []
    text = (
        "D 2024 001\nTitle: Emergency Order\nGovernor: Jared Polis\n"
        "Signed: 2024-01-10\nSummary: Directs emergency action under 24-33.5-704."
    )
    record = extract_order_metadata(text, index_url)
    valid, errors = validate_record(record)
    assert valid, errors


def test_exec_order_metadata_prefers_governor_signature_block() -> None:
    """Executive-order dates come from the signing block, not background dates."""

    text = (
        "D 2021 046\n"
        "EXECUTIVE ORDER\n"
        "Extending Executive Orders D 2020 260 and D 2020 286\n"
        "On March 5, 2020, the first presumptive case was confirmed.\n"
        "On March 10, 2020, the Governor took earlier action.\n"
        "GIVEN under my hand and the Executive Seal of the State of Colorado, "
        "this eighteenth day of February, 2021.\n"
        "Jared Polis\nGovernor\n"
    )

    record = extract_order_metadata(text, "https://www.colorado.gov/governor/test.pdf")

    assert record["id"] == "EO-2021-046"
    assert record["signed_date"] == "2021-02-18"
    assert record["governor"] == "Jared Polis"


def test_exec_order_metadata_accepts_signature_period_date() -> None:
    """Executive-order dates allow OCR punctuation found in older PDFs."""

    text = (
        "I Governor Jared Polis\n"
        "D 2019 007\n"
        "Executive Order D 2019 007\n"
        "May 31,2019\n"
        "GIVEN under my hand and Executive Seal of the State of Colorado "
        "this thirty-first day of May. 2019.\n"
        "Governor\n"
    )

    record = extract_order_metadata(text, "https://www.colorado.gov/governor/test.pdf")

    assert record["id"] == "EO-2019-007"
    assert record["signed_date"] == "2019-05-31"
    assert record["governor"] == "Jared Polis"


def test_exec_order_bulk_download_resumes_from_manifest(tmp_path: Path) -> None:
    """Executive order bulk downloads skip already fingerprinted PDFs."""

    index_url = "https://www.colorado.gov/governor/executive-orders"
    pdf_url = "https://www.colorado.gov/governor/eo/D2024001.pdf"
    html = f'<a href="{pdf_url}">D 2024 001 Emergency Order 2024-01-10</a>'
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pdf_url: FakeResponse(content=b"pdf"),
        }
    )

    first = download_all_executive_orders(tmp_path, delay=0, client=client, index_url=index_url)
    before = client.calls.count(pdf_url)
    second = download_all_executive_orders(tmp_path, delay=0, client=client, index_url=index_url)
    after = client.calls.count(pdf_url)

    assert first.downloaded == 1
    assert first.failed == 0
    assert second.skipped == 1
    assert after == before
    assert len(list(iter_jsonl(tmp_path / "download_manifest.jsonl"))) == 1


def test_exec_order_bulk_download_records_failed_items(tmp_path: Path) -> None:
    """Executive order failures are persisted for later review."""

    index_url = "https://www.colorado.gov/governor/executive-orders"
    pdf_url = "https://www.colorado.gov/governor/eo/D2024001.pdf"
    html = f'<a href="{pdf_url}">D 2024 001 Emergency Order 2024-01-10</a>'
    client = FakeClient({index_url: FakeResponse(text=html)})

    report = download_all_executive_orders(tmp_path, delay=0, client=client, index_url=index_url)
    rows = list(iter_jsonl(tmp_path / "download_failures.jsonl"))

    assert report.downloaded == 0
    assert report.failed == 1
    assert rows[0]["entry"]["pdf_url"] == pdf_url
    assert rows[0]["error"]


def test_exec_order_download_rejects_google_sign_in_artifacts(tmp_path: Path) -> None:
    """Google sign-in pages are failures, not executive-order PDFs."""

    index_url = "https://www.colorado.gov/governor/executive-orders"
    pdf_url = "https://www.colorado.gov/governor/eo/D2019007.pdf"
    html = f'<a href="{pdf_url}">D 2019 007</a>'
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pdf_url: FakeResponse(content=b"<html>Google Drive sign-in page</html>"),
        }
    )

    report = download_all_executive_orders(tmp_path, delay=0, client=client, index_url=index_url)

    assert report.downloaded == 0
    assert report.failed == 1
    assert not (tmp_path / "EO-2019-007.pdf").exists()
    rows = list(iter_jsonl(tmp_path / "download_failures.jsonl"))
    assert "sign-in" in rows[0]["error"]


def test_exec_order_rejects_google_drive_text_marker() -> None:
    """The observed Google Drive sign-in wording is blocked."""

    content = b"Loading\nSign in\nto continue to Google Drive\nForgot email?"

    reason = _invalid_executive_order_content_reason(content)

    assert reason is not None
    assert "sign-in" in reason


def test_exec_order_bulk_retries_invalid_manifest_artifact_without_overwrite(
    tmp_path: Path,
) -> None:
    """Bad archived sign-in files do not count as valid resume evidence."""

    index_url = "https://www.colorado.gov/governor/executive-orders"
    pdf_url = "https://www.colorado.gov/governor/eo/D2019007.pdf"
    html = f'<a href="{pdf_url}">D 2019 007</a>'
    bad_target = tmp_path / "EO-2019-007.pdf"
    bad_target.write_bytes(b"<html>Google Drive sign-in page</html>")
    (tmp_path / "download_manifest.jsonl").write_text(
        json.dumps(
            {
                "jurisdiction": "Colorado",
                "source_type": "executive_order",
                "document_id": "EO-2019-007",
                "document_name": "D 2019 007",
                "entry": {
                    "order_number": "D 2019 007",
                    "title": "D 2019 007",
                    "signed_date": None,
                    "source_page_url": index_url,
                    "pdf_url": pdf_url,
                },
                "source_url": pdf_url,
                "source_page_url": index_url,
                "source_format": "pdf",
                "signed_date": None,
                "archive_path": bad_target.as_posix(),
                "sha256": "0" * 64,
                "downloaded_at": "2026-07-02T00:00:00Z",
                "missing_metadata": ["signed_date"],
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pdf_url: FakeResponse(content=b"%PDF-1.7\nrecovered"),
        }
    )

    report = download_all_executive_orders(tmp_path, delay=0, client=client, index_url=index_url)

    assert report.downloaded == 1
    assert bad_target.read_bytes() == b"<html>Google Drive sign-in page</html>"
    assert len(list(tmp_path.glob("EO-2019-007_*.pdf"))) == 1


def test_exec_order_bulk_records_failure_when_invalid_retry_remains_invalid(
    tmp_path: Path,
) -> None:
    """A bad archived file plus a bad retry is queued as a failure."""

    index_url = "https://www.colorado.gov/governor/executive-orders"
    pdf_url = "https://www.colorado.gov/governor/eo/D2019007.pdf"
    html = f'<a href="{pdf_url}">D 2019 007</a>'
    bad_target = tmp_path / "EO-2019-007.pdf"
    bad_target.write_bytes(b"<html>Google Drive sign-in page</html>")
    (tmp_path / "download_manifest.jsonl").write_text(
        json.dumps(
            {
                "jurisdiction": "Colorado",
                "source_type": "executive_order",
                "document_id": "EO-2019-007",
                "document_name": "D 2019 007",
                "entry": {
                    "order_number": "D 2019 007",
                    "title": "D 2019 007",
                    "signed_date": None,
                    "source_page_url": index_url,
                    "pdf_url": pdf_url,
                },
                "source_url": pdf_url,
                "source_page_url": index_url,
                "source_format": "pdf",
                "signed_date": None,
                "archive_path": bad_target.as_posix(),
                "sha256": "0" * 64,
                "downloaded_at": "2026-07-02T00:00:00Z",
                "missing_metadata": ["signed_date"],
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pdf_url: FakeResponse(content=b"<html>to continue to Google Drive</html>"),
        }
    )

    report = download_all_executive_orders(tmp_path, delay=0, client=client, index_url=index_url)

    assert report.downloaded == 0
    assert report.failed == 1
    assert bad_target.read_bytes() == b"<html>Google Drive sign-in page</html>"
    assert list(tmp_path.glob("EO-2019-007_*.pdf")) == []


def test_exec_order_ingest_uses_manual_intake_replacement(
    project_root: Path,
    monkeypatch,
) -> None:
    """Manual official intake can replace a blocked executive-order source."""

    raw_dir = project_root / "_RAW_ARCHIVE" / "exec_orders"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pdf_url = "https://www.colorado.gov/governor/eo/D2019007.pdf"
    (raw_dir / "download_manifest.jsonl").write_text(
        json.dumps(
            {
                "jurisdiction": "Colorado",
                "source_type": "executive_order",
                "document_id": "EO-2019-007",
                "document_name": "D 2019 007",
                "entry": {
                    "order_number": "D 2019 007",
                    "title": "D 2019 007",
                    "signed_date": None,
                    "source_page_url": "https://www.colorado.gov/governor/2019-executive-orders",
                    "pdf_url": pdf_url,
                },
                "source_url": pdf_url,
                "source_page_url": "https://www.colorado.gov/governor/2019-executive-orders",
                "source_format": "pdf",
                "signed_date": None,
                "archive_path": "_RAW_ARCHIVE/exec_orders/EO-2019-007.pdf",
                "sha256": "0" * 64,
                "downloaded_at": "2026-07-02T00:00:00Z",
                "missing_metadata": ["signed_date"],
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    manual_pdf = (
        project_root
        / "_RAW_ARCHIVE"
        / "manual_intake"
        / "05_Executive_Orders"
        / "EO-2019-007"
        / "official.pdf"
    )
    manual_pdf.parent.mkdir(parents=True, exist_ok=True)
    manual_pdf.write_bytes(b"%PDF-1.7 official replacement")
    manual_sha = hashlib.sha256(manual_pdf.read_bytes()).hexdigest()
    (project_root / "_CONTROL_PLANE" / "MANUAL_SOURCE_INTAKE_LEDGER.jsonl").write_text(
        json.dumps(
            {
                "intake_id": "MSI-test",
                "record_id": "EO-2019-007",
                "layer_id": "05_Executive_Orders",
                "official_source_name": "Colorado State Publications Library",
                "official_source_url": (
                    "https://spl.cde.state.co.us/artemis/goserials/go4312internet/"
                    "go43122019007internet.pdf"
                ),
                "acquisition_method": "manual_official_download",
                "received_from": "test",
                "reviewer_name": "test",
                "reviewer_email": None,
                "custody_note": "Official replacement source artifact for EO-2019-007.",
                "original_filename": "official.pdf",
                "archive_path": manual_pdf.relative_to(project_root).as_posix(),
                "sha256": manual_sha,
                "size_bytes": manual_pdf.stat().st_size,
                "source_format": "pdf",
                "received_at": "2026-07-07T22:13:29Z",
                "status": "archived_pending_pipeline",
                "blocked_queue_match": True,
                "boundary": "test",
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "geode.connectors.exec_orders_scraper._extract_pdf_text",
        lambda _path: (
            "D 2019 007\n"
            "EXECUTIVE ORDER\n"
            "GIVEN under my hand and the Executive Seal of the State of Colorado, "
            "this fifth day of April, 2019.\n"
            "Jared Polis\nGovernor\n"
        ),
    )

    summary = ingest_archived_executive_orders(project_root)
    rows = list(iter_jsonl(project_root / "05_Executive_Orders" / "_index.jsonl"))

    assert summary.records_written == 1
    assert summary.failed_files == 0
    assert rows[0]["id"] == "EO-2019-007"
    assert rows[0]["source_path"] == manual_pdf.relative_to(project_root).as_posix()
    assert rows[0]["source_url"].startswith("https://spl.cde.state.co.us/")


def test_orchestrator_runs_injected_connectors(project_root: Path) -> None:
    """Orchestrator runs individual injected connectors and handles failures."""

    def ok(raw_dir: Path, config: dict) -> None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "done.txt").write_text("ok", encoding="utf-8")

    def fail(raw_dir: Path, config: dict) -> None:
        raise RuntimeError("boom")

    report = run_full_download(
        {
            "root": project_root,
            "connectors": ["register", "exec_orders"],
            "connector_functions": {"register": ok, "exec_orders": fail},
        }
    )
    assert report.failed == 1
    assert report.run_summary["attempted"] == 1
    assert report.run_summary["failed"] == 1
    assert (project_root / "_RAW_ARCHIVE" / "register" / "done.txt").exists()
    assert report.results[1].status == "failed"


def test_orchestrator_logs_end_of_run_summary(project_root: Path, caplog) -> None:
    """Orchestrator logs concise connector and aggregate run summaries."""

    caplog.set_level(logging.INFO)

    def ok(raw_dir: Path, config: dict) -> dict[str, object]:
        return {
            "discovered": 3,
            "downloaded": 2,
            "skipped": 1,
            "failed": 0,
            "manifest_path": (raw_dir / "download_manifest.jsonl").as_posix(),
            "errors": [],
        }

    def partial(raw_dir: Path, config: dict) -> dict[str, object]:
        return {
            "discovered": 2,
            "downloaded": 1,
            "skipped": 0,
            "failed": 1,
            "manifest_path": (raw_dir / "download_manifest.jsonl").as_posix(),
            "errors": ["blocked"],
        }

    report = run_full_download(
        {
            "root": project_root,
            "connectors": ["register", "exec_orders"],
            "connector_functions": {"register": ok, "exec_orders": partial},
        }
    )

    assert report.run_summary["attempted"] == 5
    assert report.run_summary["succeeded"] == 3
    assert report.run_summary["failed"] == 1
    assert report.run_summary["skipped"] == 1
    log_messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Connector completed connector=register status=completed attempted=3" in log_messages
    assert "Connector completed connector=exec_orders status=completed_with_errors" in log_messages
    assert "Bulk download summary attempted=5 succeeded=3 failed=1 skipped=1" in log_messages


def test_orchestrator_writes_bulk_quality_report(project_root: Path) -> None:
    """A bulk run writes a machine-readable quality report."""

    index_url = "https://www.sos.state.co.us/CCR/RegisterHome.do"
    pub_url = "https://www.sos.state.co.us/pubs/CCR/register_2024-01-10.html"
    html = f'<a href="{pub_url}">Colorado Register 2024-01-10</a>'
    client = FakeClient(
        {
            index_url: FakeResponse(text=html),
            pub_url: FakeResponse(text="register body with enough bytes"),
        }
    )

    report = run_full_download(
        {
            "root": project_root,
            "connectors": ["colorado_register"],
            "http_client": client,
            "register_index_url": index_url,
            "delay": 0,
        }
    )

    assert report.quality_report_path is not None
    quality = load_json(Path(report.quality_report_path))
    assert quality["valid"] is True
    assert quality["summary"]["attempted"] == 1
    assert quality["summary"]["succeeded"] == 1
    assert quality["summary"]["errors"] == 0
    assert quality["connectors"][0]["connector"] == "colorado_register"


def test_bulk_quality_report_flags_duplicate_empty_and_malformed_outputs(
    tmp_path: Path,
) -> None:
    """Quality reports surface duplicate outputs and malformed downloaded JSON."""

    raw_dir = tmp_path / "_RAW_ARCHIVE" / "legiscan"
    raw_dir.mkdir(parents=True)
    target = raw_dir / "2023" / "12345.json"
    target.parent.mkdir(parents=True)
    target.write_text("{not-json", encoding="utf-8")
    manifest = raw_dir / "download_manifest.jsonl"
    row = {
        "jurisdiction": "Colorado",
        "source_type": "bill",
        "document_id": "12345",
        "document_name": "Bad Bill",
        "bill_id": 12345,
        "bill_number": "HB 1",
        "session_year": 2023,
        "source_url": "https://api.legiscan.com/",
        "source_format": "json",
        "archive_path": target.as_posix(),
        "sha256": None,
        "size_bytes": target.stat().st_size,
        "downloaded_at": "2026-06-18T00:00:00Z",
        "status": "downloaded",
        "error": None,
        "missing_metadata": [],
    }
    manifest.write_text(
        "\n".join([json.dumps(row), json.dumps(row)]) + "\n",
        encoding="utf-8",
    )

    quality = build_bulk_download_quality_report(
        tmp_path,
        [
            {
                "connector": "legiscan",
                "raw_dir": raw_dir.as_posix(),
                "status": "completed",
                "summary": {
                    "bills": 1,
                    "skipped": 0,
                    "failed": 0,
                    "manifest_path": manifest.as_posix(),
                    "paths": [target.as_posix(), target.as_posix()],
                },
            }
        ],
    )
    codes = {issue.code for issue in quality.issues}

    assert quality.valid is False
    assert "duplicate_archive_path" in codes
    assert "duplicate_document_id" in codes
    assert "duplicate_summary_path" in codes
    assert "near_empty_output" in codes
    assert "malformed_json_output" in codes


def test_orchestrator_runs_source_registry_aliases(project_root: Path, monkeypatch) -> None:
    """Source-registry connector IDs route to implemented bulk downloaders."""

    calls: list[tuple[str, Path, dict[str, object]]] = []

    def register(raw_dir: Path, **kwargs: object) -> dict[str, object]:
        calls.append(("register", raw_dir, kwargs))
        return {"discovered": 1, "downloaded": 1, "failed": 0, "errors": []}

    def executive_orders(raw_dir: Path, **kwargs: object) -> dict[str, object]:
        calls.append(("exec_orders", raw_dir, kwargs))
        return {"discovered": 1, "downloaded": 0, "failed": 1, "errors": ["blocked"]}

    monkeypatch.setattr(
        "geode.connectors.orchestrator.download_all_publications",
        register,
    )
    monkeypatch.setattr(
        "geode.connectors.orchestrator.download_all_executive_orders",
        executive_orders,
    )

    report = run_full_download(
        {
            "root": project_root,
            "connectors": ["colorado_register", "executive_orders"],
            "delay": 0,
            "max_downloads": 5,
            "http_max_retries": 7,
            "http_base_delay": 0.5,
            "http_timeout_seconds": 9.0,
            "http_max_retry_delay_seconds": 11.0,
        }
    )

    assert calls[0][0:2] == ("register", project_root / "_RAW_ARCHIVE" / "register")
    assert calls[1][0:2] == ("exec_orders", project_root / "_RAW_ARCHIVE" / "exec_orders")
    assert calls[0][2]["max_retries"] == 7
    assert calls[0][2]["base_delay"] == 0.5
    assert calls[0][2]["timeout_seconds"] == 9.0
    assert calls[0][2]["max_retry_delay_seconds"] == 11.0
    assert calls[0][2]["max_downloads"] == 5
    assert calls[1][2]["max_retries"] == 7
    assert calls[1][2]["max_downloads"] == 5
    assert report.results[0].status == "completed"
    assert report.results[1].status == "completed_with_errors"
    assert report.results[1].summary["failed"] == 1


def test_orchestrator_passes_hardened_http_options_to_ccr(
    project_root: Path,
    monkeypatch,
) -> None:
    """CCR bulk runs receive configured retry, timeout, backoff, and pacing values."""

    captured: dict[str, object] = {}

    def ccr(raw_dir: Path, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        captured["raw_dir"] = raw_dir
        return {"discovered": 0, "downloaded": 0, "failed": 0, "errors": []}

    monkeypatch.setattr("geode.connectors.orchestrator.download_all_rules", ccr)

    report = run_full_download(
        {
            "root": project_root,
            "connectors": ["ccr"],
            "delay": 1.25,
            "discovery_delay": 0.75,
            "delay_jitter": 0.2,
            "discovery_delay_jitter": 0.1,
            "max_downloads": 3,
            "http_max_retries": 6,
            "http_base_delay": 0.5,
            "http_timeout_seconds": 8.0,
            "http_max_retry_delay_seconds": 13.0,
            "http_retry_jitter_ratio": 0.0,
        }
    )

    assert captured["raw_dir"] == project_root / "_RAW_ARCHIVE" / "ccr"
    assert captured["delay"] == 1.25
    assert captured["discovery_delay"] == 0.75
    assert captured["delay_jitter_seconds"] == 0.2
    assert captured["discovery_delay_jitter_seconds"] == 0.1
    assert captured["max_downloads"] == 3
    assert captured["max_retries"] == 6
    assert captured["base_delay"] == 0.5
    assert captured["timeout_seconds"] == 8.0
    assert captured["max_retry_delay_seconds"] == 13.0
    assert captured["retry_jitter_ratio"] == 0.0
    assert report.results[0].status == "completed"
