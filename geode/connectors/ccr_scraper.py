"""Colorado Code of Regulations discovery and download connector."""

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

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from geode.schemas.validators import require_official_source_url
from geode.utils.hashing import sha256_file

LOGGER = logging.getLogger(__name__)

CCR_BASE_URL = "https://www.sos.state.co.us"
CCR_DEPARTMENT_LIST_URL = f"{CCR_BASE_URL}/CCR/NumericalDeptList.do"
DOWNLOAD_MANIFEST = "download_manifest.jsonl"
CCR_NUMBER_RE = re.compile(r"\b(\d+\s+CCR\s+\d+-\d+(?:-\d+)?)\b", re.IGNORECASE)


class CCRDownloadError(RuntimeError):
    """Raised when a CCR rule cannot be downloaded after retries."""


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
        """Return DOCX URL when available, otherwise PDF URL."""

        if self.docx_url is not None:
            return str(self.docx_url)
        if self.pdf_url is not None:
            return str(self.pdf_url)
        raise CCRDownloadError(f"no downloadable URL for {self.ccr_number}")

    @property
    def preferred_extension(self) -> str:
        """Return the archive extension for the preferred source."""

        parsed = urlparse(self.preferred_url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix in {".doc", ".docx", ".pdf"}:
            return suffix
        if self.docx_url is not None:
            return ".docx"
        return ".pdf"


class DownloadManifestEntry(BaseModel):
    """One raw CCR download manifest entry."""

    model_config = ConfigDict(extra="forbid")

    ccr_number: str
    source_url: HttpUrl
    archive_path: str
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    downloaded_at: datetime
    status: str
    error: str | None = None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value


class DownloadReport(BaseModel):
    """Summary from a CCR download batch."""

    model_config = ConfigDict(extra="forbid")

    discovered: int = Field(ge=0)
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
) -> list[CCRRuleEntry]:
    """Crawl CCR browse pages and catalog rule document links."""

    department_html = _fetch_text(start_url, client)
    agency_links = _agency_links(department_html, start_url)
    entries: list[CCRRuleEntry] = []
    for agency_url, department, agency in agency_links[:max_agencies]:
        agency_html = _fetch_text(agency_url, client)
        entries.extend(_rule_entries_from_page(agency_html, agency_url, department, agency))
    return entries


def resolve_rule_info_page(
    entry: CCRRuleEntry | dict[str, Any],
    client: Any | None = None,
) -> CCRRuleEntry:
    """Resolve one SOS rule-info page into downloadable DOCX/PDF URLs."""

    rule = _coerce_rule_entry(entry)
    html = _fetch_text(str(rule.source_page_url), client)
    parser = _parse_links(html)
    pdf_url = str(rule.pdf_url) if rule.pdf_url is not None else None
    docx_url = str(rule.docx_url) if rule.docx_url is not None else None
    for link in parser.links:
        absolute = urljoin(str(rule.source_page_url), link.href)
        lower = f"{absolute} {link.text}".lower()
        if _looks_docx(lower):
            docx_url = absolute
        elif _looks_pdf(lower):
            pdf_url = absolute
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
) -> list[CCRRuleEntry]:
    """Resolve multiple SOS rule-info pages into downloadable rule entries."""

    return [resolve_rule_info_page(entry, client=client) for entry in entries]


def download_rule(
    entry: CCRRuleEntry,
    archive_dir: Path,
    client: Any | None = None,
) -> Path:
    """Download one CCR rule to the raw archive, preferring DOCX over PDF."""

    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = archive_dir / DOWNLOAD_MANIFEST
    target = archive_dir / f"{_safe_stem(entry.canonical_id)}{entry.preferred_extension}"
    prior = _manifest_entry_for(manifest_path, entry)
    if prior and target.exists() and prior.sha256 == sha256_file(target):
        LOGGER.info("Skipping already downloaded CCR rule %s", entry.ccr_number)
        return target

    try:
        response = _fetch_bytes(entry.preferred_url, client)
    except Exception as exc:
        _append_manifest(
            manifest_path,
            DownloadManifestEntry(
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
        raise CCRDownloadError(str(exc)) from exc

    tmp_path = target.with_name(f"{target.name}.tmp")
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
            ccr_number=entry.ccr_number,
            source_url=entry.preferred_url,
            archive_path=target.as_posix(),
            sha256=digest,
            size_bytes=target.stat().st_size,
            downloaded_at=datetime.now(timezone.utc),
            status="downloaded",
        ),
    )
    LOGGER.info("Downloaded CCR rule %s to %s", entry.ccr_number, target)
    return target


def download_all_rules(
    archive_dir: Path,
    delay: float = 1.0,
    client: Any | None = None,
) -> DownloadReport:
    """Discover and download all CCR rules with rate limiting and resume support."""

    entries = discover_all_rules(client=client)
    paths: list[str] = []
    errors: list[str] = []
    downloaded = 0
    skipped = 0
    failed = 0
    for index, entry in enumerate(entries):
        target = archive_dir / f"{_safe_stem(entry.canonical_id)}{entry.preferred_extension}"
        existed = target.exists()
        try:
            path = download_rule(entry, archive_dir, client=client)
        except CCRDownloadError as exc:
            failed += 1
            errors.append(f"{entry.ccr_number}: {exc}")
        else:
            paths.append(path.as_posix())
            if existed:
                skipped += 1
            else:
                downloaded += 1
        if delay > 0 and index < len(entries) - 1:
            time.sleep(delay)
    return DownloadReport(
        discovered=len(entries),
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        manifest_path=(archive_dir / DOWNLOAD_MANIFEST).as_posix(),
        paths=paths,
        errors=errors,
    )


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
        absolute = urljoin(source_page_url, link.href)
        lower = f"{absolute} {link.text}".lower()
        if not _looks_downloadable(lower):
            continue
        ccr_number = _ccr_number_from_text(f"{link.text} {absolute}")
        if ccr_number is None:
            continue
        item = grouped.setdefault(ccr_number, {})
        if _looks_docx(lower):
            item["docx_url"] = absolute
        elif _looks_pdf(lower):
            item["pdf_url"] = absolute
    entries = []
    for ccr_number, urls in sorted(grouped.items(), key=lambda item: _ccr_sort_key(item[0])):
        entries.append(
            CCRRuleEntry(
                ccr_number=ccr_number,
                department=department,
                agency=agency,
                source_page_url=source_page_url,
                pdf_url=urls.get("pdf_url"),
                docx_url=urls.get("docx_url"),
            )
        )
    return entries


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

    decoded = text.replace("_", " ").replace("%20", " ")
    match = CCR_NUMBER_RE.search(decoded)
    if not match:
        return None
    return _normalize_space(match.group(1)).upper().replace(" CCR ", " CCR ")


def _looks_downloadable(lower_url: str) -> bool:
    """Return whether a URL looks like a CCR source document."""

    return _looks_docx(lower_url) or _looks_pdf(lower_url)


def _looks_docx(lower_url: str) -> bool:
    """Return whether a URL points to a DOC/DOCX source."""

    return any(token in lower_url for token in (".docx", ".doc", "docx", "word"))


def _looks_pdf(lower_url: str) -> bool:
    """Return whether a URL points to a PDF source."""

    return ".pdf" in lower_url or "pdf" in lower_url


def _fetch_text(url: str, client: Any | None) -> str:
    """Fetch text with retry handling."""

    response = _get_with_retries(url, client)
    return str(response.text)


def _fetch_bytes(url: str, client: Any | None) -> bytes:
    """Fetch bytes with retry handling."""

    response = _get_with_retries(url, client)
    return bytes(response.content)


def _get_with_retries(url: str, client: Any | None, retries: int = 3) -> Any:
    """GET a URL with three attempts on HTTP errors."""

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = _get(url, client)
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            elif int(response.status_code) >= 400:
                raise httpx.HTTPStatusError("HTTP error", request=None, response=response)
            return response
        except Exception as exc:
            last_error = exc
            LOGGER.warning(
                "CCR request failed attempt %s/%s for %s: %s",
                attempt,
                retries,
                url,
                exc,
            )
    raise CCRDownloadError(f"failed after {retries} attempts: {last_error}")


def _get(url: str, client: Any | None) -> Any:
    """Issue one HTTP GET using an injected or temporary client."""

    if client is not None:
        return client.get(url)
    with httpx.Client(follow_redirects=True, timeout=30.0) as http_client:
        return http_client.get(url)


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


def _append_manifest(path: Path, entry: DownloadManifestEntry) -> None:
    """Append one raw-archive download manifest row atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing.append(entry.model_dump_json())
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text("\n".join(existing) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _normalize_space(value: str) -> str:
    """Normalize internal whitespace."""

    return re.sub(r"\s+", " ", value).strip()


def _safe_stem(value: str) -> str:
    """Return a filesystem-safe CCR archive stem."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
