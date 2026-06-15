"""Governor executive order discovery and download connector."""

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

from geode.extractors.citation_extractor import extract_crs_citations
from geode.schemas.models import ExecutiveOrder
from geode.schemas.validators import require_official_source_url
from geode.utils.hashing import sha256_file

EXECUTIVE_ORDERS_URL = "https://www.colorado.gov/governor/executive-orders"
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

    entry: ExecutiveOrderEntry
    archive_path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    downloaded_at: datetime


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
) -> list[ExecutiveOrderEntry]:
    """Discover executive order PDF links from the Governor website."""

    html = _fetch_text(index_url, client)
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


def download_executive_order(
    entry: ExecutiveOrderEntry,
    archive_dir: Path,
    client: Any | None = None,
) -> ExecutiveOrderDownload:
    """Download one executive order PDF and fingerprint it."""

    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"{entry.entity_id}.pdf"
    content = _fetch_bytes(str(entry.pdf_url), client)
    tmp_path = target.with_name(f"{target.name}.tmp")
    try:
        tmp_path.write_bytes(content)
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    result = ExecutiveOrderDownload(
        entry=entry,
        archive_path=target.as_posix(),
        sha256=sha256_file(target),
        downloaded_at=datetime.now(timezone.utc),
    )
    _append_manifest(archive_dir / "download_manifest.jsonl", result.model_dump(mode="json"))
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


def _fetch_text(url: str, client: Any | None) -> str:
    """Fetch text using an injected or temporary client."""

    response = _get(url, client)
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    return str(response.text)


def _fetch_bytes(url: str, client: Any | None) -> bytes:
    """Fetch bytes using an injected or temporary client."""

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

    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text("\n".join(existing) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
