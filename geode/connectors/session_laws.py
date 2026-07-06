"""Colorado session-law acquisition and structuring."""

from __future__ import annotations

import argparse
import html
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from pydantic import BaseModel, Field, HttpUrl, field_validator

from geode.constants import CONTROL_PLANE_DIR
from geode.schemas.models import LayerIndexRecord, SessionLaw
from geode.schemas.validators import require_official_source_url
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, load_json, relative_path
from geode.utils.hashing import sha256_file

SESSION_LAWS_URL = "https://leg.colorado.gov/laws/session-laws"
LAYER = "06_Session_Laws"
RAW_DIR = "_RAW_ARCHIVE/crs/session_laws"
META_NAME = "session_laws_meta.jsonl"

ROW_RE = re.compile(r"<tr\b[^>]*role=[\"']row[\"'][^>]*>(?P<body>.*?)</tr>", re.DOTALL)
CELL_RE = re.compile(
    r"<td\b[^>]*data-label=[\"'](?P<label>[^\"']+)[\"'][^>]*>(?P<body>.*?)</td>",
    re.DOTALL,
)
ANCHOR_RE = re.compile(
    r"<a\b[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<body>.*?)</a>",
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
SESSION_YEAR_RE = re.compile(r"Session Laws from the (?P<year>20\d{2})")
MEASURE_RE = re.compile(r"(?P<bill>[A-Z]{2,3}\d{2}-\d{1,4})\s*(?P<title>.*)", re.DOTALL)
DATE_RE = re.compile(r"^(?P<month>\d{2})/(?P<day>\d{2})/(?P<year>\d{4})$")


class SessionLawDiscoveryRecord(BaseModel):
    """One session-law row discovered from the official source table."""

    bill_id: str = Field(min_length=1)
    chapter: str = Field(min_length=1)
    effective_date: date | None = None
    page_number: str | None = None
    session_year: str = Field(pattern=r"^\d{4}$")
    source_page_url: HttpUrl
    source_url: HttpUrl
    title: str = Field(min_length=1)

    @field_validator("source_page_url", "source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value

    @property
    def entity_id(self) -> str:
        """Return the canonical session-law ID."""

        return f"SL-{self.session_year}-{self.chapter}"


class SessionLawPipelineSummary(BaseModel):
    """Summary of a session-law acquisition and structuring run."""

    discovered: int = Field(ge=0)
    downloaded: int = Field(ge=0)
    failed_downloads: int = Field(ge=0)
    index_path: str
    meta_path: str
    record_count: int = Field(ge=0)
    raw_dir: str
    years: list[str]


@dataclass(frozen=True)
class _RawEvidence:
    """Raw evidence path and hash for one discovered row."""

    path: Path
    sha256: str
    is_pdf: bool = False
    download_failed: bool = False


def parse_session_law_page(html_text: str, page_url: str) -> list[SessionLawDiscoveryRecord]:
    """Parse official Colorado session-law rows from one HTML page."""

    session_year = _session_year(html_text)
    records: list[SessionLawDiscoveryRecord] = []
    for match in ROW_RE.finditer(html_text):
        cells = {
            label.casefold(): body
            for label, body in (
                (cell.group("label"), cell.group("body"))
                for cell in CELL_RE.finditer(match.group("body"))
            )
        }
        if "measure" not in cells or "chapter #" not in cells or "chapter text" not in cells:
            continue
        measure = _anchor(cells["measure"])
        pdf = _anchor(cells["chapter text"])
        if measure is None or pdf is None:
            continue
        measure_text = _text(measure[1])
        measure_match = MEASURE_RE.match(measure_text)
        if not measure_match:
            continue
        effective_date = _parse_date(_text(cells.get("effective date", "")))
        chapter = _text(cells["chapter #"])
        records.append(
            SessionLawDiscoveryRecord(
                bill_id=measure_match.group("bill"),
                chapter=chapter,
                effective_date=effective_date,
                page_number=_text(cells.get("page #", "")) or None,
                session_year=session_year,
                source_page_url=page_url,
                source_url=urljoin(page_url, pdf[0]),
                title=measure_match.group("title").strip() or measure_match.group("bill"),
            )
        )
    return records


def write_session_laws_dataset(
    root: Path,
    *,
    download_pdfs: bool = False,
    max_downloads: int | None = None,
    max_pages: int | None = None,
) -> SessionLawPipelineSummary:
    """Collect and structure official Colorado session laws from the current source table."""

    resolved_root = root.resolve()
    raw_dir = resolved_root / RAW_DIR
    layer_dir = resolved_root / LAYER
    meta_path = layer_dir / "_meta" / META_NAME
    index_path = layer_dir / "_index.jsonl"
    raw_dir.mkdir(parents=True, exist_ok=True)
    page_records: list[tuple[SessionLawDiscoveryRecord, Path]] = []
    page = 1
    while True:
        if max_pages is not None and page > max_pages:
            break
        page_url = SESSION_LAWS_URL if page == 1 else f"{SESSION_LAWS_URL}?page={page}"
        response = requests.get(page_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        page_path = _preserve_page_evidence(raw_dir, page, response.text)
        rows = parse_session_law_page(response.text, page_url)
        if not rows:
            break
        page_records.extend((record, page_path) for record in rows)
        if f"?page={page + 1}" not in response.text and page > 1:
            break
        page += 1

    evidence = _build_raw_evidence(page_records, raw_dir, download_pdfs, max_downloads)
    session_laws = [_to_session_law(record) for record, _ in page_records]
    index_rows = [
        _to_index_row(resolved_root, record, law, evidence[record.entity_id])
        for record, law in zip((record for record, _ in page_records), session_laws)
    ]
    _write_layer_outputs(resolved_root, session_laws, index_rows, meta_path, index_path)
    _refresh_manifest(resolved_root, len(session_laws))
    summary = SessionLawPipelineSummary(
        discovered=len(page_records),
        downloaded=sum(item.path.suffix.lower() == ".pdf" for item in evidence.values()),
        failed_downloads=sum(item.download_failed for item in evidence.values()),
        index_path=relative_path(index_path, resolved_root),
        meta_path=relative_path(meta_path, resolved_root),
        record_count=len(session_laws),
        raw_dir=relative_path(raw_dir, resolved_root),
        years=sorted({record.session_year for record, _ in page_records}),
    )
    atomic_write_json(layer_dir / "_meta" / "session_laws_summary.json", summary, resolved_root)
    return summary


def _build_raw_evidence(
    records: list[tuple[SessionLawDiscoveryRecord, Path]],
    raw_dir: Path,
    download_pdfs: bool,
    max_downloads: int | None,
) -> dict[str, _RawEvidence]:
    """Return raw source evidence for each discovered session law."""

    evidence: dict[str, _RawEvidence] = {}
    download_count = 0
    for record, page_path in records:
        if download_pdfs and (max_downloads is None or download_count < max_downloads):
            target = raw_dir / record.session_year / f"{record.entity_id}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                evidence[record.entity_id] = _download_pdf_evidence(record, target)
                download_count += 1
            except requests.RequestException:
                evidence[record.entity_id] = _RawEvidence(
                    page_path,
                    sha256_file(page_path),
                    download_failed=True,
                )
        else:
            evidence[record.entity_id] = _RawEvidence(page_path, sha256_file(page_path))
    return evidence


def _preserve_page_evidence(raw_dir: Path, page: int, text: str) -> Path:
    """Write a page snapshot without overwriting existing raw evidence."""

    page_path = raw_dir / "pages" / f"session_laws_page_{page:03d}.html"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    content = text.encode("utf-8")
    if not page_path.exists():
        page_path.write_bytes(content)
        return page_path
    if page_path.read_bytes() == content:
        return page_path
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    versioned = page_path.with_name(f"{page_path.stem}_{timestamp}{page_path.suffix}")
    versioned.write_bytes(content)
    return versioned


def _download_pdf_evidence(record: SessionLawDiscoveryRecord, target: Path) -> _RawEvidence:
    """Download one chapter PDF without overwriting existing raw evidence."""

    if target.exists():
        return _RawEvidence(target, sha256_file(target), is_pdf=True)
    response = requests.get(
        str(record.source_url),
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise requests.RequestException(f"session law download was not a PDF: {record.source_url}")
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp_path.write_bytes(response.content)
        tmp_path.replace(target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return _RawEvidence(target, sha256_file(target), is_pdf=True)


def _to_session_law(record: SessionLawDiscoveryRecord) -> SessionLaw:
    """Convert a discovery row into a validated session-law record."""

    return SessionLaw(
        id=record.entity_id,
        session_year=record.session_year,
        chapter=record.chapter,
        bill_id=record.bill_id,
        title=record.title,
        effective_date=record.effective_date,
        statutes_affected=[],
        summary=f"{record.bill_id}: {record.title}",
        subject_tags=[],
        source_url=str(record.source_url),
        confidence={"overall": 0.82, "fields": {}, "route": "official_session_laws_table"},
    )


def _to_index_row(
    root: Path,
    record: SessionLawDiscoveryRecord,
    law: SessionLaw,
    evidence: _RawEvidence,
) -> LayerIndexRecord:
    """Build one layer index row."""

    return LayerIndexRecord(
        id=law.id,
        layer=LAYER,
        entity_type="session_law",
        title=law.title,
        citation=f"Chapter {law.chapter}, {law.session_year} Session Laws",
        path=f"{LAYER}/{law.session_year}/session_laws_{law.session_year}.jsonl",
        meta_path=f"{LAYER}/_meta/{META_NAME}",
        source_url=str(record.source_url),
        source_path=relative_path(evidence.path, root),
        publication_year=int(law.session_year),
        last_updated=datetime.now(timezone.utc),
        sha256=evidence.sha256,
        tags=[],
        confidence=law.confidence.overall,
    )


def _write_layer_outputs(
    root: Path,
    records: list[SessionLaw],
    index_rows: list[LayerIndexRecord],
    meta_path: Path,
    index_path: Path,
) -> None:
    """Write session-law JSONL outputs."""

    by_year: dict[str, list[SessionLaw]] = defaultdict(list)
    for record in records:
        by_year[record.session_year].append(record)
    for year, rows in sorted(by_year.items()):
        atomic_write_jsonl(root / LAYER / year / f"session_laws_{year}.jsonl", rows, root)
    atomic_write_jsonl(meta_path, records, root)
    atomic_write_jsonl(index_path, index_rows, root)


def _refresh_manifest(root: Path, record_count: int) -> None:
    """Refresh the master manifest session-law layer entry."""

    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("MASTER_MANIFEST.json must contain an object")
    for layer in manifest.get("data_layers", []):
        if isinstance(layer, dict) and layer.get("id") == LAYER:
            layer["record_count"] = record_count
            layer["last_ingested"] = date.today().isoformat()
            layer["last_checked"] = date.today().isoformat()
            layer["staleness_days"] = 0
            layer["status"] = "ready" if record_count else "empty"
            break
    atomic_write_json(manifest_path, manifest, root)


def _session_year(html_text: str) -> str:
    """Extract the session year from the official page heading."""

    match = SESSION_YEAR_RE.search(html_text)
    if not match:
        raise ValueError("session-law page did not expose a session year")
    return match.group("year")


def _anchor(value: str) -> tuple[str, str] | None:
    """Return href and body for the first anchor in a cell."""

    match = ANCHOR_RE.search(value)
    if not match:
        return None
    return html.unescape(match.group("href")), match.group("body")


def _text(value: str) -> str:
    """Return normalized plain text from a small HTML fragment."""

    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    value = TAG_RE.sub(" ", value)
    return " ".join(html.unescape(value).split())


def _parse_date(value: str) -> date | None:
    """Parse official MM/DD/YYYY dates."""

    if not value:
        return None
    match = DATE_RE.match(value)
    if not match:
        return None
    return date(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the session-law command parser."""

    parser = argparse.ArgumentParser(description="Collect official Colorado session laws.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--download-pdfs", action="store_true")
    parser.add_argument("--max-downloads", type=int)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    """Run the session-law collector."""

    args = build_parser().parse_args()
    summary = write_session_laws_dataset(
        args.root,
        download_pdfs=args.download_pdfs,
        max_downloads=args.max_downloads,
        max_pages=args.max_pages,
    )
    if args.json:
        print(summary.model_dump_json(indent=2))
    else:
        print(f"Session laws written: {summary.record_count}")


if __name__ == "__main__":
    main()
