"""Colorado Code of Regulations discovery and download connector."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape as html_unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from geode.connectors.archive_paths import (
    DOWNLOAD_MANIFEST_NAME,
    ccr_rule_document_path,
    download_manifest_path,
    failure_manifest_path,
    temp_path_for,
)
from geode.connectors.download_metadata import (
    COLORADO_JURISDICTION,
    missing_metadata_fields,
    source_format_from_extension,
)
from geode.connectors.ccr_identity import canonical_ccr_id, canonical_ccr_number
from geode.net.http_client import (
    DEFAULT_MAX_RETRY_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    GeodeBlockedError,
    GeodeFetchError,
    GeodeHttpAttempt,
    GeodeHttpClient,
    GeodeHttpClientConfig,
    GeodeThrottle,
    GeodeThrottleConfig,
)
from geode.schemas.validators import require_official_source_url
from geode.utils.hashing import sha256_file

LOGGER = logging.getLogger(__name__)

CCR_BASE_URL = "https://www.sos.state.co.us"
SOS_HOME_URL = f"{CCR_BASE_URL}/"
GOOGLE_REFERER = "https://www.google.com/"
CCR_WELCOME_URL = f"{CCR_BASE_URL}/CCR/Welcome.do"
CCR_SEARCH_URL = CCR_WELCOME_URL
CCR_DEPARTMENT_LIST_URL = f"{CCR_BASE_URL}/CCR/NumericalDeptList.do"
DOWNLOAD_MANIFEST = DOWNLOAD_MANIFEST_NAME
CHECKPOINT_NAME = "download_checkpoint.json"
RUN_LOG_NAME = "download_run_log.jsonl"
SUMMARY_NAME = "download_summary.json"
CCR_NUMBER_RE = re.compile(r"\b(\d+\s+CCR\s+\d+-\d+(?:-\d+)?)\b", re.IGNORECASE)
CCR_RETRY_STATUSES = frozenset({429, 502, 503, 504})
CCR_FORENSIC_HEADER_NAMES = (
    "content-type",
    "content-length",
    "server",
    "date",
    "set-cookie",
    "location",
    "retry-after",
)
CCR_BLOCKED_TEXT_RE = re.compile(
    r"("
    r"access\s+denied|forbidden|request\s+rejected|not\s+authorized|"
    r"captcha|bot\s+detection|blocked|enable\s+cookies|challenge|"
    r"incapsula|akamai|cloudflare|sucuri|attention\s+required"
    r")",
    re.IGNORECASE,
)
CCR_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/octet-stream",
    "application/download",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "binary/octet-stream",
}
CCR_HTMLISH_CONTENT_TYPES = {
    "application/xhtml+xml",
    "application/xml",
    "text/html",
    "text/plain",
    "text/xml",
}
CCR_HTML_SIGNATURES = (b"<!doctype html", b"<html", b"<head", b"<body")
CCR_PREVIEW_LIMIT_CHARS = 500


class CCRDownloadError(RuntimeError):
    """Raised when a CCR rule cannot be downloaded after retries."""


class CCRBlockedResponseError(CCRDownloadError):
    """Raised when CCR acquisition receives a blocked or challenge response."""


@dataclass(frozen=True)
class _DiscoveryResponse:
    requested_url: str
    final_url: str
    status_code: int | None
    text: str


@dataclass
class _RunAccounting:
    """Mutable accounting for one CCR bulk download run."""

    retry_count: int = 0

    def record_retry(self, attempt: GeodeHttpAttempt) -> None:
        """Record one retry attempt emitted by the shared HTTP client."""

        self.retry_count += 1


@dataclass(frozen=True)
class CCRDownloadState:
    """Reconciled download state for one CCR archive item."""

    document_id: str
    status: str
    archive_path: Path
    file_exists: bool
    checksum_matches: bool = False
    repaired_manifest: bool = False
    manifest_status: str | None = None
    error: str | None = None


class CCRRuleEntry(BaseModel):
    """Catalog entry for one CCR rule source document."""

    model_config = ConfigDict(extra="forbid")

    ccr_number: str = Field(min_length=1)
    department: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    source_page_url: HttpUrl
    browse_source_url: HttpUrl | None = None
    pdf_url: HttpUrl | None = None
    docx_url: HttpUrl | None = None

    @field_validator("source_page_url", "browse_source_url", "pdf_url", "docx_url")
    @classmethod
    def validate_source_urls(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require Secretary of State CCR URLs."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value

    @property
    def canonical_id(self) -> str:
        """Return Geode-style CCR ID."""

        return canonical_ccr_id(
            self.ccr_number,
            source_page_url=self.source_page_url,
            document_url=self.pdf_url or self.docx_url,
        )

    @property
    def preferred_url(self) -> str:
        """Return PDF URL when available, otherwise DOC/DOCX URL."""

        if self.pdf_url is not None:
            return str(self.pdf_url)
        if self.docx_url is not None:
            return str(self.docx_url)
        raise CCRDownloadError(f"no downloadable URL for {self.ccr_number}")

    @property
    def preferred_extension(self) -> str:
        """Return the archive extension for the preferred source."""

        preferred_url = self.preferred_url
        parsed = urlparse(preferred_url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix in {".doc", ".docx", ".pdf"}:
            return suffix
        if self.pdf_url is not None and preferred_url == str(self.pdf_url):
            return ".pdf"
        if self.docx_url is not None and preferred_url == str(self.docx_url):
            return ".doc"
        return ".pdf"


class DownloadManifestEntry(BaseModel):
    """One raw CCR download manifest entry."""

    model_config = ConfigDict(extra="forbid")

    jurisdiction: str = COLORADO_JURISDICTION
    source_type: str = "regulation_rule"
    document_id: str = ""
    document_name: str | None = None
    ccr_number: str
    department: str | None = None
    agency: str | None = None
    source_url: HttpUrl
    source_page_url: HttpUrl | None = None
    source_format: str | None = None
    archive_path: str
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    downloaded_at: datetime
    effective_date: str | None = None
    publication_date: str | None = None
    status: str
    error: str | None = None
    missing_metadata: list[str] = Field(default_factory=list)

    @field_validator("source_url", "source_page_url", mode="before")
    @classmethod
    def normalize_manifest_urls(cls, value: object) -> object:
        """Store manifest URLs with canonical query separators."""

        return _canonical_source_url(value)

    @field_validator("source_url", "source_page_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official source URLs."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value


class CCRDownloadFailure(BaseModel):
    """One failed CCR download record for the separate failure report."""

    model_config = ConfigDict(extra="forbid")

    jurisdiction: str = COLORADO_JURISDICTION
    source_type: str = "regulation_rule"
    document_id: str = ""
    ccr_number: str
    department: str | None = None
    agency: str | None = None
    source_url: HttpUrl
    source_page_url: HttpUrl | None = None
    archive_path: str
    failed_at: datetime
    status: str = "failed_permanent"
    blocked: bool = False
    error: str

    @field_validator("source_url", "source_page_url", mode="before")
    @classmethod
    def normalize_failure_urls(cls, value: object) -> object:
        """Store failure URLs with canonical query separators."""

        return _canonical_source_url(value)

    @field_validator("source_url", "source_page_url")
    @classmethod
    def validate_failure_source_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official source URLs."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value


class DownloadReport(BaseModel):
    """Summary from a CCR download batch."""

    model_config = ConfigDict(extra="forbid")

    discovered: int = Field(ge=0)
    attempted: int = Field(ge=0)
    downloaded: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
    permanent_failed: int = Field(ge=0)
    blocked: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    network_attempts: int = Field(ge=0)
    manifest_path: str
    failure_manifest_path: str
    checkpoint_path: str
    summary_path: str
    log_path: str
    paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class _Link:
    """Internal HTML link record."""

    def __init__(self, href: str, text: str) -> None:
        """Create a link record."""

        self.href = href
        self.text = text


class _LinkParser(HTMLParser):
    """Small stdlib anchor parser for CCR browse pages."""

    def __init__(self) -> None:
        """Initialize parser state."""

        super().__init__()
        self.links: list[_Link] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Capture anchor starts."""

        if tag.lower() != "a":
            return
        attrs_dict = {key.lower(): value for key, value in attrs}
        href = attrs_dict.get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        """Capture page and anchor text."""

        self.text_parts.append(data)
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Capture anchor ends."""

        if tag.lower() == "a" and self._current_href is not None:
            text = " ".join(part.strip() for part in self._current_text if part.strip())
            self.links.append(_Link(self._current_href, text))
            self._current_href = None
            self._current_text = []


def discover_all_rules(
    client: Any | None = None,
    start_url: str = CCR_DEPARTMENT_LIST_URL,
    max_agencies: int | None = None,
    request_delay: float = 0.0,
    request_delay_jitter_seconds: float = 0.0,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> list[CCRRuleEntry]:
    """Crawl CCR browse pages and catalog rule document links."""

    _validate_delay_options(request_delay, request_delay_jitter_seconds)
    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    discovery_throttle = GeodeThrottle(
        GeodeThrottleConfig(
            delay_seconds=request_delay,
            jitter_seconds=request_delay_jitter_seconds,
            label="ccr_discovery",
        )
    )
    department_page = _fetch_discovery_response(
        start_url,
        session,
        referer=CCR_WELCOME_URL,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    agency_links = _agency_links(department_page.text, start_url)
    raw_agency_candidates = _agency_candidate_count(department_page.text, start_url)
    _log_discovery_diagnostics(
        "department",
        department_page,
        _department_page_markers(department_page.text),
        raw_agency_candidates,
        len(agency_links),
        level=logging.INFO,
    )
    selected_agency_links = agency_links[:max_agencies]
    entries: list[CCRRuleEntry] = []
    raw_rule_candidates_total = 0
    filtered_rule_candidates_total = 0
    downloadable_rule_candidates_total = 0
    for index, (agency_url, department, agency) in enumerate(selected_agency_links):
        agency_page = _fetch_discovery_response(
            agency_url,
            session,
            referer=start_url,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
        )
        raw_rule_candidates = _rule_candidate_count(agency_page.text, agency_url)
        filtered_rule_candidates = _rule_entries_from_page(
            agency_page.text,
            agency_url,
            department,
            agency,
        )
        downloadable_rule_candidates = _resolve_rule_info_candidates(
            filtered_rule_candidates,
            session,
            request_delay=request_delay,
            request_delay_jitter_seconds=request_delay_jitter_seconds,
            throttle=discovery_throttle,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
        )
        raw_rule_candidates_total += raw_rule_candidates
        filtered_rule_candidates_total += len(filtered_rule_candidates)
        downloadable_rule_candidates_total += len(downloadable_rule_candidates)
        entries.extend(downloadable_rule_candidates)
        _log_discovery_diagnostics(
            "agency",
            agency_page,
            _agency_page_markers(agency_page.text),
            raw_rule_candidates,
            len(filtered_rule_candidates),
            resolved_count=len(downloadable_rule_candidates),
            context=f"department={department} agency={agency}",
            level=logging.DEBUG,
        )
        if index < len(selected_agency_links) - 1:
            discovery_throttle.wait(reason="ccr_agency_page")
    LOGGER.info(
        "CCR discovery summary agencies=%s raw_rule_candidates=%s "
        "filtered_rule_candidates=%s downloadable_rule_candidates=%s",
        len(selected_agency_links),
        raw_rule_candidates_total,
        filtered_rule_candidates_total,
        downloadable_rule_candidates_total,
    )
    if not entries:
        LOGGER.warning(
            "CCR discovery returned zero downloadable entries start_url=%s "
            "agency_candidates=%s raw_rule_candidates=%s filtered_rule_candidates=%s",
            start_url,
            len(agency_links),
            raw_rule_candidates_total,
            filtered_rule_candidates_total,
        )
    return entries


def iter_rule_index_entries(
    client: Any | None = None,
    start_url: str = CCR_DEPARTMENT_LIST_URL,
    max_agencies: int | None = None,
    max_items: int | None = None,
    request_delay: float = 0.0,
    request_delay_jitter_seconds: float = 0.0,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> Iterator[CCRRuleEntry]:
    """Yield CCR rule index entries from department and agency browse pages.

    This phase intentionally stops before rule-info detail resolution or document
    retrieval so bulk workflows can persist and resume a deterministic work queue.
    """

    _validate_max_downloads(max_items)
    _validate_delay_options(request_delay, request_delay_jitter_seconds)
    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    discovery_throttle = GeodeThrottle(
        GeodeThrottleConfig(
            delay_seconds=request_delay,
            jitter_seconds=request_delay_jitter_seconds,
            label="ccr_index",
        )
    )
    department_page = _fetch_discovery_response(
        start_url,
        session,
        referer=CCR_WELCOME_URL,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    agency_links = _agency_links(department_page.text, start_url)
    selected_agency_links = agency_links[:max_agencies]
    yielded = 0
    for index, (agency_url, department, agency) in enumerate(selected_agency_links):
        agency_page = _fetch_discovery_response(
            agency_url,
            session,
            referer=start_url,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
        )
        entries = _rule_entries_from_page(agency_page.text, agency_url, department, agency)
        LOGGER.debug(
            "CCR index agency department=%s agency=%s entries=%s url=%s",
            department,
            agency,
            len(entries),
            agency_url,
        )
        for entry in entries:
            if max_items is not None and yielded >= max_items:
                return
            yielded += 1
            yield entry
        if index < len(selected_agency_links) - 1:
            discovery_throttle.wait(reason="ccr_index_agency_page")


def resolve_rule_info_page(
    entry: CCRRuleEntry | dict[str, Any],
    client: Any | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> CCRRuleEntry:
    """Resolve one SOS rule-info page into downloadable DOCX/PDF URLs."""

    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    rule = _coerce_rule_entry(entry)
    html = _fetch_text(
        str(rule.source_page_url),
        session,
        referer=CCR_DEPARTMENT_LIST_URL,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    parser = _parse_links(html)
    pdf_url = str(rule.pdf_url) if rule.pdf_url is not None else None
    docx_url = str(rule.docx_url) if rule.docx_url is not None else None
    for link in parser.links:
        if _is_javascript_href(link.href):
            continue
        absolute = urljoin(str(rule.source_page_url), link.href)
        lower_href = absolute.lower()
        if _looks_docx(lower_href):
            docx_url = absolute
        elif _looks_pdf(lower_href):
            pdf_url = absolute
    script_pdf_url, script_docx_url = _download_urls_from_rule_scripts(
        html,
        str(rule.source_page_url),
    )
    pdf_url = pdf_url or script_pdf_url
    docx_url = docx_url or script_docx_url
    ccr_number = (
        canonical_ccr_number(rule.ccr_number)
        or canonical_ccr_number(rule.source_page_url, pdf_url, docx_url, html)
        or rule.ccr_number
    )
    return CCRRuleEntry(
        ccr_number=ccr_number,
        department=rule.department,
        agency=rule.agency,
        source_page_url=rule.source_page_url,
        browse_source_url=rule.browse_source_url,
        pdf_url=pdf_url,
        docx_url=docx_url,
    )


def resolve_rule_info_pages(
    entries: list[CCRRuleEntry | dict[str, Any]],
    client: Any | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> list[CCRRuleEntry]:
    """Resolve multiple SOS rule-info pages into downloadable rule entries."""

    return [
        resolve_rule_info_page(
            entry,
            client=client,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
        )
        for entry in entries
    ]


def download_rule(
    entry: CCRRuleEntry,
    archive_dir: Path,
    client: Any | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> Path:
    """Download one CCR rule to the raw archive, preferring PDF over DOC/DOCX."""

    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = download_manifest_path(archive_dir)
    target = ccr_rule_document_path(archive_dir, entry.canonical_id, entry.preferred_extension)
    state = reconcile_download_state(manifest_path, entry, target)
    if state.status == "downloaded":
        LOGGER.debug(
            "CCR download skipped document_id=%s ccr_number=%s source_url=%s "
            "archive_path=%s repaired_manifest=%s",
            entry.canonical_id,
            entry.ccr_number,
            entry.preferred_url,
            state.archive_path.as_posix(),
            state.repaired_manifest,
        )
        return state.archive_path

    try:
        response = _fetch_bytes(
            entry.preferred_url,
            session,
            referer=str(entry.source_page_url),
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
        )
    except CCRBlockedResponseError as exc:
        _record_download_failure(manifest_path, entry, target, exc)
        LOGGER.warning(
            "CCR download blocked ccr_number=%s source_url=%s archive_path=%s error=%s",
            entry.ccr_number,
            entry.preferred_url,
            target.as_posix(),
            exc,
        )
        raise
    except Exception as exc:
        _record_download_failure(manifest_path, entry, target, exc)
        LOGGER.warning(
            "CCR download failed ccr_number=%s source_url=%s archive_path=%s error=%s",
            entry.ccr_number,
            entry.preferred_url,
            target.as_posix(),
            exc,
        )
        raise CCRDownloadError(str(exc)) from exc

    actual_extension = _extension_from_signature(response)
    if actual_extension is not None and target.suffix.lower() != actual_extension:
        target = target.with_suffix(actual_extension)
    if state.manifest_status is not None:
        target = _versioned_target_if_changed(target, response)

    tmp_path = temp_path_for(target)
    try:
        tmp_path.write_bytes(response)
        _replace_artifact(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    digest = sha256_file(target)
    _append_manifest(
        manifest_path,
        DownloadManifestEntry(
            **_manifest_metadata(entry, target),
            ccr_number=entry.ccr_number,
            source_url=entry.preferred_url,
            archive_path=target.as_posix(),
            sha256=digest,
            size_bytes=target.stat().st_size,
            downloaded_at=datetime.now(timezone.utc),
            status="downloaded",
        ),
    )
    LOGGER.debug(
        "CCR download succeeded ccr_number=%s source_url=%s archive_path=%s",
        entry.ccr_number,
        entry.preferred_url,
        target.as_posix(),
    )
    return target


def _versioned_target_if_changed(target: Path, content: bytes) -> Path:
    """Return a versioned target path when a source artifact changed."""

    if not target.exists() or target.read_bytes() == content:
        return target
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = target.with_name(f"{target.stem}_{stamp}{target.suffix}")
    counter = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.stem}_{stamp}_{counter}{target.suffix}")
        counter += 1
    return candidate


def download_all_rules(
    archive_dir: Path,
    delay: float = 1.0,
    client: Any | None = None,
    discovery_delay: float = 0.0,
    delay_jitter_seconds: float = 0.0,
    discovery_delay_jitter_seconds: float = 0.0,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
    max_downloads: int | None = None,
) -> DownloadReport:
    """Discover and download all CCR rules with rate limiting and resume support."""

    _validate_max_downloads(max_downloads)
    _validate_delay_options(delay, delay_jitter_seconds)
    _validate_delay_options(discovery_delay, discovery_delay_jitter_seconds)
    archive_dir.mkdir(parents=True, exist_ok=True)
    accounting = _RunAccounting()
    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
        retry_hook=accounting.record_retry,
    )
    manifest_path = download_manifest_path(archive_dir)
    failures_path = failure_manifest_path(archive_dir)
    checkpoint_path = archive_dir / CHECKPOINT_NAME
    summary_path = archive_dir / SUMMARY_NAME
    log_path = archive_dir / RUN_LOG_NAME
    download_throttle = GeodeThrottle(
        GeodeThrottleConfig(
            delay_seconds=delay,
            jitter_seconds=delay_jitter_seconds,
            label="ccr_document",
        )
    )
    _append_run_log(log_path, {"event": "started", "archive_dir": archive_dir.as_posix()})
    entries = discover_all_rules(
        client=session,
        request_delay=discovery_delay,
        request_delay_jitter_seconds=discovery_delay_jitter_seconds,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    LOGGER.info(
        "CCR bulk download discovered=%s archive_dir=%s",
        len(entries),
        archive_dir.as_posix(),
    )
    _append_run_log(
        log_path,
        {"event": "discovered", "count": len(entries), "archive_dir": archive_dir.as_posix()},
    )
    paths: list[str] = []
    errors: list[str] = []
    downloaded = 0
    skipped = 0
    failed = 0
    blocked = 0
    permanent_failed = 0
    network_attempts = 0
    manifest_path = download_manifest_path(archive_dir)
    _rewrite_manifest_urls(manifest_path)
    paused = False
    for index, entry in enumerate(entries):
        target = ccr_rule_document_path(archive_dir, entry.canonical_id, entry.preferred_extension)
        already_downloaded = _is_downloaded(manifest_path, entry, target)
        if already_downloaded:
            paths.append(target.as_posix())
            skipped += 1
            _append_run_log(log_path, _run_event("skipped", entry, index, target))
            _write_checkpoint(
                checkpoint_path,
                _checkpoint_payload(
                    "running",
                    index=index,
                    total=len(entries),
                    entry=entry,
                    downloaded=downloaded,
                    skipped=skipped,
                    failed=failed,
                    blocked=blocked,
                    network_attempts=network_attempts,
                    retry_count=accounting.retry_count,
                ),
            )
            continue
        if max_downloads is not None and network_attempts >= max_downloads:
            LOGGER.info(
                "CCR bulk download paused max_downloads=%s archive_dir=%s",
                max_downloads,
                archive_dir.as_posix(),
            )
            paused = True
            _append_run_log(
                log_path,
                {
                    "event": "paused",
                    "max_downloads": max_downloads,
                    "network_attempts": network_attempts,
                },
            )
            break
        network_attempts += 1
        try:
            path = download_rule(
                entry,
                archive_dir,
                client=session,
                max_retries=max_retries,
                base_delay=base_delay,
                timeout_seconds=timeout_seconds,
                max_retry_delay_seconds=max_retry_delay_seconds,
                retry_jitter_ratio=retry_jitter_ratio,
            )
        except CCRBlockedResponseError as exc:
            failed += 1
            blocked += 1
            errors.append(f"{entry.ccr_number}: {exc}")
            _append_run_log(log_path, _run_event("blocked", entry, index, target, exc))
            _write_checkpoint(
                checkpoint_path,
                _checkpoint_payload(
                    "running",
                    index=index,
                    total=len(entries),
                    entry=entry,
                    downloaded=downloaded,
                    skipped=skipped,
                    failed=failed,
                    blocked=blocked,
                    network_attempts=network_attempts,
                    retry_count=accounting.retry_count,
                ),
            )
        except CCRDownloadError as exc:
            failed += 1
            permanent_failed += 1
            errors.append(f"{entry.ccr_number}: {exc}")
            _append_run_log(log_path, _run_event("failed", entry, index, target, exc))
            _write_checkpoint(
                checkpoint_path,
                _checkpoint_payload(
                    "running",
                    index=index,
                    total=len(entries),
                    entry=entry,
                    downloaded=downloaded,
                    skipped=skipped,
                    failed=failed,
                    blocked=blocked,
                    network_attempts=network_attempts,
                    retry_count=accounting.retry_count,
                ),
            )
        else:
            paths.append(path.as_posix())
            downloaded += 1
            _append_run_log(log_path, _run_event("downloaded", entry, index, path))
            _write_checkpoint(
                checkpoint_path,
                _checkpoint_payload(
                    "running",
                    index=index,
                    total=len(entries),
                    entry=entry,
                    downloaded=downloaded,
                    skipped=skipped,
                    failed=failed,
                    blocked=blocked,
                    network_attempts=network_attempts,
                    retry_count=accounting.retry_count,
                ),
            )
        if (
            index < len(entries) - 1
            and (max_downloads is None or network_attempts < max_downloads)
        ):
            download_throttle.wait(reason="ccr_document_download")
    report = DownloadReport(
        discovered=len(entries),
        attempted=downloaded + skipped + failed,
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        permanent_failed=permanent_failed,
        blocked=blocked,
        retry_count=accounting.retry_count,
        network_attempts=network_attempts,
        manifest_path=manifest_path.as_posix(),
        failure_manifest_path=failures_path.as_posix(),
        checkpoint_path=checkpoint_path.as_posix(),
        summary_path=summary_path.as_posix(),
        log_path=log_path.as_posix(),
        paths=paths,
        errors=errors,
    )
    _write_checkpoint(
        checkpoint_path,
        {
            **_checkpoint_payload(
                "paused" if paused else "completed",
                index=max(downloaded + skipped + failed - 1, -1),
                total=len(entries),
                entry=None,
                downloaded=downloaded,
                skipped=skipped,
                failed=failed,
                blocked=blocked,
                network_attempts=network_attempts,
                retry_count=accounting.retry_count,
            ),
            "summary_path": summary_path.as_posix(),
        },
    )
    _write_summary_report(summary_path, report)
    _append_run_log(log_path, {"event": "summary", **report.model_dump(mode="json")})
    log_summary = LOGGER.warning if failed else LOGGER.info
    log_summary(
        "CCR bulk download summary attempted=%s succeeded=%s failed=%s skipped=%s "
        "blocked=%s retries=%s archive_dir=%s manifest=%s failures=%s summary=%s",
        report.attempted,
        report.downloaded,
        report.failed,
        report.skipped,
        report.blocked,
        report.retry_count,
        archive_dir.as_posix(),
        report.manifest_path,
        report.failure_manifest_path,
        report.summary_path,
    )
    return report


def _validate_max_downloads(max_downloads: int | None) -> None:
    """Validate an optional per-run network-attempt cap."""

    if max_downloads is not None and max_downloads < 0:
        raise ValueError("max_downloads cannot be negative")


def _validate_delay_options(delay_seconds: float, jitter_seconds: float) -> None:
    """Validate CCR throttle options."""

    if delay_seconds < 0:
        raise ValueError("delay cannot be negative")
    if jitter_seconds < 0:
        raise ValueError("delay jitter cannot be negative")


def _run_event(
    event: str,
    entry: CCRRuleEntry,
    index: int,
    path: Path,
    error: Exception | None = None,
) -> dict[str, object]:
    """Return one JSON-serializable CCR run-log event."""

    payload: dict[str, object] = {
        "event": event,
        "index": index,
        "ccr_number": entry.ccr_number,
        "document_id": entry.canonical_id,
        "source_url": _canonical_source_url(entry.preferred_url),
        "source_page_url": _canonical_source_url(str(entry.source_page_url)),
        "archive_path": path.as_posix(),
    }
    if error is not None:
        payload["error"] = str(error)
        payload["blocked"] = isinstance(error, CCRBlockedResponseError)
    return payload


def _checkpoint_payload(
    status: str,
    *,
    index: int,
    total: int,
    entry: CCRRuleEntry | None,
    downloaded: int,
    skipped: int,
    failed: int,
    blocked: int,
    network_attempts: int,
    retry_count: int,
) -> dict[str, object]:
    """Return one checkpoint payload for an in-progress or completed run."""

    payload: dict[str, object] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_index": index,
        "total_discovered": total,
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "blocked": blocked,
        "network_attempts": network_attempts,
        "retry_count": retry_count,
    }
    if entry is not None:
        payload["last_ccr_number"] = entry.ccr_number
        payload["last_document_id"] = entry.canonical_id
    return payload


def _write_checkpoint(path: Path, payload: dict[str, object]) -> None:
    """Write the latest CCR checkpoint atomically."""

    _write_json_artifact(path, payload)


def _write_summary_report(path: Path, report: DownloadReport) -> None:
    """Write a CCR run summary report atomically."""

    _write_json_artifact(path, report.model_dump(mode="json"))


def _append_run_log(path: Path, payload: dict[str, object]) -> None:
    """Append one CCR run-log event atomically."""

    event = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    _append_jsonl_artifact(path, event)


def _write_json_artifact(path: Path, payload: dict[str, object]) -> None:
    """Write a JSON artifact atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = temp_path_for(path)
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _replace_artifact(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _append_jsonl_artifact(path: Path, payload: dict[str, object]) -> None:
    """Append one JSON object to a JSONL artifact atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    tmp_path = temp_path_for(path)
    try:
        tmp_path.write_text("\n".join(existing) + "\n", encoding="utf-8", newline="\n")
        _replace_artifact(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _coerce_rule_entry(entry: CCRRuleEntry | dict[str, Any]) -> CCRRuleEntry:
    """Coerce downloader handoff dictionaries into CCR rule entries."""

    if isinstance(entry, CCRRuleEntry):
        return entry
    allowed = {
        "ccr_number",
        "department",
        "agency",
        "source_page_url",
        "browse_source_url",
        "pdf_url",
        "docx_url",
    }
    return CCRRuleEntry.model_validate(
        {key: value for key, value in entry.items() if key in allowed}
    )


def _agency_links(html: str, base_url: str) -> list[tuple[str, str, str]]:
    """Extract agency browse links from the department list page."""

    parser = _parse_links(html)
    page_text = " ".join(parser.text_parts)
    department_by_prefix = _department_map(page_text)
    links: list[tuple[str, str, str]] = []
    for link in parser.links:
        absolute = urljoin(base_url, link.href)
        if "NumericalCCRDocList.do" not in absolute:
            continue
        agency = _normalize_space(link.text)
        prefix = agency.split(" ", 1)[0]
        query = parse_qs(urlparse(absolute).query)
        department = query.get("deptName", [department_by_prefix.get(prefix, "")])[0]
        agency = query.get("agencyName", [agency])[0]
        department = _normalize_space(department or "Unknown Department")
        agency = _normalize_space(agency)
        links.append((absolute, department, agency))
    return links


def _agency_candidate_count(html: str, base_url: str) -> int:
    """Return raw agency-link candidates before full agency filtering."""

    parser = _parse_links(html)
    return sum(
        1
        for link in parser.links
        if "NumericalCCRDocList.do" in urljoin(base_url, link.href)
    )


def _rule_candidate_count(html: str, base_url: str) -> int:
    """Return raw rule-link candidates before full rule filtering."""

    parser = _parse_links(html)
    return sum(
        1
        for link in parser.links
        if _looks_rule_info(urljoin(base_url, link.href).lower())
        or _looks_downloadable(urljoin(base_url, link.href).lower())
    )


def _department_page_markers(html: str) -> dict[str, bool]:
    """Return expected department-list page markers."""

    return {
        "browse_rules": "Browse Rules" in html or "Browse rules" in html,
        "agency_links": "NumericalCCRDocList.do" in html,
        "ccr_application": "/CCR/" in html,
    }


def _agency_page_markers(html: str) -> dict[str, bool]:
    """Return expected agency rule-list page markers."""

    return {
        "rule_info_links": "DisplayRule.do" in html,
        "direct_doc_links": "GenerateRuleDoc" in html,
        "direct_pdf_links": "GenerateRulePdf" in html,
        "ccr_numbers": bool(CCR_NUMBER_RE.search(unquote(html))),
    }


def _log_discovery_diagnostics(
    page_kind: str,
    response: _DiscoveryResponse,
    markers: dict[str, bool],
    raw_candidates: int,
    filtered_candidates: int,
    *,
    resolved_count: int | None = None,
    context: str = "",
    level: int = logging.INFO,
) -> None:
    """Log targeted CCR discovery diagnostics for one fetched page."""

    resolved = "" if resolved_count is None else f" resolved_candidates={resolved_count}"
    context_text = "" if not context else f" {context}"
    LOGGER.log(
        level,
        "CCR discovery page=%s requested_url=%s final_url=%s status=%s "
        "markers=%s raw_candidates=%s filtered_candidates=%s%s%s",
        page_kind,
        response.requested_url,
        response.final_url,
        response.status_code,
        ",".join(f"{key}:{value}" for key, value in sorted(markers.items())),
        raw_candidates,
        filtered_candidates,
        resolved,
        context_text,
    )


def _rule_entries_from_page(
    html: str,
    source_page_url: str,
    department: str,
    agency: str,
) -> list[CCRRuleEntry]:
    """Extract rule PDF/DOCX links from one agency page."""

    parser = _parse_links(html)
    grouped: dict[str, dict[str, str]] = {}
    for link in parser.links:
        if _is_javascript_href(link.href):
            continue
        absolute = urljoin(source_page_url, link.href)
        lower_href = absolute.lower()
        if _looks_rule_info(lower_href):
            ccr_number = _ccr_number_from_text(f"{link.text} {absolute}")
            if ccr_number is None:
                continue
            grouped.setdefault(ccr_number, {})["source_page_url"] = absolute
            continue
        if not _looks_downloadable(lower_href):
            continue
        ccr_number = _ccr_number_from_text(f"{link.text} {absolute}")
        if ccr_number is None:
            continue
        item = grouped.setdefault(ccr_number, {})
        if _looks_docx(lower_href):
            item["docx_url"] = absolute
        elif _looks_pdf(lower_href):
            item["pdf_url"] = absolute
    entries = []
    for ccr_number, urls in sorted(grouped.items(), key=lambda item: _ccr_sort_key(item[0])):
        entries.append(
            CCRRuleEntry(
                ccr_number=ccr_number,
                department=department,
                agency=agency,
                source_page_url=urls.get("source_page_url", source_page_url),
                browse_source_url=source_page_url,
                pdf_url=urls.get("pdf_url"),
                docx_url=urls.get("docx_url"),
            )
        )
    return entries


def _resolve_rule_info_candidates(
    entries: list[CCRRuleEntry],
    session: Any,
    request_delay: float = 0.0,
    request_delay_jitter_seconds: float = 0.0,
    throttle: GeodeThrottle | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> list[CCRRuleEntry]:
    """Resolve rule-info candidates into entries with download URLs."""

    _validate_delay_options(request_delay, request_delay_jitter_seconds)
    page_throttle = throttle or GeodeThrottle(
        GeodeThrottleConfig(
            delay_seconds=request_delay,
            jitter_seconds=request_delay_jitter_seconds,
            label="ccr_rule_info",
        )
    )
    resolved_entries: list[CCRRuleEntry] = []
    for index, entry in enumerate(entries):
        if entry.pdf_url is not None or entry.docx_url is not None:
            resolved_entries.append(entry)
        else:
            try:
                resolved = resolve_rule_info_page(
                    entry,
                    client=session,
                    max_retries=max_retries,
                    base_delay=base_delay,
                    timeout_seconds=timeout_seconds,
                    max_retry_delay_seconds=max_retry_delay_seconds,
                    retry_jitter_ratio=retry_jitter_ratio,
                )
            except Exception as exc:
                LOGGER.warning(
                    "CCR rule-info resolution failed ccr_number=%s source_page_url=%s "
                    "error=%s",
                    entry.ccr_number,
                    entry.source_page_url,
                    exc,
                )
            else:
                if resolved.pdf_url is not None or resolved.docx_url is not None:
                    resolved_entries.append(resolved)
                else:
                    LOGGER.warning(
                        "CCR rule-info page had no downloadable URLs ccr_number=%s "
                        "source_page_url=%s",
                        entry.ccr_number,
                        entry.source_page_url,
                    )
        if index < len(entries) - 1:
            page_throttle.wait(reason="ccr_rule_info_page")
    return resolved_entries


def _ccr_sort_key(ccr_number: str) -> tuple[int, int, int]:
    """Return a natural sort key for CCR numbers."""

    match = re.search(r"(\d+)\s+CCR\s+(\d+)-(\d+)", ccr_number, re.IGNORECASE)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def _department_map(page_text: str) -> dict[str, str]:
    """Build a CCR prefix to department-name map from browse page text."""

    departments: dict[str, str] = {}
    pattern = re.compile(r"\b(\d{3,4})\s+(Department [A-Za-z ,&'-]+)")
    for match in pattern.finditer(page_text):
        departments.setdefault(match.group(1), _normalize_space(match.group(2)))
    return departments


def _parse_links(html: str) -> _LinkParser:
    """Parse links from HTML."""

    parser = _LinkParser()
    parser.feed(html)
    return parser


def _ccr_number_from_text(text: str) -> str | None:
    """Extract a CCR number from link text or URL."""

    decoded = unquote(text).replace("_", " ").replace("%20", " ")
    match = CCR_NUMBER_RE.search(decoded)
    if not match:
        return None
    return _normalize_space(match.group(1)).upper().replace(" CCR ", " CCR ")


def _looks_downloadable(lower_url: str) -> bool:
    """Return whether a URL looks like a CCR source document."""

    return _looks_docx(lower_url) or _looks_pdf(lower_url)


def _looks_rule_info(lower_url: str) -> bool:
    """Return whether a URL points to an SOS CCR rule-info page."""

    return "displayrule.do" in lower_url and "action=ruleinfo" in lower_url


def _download_urls_from_rule_scripts(
    html: str,
    source_page_url: str,
) -> tuple[str | None, str | None]:
    """Extract live SOS PDF/DOCX URLs from JavaScript download calls."""

    pdf_url: str | None = None
    docx_url: str | None = None
    pattern = re.compile(
        r"OpenRule(?P<kind>Window|WordVersion)\(\s*['\"](?P<version>\d+)['\"]\s*,"
        r"\s*['\"](?P<file_name>[^'\"]+)['\"]\s*\)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        version = quote(match.group("version"))
        file_name = quote(match.group("file_name"))
        base = f"/CCR/GenerateRulePdf.do?ruleVersionId={version}&fileName={file_name}"
        absolute = urljoin(source_page_url, base)
        if match.group("kind").casefold() == "wordversion":
            docx_url = docx_url or f"{absolute}&type=word"
        else:
            pdf_url = pdf_url or f"{absolute}&type=pdf"
        if pdf_url and docx_url:
            break
    return pdf_url, docx_url


def _is_javascript_href(href: str) -> bool:
    """Return whether a link href is JavaScript rather than a document URL."""

    return href.strip().lower().startswith("javascript:")


def _looks_docx(lower_url: str) -> bool:
    """Return whether a URL points to a DOC/DOCX source."""

    return any(
        token in lower_url
        for token in (
            ".docx",
            ".doc?",
            ".doc&",
            "generateruledoc",
            "type=word",
            "wordversion",
        )
    )


def _looks_pdf(lower_url: str) -> bool:
    """Return whether a URL points to a PDF source."""

    return ".pdf" in lower_url or "pdf" in lower_url


def _extension_from_signature(content: bytes) -> str | None:
    """Return a document extension inferred from its magic bytes."""

    if content[:4] == b"%PDF":
        return ".pdf"
    if content[:4] == b"PK\x03\x04":
        return ".docx"
    if content[:8] == b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1":
        return ".doc"
    return None


def _session_or_client(
    client: Any | None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
    retry_hook: Any | None = None,
) -> GeodeHttpClient:
    """Return a shared HTTP client, wrapping injected sessions when needed."""

    if isinstance(client, GeodeHttpClient) and retry_hook is not None:
        LOGGER.debug("CCR retry accounting disabled for preconfigured HTTP client.")
    if isinstance(client, GeodeHttpClient):
        return client
    http_client = GeodeHttpClient(
        session=client,
        config=GeodeHttpClientConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
            retry_hook=retry_hook,
        ),
    )
    if client is None:
        _prime_sos_session(
            http_client,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
        )
    return http_client


def _prime_sos_session(
    client: GeodeHttpClient,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> None:
    """Walk the SOS referer chain to collect cookies before CCR requests."""

    if getattr(client, "_geode_sos_primed", False):
        return

    try:
        client.get(
            SOS_HOME_URL,
            referer=GOOGLE_REFERER,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
            retry_statuses=CCR_RETRY_STATUSES,
        )
        next_referer = SOS_HOME_URL
    except GeodeFetchError as exc:
        if exc.status_code != 403:
            raise
        LOGGER.warning(
            "SOS homepage returned 403 after retries; harvesting CCR search cookies."
        )
        client.get(
            CCR_SEARCH_URL,
            referer=GOOGLE_REFERER,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
            retry_statuses=CCR_RETRY_STATUSES,
        )
        next_referer = CCR_SEARCH_URL

    client.get(
        CCR_WELCOME_URL,
        referer=next_referer,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
        retry_statuses=CCR_RETRY_STATUSES,
    )
    client.get(
        CCR_DEPARTMENT_LIST_URL,
        referer=CCR_WELCOME_URL,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
        retry_statuses=CCR_RETRY_STATUSES,
    )
    try:
        setattr(client, "_geode_sos_primed", True)
    except Exception:
        LOGGER.debug("Could not mark SOS session as primed.", exc_info=True)


def _fetch_discovery_response(
    url: str,
    client: Any | None,
    referer: str | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> _DiscoveryResponse:
    """Fetch a CCR discovery page with response metadata for diagnostics."""

    response = _get_with_retries(
        url,
        client,
        referer=referer,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    _validate_ccr_response(response, url=url, referer=referer, expected_kind="html")
    return _DiscoveryResponse(
        requested_url=url,
        final_url=str(getattr(response, "url", url)),
        status_code=_response_status_code(response),
        text=str(response.text),
    )


def _fetch_text(
    url: str,
    client: Any | None,
    referer: str | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> str:
    """Fetch text with retry handling."""

    response = _fetch_discovery_response(
        url,
        client,
        referer=referer,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    return response.text


def _fetch_bytes(
    url: str,
    client: Any | None,
    referer: str | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> bytes:
    """Fetch bytes with retry handling."""

    response = _get_with_retries(
        url,
        client,
        referer=referer,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    _validate_ccr_response(response, url=url, referer=referer, expected_kind="document")
    return bytes(response.content)


def _get_with_retries(
    url: str,
    client: Any | None,
    referer: str | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    retry_jitter_ratio: float = 0.25,
) -> Any:
    """GET a URL using the shared HTTP client."""

    http_client = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        retry_jitter_ratio=retry_jitter_ratio,
    )
    try:
        return http_client.get(
            url,
            referer=referer,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            retry_jitter_ratio=retry_jitter_ratio,
            retry_statuses=CCR_RETRY_STATUSES,
        )
    except GeodeBlockedError as exc:
        if exc.last_response is not None:
            _log_ccr_blocked_response(
                url,
                exc.last_response,
                referer=referer,
                reason=exc.retry_reason or "http_blocked",
            )
        raise CCRBlockedResponseError(str(exc)) from exc
    except GeodeFetchError as exc:
        if exc.status_code == 403 and exc.last_response is not None:
            _log_ccr_blocked_response(
                url,
                exc.last_response,
                referer=referer,
                reason=exc.retry_reason or "http_403",
            )
            raise CCRBlockedResponseError(str(exc)) from exc
        raise CCRDownloadError(str(exc)) from exc


def _validate_ccr_response(
    response: Any,
    *,
    url: str,
    referer: str | None,
    expected_kind: str,
) -> None:
    """Validate a CCR response for blocked pages and expected body shape."""

    status_code = _response_status_code(response)
    if status_code == 403 or _looks_blocked_response(response):
        reason = "http_403" if status_code == 403 else "blocked_content"
        _log_ccr_blocked_response(url, response, referer=referer, reason=reason)
        raise CCRBlockedResponseError(
            f"CCR request blocked for {url} status={status_code} reason={reason}"
        )

    if expected_kind == "html":
        _validate_ccr_html_response(response, url=url, referer=referer)
        return
    if expected_kind == "document":
        _validate_ccr_document_response(response, url=url, referer=referer)
        return
    raise ValueError(f"unsupported CCR response kind: {expected_kind}")


def _validate_ccr_html_response(
    response: Any,
    *,
    url: str,
    referer: str | None,
) -> None:
    """Validate that a CCR discovery response looks like navigable HTML/text."""

    content_type = _response_content_type(response)
    content = _response_content_bytes(response)
    if not content:
        _log_ccr_unexpected_response(
            url,
            response,
            referer=referer,
            reason="empty_html_response",
        )
        raise CCRDownloadError(f"CCR discovery response was empty for {url}")
    if content_type and not _content_type_in(content_type, CCR_HTMLISH_CONTENT_TYPES):
        _log_ccr_unexpected_response(
            url,
            response,
            referer=referer,
            reason="unexpected_html_content_type",
        )
        raise CCRDownloadError(
            f"CCR discovery response for {url} returned content-type {content_type!r}"
        )


def _validate_ccr_document_response(
    response: Any,
    *,
    url: str,
    referer: str | None,
) -> None:
    """Validate that a CCR document fetch returned a PDF, DOC, or DOCX body."""

    content_type = _response_content_type(response)
    content = _response_content_bytes(response)
    if _looks_document_response(response):
        return
    if not content:
        _log_ccr_unexpected_response(
            url,
            response,
            referer=referer,
            reason="empty_document_response",
        )
        raise CCRDownloadError(f"CCR document response was empty for {url}")
    if _looks_html_bytes(content) or _content_type_in(content_type, CCR_HTMLISH_CONTENT_TYPES):
        _log_ccr_blocked_response(
            url,
            response,
            referer=referer,
            reason="document_fetch_returned_html",
        )
        raise CCRBlockedResponseError(
            f"CCR document fetch returned HTML/text instead of a document for {url}"
        )
    _log_ccr_unexpected_response(
        url,
        response,
        referer=referer,
        reason="unknown_document_content",
    )
    raise CCRDownloadError(
        f"CCR document response for {url} did not match PDF/DOC/DOCX signatures"
    )


def _looks_blocked_response(response: Any) -> bool:
    """Return whether a response body looks like access denial or a challenge."""

    return bool(CCR_BLOCKED_TEXT_RE.search(_safe_response_preview(response)))


def _looks_document_response(response: Any) -> bool:
    """Return whether a response appears to contain a CCR source document."""

    content = _response_content_bytes(response)
    if _extension_from_signature(content) is not None:
        return True
    content_type = _response_content_type(response)
    return _content_type_in(content_type, CCR_DOCUMENT_CONTENT_TYPES) and not _looks_html_bytes(
        content
    )


def _looks_html_bytes(content: bytes) -> bool:
    """Return whether bytes appear to be an HTML page."""

    sample = content[:200].lstrip().lower()
    return any(sample.startswith(signature) for signature in CCR_HTML_SIGNATURES)


def _content_type_in(content_type: str, expected: set[str]) -> bool:
    """Return whether a content type matches a normalized expected set."""

    normalized = content_type.split(";", 1)[0].strip().casefold()
    return bool(normalized and normalized in {item.casefold() for item in expected})


def _log_ccr_blocked_response(
    url: str,
    response: Any,
    *,
    referer: str | None,
    reason: str,
) -> None:
    """Log forensic details for a blocked or challenge CCR response."""

    LOGGER.warning(
        "CCR blocked response reason=%s requested_url=%s final_url=%s referer=%s "
        "status=%s content_type=%s headers=%s preview=%r",
        reason,
        url,
        getattr(response, "url", url),
        referer,
        _response_status_code(response),
        _response_content_type(response),
        _response_header_subset(response),
        _safe_response_preview(response),
    )


def _log_ccr_unexpected_response(
    url: str,
    response: Any,
    *,
    referer: str | None,
    reason: str,
) -> None:
    """Log forensic details for a malformed CCR response."""

    LOGGER.warning(
        "CCR unexpected response reason=%s requested_url=%s final_url=%s referer=%s "
        "status=%s content_type=%s headers=%s preview=%r",
        reason,
        url,
        getattr(response, "url", url),
        referer,
        _response_status_code(response),
        _response_content_type(response),
        _response_header_subset(response),
        _safe_response_preview(response),
    )


def _response_content_type(response: Any) -> str:
    """Return response content type, if present."""

    return _response_header_value(response, "Content-Type") or ""


def _response_header_value(response: Any, name: str) -> str | None:
    """Return a response header value using case-insensitive matching."""

    headers = getattr(response, "headers", {})
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        if value is None:
            value = getter(name.lower())
        if value is not None:
            return str(value)
    for key, value in getattr(headers, "items", lambda: [])():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


def _response_header_subset(response: Any) -> dict[str, str]:
    """Return the response headers most useful for CCR block diagnostics."""

    headers = getattr(response, "headers", {})
    subset: dict[str, str] = {}
    for key, value in getattr(headers, "items", lambda: [])():
        lowered = str(key).casefold()
        if lowered in CCR_FORENSIC_HEADER_NAMES:
            subset[str(key)] = str(value)
    return subset


def _response_content_bytes(response: Any) -> bytes:
    """Return response content as bytes."""

    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8")
    return bytes(content or b"")


def _safe_response_preview(response: Any) -> str:
    """Return a small normalized body preview for diagnostics."""

    text = getattr(response, "text", None)
    if not isinstance(text, str):
        text = _response_content_bytes(response).decode("utf-8", errors="replace")
    preview = _normalize_space(text)
    if len(preview) > CCR_PREVIEW_LIMIT_CHARS:
        return f"{preview[:CCR_PREVIEW_LIMIT_CHARS]}..."
    return preview


def _response_status_code(response: Any) -> int | None:
    """Return a response status code when one is available."""

    status_code = getattr(response, "status_code", None)
    if status_code is None:
        return None
    try:
        return int(status_code)
    except (TypeError, ValueError):
        return None


def _manifest_entry_for(
    manifest_path: Path,
    entry: CCRRuleEntry,
) -> DownloadManifestEntry | None:
    """Return the latest manifest entry for a CCR rule."""

    if not manifest_path.exists():
        return None
    latest: DownloadManifestEntry | None = None
    document_id = entry.canonical_id
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        manifest_entry = DownloadManifestEntry.model_validate(payload)
        if manifest_entry.document_id == document_id or manifest_entry.ccr_number == entry.ccr_number:
            latest = manifest_entry
    return latest


def reconcile_download_state(
    manifest_path: Path,
    entry: CCRRuleEntry,
    target: Path,
) -> CCRDownloadState:
    """Reconcile manifest and archive-file state for one CCR rule."""

    prior = _manifest_entry_for(manifest_path, entry)
    actual_path = _existing_archive_path(target, prior)
    if prior and prior.status == "downloaded":
        prior_path = Path(prior.archive_path)
        if (
            prior_path.exists()
            and _archive_file_has_document_signature(prior_path)
            and prior.sha256 == sha256_file(prior_path)
        ):
            return CCRDownloadState(
                document_id=entry.canonical_id,
                status="downloaded",
                archive_path=prior_path,
                file_exists=True,
                checksum_matches=True,
                manifest_status=prior.status,
            )
        if actual_path is None:
            return CCRDownloadState(
                document_id=entry.canonical_id,
                status="missing_file",
                archive_path=prior_path,
                file_exists=False,
                manifest_status=prior.status,
                error="manifest row exists but archived file is missing or checksum mismatched",
            )
    if actual_path is not None and _archive_file_has_document_signature(actual_path):
        _append_manifest(
            manifest_path,
            DownloadManifestEntry(
                **_manifest_metadata(entry, actual_path),
                ccr_number=entry.ccr_number,
                source_url=entry.preferred_url,
                archive_path=actual_path.as_posix(),
                sha256=sha256_file(actual_path),
                size_bytes=actual_path.stat().st_size,
                downloaded_at=datetime.now(timezone.utc),
                status="downloaded",
            ),
        )
        return CCRDownloadState(
            document_id=entry.canonical_id,
            status="downloaded",
            archive_path=actual_path,
            file_exists=True,
            checksum_matches=True,
            repaired_manifest=True,
            manifest_status=prior.status if prior else None,
        )
    if prior is not None:
        return CCRDownloadState(
            document_id=entry.canonical_id,
            status=_canonical_download_status(prior.status),
            archive_path=Path(prior.archive_path),
            file_exists=False,
            manifest_status=prior.status,
            error=prior.error,
        )
    return CCRDownloadState(
        document_id=entry.canonical_id,
        status="discovered",
        archive_path=target,
        file_exists=False,
    )


def _archive_file_has_document_signature(path: Path) -> bool:
    """Return whether an existing archive file has a supported document signature."""

    try:
        return _extension_from_signature(path.read_bytes()[:16]) is not None
    except OSError:
        return False


def _is_downloaded(
    manifest_path: Path,
    entry: CCRRuleEntry,
    target: Path,
) -> bool:
    """Return whether a CCR rule has a matching archived file and manifest row."""

    return reconcile_download_state(manifest_path, entry, target).status == "downloaded"


def _existing_archive_path(target: Path, prior: DownloadManifestEntry | None) -> Path | None:
    """Return an existing archive path for expected target or known alternate suffixes."""

    candidates: list[Path] = []
    if prior is not None:
        candidates.append(Path(prior.archive_path))
    candidates.append(target)
    candidates.extend(target.with_suffix(suffix) for suffix in (".pdf", ".doc", ".docx"))
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def _canonical_download_status(status: str) -> str:
    """Normalize legacy CCR manifest status values."""

    if status == "failed":
        return "failed_permanent"
    if status in {"downloaded", "blocked", "failed_permanent", "skipped_existing"}:
        return status
    return status or "discovered"


def _canonical_source_url(value: object) -> object:
    """Normalize HTML-encoded query separators in persisted source URLs."""

    if value is None:
        return None
    previous = str(value)
    for _ in range(3):
        current = html_unescape(previous)
        if current == previous:
            return current
        previous = current
    return previous


def _manifest_metadata(entry: CCRRuleEntry, target: Path) -> dict[str, object]:
    """Return normalized CCR raw-download metadata for a manifest row."""

    metadata = {
        "document_id": entry.canonical_id,
        "document_name": entry.ccr_number,
        "department": entry.department,
        "agency": entry.agency,
        "source_page_url": _canonical_source_url(str(entry.source_page_url)),
        "source_format": source_format_from_extension(target.suffix),
        "effective_date": None,
        "publication_date": None,
    }
    return {
        **metadata,
        "missing_metadata": missing_metadata_fields(metadata),
    }


def _record_download_failure(
    manifest_path: Path,
    entry: CCRRuleEntry,
    target: Path,
    error: Exception,
) -> None:
    """Append failed CCR download rows to manifest and failure report."""

    failed_at = datetime.now(timezone.utc)
    status = "blocked" if isinstance(error, CCRBlockedResponseError) else "failed_permanent"
    _append_manifest(
        manifest_path,
        DownloadManifestEntry(
            **_manifest_metadata(entry, target),
            ccr_number=entry.ccr_number,
            source_url=entry.preferred_url,
            archive_path=target.as_posix(),
            sha256=None,
            size_bytes=0,
            downloaded_at=failed_at,
            status=status,
            error=str(error),
        ),
    )
    _append_failure(
        failure_manifest_path(manifest_path.parent),
        CCRDownloadFailure(
            document_id=entry.canonical_id,
            ccr_number=entry.ccr_number,
            department=entry.department,
            agency=entry.agency,
            source_url=entry.preferred_url,
            source_page_url=entry.source_page_url,
            archive_path=target.as_posix(),
            failed_at=failed_at,
            status=status,
            blocked=isinstance(error, CCRBlockedResponseError),
            error=str(error),
        ),
    )


def _canonical_source_url(value: object) -> object:
    """Normalize HTML-encoded query separators in persisted source URLs."""

    if value is None:
        return None
    previous = str(value)
    for _ in range(3):
        current = html_unescape(previous)
        if current == previous:
            return current
        previous = current
    return previous

def _canonical_manifest_line(line: str) -> str:
    """Return one manifest JSONL row with canonical source URL fields."""

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return line
    if not isinstance(payload, dict):
        return line
    for field in ("source_url", "source_page_url"):
        if payload.get(field) is not None:
            payload[field] = _canonical_source_url(payload[field])
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _canonical_manifest_lines(lines: list[str]) -> list[str]:
    """Return manifest JSONL rows with canonical source URL fields."""

    return [_canonical_manifest_line(line) if line.strip() else line for line in lines]


def _rewrite_manifest_urls(path: Path) -> None:
    """Rewrite an existing manifest only when URL fields need canonicalization."""

    if not path.exists():
        return
    existing = path.read_text(encoding="utf-8").splitlines()
    canonical = _canonical_manifest_lines(existing)
    if canonical == existing:
        return
    tmp_path = temp_path_for(path)
    try:
        tmp_path.write_text("\n".join(canonical) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _canonical_manifest_line(line: str) -> str:
    """Return one manifest JSONL row with canonical source URL fields."""

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return line
    if not isinstance(payload, dict):
        return line
    for field in ("source_url", "source_page_url"):
        if payload.get(field) is not None:
            payload[field] = _canonical_source_url(payload[field])
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _canonical_manifest_lines(lines: list[str]) -> list[str]:
    """Return manifest JSONL rows with canonical source URL fields."""

    return [_canonical_manifest_line(line) if line.strip() else line for line in lines]


def _rewrite_manifest_urls(path: Path) -> None:
    """Rewrite an existing manifest only when URL fields need canonicalization."""

    if not path.exists():
        return
    existing = path.read_text(encoding="utf-8").splitlines()
    canonical = _canonical_manifest_lines(existing)
    if canonical == existing:
        return
    tmp_path = temp_path_for(path)
    try:
        tmp_path.write_text("\n".join(canonical) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _append_manifest(path: Path, entry: DownloadManifestEntry) -> None:
    """Append one raw-archive download manifest row atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        _canonical_manifest_lines(path.read_text(encoding="utf-8").splitlines())
        if path.exists()
        else []
    )
    existing.append(_canonical_manifest_line(entry.model_dump_json()))
    tmp_path = temp_path_for(path)
    try:
        tmp_path.write_text("\n".join(existing) + "\n", encoding="utf-8", newline="\n")
        _replace_artifact(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _replace_artifact(tmp_path: Path, target: Path) -> None:
    """Replace an artifact with a short bounded retry for Windows file locks."""

    for attempt in range(1, 8):
        try:
            os.replace(tmp_path, target)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05 * attempt)


def _append_failure(path: Path, entry: CCRDownloadFailure) -> None:
    """Append one CCR failure-report row atomically."""

    _append_jsonl_artifact(path, entry.model_dump(mode="json"))


def _normalize_space(value: str) -> str:
    """Normalize internal whitespace."""

    return re.sub(r"\s+", " ", value).strip()
