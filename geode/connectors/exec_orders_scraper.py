"""Governor executive order discovery and download connector."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from geode.constants import CONTROL_PLANE_DIR, RAW_ARCHIVE_DIR
from geode.connectors.archive_paths import (
    DOWNLOAD_MANIFEST_NAME,
    FAILURE_MANIFEST_NAME,
    download_manifest_path,
    executive_order_pdf_path,
    failure_manifest_path,
    temp_path_for,
)
from geode.connectors.download_metadata import (
    COLORADO_JURISDICTION,
    missing_metadata_fields,
    source_format_from_extension,
)
from geode.extractors.citation_extractor import extract_crs_citations
from geode.net.http_client import (
    DEFAULT_MAX_RETRY_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    build_session,
    polite_get,
)
from geode.schemas.models import ExecutiveOrder, LayerIndexRecord, UpdateLogRecord
from geode.schemas.validators import require_official_source_url
from geode.utils.file_io import (
    append_jsonl_record_atomic,
    atomic_write_json,
    atomic_write_jsonl,
    iter_jsonl,
    load_json,
    relative_path,
)
from geode.utils.hashing import sha256_file, sha256_text

LOGGER = logging.getLogger(__name__)

EXECUTIVE_ORDERS_URL = "https://www.colorado.gov/governor/executive-orders"
DOWNLOAD_MANIFEST = DOWNLOAD_MANIFEST_NAME
FAILURE_MANIFEST = FAILURE_MANIFEST_NAME
MANUAL_INTAKE_LEDGER = Path(CONTROL_PLANE_DIR) / "MANUAL_SOURCE_INTAKE_LEDGER.jsonl"
ORDER_RE = re.compile(r"\b(?:EO|D)\s*(?P<year>20\d{2})[-\s]?(?P<number>\d{3})\b")
DATE_RE = re.compile(r"\b(20\d{2})[-_/](\d{2})[-_/](\d{2})\b")
GOVERNOR_HEADER_RE = re.compile(
    r"^(?:[I1]\s+)?Governor\s+(?P<name>[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){1,4})$"
)
SIGNED_LABEL_RE = re.compile(
    r"^\s*Signed:\s*(?P<year>20\d{2})[-_/](?P<month>\d{2})[-_/](?P<day>\d{2})\s*$",
    re.IGNORECASE | re.MULTILINE,
)
MONTH_DATE_RE = re.compile(
    r"\b(?P<month>January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(?P<day>\d{1,2}),\s*(?P<year>20\d{2})\b",
    re.IGNORECASE,
)
SIGNED_BLOCK_RE = re.compile(
    r"\bGIVEN\s+under\s+my\s+hand\b(?P<block>.{0,900})",
    re.IGNORECASE | re.DOTALL,
)
SIGNED_WRITTEN_DATE_RE = re.compile(
    r"\bthis\s+(?P<day>[A-Za-z]+(?:[-\s][A-Za-z]+)?)\s+day\s+of\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s*[,\.]?\s+(?P<year>20\d{2})\b",
    re.IGNORECASE,
)
SIGNED_NUMERIC_DATE_RE = re.compile(
    r"\bthis\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s*[,\.]?\s+(?P<year>20\d{2})\b",
    re.IGNORECASE,
)
YEAR_PAGE_RE = re.compile(r"/governor/(20\d{2})-executive-orders\b")
INVALID_DOWNLOAD_BYTE_MARKERS = (
    b"google drive sign-in",
    b"accounts.google.com",
    b"servicelogin",
    b"couldn't preview file",
    b"to continue to google drive",
    b"forgot email",
    b"use guest mode to sign in privately",
)
INVALID_DOWNLOAD_TEXT_MARKERS = (
    "google drive sign-in",
    "accounts.google.com",
    "service login",
    "to continue to google drive",
    "forgot email",
    "use guest mode to sign in privately",
    "helpprivacyterms",
)
WRITTEN_ORDINAL_DAYS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "twenty-first": 21,
    "twenty second": 22,
    "twenty-second": 22,
    "twenty third": 23,
    "twenty-third": 23,
    "twenty fourth": 24,
    "twenty-fourth": 24,
    "twenty fifth": 25,
    "twenty-fifth": 25,
    "twenty sixth": 26,
    "twenty-sixth": 26,
    "twenty seventh": 27,
    "twenty-seventh": 27,
    "twenty eighth": 28,
    "twenty-eighth": 28,
    "twenty ninth": 29,
    "twenty-ninth": 29,
    "thirtieth": 30,
    "thirty first": 31,
    "thirty-first": 31,
}


class ExecutiveOrderEntry(BaseModel):
    """One executive order source link."""

    model_config = ConfigDict(extra="forbid")

    order_number: str
    title: str
    signed_date: str | None = None
    source_page_url: HttpUrl
    pdf_url: HttpUrl

    @field_validator("source_page_url", "pdf_url")
    @classmethod
    def validate_urls(cls, value: HttpUrl) -> HttpUrl:
        """Require official Colorado URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @property
    def entity_id(self) -> str:
        """Return Geode executive order ID."""

        match = ORDER_RE.search(self.order_number)
        if not match:
            return self.order_number
        return f"EO-{match.group('year')}-{match.group('number')}"


class ExecutiveOrderDownload(BaseModel):
    """Downloaded executive order metadata."""

    model_config = ConfigDict(extra="forbid")

    jurisdiction: str = COLORADO_JURISDICTION
    source_type: str = "executive_order"
    document_id: str = ""
    document_name: str | None = None
    entry: ExecutiveOrderEntry
    source_url: HttpUrl | None = None
    source_page_url: HttpUrl | None = None
    source_format: str | None = None
    signed_date: str | None = None
    archive_path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    downloaded_at: datetime
    missing_metadata: list[str] = Field(default_factory=list)

    @field_validator("source_url", "source_page_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official source URLs when present."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value


class ExecutiveOrderDownloadFailure(BaseModel):
    """Failed executive order PDF download attempt."""

    model_config = ConfigDict(extra="forbid")

    jurisdiction: str = COLORADO_JURISDICTION
    source_type: str = "executive_order"
    document_id: str = ""
    document_name: str | None = None
    entry: ExecutiveOrderEntry
    source_url: HttpUrl | None = None
    source_page_url: HttpUrl | None = None
    source_format: str | None = None
    signed_date: str | None = None
    archive_path: str
    failed_at: datetime
    error: str
    missing_metadata: list[str] = Field(default_factory=list)

    @field_validator("source_url", "source_page_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official source URLs when present."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value


class DownloadReport(BaseModel):
    """Summary from an executive order download batch."""

    model_config = ConfigDict(extra="forbid")

    discovered: int = Field(ge=0)
    attempted: int = Field(ge=0)
    downloaded: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
    manifest_path: str
    paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ExecutiveOrderIngestSummary(BaseModel):
    """Summary for structuring archived executive orders."""

    model_config = ConfigDict(extra="forbid")

    archive_dir: str
    records_written: int = Field(ge=0)
    failed_files: int = Field(ge=0)
    output_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class _LinkParser(HTMLParser):
    """Minimal anchor parser."""

    def __init__(self) -> None:
        """Initialize parser state."""

        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Capture anchor starts."""

        if tag.lower() == "a":
            attrs_dict = {key.lower(): value for key, value in attrs}
            self._href = attrs_dict.get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        """Capture anchor text."""

        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Capture anchor ends."""

        if tag.lower() == "a" and self._href:
            text = " ".join(part.strip() for part in self._text if part.strip())
            self.links.append((self._href, text))
            self._href = None
            self._text = []


def discover_executive_orders(
    client: Any | None = None,
    index_url: str = EXECUTIVE_ORDERS_URL,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> list[ExecutiveOrderEntry]:
    """Discover executive order PDF links from the Governor website."""

    session = _session_or_client(client)
    html = _fetch_text(
        index_url,
        session,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    entries = _entries_from_html(html, index_url)
    for year_url in _year_page_urls(html, index_url):
        if year_url.rstrip("/") == index_url.rstrip("/"):
            continue
        try:
            year_html = _fetch_text(
                year_url,
                session,
                max_retries=max_retries,
                base_delay=base_delay,
                timeout_seconds=timeout_seconds,
                max_retry_delay_seconds=max_retry_delay_seconds,
            )
        except Exception as exc:
            LOGGER.warning("Executive order year page skipped url=%s error=%s", year_url, exc)
            continue
        entries.extend(_entries_from_html(year_html, year_url))
    return _dedupe_entries(entries)


def _entries_from_html(html: str, page_url: str) -> list[ExecutiveOrderEntry]:
    """Extract executive order document links from one Governor page."""

    parser = _LinkParser()
    parser.feed(html)
    entries: list[ExecutiveOrderEntry] = []
    for href, text in parser.links:
        absolute = urljoin(page_url, href)
        if not _is_order_document_url(absolute):
            continue
        order_match = ORDER_RE.search(text) or ORDER_RE.search(absolute)
        if not order_match:
            continue
        order_number = f"D {order_match.group('year')} {order_match.group('number')}"
        entries.append(
            ExecutiveOrderEntry(
                order_number=order_number,
                title=text,
                signed_date=_date_from_text(text),
                source_page_url=page_url,
                pdf_url=_download_url(absolute),
            )
        )
    return entries


def _year_page_urls(html: str, page_url: str) -> list[str]:
    """Return linked Governor year pages from the executive-order index."""

    parser = _LinkParser()
    parser.feed(html)
    urls: list[str] = []
    for href, _text in parser.links:
        absolute = urljoin(page_url, href)
        if YEAR_PAGE_RE.search(urlparse(absolute).path):
            urls.append(absolute)
    return sorted(set(urls))


def _dedupe_entries(entries: list[ExecutiveOrderEntry]) -> list[ExecutiveOrderEntry]:
    """Return entries keyed by executive-order ID in source order."""

    seen: set[str] = set()
    unique: list[ExecutiveOrderEntry] = []
    for entry in entries:
        if entry.entity_id in seen:
            continue
        seen.add(entry.entity_id)
        unique.append(entry)
    return unique


def _is_order_document_url(url: str) -> bool:
    """Return whether a URL looks like an order document link."""

    parsed = urlparse(url)
    if ".pdf" in parsed.path.lower():
        return True
    return parsed.netloc.lower() == "drive.google.com" and "/file/d/" in parsed.path


def _download_url(url: str) -> str:
    """Return a direct download URL for supported document links."""

    parsed = urlparse(url)
    if parsed.netloc.lower() != "drive.google.com":
        return url
    file_match = re.search(r"/file/d/([^/]+)", parsed.path)
    if file_match:
        return f"https://drive.google.com/uc?export=download&id={file_match.group(1)}"
    query_id = parse_qs(parsed.query).get("id", [None])[0]
    if query_id:
        return f"https://drive.google.com/uc?export=download&id={query_id}"
    return url


def download_all_executive_orders(
    archive_dir: Path,
    delay: float = 1.0,
    client: Any | None = None,
    index_url: str = EXECUTIVE_ORDERS_URL,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    max_downloads: int | None = None,
) -> DownloadReport:
    """Discover and download executive order PDFs with resume support."""

    _validate_max_downloads(max_downloads)
    session = _session_or_client(client)
    entries = discover_executive_orders(
        client=session,
        index_url=index_url,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    LOGGER.info(
        "Executive orders bulk download discovered=%s archive_dir=%s",
        len(entries),
        archive_dir.as_posix(),
    )
    manifest_path = download_manifest_path(archive_dir)
    paths: list[str] = []
    errors: list[str] = []
    downloaded = 0
    skipped = 0
    failed = 0
    network_attempts = 0
    for index, entry in enumerate(entries):
        target = _archive_path_for_order(entry, archive_dir)
        already_downloaded = _is_downloaded(manifest_path, entry, target)
        if already_downloaded:
            paths.append(target.as_posix())
            skipped += 1
            continue
        if max_downloads is not None and network_attempts >= max_downloads:
            LOGGER.info(
                "Executive orders bulk download paused max_downloads=%s archive_dir=%s",
                max_downloads,
                archive_dir.as_posix(),
            )
            break
        network_attempts += 1
        try:
            result = download_executive_order(
                entry,
                archive_dir,
                client=session,
                max_retries=max_retries,
                base_delay=base_delay,
                timeout_seconds=timeout_seconds,
                max_retry_delay_seconds=max_retry_delay_seconds,
            )
        except Exception as exc:
            failed += 1
            errors.append(f"{entry.entity_id}: {exc}")
            LOGGER.warning(
                "Executive order download failed order_id=%s source_url=%s "
                "archive_path=%s error=%s",
                entry.entity_id,
                entry.pdf_url,
                target.as_posix(),
                exc,
            )
            _append_failure(
                failure_manifest_path(archive_dir),
                ExecutiveOrderDownloadFailure(
                    **_manifest_metadata(entry, target),
                    entry=entry,
                    archive_path=target.as_posix(),
                    failed_at=datetime.now(timezone.utc),
                    error=str(exc),
                ),
            )
        else:
            paths.append(result.archive_path)
            downloaded += 1
        if (
            delay > 0
            and index < len(entries) - 1
            and (max_downloads is None or network_attempts < max_downloads)
        ):
            time.sleep(delay)
    report = DownloadReport(
        discovered=len(entries),
        attempted=downloaded + skipped + failed,
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        manifest_path=manifest_path.as_posix(),
        paths=paths,
        errors=errors,
    )
    log_summary = LOGGER.warning if failed else LOGGER.info
    log_summary(
        "Executive orders bulk download summary attempted=%s succeeded=%s "
        "failed=%s skipped=%s archive_dir=%s manifest=%s",
        report.attempted,
        report.downloaded,
        report.failed,
        report.skipped,
        archive_dir.as_posix(),
        report.manifest_path,
    )
    return report


def ingest_archived_executive_orders(
    root: Path,
    archive_dir: Path | None = None,
) -> ExecutiveOrderIngestSummary:
    """Write structured executive-order records from archived PDFs."""

    project_root = root.resolve()
    source_dir = (archive_dir or project_root / RAW_ARCHIVE_DIR / "exec_orders").resolve()
    raw_root = (project_root / RAW_ARCHIVE_DIR / "exec_orders").resolve()
    if not source_dir.is_relative_to(raw_root):
        raise ValueError("executive order archive_dir must live under _RAW_ARCHIVE/exec_orders")
    manifest_path = download_manifest_path(source_dir)
    layer_root = project_root / "05_Executive_Orders"
    layer_root.mkdir(parents=True, exist_ok=True)
    (layer_root / "_meta").mkdir(parents=True, exist_ok=True)

    manual_downloads, manual_errors = _manual_intake_executive_order_downloads(project_root)
    manual_ids = {download.entry.entity_id for download in manual_downloads}
    records_by_id: dict[str, ExecutiveOrder] = {}
    errors: list[str] = []
    if manifest_path.exists():
        for payload in iter_jsonl(manifest_path):
            try:
                download = ExecutiveOrderDownload.model_validate(payload)
                if download.entry.entity_id in manual_ids:
                    continue
                records_by_id[download.entry.entity_id] = _executive_order_record(
                    download,
                    project_root,
                )
            except Exception as exc:
                errors.append(str(exc))
    errors.extend(manual_errors)
    for download in manual_downloads:
        try:
            records_by_id[download.entry.entity_id] = _executive_order_record(
                download,
                project_root,
            )
        except Exception as exc:
            errors.append(str(exc))

    records = list(records_by_id.values())

    grouped: dict[str, list[ExecutiveOrder]] = {}
    for record in records:
        decade = f"{record.signed_date.year // 10 * 10}_{record.signed_date.year // 10 * 10 + 9}"
        grouped.setdefault(decade, []).append(record)

    output_paths: list[Path] = []
    for decade, decade_records in sorted(grouped.items()):
        path = layer_root / decade / f"exec_orders_{decade}.jsonl"
        atomic_write_jsonl(path, sorted(decade_records, key=lambda item: item.id), project_root)
        output_paths.append(path)
    _remove_stale_decade_files(layer_root, set(output_paths))

    index_path = layer_root / "_index.jsonl"
    index_rows = [
        _executive_order_index_record(record, project_root)
        for record in sorted(records, key=lambda item: item.id)
    ]
    atomic_write_jsonl(index_path, index_rows, project_root)
    output_paths.append(index_path)

    manifest = load_json(project_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    now = datetime.now(timezone.utc)
    for layer in manifest.get("data_layers", []):
        if isinstance(layer, dict) and layer.get("id") == "05_Executive_Orders":
            layer["record_count"] = len(records)
            layer["last_ingested"] = now.date().isoformat()
            layer["last_checked"] = now.date().isoformat()
            layer["staleness_days"] = 0
            layer["status"] = "ready" if records else "empty"
            break
    atomic_write_json(
        project_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json",
        manifest,
        project_root,
    )
    output_paths.append(project_root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")

    event = UpdateLogRecord(
        event_id=f"UL-{now.strftime('%Y%m%dT%H%M%S%fZ')}-exec_orders",
        timestamp=now,
        event_type="executive_orders_ingested",
        layer="05_Executive_Orders",
        entity_id=None,
        action="ingest_archived_executive_orders",
        source_path=relative_path(manifest_path, project_root) if manifest_path.exists() else None,
        output_paths=[relative_path(path, project_root) for path in output_paths],
        record_count=len(records),
        sha256=None,
        message=(
            f"Ingested {len(records)} executive order records, including "
            f"{len(manual_downloads)} manual official source artifact(s)."
        ),
    )
    append_jsonl_record_atomic(
        project_root / CONTROL_PLANE_DIR / "UPDATE_LOG.jsonl",
        event,
        project_root,
    )
    output_paths.append(project_root / CONTROL_PLANE_DIR / "UPDATE_LOG.jsonl")

    return ExecutiveOrderIngestSummary(
        archive_dir=relative_path(source_dir, project_root),
        records_written=len(records),
        failed_files=len(errors),
        output_paths=[relative_path(path, project_root) for path in output_paths],
        errors=errors,
    )


def _executive_order_record(download: ExecutiveOrderDownload, root: Path) -> ExecutiveOrder:
    """Build a validated executive-order record from one archived download."""

    archive_path = Path(download.archive_path)
    if not archive_path.is_absolute():
        archive_path = root / archive_path
    text = _extract_pdf_text(archive_path)
    if not text.strip():
        text = download.entry.title
    signed_date = _signed_date_from_order_text(text, download.entry.entity_id)
    if not signed_date and download.signed_date:
        signed_date = _date_if_expected_year(download.signed_date, download.entry.entity_id)
    if not signed_date:
        raise ValueError(f"signed date missing for {download.entry.entity_id}")
    title = _line_value(text, "Title") or download.entry.title or download.entry.entity_id
    summary = _line_value(text, "Summary") or title
    governor = _governor_from_text(text) or "Unknown Governor"
    return ExecutiveOrder.model_validate(
        {
            "entity_type": "executive_order",
            "id": download.entry.entity_id,
            "order_number": download.entry.order_number,
            "title": title,
            "governor": governor,
            "signed_date": signed_date,
            "status": "active",
            "full_text": text,
            "summary": summary,
            "statutes_cited": [
                citation.canonical_form for citation in extract_crs_citations(text)
            ],
            "subject_tags": [],
            "source_url": str(download.source_url or download.entry.pdf_url),
            "source_path": relative_path(archive_path, root),
            "confidence": {"overall": 0.75},
        }
    )


def _manual_intake_executive_order_downloads(
    root: Path,
) -> tuple[list[ExecutiveOrderDownload], list[str]]:
    """Return executive-order downloads backed by approved manual intake records."""

    ledger_path = root / MANUAL_INTAKE_LEDGER
    if not ledger_path.exists():
        return [], []

    downloads: list[ExecutiveOrderDownload] = []
    errors: list[str] = []
    for payload in iter_jsonl(ledger_path):
        if payload.get("layer_id") != "05_Executive_Orders":
            continue
        try:
            downloads.append(_manual_intake_download(root, payload))
        except Exception as exc:
            errors.append(f"manual intake {payload.get('record_id')}: {exc}")
    return downloads, errors


def _manual_intake_download(root: Path, payload: dict[str, Any]) -> ExecutiveOrderDownload:
    """Convert one manual intake ledger row into executive-order source metadata."""

    record_id = str(payload.get("record_id") or "")
    order_number = _order_number_from_entity_id(record_id)
    archive_path = Path(str(payload.get("archive_path") or ""))
    if not archive_path.is_absolute():
        archive_path = root / archive_path
    if not archive_path.exists():
        raise ValueError(f"manual archive file is missing: {archive_path}")
    expected_sha = str(payload.get("sha256") or "")
    actual_sha = sha256_file(archive_path)
    if expected_sha and actual_sha != expected_sha:
        raise ValueError("manual archive SHA-256 does not match ledger")
    source_url = str(payload.get("official_source_url") or "")
    if not source_url:
        raise ValueError("manual intake official_source_url is missing")
    require_official_source_url(source_url)
    downloaded_at = payload.get("received_at") or datetime.now(timezone.utc)
    return ExecutiveOrderDownload(
        jurisdiction=COLORADO_JURISDICTION,
        source_type="executive_order",
        document_id=record_id,
        document_name=order_number,
        entry=ExecutiveOrderEntry(
            order_number=order_number,
            title=order_number,
            signed_date=None,
            source_page_url=source_url,
            pdf_url=source_url,
        ),
        source_url=source_url,
        source_page_url=source_url,
        source_format=source_format_from_extension(archive_path.suffix),
        signed_date=None,
        archive_path=relative_path(archive_path, root),
        sha256=actual_sha,
        downloaded_at=downloaded_at,
        missing_metadata=["signed_date"],
    )


def _order_number_from_entity_id(entity_id: str) -> str:
    """Return the Governor order number display value for an EO entity ID."""

    match = re.match(r"^EO-(20\d{2})-(\d{3})$", entity_id)
    if not match:
        raise ValueError(f"invalid executive-order id: {entity_id}")
    return f"D {match.group(1)} {match.group(2)}"


def _executive_order_index_record(record: ExecutiveOrder, root: Path) -> LayerIndexRecord:
    """Build one layer index row for an executive-order record."""

    decade = f"{record.signed_date.year // 10 * 10}_{record.signed_date.year // 10 * 10 + 9}"
    content_path = root / "05_Executive_Orders" / decade / f"exec_orders_{decade}.jsonl"
    return LayerIndexRecord(
        entity_id=record.id,
        layer="05_Executive_Orders",
        entity_type="executive_order",
        title=record.title,
        citation=record.order_number,
        path=relative_path(content_path, root),
        meta_path=None,
        source_url=record.source_url,
        source_path=record.source_path,
        publication_year=record.signed_date.year,
        last_updated=datetime.now(timezone.utc),
        sha256=sha256_text(record.full_text),
        tags=["executive_order"],
        confidence=record.confidence.overall,
    )


def _remove_stale_decade_files(layer_root: Path, current_paths: set[Path]) -> None:
    """Remove obsolete generated executive-order decade files."""

    current_resolved = {path.resolve() for path in current_paths}
    for path in layer_root.glob("*_*/exec_orders_*_*.jsonl"):
        if path.resolve() in current_resolved:
            continue
        path.unlink()
        try:
            path.parent.rmdir()
        except OSError:
            pass


def _extract_pdf_text(path: Path) -> str:
    """Extract text from an archived executive-order PDF."""

    import fitz

    with fitz.open(path) as document:
        return "\n".join(page.get_text("text") for page in document).strip()


def _validate_max_downloads(max_downloads: int | None) -> None:
    """Validate an optional per-run network-attempt cap."""

    if max_downloads is not None and max_downloads < 0:
        raise ValueError("max_downloads cannot be negative")


def download_executive_order(
    entry: ExecutiveOrderEntry,
    archive_dir: Path,
    client: Any | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> ExecutiveOrderDownload:
    """Download one executive order PDF and fingerprint it."""

    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = download_manifest_path(archive_dir)
    target = _archive_path_for_order(entry, archive_dir)
    prior = _manifest_entry_for(manifest_path, entry)
    if (
        prior
        and target.exists()
        and prior.sha256 == sha256_file(target)
        and _stored_archive_invalid_reason(target) is None
    ):
        LOGGER.debug(
            "Executive order download skipped order_id=%s source_url=%s archive_path=%s",
            entry.entity_id,
            entry.pdf_url,
            target.as_posix(),
        )
        return prior

    content = _fetch_bytes(
        str(entry.pdf_url),
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    invalid_reason = _invalid_executive_order_content_reason(content)
    if invalid_reason is not None:
        raise ValueError(invalid_reason)
    write_target = _versioned_target_if_changed(target, content)
    tmp_path = temp_path_for(write_target)
    try:
        tmp_path.write_bytes(content)
        os.replace(tmp_path, write_target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    result = ExecutiveOrderDownload(
        **_manifest_metadata(entry, write_target),
        entry=entry,
        archive_path=write_target.as_posix(),
        sha256=sha256_file(write_target),
        downloaded_at=datetime.now(timezone.utc),
    )
    _append_manifest(manifest_path, result.model_dump(mode="json"))
    LOGGER.debug(
        "Executive order download succeeded order_id=%s source_url=%s archive_path=%s",
        entry.entity_id,
        entry.pdf_url,
        target.as_posix(),
    )
    return result


def extract_order_metadata(text: str, source_url: str) -> dict[str, Any]:
    """Extract executive order metadata from text and validate schema."""

    order_match = ORDER_RE.search(text)
    if not order_match:
        raise ValueError("executive order number not found")
    entity_id = f"EO-{order_match.group('year')}-{order_match.group('number')}"
    signed_date = _signed_date_from_order_text(text, entity_id)
    if not signed_date:
        raise ValueError("signed date not found")
    title = _line_value(text, "Title") or entity_id
    governor = _governor_from_text(text) or "Unknown Governor"
    summary = _line_value(text, "Summary") or title
    citations = [citation.canonical_form for citation in extract_crs_citations(text)]
    record = {
        "entity_type": "executive_order",
        "id": entity_id,
        "order_number": order_match.group(0),
        "title": title,
        "governor": governor,
        "signed_date": signed_date,
        "status": "active",
        "full_text": text,
        "summary": summary,
        "statutes_cited": citations,
        "subject_tags": [],
        "source_url": source_url,
        "confidence": {"overall": 0.8},
    }
    ExecutiveOrder.model_validate(record)
    return record


def _fetch_text(
    url: str,
    client: Any | None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> str:
    """Fetch text using an injected or temporary client."""

    response = _get(
        url,
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    return str(response.text)


def _fetch_bytes(
    url: str,
    client: Any | None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> bytes:
    """Fetch bytes using an injected or temporary client."""

    response = _get(
        url,
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    return bytes(response.content)


def _get(
    url: str,
    client: Any | None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> Any:
    """Issue one GET request with Geode's hardened retry client."""

    return polite_get(
        _session_or_client(client),
        url,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )


def _session_or_client(client: Any | None) -> Any:
    """Return an injected client or a browser-like HTTP session."""

    if client is not None:
        return client
    return build_session()


def _date_from_text(text: str) -> str | None:
    """Extract an ISO date from text."""

    match = DATE_RE.search(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    month_match = MONTH_DATE_RE.search(text)
    if not month_match:
        return None
    parsed = datetime.strptime(
        (
            f"{month_match.group('month')} {month_match.group('day')}, "
            f"{month_match.group('year')}"
        ),
        "%B %d, %Y",
    )
    return parsed.date().isoformat()


def _signed_date_from_order_text(text: str, entity_id: str) -> str | None:
    """Extract the signing date that belongs to the executive order itself."""

    text = _normalize_date_ocr_text(text)
    expected_year = _expected_year(entity_id)
    candidates: list[str] = []
    label_match = SIGNED_LABEL_RE.search(text)
    if label_match:
        candidates.append(
            (
                f"{label_match.group('year')}-{label_match.group('month')}-"
                f"{label_match.group('day')}"
            )
        )
    for block_match in SIGNED_BLOCK_RE.finditer(text):
        block = " ".join(block_match.group("block").split())
        candidates.extend(_signed_dates_from_block(block))
    selected = _first_expected_date(candidates, expected_year)
    if selected:
        return selected

    header = text[:1200]
    order_match = ORDER_RE.search(header)
    if order_match:
        selected = _first_expected_date(
            _month_dates_from_text(header[order_match.start() : order_match.start() + 400]),
            expected_year,
        )
        if selected:
            return selected

    return _first_expected_date(_month_dates_from_text(text), expected_year)


def _normalize_date_ocr_text(text: str) -> str:
    """Normalize common OCR spacing errors in executive-order date text."""

    text = re.sub(r"\b20\s*[IiLl1]\s*9\b", "2019", text)
    text = re.sub(r"\b20\s*[Oo0]\s*9\b", "2009", text)
    for month in (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ):
        spaced = r"\s*".join(re.escape(char) for char in month)
        text = re.sub(rf"\b{spaced}\b", month, text, flags=re.IGNORECASE)
    return text


def _signed_dates_from_block(text: str) -> list[str]:
    """Return candidate signing dates from a Governor signature block."""

    dates: list[str] = []
    for match in SIGNED_WRITTEN_DATE_RE.finditer(text):
        day = WRITTEN_ORDINAL_DAYS.get(" ".join(match.group("day").casefold().split()))
        if day is not None:
            dates.append(_month_day_year_to_iso(match.group("month"), day, match.group("year")))
    for match in SIGNED_NUMERIC_DATE_RE.finditer(text):
        dates.append(
            _month_day_year_to_iso(
                match.group("month"),
                int(match.group("day")),
                match.group("year"),
            )
        )
    dates.extend(_month_dates_from_text(text))
    return dates


def _month_dates_from_text(text: str) -> list[str]:
    """Return month-name dates as ISO strings."""

    dates: list[str] = []
    for match in MONTH_DATE_RE.finditer(text):
        dates.append(
            _month_day_year_to_iso(
                match.group("month"),
                int(match.group("day")),
                match.group("year"),
            )
        )
    return dates


def _month_day_year_to_iso(month: str, day: int, year: str) -> str:
    """Convert a month-name date to ISO format."""

    parsed = datetime.strptime(f"{month} {day}, {year}", "%B %d, %Y")
    return parsed.date().isoformat()


def _expected_year(entity_id: str) -> int | None:
    """Return the year embedded in a Geode executive-order ID."""

    match = re.match(r"^EO-(20\d{2})-\d{3}$", entity_id)
    return int(match.group(1)) if match else None


def _first_expected_date(dates: list[str], expected_year: int | None) -> str | None:
    """Return the first candidate matching the order year."""

    if expected_year is None:
        return dates[0] if dates else None
    for value in dates:
        if value.startswith(f"{expected_year}-"):
            return value
    return None


def _date_if_expected_year(value: str, entity_id: str) -> str | None:
    """Return a manifest date only when it matches the order year."""

    expected_year = _expected_year(entity_id)
    if expected_year is None or value.startswith(f"{expected_year}-"):
        return value
    return None


def _line_value(text: str, label: str) -> str | None:
    """Extract a labeled text line."""

    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _governor_from_text(text: str) -> str | None:
    """Extract the Governor name from common header or signature text."""

    labeled = _line_value(text, "Governor")
    if labeled:
        return labeled

    lines = [_clean_governor_line(line) for line in text.splitlines()]
    for line in lines[:25]:
        match = GOVERNOR_HEADER_RE.match(line)
        if match:
            return match.group("name").strip()

    for index, line in enumerate(lines):
        if line.casefold() != "governor" or index == 0:
            continue
        candidate = lines[index - 1]
        if _looks_like_person_name(candidate):
            return candidate
    return None


def _clean_governor_line(line: str) -> str:
    """Normalize one OCR line before Governor-name matching."""

    return " ".join(line.replace("|", " ").strip().split())


def _looks_like_person_name(value: str) -> bool:
    """Return whether a line looks like a source-stated person name."""

    if not value or any(char.isdigit() for char in value):
        return False
    parts = value.split()
    if len(parts) < 2 or len(parts) > 5:
        return False
    return all(part[:1].isupper() for part in parts)


def _append_manifest(path: Path, payload: dict[str, Any]) -> None:
    """Append one manifest row atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    tmp_path = temp_path_for(path)
    try:
        tmp_path.write_text("\n".join(existing) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _append_failure(path: Path, failure: ExecutiveOrderDownloadFailure) -> None:
    """Append one failed executive order download row atomically."""

    _append_manifest(path, failure.model_dump(mode="json"))


def _manifest_metadata(entry: ExecutiveOrderEntry, target: Path) -> dict[str, object]:
    """Return normalized executive-order raw-download metadata for a manifest row."""

    metadata = {
        "document_id": entry.entity_id,
        "document_name": entry.title,
        "source_url": str(entry.pdf_url),
        "source_page_url": str(entry.source_page_url),
        "source_format": source_format_from_extension(target.suffix),
        "signed_date": entry.signed_date,
    }
    return {
        **metadata,
        "missing_metadata": missing_metadata_fields(metadata),
    }


def _archive_path_for_order(entry: ExecutiveOrderEntry, archive_dir: Path) -> Path:
    """Return the raw archive path for one executive order."""

    return executive_order_pdf_path(archive_dir, entry.entity_id)


def _is_downloaded(
    manifest_path: Path,
    entry: ExecutiveOrderEntry,
    target: Path,
) -> bool:
    """Return whether an order has a matching archived file and manifest row."""

    prior = _manifest_entry_for(manifest_path, entry)
    if prior is None:
        return False
    prior_path = Path(prior.archive_path)
    project_root = target.parent.parent.parent
    candidate = prior_path if prior_path.is_absolute() else project_root / prior_path
    if not candidate.exists() or prior.sha256 != sha256_file(candidate):
        return False
    return _stored_archive_invalid_reason(candidate) is None


def _manifest_entry_for(
    manifest_path: Path,
    entry: ExecutiveOrderEntry,
) -> ExecutiveOrderDownload | None:
    """Return the latest successful manifest entry for one executive order."""

    if not manifest_path.exists():
        return None
    latest: ExecutiveOrderDownload | None = None
    for payload in iter_jsonl(manifest_path):
        manifest_entry = ExecutiveOrderDownload.model_validate(payload)
        if manifest_entry.entry.entity_id == entry.entity_id:
            latest = manifest_entry
    return latest


def _versioned_target_if_changed(target: Path, content: bytes) -> Path:
    """Return a timestamped target when an existing raw file would change."""

    if not target.exists() or target.read_bytes() == content:
        return target
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return target.with_name(f"{target.stem}_{stamp}{target.suffix}")


def _invalid_executive_order_content_reason(content: bytes) -> str | None:
    """Return why downloaded content is not a usable executive-order artifact."""

    preview = content[:65536].lower()
    if any(marker in preview for marker in INVALID_DOWNLOAD_BYTE_MARKERS):
        return "official source returned a sign-in or preview page instead of an executive order PDF"
    if content.startswith(b"%PDF"):
        text = _extract_pdf_text_from_bytes(content)
        lowered = text.casefold()
        if any(marker in lowered for marker in INVALID_DOWNLOAD_TEXT_MARKERS):
            return "official source returned a sign-in page rendered as a PDF"
    return None


def _stored_archive_invalid_reason(path: Path) -> str | None:
    """Return why an existing archived artifact is not usable source evidence."""

    try:
        return _invalid_executive_order_content_reason(path.read_bytes())
    except OSError as exc:
        return str(exc)


def _extract_pdf_text_from_bytes(content: bytes) -> str:
    """Extract text from PDF bytes for defensive content validation."""

    try:
        import fitz

        with fitz.open(stream=content, filetype="pdf") as document:
            pages: list[str] = []
            for page_index, page in enumerate(document):
                if page_index >= 3:
                    break
                pages.append(page.get_text("text"))
            return "\n".join(pages).strip()
    except Exception:
        return ""
