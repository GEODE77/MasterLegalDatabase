"""Colorado Register scraper and rulemaking-notice extractor."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from geode.schemas.validators import require_official_source_url
from geode.utils.hashing import sha256_file

REGISTER_URL = "https://www.sos.state.co.us/pubs/CCR/register.html"
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

    publication: RegisterPublication
    archive_path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    downloaded_at: datetime


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
) -> list[RegisterPublication]:
    """Discover Colorado Register publication links from an index page."""

    html = _fetch_text(index_url, client)
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
) -> RegisterDownload:
    """Download one Colorado Register publication and fingerprint it."""

    archive_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(str(publication.url)).suffix or ".html"
    target = archive_dir / f"register_{publication.publication_date}{suffix}"
    content = _fetch_bytes(str(publication.url), client)
    tmp_path = target.with_name(f"{target.name}.tmp")
    try:
        tmp_path.write_bytes(content)
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    result = RegisterDownload(
        publication=publication,
        archive_path=target.as_posix(),
        sha256=sha256_file(target),
        downloaded_at=datetime.now(timezone.utc),
    )
    _append_manifest(archive_dir / "download_manifest.jsonl", result.model_dump(mode="json"))
    return result


def _fetch_text(url: str, client: Any | None) -> str:
    """Fetch text with an injected or temporary client."""

    response = _get(url, client)
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    return str(response.text)


def _fetch_bytes(url: str, client: Any | None) -> bytes:
    """Fetch bytes with an injected or temporary client."""

    response = _get(url, client)
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    return bytes(response.content)


def _get(url: str, client: Any | None) -> Any:
    """Issue one GET request."""

    if client is not None:
        return client.get(url)
    with httpx.Client(timeout=30.0, follow_redirects=True) as http_client:
        return http_client.get(url)


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

    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text("\n".join(existing) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
