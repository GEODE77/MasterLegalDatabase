"""Colorado Code of Regulations discovery and download connector."""

from __future__ import annotations

import json
import logging
import os
import re
import time
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
    temp_path_for,
)
from geode.connectors.download_metadata import (
    COLORADO_JURISDICTION,
    missing_metadata_fields,
    source_format_from_extension,
)
from geode.net.http_client import (
    DEFAULT_MAX_RETRY_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    GeodeFetchError,
    build_session,
    polite_get,
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
CCR_NUMBER_RE = re.compile(r"\b(\d+\s+CCR\s+\d+-\d+(?:-\d+)?)\b", re.IGNORECASE)


class CCRDownloadError(RuntimeError):
    """Raised when a CCR rule cannot be downloaded after retries."""


@dataclass(frozen=True)
class _DiscoveryResponse:
    requested_url: str
    final_url: str
    status_code: int | None
    text: str


class CCRRuleEntry(BaseModel):
    """Catalog entry for one CCR rule source document."""

    model_config = ConfigDict(extra="forbid")

    ccr_number: str = Field(min_length=1)
    department: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    source_page_url: HttpUrl
    pdf_url: HttpUrl | None = None
    docx_url: HttpUrl | None = None

    @field_validator("source_page_url", "pdf_url", "docx_url")
    @classmethod
    def validate_source_urls(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require Secretary of State CCR URLs."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value

    @property
    def canonical_id(self) -> str:
        """Return Geode-style CCR ID."""

        return self.ccr_number.replace(" ", "_")

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


class DownloadReport(BaseModel):
    """Summary from a CCR download batch."""

    model_config = ConfigDict(extra="forbid")

    discovered: int = Field(ge=0)
    attempted: int = Field(ge=0)
    downloaded: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
    manifest_path: str
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
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> list[CCRRuleEntry]:
    """Crawl CCR browse pages and catalog rule document links."""

    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    department_page = _fetch_discovery_response(
        start_url,
        session,
        referer=CCR_WELCOME_URL,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
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
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
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
        if request_delay > 0 and index < len(selected_agency_links) - 1:
            time.sleep(request_delay)
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


def resolve_rule_info_page(
    entry: CCRRuleEntry | dict[str, Any],
    client: Any | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> CCRRuleEntry:
    """Resolve one SOS rule-info page into downloadable DOCX/PDF URLs."""

    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
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
    return CCRRuleEntry(
        ccr_number=rule.ccr_number,
        department=rule.department,
        agency=rule.agency,
        source_page_url=rule.source_page_url,
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
) -> Path:
    """Download one CCR rule to the raw archive, preferring PDF over DOC/DOCX."""

    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = download_manifest_path(archive_dir)
    target = ccr_rule_document_path(archive_dir, entry.canonical_id, entry.preferred_extension)
    prior = _manifest_entry_for(manifest_path, entry)
    if prior and target.exists() and prior.sha256 == sha256_file(target):
        LOGGER.debug(
            "CCR download skipped ccr_number=%s source_url=%s archive_path=%s",
            entry.ccr_number,
            entry.preferred_url,
            target.as_posix(),
        )
        return target

    try:
        response = _fetch_bytes(
            entry.preferred_url,
            session,
            referer=str(entry.source_page_url),
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
        )
    except Exception as exc:
        _append_manifest(
            manifest_path,
            DownloadManifestEntry(
                **_manifest_metadata(entry, target),
                ccr_number=entry.ccr_number,
                source_url=entry.preferred_url,
                archive_path=target.as_posix(),
                sha256=None,
                size_bytes=0,
                downloaded_at=datetime.now(timezone.utc),
                status="failed",
                error=str(exc),
            ),
        )
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

    tmp_path = temp_path_for(target)
    try:
        tmp_path.write_bytes(response)
        os.replace(tmp_path, target)
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


def download_all_rules(
    archive_dir: Path,
    delay: float = 1.0,
    client: Any | None = None,
    discovery_delay: float = 0.0,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    max_downloads: int | None = None,
) -> DownloadReport:
    """Discover and download all CCR rules with rate limiting and resume support."""

    _validate_max_downloads(max_downloads)
    session = _session_or_client(
        client,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    entries = discover_all_rules(
        client=session,
        request_delay=discovery_delay,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    LOGGER.info(
        "CCR bulk download discovered=%s archive_dir=%s",
        len(entries),
        archive_dir.as_posix(),
    )
    paths: list[str] = []
    errors: list[str] = []
    downloaded = 0
    skipped = 0
    failed = 0
    network_attempts = 0
    manifest_path = download_manifest_path(archive_dir)
    _rewrite_manifest_urls(manifest_path)
    for index, entry in enumerate(entries):
        target = ccr_rule_document_path(archive_dir, entry.canonical_id, entry.preferred_extension)
        already_downloaded = _is_downloaded(manifest_path, entry, target)
        if already_downloaded:
            paths.append(target.as_posix())
            skipped += 1
            continue
        if max_downloads is not None and network_attempts >= max_downloads:
            LOGGER.info(
                "CCR bulk download paused max_downloads=%s archive_dir=%s",
                max_downloads,
                archive_dir.as_posix(),
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
            )
        except CCRDownloadError as exc:
            failed += 1
            errors.append(f"{entry.ccr_number}: {exc}")
        else:
            paths.append(path.as_posix())
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
        "CCR bulk download summary attempted=%s succeeded=%s failed=%s skipped=%s "
        "archive_dir=%s manifest=%s",
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


def _coerce_rule_entry(entry: CCRRuleEntry | dict[str, Any]) -> CCRRuleEntry:
    """Coerce downloader handoff dictionaries into CCR rule entries."""

    if isinstance(entry, CCRRuleEntry):
        return entry
    allowed = {
        "ccr_number",
        "department",
        "agency",
        "source_page_url",
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
                pdf_url=urls.get("pdf_url"),
                docx_url=urls.get("docx_url"),
            )
        )
    return entries


def _resolve_rule_info_candidates(
    entries: list[CCRRuleEntry],
    session: Any,
    request_delay: float = 0.0,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> list[CCRRuleEntry]:
    """Resolve rule-info candidates into entries with download URLs."""

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
        if request_delay > 0 and index < len(entries) - 1:
            time.sleep(request_delay)
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


def _download_urls_from_rule_scripts(html: str, source_page_url: str) -> tuple[str | None, str | None]:
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
) -> Any:
    """Return an injected client or a warmed SOS browser session."""

    if client is not None:
        return client
    session = build_session()
    _prime_sos_session(
        session,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    return session


def _prime_sos_session(
    session: Any,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> None:
    """Walk the SOS referer chain to collect cookies before CCR requests."""

    if getattr(session, "_geode_sos_primed", False):
        return

    try:
        polite_get(
            session,
            SOS_HOME_URL,
            referer=GOOGLE_REFERER,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
        )
        next_referer = SOS_HOME_URL
    except GeodeFetchError as exc:
        if exc.status_code != 403:
            raise
        LOGGER.warning(
            "SOS homepage returned 403 after retries; harvesting CCR search cookies."
        )
        polite_get(
            session,
            CCR_SEARCH_URL,
            referer=GOOGLE_REFERER,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
        )
        next_referer = CCR_SEARCH_URL

    polite_get(
        session,
        CCR_WELCOME_URL,
        referer=next_referer,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    polite_get(
        session,
        CCR_DEPARTMENT_LIST_URL,
        referer=CCR_WELCOME_URL,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    try:
        setattr(session, "_geode_sos_primed", True)
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
    )
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
    )
    return bytes(response.content)


def _get_with_retries(
    url: str,
    client: Any | None,
    referer: str | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> Any:
    """GET a URL using the hardened polite client."""

    session = (
        client
        if client is not None
        else _session_or_client(
            None,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
        )
    )
    try:
        return polite_get(
            session,
            url,
            referer=referer,
            max_retries=max_retries,
            base_delay=base_delay,
            timeout_seconds=timeout_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
        )
    except GeodeFetchError as exc:
        raise CCRDownloadError(str(exc)) from exc


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
    """Return the latest successful manifest entry for a CCR rule."""

    if not manifest_path.exists():
        return None
    latest: DownloadManifestEntry | None = None
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        manifest_entry = DownloadManifestEntry.model_validate(payload)
        if manifest_entry.ccr_number == entry.ccr_number and manifest_entry.status == "downloaded":
            latest = manifest_entry
    return latest


def _is_downloaded(
    manifest_path: Path,
    entry: CCRRuleEntry,
    target: Path,
) -> bool:
    """Return whether a CCR rule has a matching archived file and manifest row."""

    prior = _manifest_entry_for(manifest_path, entry)
    return bool(prior and target.exists() and prior.sha256 == sha256_file(target))


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
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _normalize_space(value: str) -> str:
    """Normalize internal whitespace."""

    return re.sub(r"\s+", " ", value).strip()
