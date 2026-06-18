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
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

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
from geode.schemas.models import ExecutiveOrder
from geode.schemas.validators import require_official_source_url
from geode.utils.file_io import iter_jsonl
from geode.utils.hashing import sha256_file

LOGGER = logging.getLogger(__name__)

EXECUTIVE_ORDERS_URL = "https://www.colorado.gov/governor/executive-orders"
DOWNLOAD_MANIFEST = DOWNLOAD_MANIFEST_NAME
FAILURE_MANIFEST = FAILURE_MANIFEST_NAME
ORDER_RE = re.compile(r"\b(?:EO|D)\s*(?P<year>20\d{2})[-\s]?(?P<number>\d{3})\b")
DATE_RE = re.compile(r"\b(20\d{2})[-_/](\d{2})[-_/](\d{2})\b")


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

    html = _fetch_text(
        index_url,
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    parser = _LinkParser()
    parser.feed(html)
    entries = []
    for href, text in parser.links:
        absolute = urljoin(index_url, href)
        if ".pdf" not in absolute.lower():
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
                source_page_url=index_url,
                pdf_url=absolute,
            )
        )
    return entries


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
    if prior and target.exists() and prior.sha256 == sha256_file(target):
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
    tmp_path = temp_path_for(target)
    try:
        tmp_path.write_bytes(content)
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    result = ExecutiveOrderDownload(
        **_manifest_metadata(entry, target),
        entry=entry,
        archive_path=target.as_posix(),
        sha256=sha256_file(target),
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
    signed_date = _date_from_text(text)
    if not signed_date:
        raise ValueError("signed date not found")
    entity_id = f"EO-{order_match.group('year')}-{order_match.group('number')}"
    title = _line_value(text, "Title") or entity_id
    governor = _line_value(text, "Governor") or "Unknown Governor"
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
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _line_value(text: str, label: str) -> str | None:
    """Extract a labeled text line."""

    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else None


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
    return bool(prior and target.exists() and prior.sha256 == sha256_file(target))


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
