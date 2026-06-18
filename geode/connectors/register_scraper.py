"""Colorado Register scraper and rulemaking-notice extractor."""

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
    failure_manifest_path,
    register_publication_path,
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
    build_session,
    polite_get,
)
from geode.schemas.validators import require_official_source_url
from geode.utils.file_io import iter_jsonl
from geode.utils.hashing import sha256_file

LOGGER = logging.getLogger(__name__)

REGISTER_URL = "https://www.sos.state.co.us/pubs/CCR/register.html"
DOWNLOAD_MANIFEST = DOWNLOAD_MANIFEST_NAME
FAILURE_MANIFEST = FAILURE_MANIFEST_NAME
NOTICE_LINE_RE = re.compile(
    r"NOTICE:\s*(?P<notice_type>\w+)\s*\|\s*CCR:\s*(?P<ccr>[^|]+)\|"
    r"\s*Agency:\s*(?P<agency>[^|]+)\|\s*Publication:\s*(?P<publication>[^|]+)"
    r"(?:\|\s*Hearing:\s*(?P<hearing>[^|]+))?"
    r"(?:\|\s*Effective:\s*(?P<effective>[^|]+))?"
    r"\|\s*Summary:\s*(?P<summary>.+)",
    re.IGNORECASE,
)


class RegisterPublication(BaseModel):
    """One Colorado Register publication link."""

    model_config = ConfigDict(extra="forbid")

    title: str
    publication_date: str
    url: HttpUrl

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official Secretary of State URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value


class RegisterDownload(BaseModel):
    """Downloaded Register publication metadata."""

    model_config = ConfigDict(extra="forbid")

    jurisdiction: str = COLORADO_JURISDICTION
    source_type: str = "colorado_register_publication"
    document_id: str = ""
    document_name: str | None = None
    publication: RegisterPublication
    source_url: HttpUrl | None = None
    source_format: str | None = None
    publication_date: str | None = None
    archive_path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    downloaded_at: datetime
    missing_metadata: list[str] = Field(default_factory=list)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official source URLs when present."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value


class RegisterDownloadFailure(BaseModel):
    """Failed Colorado Register publication download attempt."""

    model_config = ConfigDict(extra="forbid")

    jurisdiction: str = COLORADO_JURISDICTION
    source_type: str = "colorado_register_publication"
    document_id: str = ""
    document_name: str | None = None
    publication: RegisterPublication
    source_url: HttpUrl | None = None
    source_format: str | None = None
    publication_date: str | None = None
    archive_path: str
    failed_at: datetime
    error: str
    missing_metadata: list[str] = Field(default_factory=list)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Require official source URLs when present."""

        if value is not None:
            require_official_source_url(str(value).rstrip("/"))
        return value


class DownloadReport(BaseModel):
    """Summary from a Colorado Register publication download batch."""

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
    """Minimal link parser."""

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


def discover_publications(
    client: Any | None = None,
    index_url: str = REGISTER_URL,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> list[RegisterPublication]:
    """Discover Colorado Register publication links from an index page."""

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
    publications = []
    for href, text in parser.links:
        absolute = urljoin(index_url, href)
        if not any(token in absolute.lower() for token in (".pdf", ".html", ".htm")):
            continue
        publication_date = _date_from_text(text) or _date_from_text(absolute)
        if not publication_date:
            continue
        publications.append(
            RegisterPublication(title=text, publication_date=publication_date, url=absolute)
        )
    return publications


def download_all_publications(
    archive_dir: Path,
    delay: float = 1.0,
    client: Any | None = None,
    index_url: str = REGISTER_URL,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
    max_downloads: int | None = None,
) -> DownloadReport:
    """Discover and download Colorado Register publications with resume support."""

    _validate_max_downloads(max_downloads)
    session = _session_or_client(client)
    publications = discover_publications(
        client=session,
        index_url=index_url,
        max_retries=max_retries,
        base_delay=base_delay,
        timeout_seconds=timeout_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    LOGGER.info(
        "Colorado Register bulk download discovered=%s archive_dir=%s",
        len(publications),
        archive_dir.as_posix(),
    )
    manifest_path = download_manifest_path(archive_dir)
    paths: list[str] = []
    errors: list[str] = []
    downloaded = 0
    skipped = 0
    failed = 0
    network_attempts = 0
    for index, publication in enumerate(publications):
        target = _archive_path_for_publication(publication, archive_dir)
        already_downloaded = _is_downloaded(manifest_path, publication, target)
        if already_downloaded:
            paths.append(target.as_posix())
            skipped += 1
            continue
        if max_downloads is not None and network_attempts >= max_downloads:
            LOGGER.info(
                "Colorado Register bulk download paused max_downloads=%s archive_dir=%s",
                max_downloads,
                archive_dir.as_posix(),
            )
            break
        network_attempts += 1
        try:
            result = download_publication(
                publication,
                archive_dir,
                client=session,
                max_retries=max_retries,
                base_delay=base_delay,
                timeout_seconds=timeout_seconds,
                max_retry_delay_seconds=max_retry_delay_seconds,
            )
        except Exception as exc:
            failed += 1
            errors.append(f"{publication.publication_date}: {exc}")
            LOGGER.warning(
                "Colorado Register download failed publication_date=%s source_url=%s "
                "archive_path=%s error=%s",
                publication.publication_date,
                publication.url,
                target.as_posix(),
                exc,
            )
            _append_failure(
                failure_manifest_path(archive_dir),
                RegisterDownloadFailure(
                    **_manifest_metadata(publication, target),
                    publication=publication,
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
            and index < len(publications) - 1
            and (max_downloads is None or network_attempts < max_downloads)
        ):
            time.sleep(delay)
    report = DownloadReport(
        discovered=len(publications),
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
        "Colorado Register bulk download summary attempted=%s succeeded=%s "
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


def extract_rulemaking_notices(text: str, source_url: str) -> list[dict[str, Any]]:
    """Extract fixture-friendly Colorado Register rulemaking notice records."""

    notices = []
    for index, line in enumerate(text.splitlines(), start=1):
        match = NOTICE_LINE_RE.search(line)
        if not match:
            continue
        publication_date = match.group("publication").strip()
        ccr_rule = _canonical_ccr(match.group("ccr"))
        notices.append(
            {
                "entity_type": "rulemaking_notice",
                "id": f"RM-{publication_date[:4]}-{index:05d}",
                "notice_type": match.group("notice_type").casefold(),
                "ccr_rule_affected": ccr_rule,
                "agency_code": match.group("agency").strip(),
                "hearing_date": _optional_date(match.group("hearing")),
                "effective_date": _optional_date(match.group("effective")),
                "publication_date": publication_date,
                "summary": match.group("summary").strip(),
                "subject_tags": [],
                "source_url": source_url,
                "confidence": {"overall": 0.8},
            }
        )
    return notices


def download_publication(
    publication: RegisterPublication,
    archive_dir: Path,
    client: Any | None = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> RegisterDownload:
    """Download one Colorado Register publication and fingerprint it."""

    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = download_manifest_path(archive_dir)
    target = _archive_path_for_publication(publication, archive_dir)
    prior = _manifest_entry_for(manifest_path, publication)
    if prior and target.exists() and prior.sha256 == sha256_file(target):
        LOGGER.debug(
            "Colorado Register download skipped publication_date=%s source_url=%s "
            "archive_path=%s",
            publication.publication_date,
            publication.url,
            target.as_posix(),
        )
        return prior

    content = _fetch_bytes(
        str(publication.url),
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
    result = RegisterDownload(
        **_manifest_metadata(publication, target),
        publication=publication,
        archive_path=target.as_posix(),
        sha256=sha256_file(target),
        downloaded_at=datetime.now(timezone.utc),
    )
    _append_manifest(manifest_path, result.model_dump(mode="json"))
    LOGGER.debug(
        "Colorado Register download succeeded publication_date=%s source_url=%s "
        "archive_path=%s",
        publication.publication_date,
        publication.url,
        target.as_posix(),
    )
    return result


def _fetch_text(
    url: str,
    client: Any | None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retry_delay_seconds: float | None = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> str:
    """Fetch text with an injected or temporary client."""

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
    """Fetch bytes with an injected or temporary client."""

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

    match = re.search(r"\b(20\d{2})[-_/](\d{2})[-_/](\d{2})\b", text)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _optional_date(value: str | None) -> str | None:
    """Normalize optional date text."""

    if value is None:
        return None
    return _date_from_text(value.strip()) or value.strip()


def _canonical_ccr(value: str) -> str:
    """Normalize CCR citation text into Geode ID style."""

    return re.sub(r"\s+", "_", value.strip())


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


def _append_failure(path: Path, failure: RegisterDownloadFailure) -> None:
    """Append one failed Register download row atomically."""

    _append_manifest(path, failure.model_dump(mode="json"))


def _manifest_metadata(publication: RegisterPublication, target: Path) -> dict[str, object]:
    """Return normalized Register raw-download metadata for a manifest row."""

    metadata = {
        "document_id": publication.publication_date,
        "document_name": publication.title,
        "source_url": str(publication.url),
        "source_format": source_format_from_extension(target.suffix),
        "publication_date": publication.publication_date,
    }
    return {
        **metadata,
        "missing_metadata": missing_metadata_fields(metadata),
    }


def _archive_path_for_publication(publication: RegisterPublication, archive_dir: Path) -> Path:
    """Return the raw archive path for one Register publication."""

    return register_publication_path(
        archive_dir,
        publication.publication_date,
        str(publication.url),
    )


def _is_downloaded(
    manifest_path: Path,
    publication: RegisterPublication,
    target: Path,
) -> bool:
    """Return whether a publication has a matching archived file and manifest row."""

    prior = _manifest_entry_for(manifest_path, publication)
    return bool(prior and target.exists() and prior.sha256 == sha256_file(target))


def _manifest_entry_for(
    manifest_path: Path,
    publication: RegisterPublication,
) -> RegisterDownload | None:
    """Return the latest successful manifest entry for one Register publication."""

    if not manifest_path.exists():
        return None
    latest: RegisterDownload | None = None
    for payload in iter_jsonl(manifest_path):
        manifest_entry = RegisterDownload.model_validate(payload)
        if str(manifest_entry.publication.url) == str(publication.url):
            latest = manifest_entry
    return latest
