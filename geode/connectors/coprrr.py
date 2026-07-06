"""COPRRR supplementary review acquisition."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.schemas.models import COPRRRReview, LayerIndexRecord
from geode.utils.file_io import (
    atomic_write_json,
    atomic_write_jsonl,
    iter_jsonl,
    load_json,
    relative_path,
)
from geode.utils.hashing import sha256_file, sha256_text

LAYER = "07_Supplementary"
RAW_DIR = "_RAW_ARCHIVE/supplementary/coprrr"
SOURCE_URL = "https://coprrr.colorado.gov/"
INDEX_NAME = "_index.jsonl"
META_NAME = "coprrr_reviews_meta.jsonl"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,*/*",
    "Referer": SOURCE_URL,
}
PDF_LINK_RE = re.compile(
    r"<a[^>]+href=[\"'](?P<href>[^\"']+\.pdf[^\"']*)[\"'][^>]*>(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4}\b"
)


class COPRRRSummary(BaseModel):
    """Summary from a COPRRR collection run."""

    discovered: int = Field(ge=0)
    downloaded: int = Field(ge=0)
    records_written: int = Field(ge=0)
    failed: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def collect_coprrr_reviews(root: Path) -> COPRRRSummary:
    """Download and structure official COPRRR PDF reviews."""

    project_root = root.resolve()
    raw_dir = project_root / RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    links = _discover_links()
    records: list[COPRRRReview] = []
    errors: list[str] = []
    for url, title in links:
        try:
            target = raw_dir / _safe_pdf_name(url)
            if not target.exists():
                response = requests.get(url, headers=HEADERS, timeout=60)
                response.raise_for_status()
                if not response.content.startswith(b"%PDF"):
                    raise ValueError(f"COPRRR download was not a PDF: {url}")
                tmp_path = target.with_suffix(target.suffix + ".tmp")
                try:
                    tmp_path.write_bytes(response.content)
                    tmp_path.replace(target)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()
            records.append(_record_from_pdf(target, url, title))
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    _write_outputs(project_root, records)
    _refresh_manifest(project_root)
    summary = COPRRRSummary(
        discovered=len(links),
        downloaded=len(records),
        records_written=len(records),
        failed=len(errors),
        errors=errors,
    )
    atomic_write_json(
        project_root / LAYER / "_meta" / "coprrr_reviews_summary.json",
        summary,
        project_root,
    )
    return summary


def _discover_links() -> list[tuple[str, str]]:
    """Return official COPRRR PDF links and visible titles."""

    response = requests.get(SOURCE_URL, headers=HEADERS, timeout=60)
    response.raise_for_status()
    links: list[tuple[str, str]] = []
    for match in PDF_LINK_RE.finditer(response.text):
        title = _clean_html(match.group("body"))
        links.append((urljoin(SOURCE_URL, match.group("href")), title))
    return links


def _record_from_pdf(path: Path, source_url: str, fallback_title: str) -> COPRRRReview:
    """Build one COPRRR record from a downloaded PDF."""

    text = _extract_pdf_text(path)
    publication = _publication_date(text)
    title = _program_title(text) or fallback_title or path.stem
    year = publication[:4]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")[:48] or path.stem
    return COPRRRReview(
        id=f"COPRRR-{year}-{slug}",
        review_type="sunset" if "sunset" in path.name.casefold() else "sunrise",
        program_reviewed=title,
        agency_code="DORA_COPRRR",
        publication_date=publication,
        recommendation="See official COPRRR review.",
        summary=title,
        subject_tags=[],
        source_url=source_url,
        confidence={"overall": 0.78},
    )


def _write_outputs(root: Path, records: list[COPRRRReview]) -> None:
    """Write COPRRR records and merge the supplementary index."""

    layer_root = root / LAYER
    record_path = layer_root / "coprrr_reviews" / "coprrr_reviews_2025.jsonl"
    meta_path = layer_root / "_meta" / META_NAME
    index_path = layer_root / INDEX_NAME
    atomic_write_jsonl(record_path, records, root)
    atomic_write_jsonl(meta_path, records, root)
    existing = [
        LayerIndexRecord.model_validate(row)
        for row in iter_jsonl(index_path)
        if row.get("entity_type") != "coprrr_review"
    ] if index_path.exists() else []
    now = datetime.now(timezone.utc)
    new_rows = [
        LayerIndexRecord(
            id=record.id,
            layer=LAYER,
            entity_type="coprrr_review",
            title=record.program_reviewed,
            citation=record.id,
            path=relative_path(record_path, root),
            meta_path=relative_path(meta_path, root),
            source_url=record.source_url,
            source_path=relative_path(
                root / RAW_DIR / _safe_pdf_name(str(record.source_url)),
                root,
            ),
            publication_year=record.publication_date.year,
            last_updated=now,
            sha256=sha256_text(record.summary),
            tags=["coprrr_review"],
            confidence=record.confidence.overall,
        )
        for record in records
    ]
    atomic_write_jsonl(index_path, [*existing, *new_rows], root)


def _refresh_manifest(root: Path) -> None:
    """Refresh the supplementary manifest count."""

    index_path = root / LAYER / INDEX_NAME
    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    manifest = load_json(manifest_path)
    count = sum(1 for _ in iter_jsonl(index_path))
    today = datetime.now(timezone.utc).date().isoformat()
    for layer in manifest.get("data_layers", []):
        if isinstance(layer, dict) and layer.get("id") == LAYER:
            layer["record_count"] = count
            layer["last_ingested"] = today
            layer["last_checked"] = today
            layer["staleness_days"] = 0
            layer["status"] = "ready" if count else "empty"
            break
    atomic_write_json(manifest_path, manifest, root)


def _extract_pdf_text(path: Path) -> str:
    """Extract PDF text."""

    import fitz

    with fitz.open(path) as document:
        return "\n".join(page.get_text("text") for page in document).strip()


def _publication_date(text: str) -> str:
    """Return the first exact month-name date from a COPRRR PDF."""

    match = DATE_RE.search(text)
    if not match:
        raise ValueError("publication date not found")
    return datetime.strptime(match.group(0), "%B %d, %Y").date().isoformat()


def _program_title(text: str) -> str | None:
    """Return the visible report program title."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if "sunset review" in line.casefold() and index + 1 < len(lines):
            return lines[index + 1]
    return None


def _clean_html(value: str) -> str:
    """Return normalized visible anchor text."""

    return " ".join(html.unescape(TAG_RE.sub(" ", value)).split())


def _safe_pdf_name(url: str) -> str:
    """Return a stable local PDF filename."""

    parsed_name = Path(urlparse(url).path).name
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", parsed_name) or "coprrr.pdf"
