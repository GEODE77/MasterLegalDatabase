"""Colorado Attorney General opinion acquisition and structuring."""

from __future__ import annotations

import argparse
import html
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import fitz
import requests
from pydantic import BaseModel, Field, HttpUrl, field_validator

from geode.constants import CONTROL_PLANE_DIR
from geode.extractors.citation_extractor import extract_crs_citations
from geode.schemas.models import AGOpinion, LayerIndexRecord
from geode.schemas.validators import require_official_source_url
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl, load_json, relative_path
from geode.utils.hashing import sha256_file

MAIN_URL = "https://coag.gov/attorney-general-opinions/"
LAYER = "07_Supplementary"
RAW_DIR = "_RAW_ARCHIVE/supplementary/ag_opinions"
META_NAME = "ag_opinions_meta.jsonl"

ANCHOR_RE = re.compile(
    r"<a\b[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<body>.*?)</a>",
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
YEAR_PAGE_RE = re.compile(
    r"https://coag\.gov/(?:attorney-general-opinions/)?"
    r"(?:20\d{2}|201\d)-formal-ag-opinions(?:-2)?/"
)
OPINION_LINK_RE = re.compile(r"No\.\s*(?P<number>\d{2}-\d{2,3})\s*\(PDF\)", re.IGNORECASE)
OPINION_NUMBER_RE = re.compile(r"No\.\s*(?P<number>\d{2}-\d{2,3})", re.IGNORECASE)
NUMERIC_DATE_RE = re.compile(r"\b(?P<date>\d{1,2}/\d{1,2}/\d{4})\b")
MONTH_DATE_RE = re.compile(
    r"\b(?P<date>(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4})\b",
    re.IGNORECASE,
)
ATTORNEY_GENERAL_RE = re.compile(r"of\s+(?P<name>[A-Z][A-Z .]+?)\s+Attorney General")


class AGOpinionLink(BaseModel):
    """One AG opinion PDF link discovered from an official year page."""

    opinion_number: str
    source_page_url: HttpUrl
    source_url: HttpUrl
    title: str

    @field_validator("source_page_url", "source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value


class AGOpinionPipelineSummary(BaseModel):
    """Summary of an AG opinion acquisition run."""

    discovered: int = Field(ge=0)
    downloaded: int = Field(ge=0)
    failed: int = Field(ge=0)
    index_path: str
    meta_path: str
    record_count: int = Field(ge=0)
    raw_dir: str
    years: list[str]


def discover_ag_opinion_links(max_year_pages: int | None = None) -> list[AGOpinionLink]:
    """Discover AG opinion PDF links from official opinion pages."""

    main_html = _fetch_text(MAIN_URL)
    year_urls = _year_page_urls(main_html)
    if max_year_pages is not None:
        year_urls = year_urls[:max_year_pages]
    links: list[AGOpinionLink] = []
    for year_url in year_urls:
        page_html = _fetch_text(year_url)
        links.extend(_opinion_links_from_year_page(page_html, year_url))
    return _dedupe_links(links)


def write_ag_opinions_dataset(
    root: Path,
    *,
    max_opinions: int | None = None,
    max_year_pages: int | None = None,
) -> AGOpinionPipelineSummary:
    """Collect and structure official Colorado Attorney General opinions."""

    resolved_root = root.resolve()
    raw_dir = resolved_root / RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    links = discover_ag_opinion_links(max_year_pages=max_year_pages)
    if max_opinions is not None:
        links = links[:max_opinions]
    records: list[AGOpinion] = []
    index_rows: list[LayerIndexRecord] = []
    failed = 0
    for link in links:
        try:
            pdf_path = _download_pdf(raw_dir, link)
            text = _extract_pdf_text(pdf_path)
            record = _to_ag_opinion(link, text)
            records.append(record)
            index_rows.append(_to_index_row(resolved_root, link, record, pdf_path))
        except Exception:
            failed += 1
    meta_path = resolved_root / LAYER / "_meta" / META_NAME
    index_path = resolved_root / LAYER / "_index.jsonl"
    _write_outputs(resolved_root, records, index_rows, meta_path, index_path)
    _refresh_manifest(resolved_root, len(records))
    summary = AGOpinionPipelineSummary(
        discovered=len(links),
        downloaded=len(records),
        failed=failed,
        index_path=relative_path(index_path, resolved_root),
        meta_path=relative_path(meta_path, resolved_root),
        record_count=len(records),
        raw_dir=relative_path(raw_dir, resolved_root),
        years=sorted({record.issued_date.isoformat()[:4] for record in records}),
    )
    atomic_write_json(
        resolved_root / LAYER / "_meta" / "ag_opinions_summary.json",
        summary,
        resolved_root,
    )
    return summary


def _year_page_urls(main_html: str) -> list[str]:
    """Return official yearly AG opinion pages."""

    urls = []
    for href, _body in _anchors(main_html):
        absolute = urljoin(MAIN_URL, href)
        if YEAR_PAGE_RE.search(absolute) and absolute not in urls:
            urls.append(absolute)
    normalized = html.unescape(main_html).replace("\\/", "/")
    for match in YEAR_PAGE_RE.finditer(normalized):
        if match.group(0) not in urls:
            urls.append(match.group(0))
    return urls


def _opinion_links_from_year_page(page_html: str, page_url: str) -> list[AGOpinionLink]:
    """Extract opinion PDF links from one official year page."""

    links = []
    for href, body in _anchors(page_html):
        body_text = _text(body)
        match = OPINION_LINK_RE.search(body_text)
        if not match:
            continue
        title = _nearby_title(page_html, body_text)
        links.append(
            AGOpinionLink(
                opinion_number=match.group("number"),
                source_page_url=page_url,
                source_url=urljoin(page_url, href),
                title=title,
            )
        )
    return links


def _dedupe_links(links: list[AGOpinionLink]) -> list[AGOpinionLink]:
    """Dedupe opinion links by URL."""

    by_url: dict[str, AGOpinionLink] = {}
    for link in links:
        by_url[str(link.source_url)] = link
    return list(by_url.values())


def _download_pdf(raw_dir: Path, link: AGOpinionLink) -> Path:
    """Download one AG opinion PDF to the raw archive."""

    year = f"20{link.opinion_number.split('-', 1)[0]}"
    number = link.opinion_number.split("-", 1)[1]
    target = raw_dir / year / f"AGO-{year}-{number}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return target
    response = requests.get(str(link.source_url), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"AG opinion download was not a PDF: {link.source_url}")
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp_path.write_bytes(response.content)
        tmp_path.replace(target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return target


def _extract_pdf_text(path: Path) -> str:
    """Extract text from an AG opinion PDF."""

    with fitz.open(path) as document:
        return "\n".join(page.get_text() for page in document)


def _to_ag_opinion(link: AGOpinionLink, text: str) -> AGOpinion:
    """Convert one official PDF into a validated AG opinion record."""

    number = _opinion_number(text)
    issued = _issued_date(text)
    year = issued.year
    number_suffix = number.split("-", 1)[1]
    attorney_general = _attorney_general(text)
    citations = [citation.canonical_form for citation in extract_crs_citations(text)]
    title = link.title.split(" Return to main opinion page", 1)[0].strip()
    return AGOpinion(
        id=f"AGO-{year}-{number_suffix}",
        opinion_number=number,
        title=title,
        attorney_general=attorney_general,
        issued_date=issued,
        statutes_interpreted=sorted(set(citations)),
        summary=title,
        subject_tags=[],
        source_url=str(link.source_url),
        confidence={"overall": 0.84, "fields": {}, "route": "official_ag_pdf"},
    )


def _to_index_row(
    root: Path,
    link: AGOpinionLink,
    record: AGOpinion,
    pdf_path: Path,
) -> LayerIndexRecord:
    """Build one supplementary index row."""

    return LayerIndexRecord(
        id=record.id,
        layer=LAYER,
        entity_type="ag_opinion",
        title=record.title,
        citation=record.opinion_number,
        path=f"{LAYER}/ag_opinions/ag_opinions_{record.issued_date.year}.jsonl",
        meta_path=f"{LAYER}/_meta/{META_NAME}",
        source_url=str(link.source_url),
        source_path=relative_path(pdf_path, root),
        publication_year=record.issued_date.year,
        last_updated=datetime.now(timezone.utc),
        sha256=sha256_file(pdf_path),
        tags=[],
        confidence=record.confidence.overall,
    )


def _write_outputs(
    root: Path,
    records: list[AGOpinion],
    index_rows: list[LayerIndexRecord],
    meta_path: Path,
    index_path: Path,
) -> None:
    """Write supplementary AG opinion outputs."""

    by_year: dict[int, list[AGOpinion]] = defaultdict(list)
    for record in records:
        by_year[record.issued_date.year].append(record)
    for year, rows in sorted(by_year.items()):
        atomic_write_jsonl(root / LAYER / "ag_opinions" / f"ag_opinions_{year}.jsonl", rows, root)
    atomic_write_jsonl(meta_path, records, root)
    existing = [
        LayerIndexRecord.model_validate(row)
        for row in iter_jsonl(index_path)
        if row.get("entity_type") != "ag_opinion"
    ] if index_path.exists() else []
    atomic_write_jsonl(index_path, [*existing, *index_rows], root)


def _refresh_manifest(root: Path, record_count: int) -> None:
    """Refresh the master manifest supplementary layer entry."""

    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    index_path = root / LAYER / "_index.jsonl"
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("MASTER_MANIFEST.json must contain an object")
    layer_count = sum(1 for _ in iter_jsonl(index_path)) if index_path.exists() else record_count
    for layer in manifest.get("data_layers", []):
        if isinstance(layer, dict) and layer.get("id") == LAYER:
            layer["record_count"] = layer_count
            layer["last_ingested"] = date.today().isoformat()
            layer["last_checked"] = date.today().isoformat()
            layer["staleness_days"] = 0
            layer["status"] = "ready" if layer_count else "empty"
            break
    atomic_write_json(manifest_path, manifest, root)


def _fetch_text(url: str) -> str:
    """Fetch one official page."""

    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return response.text


def _anchors(value: str) -> list[tuple[str, str]]:
    """Return href and body for all anchors."""

    return [
        (html.unescape(match.group("href")), match.group("body"))
        for match in ANCHOR_RE.finditer(value)
    ]


def _text(value: str) -> str:
    """Return normalized text from an HTML fragment."""

    return " ".join(html.unescape(TAG_RE.sub(" ", value)).split())


def _nearby_title(page_html: str, link_text: str) -> str:
    """Extract the text following the opinion link from a paragraph."""

    index = _text(page_html).find(link_text)
    if index < 0:
        return link_text
    tail = _text(page_html)[index + len(link_text) : index + len(link_text) + 260]
    return tail.lstrip(" -–—") or link_text


def _parse_date(value: str) -> date:
    """Parse dates from opinion PDFs."""

    if "/" in value:
        month, day, year = (int(part) for part in value.split("/"))
        return date(year, month, day)
    return datetime.strptime(value, "%B %d, %Y").date()


def _opinion_number(text: str) -> str:
    """Extract an official opinion number."""

    match = OPINION_NUMBER_RE.search(text)
    if not match:
        raise ValueError("opinion number not found in PDF text")
    return match.group("number")


def _issued_date(text: str) -> date:
    """Extract the issued date from official opinion text."""

    numeric = NUMERIC_DATE_RE.search(text)
    if numeric:
        return _parse_date(numeric.group("date"))
    month = MONTH_DATE_RE.search(text)
    if month:
        return _parse_date(month.group("date"))
    raise ValueError("issued date not found in PDF text")


def _attorney_general(text: str) -> str:
    """Extract attorney general name from PDF text."""

    match = ATTORNEY_GENERAL_RE.search(text)
    if not match:
        return "Unknown Attorney General"
    return " ".join(
        part.capitalize() if len(part) > 1 else part for part in match.group("name").split()
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the AG opinion command parser."""

    parser = argparse.ArgumentParser(description="Collect official Colorado AG opinions.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--max-opinions", type=int)
    parser.add_argument("--max-year-pages", type=int)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    """Run the AG opinion collector."""

    args = build_parser().parse_args()
    summary = write_ag_opinions_dataset(
        args.root,
        max_opinions=args.max_opinions,
        max_year_pages=args.max_year_pages,
    )
    if args.json:
        print(summary.model_dump_json(indent=2))
    else:
        print(f"AG opinions written: {summary.record_count}")


if __name__ == "__main__":
    main()
