"""Colorado Register and eDocket normalization pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.archive_paths import (
    download_manifest_path,
    raw_connector_dir,
    safe_archive_stem,
    url_suffix,
)
from geode.connectors.register_table_parser import (
    RegisterTableNotice,
    extract_register_table_notices,
)
from geode.connectors.register_scraper import (
    REGISTER_URL,
    RegisterDownload,
    download_all_publications,
)
from geode.constants import CONTROL_PLANE_DIR, RAW_ARCHIVE_DIR
from geode.extractors.converter import convert_to_markdown
from geode.net.http_client import GeodeBlockedError, GeodeHttpClient, GeodeHttpClientConfig
from geode.schemas import CrosswalkEntry, LayerIndexRecord, RulemakingNotice
from geode.utils.file_io import (
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    iter_jsonl,
    load_json,
    relative_path,
)
from geode.utils.hashing import sha256_text
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)

RULEMAKING_LAYER = "04_Rulemaking"
DATASET_DIR = "_dataset"
META_DIR = "_meta"
NOTICE_DATASET_NAME = "rulemaking_notices.jsonl"
NOTICE_CSV_NAME = "rulemaking_notices.csv"
NOTICE_SUMMARY_NAME = "rulemaking_summary.json"
NOTICE_META_NAME = "rulemaking_notices_meta.jsonl"
RULEMAKING_CROSSWALK_NAME = "rulemaking_to_regulation.jsonl"
QUALITY_DIR = "_quality"
QUALITY_REPORT_NAME = "register_extraction_quality.json"
GAP_REPORT_NAME = "register_extraction_gaps.jsonl"
QUARANTINE_NAME = "register_extraction_quarantine.jsonl"
REVIEW_HIGH_CONFIDENCE_NAME = "review_sample_high_confidence.jsonl"
REVIEW_LOW_CONFIDENCE_NAME = "review_sample_low_confidence.jsonl"
REVIEW_QUARANTINE_NAME = "review_sample_quarantine.jsonl"
EDOCKET_DETAIL_DATASET_NAME = "edocket_details.jsonl"
EDOCKET_DOCUMENT_DATASET_NAME = "edocket_documents.jsonl"
EDOCKET_PUBLIC_URL = "https://www.sos.state.co.us/CCR/eDocketPublic.do"

STRUCTURED_NOTICE_RE = re.compile(
    r"NOTICE:\s*(?P<notice_type>[^|]+)\|\s*CCR:\s*(?P<ccr>[^|]+)\|"
    r"\s*Agency:\s*(?P<agency>[^|]+)\|\s*Publication:\s*(?P<publication>[^|]+)"
    r"(?:\|\s*Hearing:\s*(?P<hearing>[^|]+))?"
    r"(?:\|\s*Effective:\s*(?P<effective>[^|]+))?"
    r"(?:\|\s*eDocket:\s*(?P<edocket>[^|]+))?"
    r"\|\s*Summary:\s*(?P<summary>.+)",
    re.IGNORECASE,
)
CCR_RE = re.compile(r"\b(?P<ccr>\d{1,2}\s+CCR\s+\d+-\d+(?:-\d+)?)\b", re.IGNORECASE)
EDOCKET_RE = re.compile(
    r"\b(?:eDocket|tracking(?:\s+number)?|tracking\s+no\.?)[:#\s]+"
    r"(?P<edocket>[A-Za-z0-9][A-Za-z0-9_-]{3,})",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"\b(20\d{2})[-_/](\d{1,2})[-_/](\d{1,2})\b")
URL_RE = re.compile(r"https://www\.sos\.state\.co\.us/[^\s)'\"<>]+", re.IGNORECASE)
RELATIVE_EDOCKET_URL_RE = re.compile(r"""['"](?P<url>/CCR/eDocket[^'"]+)['"]""", re.IGNORECASE)
TRACKING_NUM_RE = re.compile(r"\btrackingNum=(?P<edocket>[A-Za-z0-9_-]+)", re.IGNORECASE)
DOCUMENT_HREF_RE = re.compile(
    r"""href=['"](?P<href>[^'"]+\.(?:pdf|docx?|rtf|html?)(?:\?[^'"]*)?)['"]""",
    re.IGNORECASE,
)

SUBJECT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("air_quality", ("air quality", "emission", "stationary source", "ozone")),
    ("water_quality", ("water quality", "discharge", "drinking water", "wastewater")),
    ("solid_waste", ("solid waste", "landfill")),
    ("hazardous_waste", ("hazardous waste", "hazardous material")),
    ("labor_employment", ("employment", "labor", "worker", "workplace")),
    ("wages_hours", ("wage", "paid leave", "overtime")),
    ("workplace_safety", ("safety", "occupational")),
    ("workers_compensation", ("workers' compensation", "workers compensation")),
    ("energy", ("energy", "electric", "gas utility", "utility")),
    ("utility_regulation", ("public utilities", "utility", "pipeline")),
    ("oil_gas", ("oil and gas", "oil", "gas conservation")),
    ("mining", ("mining", "minerals", "reclamation")),
    ("transportation", ("transportation", "motor vehicle", "commercial vehicle")),
    ("rulemaking", ("rulemaking", "rule-making", "notice of")),
    ("permitting", ("permit", "permitting")),
    ("reporting", ("report", "reporting")),
    ("inspection", ("inspection", "inspect")),
    ("enforcement", ("enforcement", "penalty", "fine")),
)


class RulemakingPipelineSummary(BaseModel):
    """Summary from normalized Colorado Register/eDocket processing."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    archive_dir: str
    manifest_path: str
    records_total: int = Field(ge=0)
    source_publications_total: int = Field(ge=0)
    publications_with_notices: int = Field(ge=0)
    extraction_failures: int = Field(ge=0)
    edocket_references_total: int = Field(ge=0)
    ccr_crosswalk_rows_total: int = Field(ge=0)
    dataset_jsonl_path: str
    dataset_csv_path: str
    index_path: str
    meta_path: str
    summary_path: str
    crosswalk_path: str
    quality_report_path: str
    gap_report_path: str
    quarantine_path: str
    review_sample_paths: list[str] = Field(default_factory=list)
    edocket_detail_dataset_path: str | None = None
    edocket_document_dataset_path: str | None = None
    edocket_details_fetched: int = Field(default=0, ge=0)
    edocket_details_failed: int = Field(default=0, ge=0)
    edocket_documents_downloaded: int = Field(default=0, ge=0)
    edocket_documents_failed: int = Field(default=0, ge=0)
    gap_rows_total: int = Field(default=0, ge=0)
    quarantine_rows_total: int = Field(default=0, ge=0)
    year_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExtractedNotice(BaseModel):
    """Internal normalized notice candidate before schema validation."""

    model_config = ConfigDict(extra="forbid")

    notice_type: str
    ccr_citation: str
    ccr_rule_affected: str
    agency_code: str
    agency: str | None = None
    summary: str
    publication_date: str
    hearing_date: str | None = None
    effective_date: str | None = None
    edocket_tracking_number: str | None = None
    edocket_url: str | None = None
    source_url: str
    source_path: str | None = None
    extraction_method: str
    source_section_heading: str | None = None
    source_row_number: int | None = None
    source_evidence: str | None = None
    notice_type_source: str | None = None
    field_confidence: dict[str, float] = Field(default_factory=dict)


class RegisterExtractionGap(BaseModel):
    """A Register publication that did not produce normalized notice records."""

    model_config = ConfigDict(extra="forbid")

    publication_date: str | None = None
    source_url: str
    source_path: str | None = None
    reason: str
    ccr_candidates: list[str] = Field(default_factory=list)
    edocket_candidates: list[str] = Field(default_factory=list)


class RegisterExtractionQuarantineRecord(BaseModel):
    """A source artifact that needs review because extraction signals conflict."""

    model_config = ConfigDict(extra="forbid")

    publication_date: str | None = None
    source_url: str
    source_path: str | None = None
    reason: str
    evidence: str
    ccr_candidates: list[str] = Field(default_factory=list)
    edocket_candidates: list[str] = Field(default_factory=list)


class RegisterExtractionBatch(BaseModel):
    """Extraction results and audit diagnostics from archived Register publications."""

    model_config = ConfigDict(extra="forbid")

    records: list[RulemakingNotice] = Field(default_factory=list)
    source_count: int = Field(ge=0)
    publications_with_notices: int = Field(ge=0)
    failures: int = Field(ge=0)
    gaps: list[RegisterExtractionGap] = Field(default_factory=list)
    quarantine: list[RegisterExtractionQuarantineRecord] = Field(default_factory=list)


class RegisterExtractionQualityReport(BaseModel):
    """Aggregate quality report for Register extraction."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    source_publications_total: int = Field(ge=0)
    records_total: int = Field(ge=0)
    publications_with_notices: int = Field(ge=0)
    publications_without_notices: int = Field(ge=0)
    extraction_failures: int = Field(ge=0)
    edocket_references_total: int = Field(ge=0)
    ccr_crosswalk_rows_total: int = Field(ge=0)
    gap_rows_total: int = Field(ge=0)
    quarantine_rows_total: int = Field(ge=0)
    method_counts: dict[str, int] = Field(default_factory=dict)
    notice_type_counts: dict[str, int] = Field(default_factory=dict)
    confidence_buckets: dict[str, int] = Field(default_factory=dict)
    missing_field_counts: dict[str, int] = Field(default_factory=dict)


class EdocketDetailRecord(BaseModel):
    """Downloaded or attempted eDocket detail page record."""

    model_config = ConfigDict(extra="forbid")

    tracking_number: str
    source_url: str
    archive_path: str | None = None
    status: str
    retrieved_at: datetime
    content_type: str | None = None
    linked_document_count: int = Field(default=0, ge=0)
    text_preview: str | None = None
    error: str | None = None


class EdocketDocumentRecord(BaseModel):
    """Document link discovered from an eDocket detail page."""

    model_config = ConfigDict(extra="forbid")

    tracking_number: str
    document_url: str
    source_detail_url: str
    status: str = "discovered"
    archive_path: str | None = None
    content_type: str | None = None
    downloaded_at: datetime | None = None
    error: str | None = None


class _TextExtractor(HTMLParser):
    """Small HTML text extractor for downloaded Register HTML pages."""

    def __init__(self) -> None:
        """Initialize text collection state."""

        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Collect visible text chunks."""

        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        """Return newline-separated extracted text."""

        return "\n".join(self.parts)


def write_rulemaking_dataset(
    output_root: Path,
    archive_dir: Path | None = None,
    *,
    fetch_edocket_details: bool = False,
    edocket_delay: float = 1.0,
    max_edocket_details: int | None = None,
    download_edocket_documents: bool = False,
) -> RulemakingPipelineSummary:
    """Normalize archived Colorado Register publications into ``04_Rulemaking``.

    Args:
        output_root: Geode project root.
        archive_dir: Optional raw Register archive directory. Defaults to
            ``_RAW_ARCHIVE/register`` under ``output_root``.

    Returns:
        Summary with output locations and record counts.
    """

    root = output_root.resolve()
    raw_dir = archive_dir or raw_connector_dir(root / RAW_ARCHIVE_DIR, "colorado_register")
    manifest_path = download_manifest_path(raw_dir)
    layer_dir = root / RULEMAKING_LAYER
    dataset_dir = layer_dir / DATASET_DIR
    meta_dir = layer_dir / META_DIR
    quality_dir = layer_dir / QUALITY_DIR
    dataset_path = dataset_dir / NOTICE_DATASET_NAME
    csv_path = dataset_dir / NOTICE_CSV_NAME
    summary_path = dataset_dir / NOTICE_SUMMARY_NAME
    index_path = layer_dir / "_index.jsonl"
    meta_path = meta_dir / NOTICE_META_NAME
    crosswalk_path = root / "_CROSSWALKS" / RULEMAKING_CROSSWALK_NAME
    quality_report_path = quality_dir / QUALITY_REPORT_NAME
    gap_report_path = quality_dir / GAP_REPORT_NAME
    quarantine_path = quality_dir / QUARANTINE_NAME
    review_high_path = quality_dir / REVIEW_HIGH_CONFIDENCE_NAME
    review_low_path = quality_dir / REVIEW_LOW_CONFIDENCE_NAME
    review_quarantine_path = quality_dir / REVIEW_QUARANTINE_NAME
    edocket_detail_path = dataset_dir / EDOCKET_DETAIL_DATASET_NAME
    edocket_document_path = dataset_dir / EDOCKET_DOCUMENT_DATASET_NAME

    batch = _records_from_manifest(
        manifest_path,
        root,
    )
    deduped = _dedupe_records(batch.records)
    year_paths = _write_year_files(layer_dir, deduped, root)
    atomic_write_jsonl(dataset_path, deduped, root)
    _write_notice_csv(csv_path, deduped, root)
    atomic_write_jsonl(meta_path, deduped, root)
    atomic_write_jsonl(index_path, _index_rows(deduped, root, index_path), root)
    crosswalk_rows = _write_crosswalk(crosswalk_path, deduped, root)
    atomic_write_jsonl(gap_report_path, batch.gaps, root)
    atomic_write_jsonl(quarantine_path, batch.quarantine, root)
    review_paths = _write_review_samples(
        deduped,
        batch.quarantine,
        review_high_path,
        review_low_path,
        review_quarantine_path,
        root,
    )
    quality_report = _quality_report(
        deduped,
        source_count=batch.source_count,
        publications_with_notices=batch.publications_with_notices,
        failures=batch.failures,
        gaps=batch.gaps,
        quarantine=batch.quarantine,
        crosswalk_rows=len(crosswalk_rows),
    )
    atomic_write_json(quality_report_path, quality_report, root)
    edocket_details: list[EdocketDetailRecord] = []
    edocket_documents: list[EdocketDocumentRecord] = []
    if fetch_edocket_details:
        edocket_details, edocket_documents = fetch_edocket_detail_pages(
            root,
            deduped,
            delay=edocket_delay,
            max_details=max_edocket_details,
            download_documents=download_edocket_documents,
        )
        atomic_write_jsonl(edocket_detail_path, edocket_details, root)
        atomic_write_jsonl(edocket_document_path, edocket_documents, root)
    _refresh_master_manifest(root, len(deduped))

    summary = RulemakingPipelineSummary(
        generated_at=datetime.now(timezone.utc),
        output_root=root.as_posix(),
        archive_dir=raw_dir.as_posix(),
        manifest_path=manifest_path.as_posix(),
        records_total=len(deduped),
        source_publications_total=batch.source_count,
        publications_with_notices=batch.publications_with_notices,
        extraction_failures=batch.failures,
        edocket_references_total=sum(1 for record in deduped if record.edocket_tracking_number),
        ccr_crosswalk_rows_total=len(crosswalk_rows),
        dataset_jsonl_path=dataset_path.as_posix(),
        dataset_csv_path=csv_path.as_posix(),
        index_path=index_path.as_posix(),
        meta_path=meta_path.as_posix(),
        summary_path=summary_path.as_posix(),
        crosswalk_path=crosswalk_path.as_posix(),
        quality_report_path=quality_report_path.as_posix(),
        gap_report_path=gap_report_path.as_posix(),
        quarantine_path=quarantine_path.as_posix(),
        review_sample_paths=[path.as_posix() for path in review_paths],
        edocket_detail_dataset_path=edocket_detail_path.as_posix() if fetch_edocket_details else None,
        edocket_document_dataset_path=edocket_document_path.as_posix()
        if fetch_edocket_details
        else None,
        edocket_details_fetched=sum(
            1 for detail in edocket_details if detail.status in {"downloaded", "skipped_existing"}
        ),
        edocket_details_failed=sum(
            1 for detail in edocket_details if detail.status in {"blocked", "failed"}
        ),
        edocket_documents_downloaded=sum(
            1
            for document in edocket_documents
            if document.status in {"downloaded", "skipped_existing"}
        ),
        edocket_documents_failed=sum(
            1 for document in edocket_documents if document.status in {"blocked", "failed"}
        ),
        gap_rows_total=len(batch.gaps),
        quarantine_rows_total=len(batch.quarantine),
        year_files=[path.as_posix() for path in year_paths],
        warnings=[] if manifest_path.exists() else [f"missing manifest: {manifest_path.as_posix()}"],
    )
    atomic_write_json(summary_path, summary, root)
    LOGGER.info(
        "Wrote Rulemaking dataset records=%s publications=%s edocket_refs=%s jsonl=%s",
        summary.records_total,
        summary.source_publications_total,
        summary.edocket_references_total,
        summary.dataset_jsonl_path,
    )
    return summary


def extract_register_notices(
    text: str,
    source_url: str,
    *,
    publication_date: str | None = None,
    source_path: str | None = None,
) -> list[RulemakingNotice]:
    """Extract conservative Register/eDocket rulemaking notices from text."""

    extracted: list[ExtractedNotice] = []
    for row in extract_register_table_notices(text):
        notice = _notice_from_table_row(
            row,
            source_url,
            publication_date=publication_date,
            source_path=source_path,
        )
        if notice is not None:
            extracted.append(notice)
    for line in text.splitlines():
        match = STRUCTURED_NOTICE_RE.search(line)
        if match:
            notice = _notice_from_structured_match(
                match,
                source_url,
                publication_date=publication_date,
                source_path=source_path,
            )
            if notice is not None:
                extracted.append(notice)
    if not extracted:
        extracted.extend(
            _unstructured_notices(
                text,
                source_url,
                publication_date=publication_date,
                source_path=source_path,
            )
        )
    return [_notice_model(notice) for notice in extracted]


def run_register_pipeline(
    output_root: Path,
    *,
    download: bool = False,
    max_downloads: int | None = None,
    delay: float = 1.0,
    index_url: str = REGISTER_URL,
    years: list[int] | None = None,
    fetch_edocket_details: bool = False,
    edocket_delay: float = 1.0,
    max_edocket_details: int | None = None,
    download_edocket_documents: bool = False,
) -> RulemakingPipelineSummary:
    """Optionally download Register publications, then normalize archived notices."""

    root = output_root.resolve()
    archive_dir = raw_connector_dir(root / RAW_ARCHIVE_DIR, "colorado_register")
    if download:
        download_all_publications(
            archive_dir,
            delay=delay,
            index_url=index_url,
            years=years,
            max_downloads=max_downloads,
        )
    return write_rulemaking_dataset(
        root,
        archive_dir,
        fetch_edocket_details=fetch_edocket_details,
        edocket_delay=edocket_delay,
        max_edocket_details=max_edocket_details,
        download_edocket_documents=download_edocket_documents,
    )


def fetch_edocket_detail_pages(
    output_root: Path,
    records: list[RulemakingNotice],
    *,
    delay: float = 1.0,
    max_details: int | None = None,
    download_documents: bool = False,
) -> tuple[list[EdocketDetailRecord], list[EdocketDocumentRecord]]:
    """Fetch discovered eDocket detail pages and list linked source documents.

    The function only follows eDocket URLs already present in normalized
    Register notice records. It does not fabricate search queries or scrape
    undocumented endpoints.
    """

    root = output_root.resolve()
    archive_dir = raw_connector_dir(root / RAW_ARCHIVE_DIR, "edocket")
    archive_dir.mkdir(parents=True, exist_ok=True)
    client = GeodeHttpClient(
        config=GeodeHttpClientConfig(
            max_retries=3,
            base_delay=max(delay, 0.25),
            throttle_delay_seconds=delay,
            timeout_seconds=30.0,
        )
    )
    details: list[EdocketDetailRecord] = []
    documents: list[EdocketDocumentRecord] = []
    seen: dict[str, str] = {}
    for record in records:
        if not record.edocket_tracking_number or not record.edocket_url:
            continue
        seen.setdefault(record.edocket_tracking_number, str(record.edocket_url).rstrip("/"))
    detail_items = list(sorted(seen.items()))
    if max_details is not None:
        detail_items = detail_items[:max_details]
    for tracking_number, url in detail_items:
        archive_path = archive_dir / f"edocket_{safe_archive_stem(tracking_number)}.html"
        retrieved_at = datetime.now(timezone.utc)
        if archive_path.exists():
            html = archive_path.read_text(encoding="utf-8", errors="ignore")
            linked_docs = _document_links_from_html(html, url, tracking_number)
            details.append(
                EdocketDetailRecord(
                    tracking_number=tracking_number,
                    source_url=url,
                    archive_path=_relative_or_absolute(archive_path, root),
                    status="skipped_existing",
                    retrieved_at=retrieved_at,
                    content_type="text/html",
                    linked_document_count=len(linked_docs),
                    text_preview=_clean_human_text(html)[:500],
                )
            )
            documents.extend(linked_docs)
            continue
        try:
            response = client.get(
                url,
                allowed_content_types=frozenset({"text/html", "application/xhtml+xml"}),
                require_content=True,
            )
        except GeodeBlockedError as exc:
            details.append(_edocket_failure_record(tracking_number, url, "blocked", exc))
            continue
        except Exception as exc:
            details.append(_edocket_failure_record(tracking_number, url, "failed", exc))
            continue
        _write_raw_once(archive_path, response.content)
        linked_docs = _document_links_from_html(response.text, url, tracking_number)
        details.append(
            EdocketDetailRecord(
                tracking_number=tracking_number,
                source_url=url,
                archive_path=_relative_or_absolute(archive_path, root),
                status="downloaded",
                retrieved_at=retrieved_at,
                content_type=response.headers.get("Content-Type"),
                linked_document_count=len(linked_docs),
                text_preview=_clean_human_text(response.text)[:500],
            )
        )
        documents.extend(linked_docs)
    if download_documents:
        documents = _fetch_edocket_documents(root, client, documents)
    client.close()
    return details, _dedupe_edocket_documents(documents)


def _edocket_failure_record(
    tracking_number: str,
    url: str,
    status: str,
    exc: Exception,
) -> EdocketDetailRecord:
    """Build a failed eDocket detail record."""

    return EdocketDetailRecord(
        tracking_number=tracking_number,
        source_url=url,
        status=status,
        retrieved_at=datetime.now(timezone.utc),
        error=str(exc)[:500],
    )


def _document_links_from_html(
    html: str,
    detail_url: str,
    tracking_number: str,
) -> list[EdocketDocumentRecord]:
    """Extract official document links from an eDocket detail page."""

    records: list[EdocketDocumentRecord] = []
    for match in DOCUMENT_HREF_RE.finditer(html):
        document_url = urljoin(detail_url, match.group("href"))
        if "sos.state.co.us" not in document_url.casefold():
            continue
        records.append(
            EdocketDocumentRecord(
                tracking_number=tracking_number,
                document_url=document_url,
                source_detail_url=detail_url,
            )
        )
    return _dedupe_edocket_documents(records)


def _fetch_edocket_documents(
    root: Path,
    client: GeodeHttpClient,
    records: list[EdocketDocumentRecord],
) -> list[EdocketDocumentRecord]:
    """Download discovered eDocket document links into the raw archive."""

    archive_dir = raw_connector_dir(root / RAW_ARCHIVE_DIR, "edocket") / "documents"
    archive_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[EdocketDocumentRecord] = []
    for record in _dedupe_edocket_documents(records):
        archive_path = _edocket_document_archive_path(archive_dir, record)
        downloaded_at = datetime.now(timezone.utc)
        if archive_path.exists():
            downloaded.append(
                record.model_copy(
                    update={
                        "status": "skipped_existing",
                        "archive_path": _relative_or_absolute(archive_path, root),
                        "downloaded_at": downloaded_at,
                    }
                )
            )
            continue
        try:
            response = client.get(
                record.document_url,
                referer=record.source_detail_url,
                require_content=True,
            )
        except GeodeBlockedError as exc:
            downloaded.append(
                record.model_copy(
                    update={"status": "blocked", "downloaded_at": downloaded_at, "error": str(exc)[:500]}
                )
            )
            continue
        except Exception as exc:
            downloaded.append(
                record.model_copy(
                    update={"status": "failed", "downloaded_at": downloaded_at, "error": str(exc)[:500]}
                )
            )
            continue
        _write_raw_once(archive_path, response.content)
        downloaded.append(
            record.model_copy(
                update={
                    "status": "downloaded",
                    "archive_path": _relative_or_absolute(archive_path, root),
                    "content_type": response.headers.get("Content-Type"),
                    "downloaded_at": downloaded_at,
                }
            )
        )
    return downloaded


def _edocket_document_archive_path(archive_dir: Path, record: EdocketDocumentRecord) -> Path:
    """Return a deterministic raw archive path for one eDocket document."""

    suffix = url_suffix(record.document_url, ".bin")
    stem = safe_archive_stem(Path(record.document_url.split("?", 1)[0]).stem)
    return archive_dir / safe_archive_stem(record.tracking_number) / f"{stem}{suffix}"


def _dedupe_edocket_documents(
    records: list[EdocketDocumentRecord],
) -> list[EdocketDocumentRecord]:
    """Return deterministic unique eDocket document records."""

    deduped: dict[tuple[str, str], EdocketDocumentRecord] = {}
    for record in records:
        deduped[(record.tracking_number, record.document_url)] = record
    return [deduped[key] for key in sorted(deduped)]


def _write_raw_once(path: Path, content: bytes) -> None:
    """Write a raw archive artifact once without replacing existing files."""

    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        temp_path.write_bytes(content)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    """Build the Register/eDocket pipeline CLI parser."""

    parser = argparse.ArgumentParser(description="Normalize Colorado Register/eDocket notices.")
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--max-downloads", type=int)
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--fetch-edocket-details", action="store_true")
    parser.add_argument("--edocket-delay", type=float, default=1.0)
    parser.add_argument("--max-edocket-details", type=int)
    parser.add_argument("--download-edocket-documents", action="store_true")
    parser.add_argument("--register-index-url", default=REGISTER_URL)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Register/eDocket pipeline CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(logging, args.log_level))
    if args.max_downloads is not None and args.max_downloads < 0:
        parser.error("--max-downloads cannot be negative")
    if args.delay < 0:
        parser.error("--delay cannot be negative")
    if args.edocket_delay < 0:
        parser.error("--edocket-delay cannot be negative")
    if args.max_edocket_details is not None and args.max_edocket_details < 0:
        parser.error("--max-edocket-details cannot be negative")
    if args.download_edocket_documents and not args.fetch_edocket_details:
        parser.error("--download-edocket-documents requires --fetch-edocket-details")
    if (args.start_year is None) != (args.end_year is None):
        parser.error("--start-year and --end-year must be supplied together")
    if args.start_year is not None and args.end_year is not None and args.start_year > args.end_year:
        parser.error("--start-year cannot be after --end-year")

    try:
        years = (
            list(range(args.start_year, args.end_year + 1))
            if args.start_year is not None and args.end_year is not None
            else None
        )
        if args.download:
            summary = run_register_pipeline(
                args.output_root,
                download=True,
                max_downloads=args.max_downloads,
                delay=args.delay,
                index_url=args.register_index_url,
                years=years,
                fetch_edocket_details=args.fetch_edocket_details,
                edocket_delay=args.edocket_delay,
                max_edocket_details=args.max_edocket_details,
                download_edocket_documents=args.download_edocket_documents,
            )
        else:
            summary = write_rulemaking_dataset(
                args.output_root,
                args.archive_dir,
                fetch_edocket_details=args.fetch_edocket_details,
                edocket_delay=args.edocket_delay,
                max_edocket_details=args.max_edocket_details,
                download_edocket_documents=args.download_edocket_documents,
            )
    except Exception as exc:
        LOGGER.exception("Register/eDocket pipeline failed: %s", exc)
        return 1

    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        _print_summary(summary)
    return 0


def _records_from_manifest(
    manifest_path: Path,
    root: Path,
) -> RegisterExtractionBatch:
    """Return notice records extracted from a Register download manifest."""

    if not manifest_path.exists():
        return RegisterExtractionBatch(source_count=0, publications_with_notices=0, failures=0)
    records: list[RulemakingNotice] = []
    gaps: list[RegisterExtractionGap] = []
    quarantine: list[RegisterExtractionQuarantineRecord] = []
    publications_with_notices = 0
    failures = 0
    latest_entries: dict[str, RegisterDownload] = {}
    for row_number, payload in enumerate(iter_jsonl(manifest_path), start=1):
        try:
            entry = RegisterDownload.model_validate(payload)
        except Exception as exc:
            failures += 1
            LOGGER.warning("Register manifest row invalid row=%s error=%s", row_number, exc)
            continue
        latest_entries[str(entry.source_url or entry.publication.url)] = entry
    for source_count, entry in enumerate(
        [latest_entries[key] for key in sorted(latest_entries)],
        start=1,
    ):
        try:
            archive_path = Path(entry.archive_path)
            if not archive_path.is_absolute():
                archive_path = root / entry.archive_path
            text = _read_publication_text(archive_path, str(entry.source_url or entry.publication.url))
            source_path = _relative_or_absolute(archive_path, root)
            notices = extract_register_notices(
                text,
                str(entry.source_url or entry.publication.url),
                publication_date=entry.publication_date,
                source_path=source_path,
            )
        except Exception as exc:
            failures += 1
            LOGGER.warning("Register notice extraction failed row=%s error=%s", source_count, exc)
            continue
        if notices:
            publications_with_notices += 1
            records.extend(notices)
        else:
            gap, quarantine_row = _gap_records_for_publication(entry, source_path, text)
            gaps.append(gap)
            if quarantine_row is not None:
                quarantine.append(quarantine_row)
    return RegisterExtractionBatch(
        records=records,
        source_count=len(latest_entries),
        publications_with_notices=publications_with_notices,
        failures=failures,
        gaps=gaps,
        quarantine=quarantine,
    )


def _notice_from_table_row(
    row: RegisterTableNotice,
    source_url: str,
    *,
    publication_date: str | None,
    source_path: str | None,
) -> ExtractedNotice | None:
    """Build an extracted notice from a parsed Register table row."""

    pub_date = publication_date or row.effective_date or row.hearing_date
    if not pub_date:
        return None
    agency = row.agency or row.department
    return ExtractedNotice(
        notice_type=row.notice_type,
        ccr_citation=row.ccr_citation,
        ccr_rule_affected=row.ccr_rule_affected,
        agency_code=safe_archive_stem(agency or "UNKNOWN").upper(),
        agency=agency,
        summary=_clean_human_text(row.summary),
        publication_date=pub_date,
        hearing_date=row.hearing_date,
        effective_date=row.effective_date,
        edocket_tracking_number=row.edocket_tracking_number,
        edocket_url=urljoin(source_url, row.edocket_href) if row.edocket_href else None,
        source_url=source_url,
        source_path=source_path,
        extraction_method="register_table_row",
        source_section_heading=row.section_heading,
        source_row_number=row.row_number,
        source_evidence=row.evidence,
        notice_type_source=row.notice_type_source,
        field_confidence={
            "ccr_rule_affected": 0.95,
            "agency": 0.85 if agency else 0.0,
            "notice_type": 0.85 if row.notice_type_source != "default" else 0.55,
            "edocket_tracking_number": 0.95 if row.edocket_tracking_number else 0.0,
            "summary": 0.80,
        },
    )


def _notice_from_structured_match(
    match: re.Match[str],
    source_url: str,
    *,
    publication_date: str | None,
    source_path: str | None,
) -> ExtractedNotice | None:
    """Build an extracted notice from a structured fixture-friendly line."""

    pub_date = _date_text(match.group("publication")) or publication_date
    ccr_citation = _clean(match.group("ccr"))
    if not pub_date or not ccr_citation:
        return None
    edocket = _clean_optional(match.group("edocket")) or _edocket_from_text(match.group(0))
    agency = _clean_optional(match.group("agency"))
    return ExtractedNotice(
        notice_type=_normalize_notice_type(match.group("notice_type")),
        ccr_citation=ccr_citation,
        ccr_rule_affected=_canonical_ccr_id(ccr_citation),
        agency_code=safe_archive_stem(agency or "UNKNOWN").upper(),
        agency=agency,
        summary=_clean_human_text(match.group("summary")),
        publication_date=pub_date,
        hearing_date=_date_text(match.group("hearing")),
        effective_date=_date_text(match.group("effective")),
        edocket_tracking_number=edocket,
        edocket_url=_edocket_url_from_text(match.group(0), source_url),
        source_url=source_url,
        source_path=source_path,
        extraction_method="structured_register_notice_line",
        source_evidence=_clean_human_text(match.group(0))[:1000],
        notice_type_source="structured_notice_line",
        field_confidence={
            "ccr_rule_affected": 0.95,
            "agency": 0.90 if agency else 0.0,
            "notice_type": 0.95,
            "edocket_tracking_number": 0.90 if edocket else 0.0,
            "summary": 0.90,
        },
    )


def _unstructured_notices(
    text: str,
    source_url: str,
    *,
    publication_date: str | None,
    source_path: str | None,
) -> list[ExtractedNotice]:
    """Extract conservative notice records from less structured Register text."""

    records: list[ExtractedNotice] = []
    paragraphs = _paragraphs(text)
    for paragraph in paragraphs:
        lowered = paragraph.casefold()
        if "notice" not in lowered or "rule" not in lowered:
            continue
        ccr_match = CCR_RE.search(paragraph)
        if not ccr_match:
            continue
        pub_date = publication_date or _date_text(paragraph)
        if not pub_date:
            continue
        ccr_citation = _clean(ccr_match.group("ccr"))
        edocket = _edocket_from_text(paragraph)
        records.append(
            ExtractedNotice(
                notice_type=_infer_notice_type(paragraph),
                ccr_citation=ccr_citation,
                ccr_rule_affected=_canonical_ccr_id(ccr_citation),
                agency_code=_infer_agency_code(paragraph),
                agency=_infer_agency_name(paragraph),
                summary=_summarize_paragraph(paragraph),
                publication_date=pub_date,
                hearing_date=_date_after_label(paragraph, "hearing"),
                effective_date=_date_after_label(paragraph, "effective"),
                edocket_tracking_number=edocket,
                edocket_url=_edocket_url_from_text(paragraph, source_url),
                source_url=source_url,
                source_path=source_path,
                extraction_method="conservative_register_text_scan",
                source_evidence=_clean_human_text(paragraph)[:1000],
                notice_type_source="paragraph_keywords",
                field_confidence={
                    "ccr_rule_affected": 0.80,
                    "agency": 0.60 if _infer_agency_name(paragraph) else 0.0,
                    "notice_type": 0.65,
                    "edocket_tracking_number": 0.80 if edocket else 0.0,
                    "summary": 0.65,
                },
            )
        )
    return records


def _notice_model(notice: ExtractedNotice) -> RulemakingNotice:
    """Validate an extracted notice against the corpus schema."""

    payload = notice.model_dump()
    payload.update(
        {
            "entity_type": "rulemaking_notice",
            "id": _notice_id(notice),
            "title": _notice_title(notice),
            "subject_tags": _subject_tags(notice),
            "confidence": {"overall": _confidence_for(notice)},
        }
    )
    if payload.get("edocket_url") is None and notice.edocket_tracking_number:
        payload["edocket_url"] = EDOCKET_PUBLIC_URL
    return RulemakingNotice.model_validate(payload)


def _read_publication_text(path: Path, source_url: str) -> str:
    """Read or convert one archived Register publication into text."""

    suffix = path.suffix.casefold()
    if suffix in {".html", ".htm", ".txt"}:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        return raw
    if suffix == ".pdf":
        return convert_to_markdown(path, source_url=source_url).markdown_text
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except UnicodeDecodeError:
        return ""


def _dedupe_records(records: list[RulemakingNotice]) -> list[RulemakingNotice]:
    """Collapse duplicate notices by canonical notice ID."""

    deduped: dict[str, RulemakingNotice] = {}
    for record in records:
        deduped[record.id] = record
    return [deduped[key] for key in sorted(deduped)]


def _write_year_files(layer_dir: Path, records: list[RulemakingNotice], root: Path) -> list[Path]:
    """Write chronological year/quarter JSONL files."""

    grouped: dict[tuple[int, int], list[RulemakingNotice]] = defaultdict(list)
    for record in records:
        grouped[(record.publication_date.year, _quarter(record.publication_date.month))].append(record)
    written: list[Path] = []
    for (year, quarter), group in sorted(grouped.items()):
        path = layer_dir / str(year) / f"register_{year}_Q{quarter}.jsonl"
        atomic_write_jsonl(path, group, root)
        written.append(path)
    return written


def _write_notice_csv(path: Path, records: list[RulemakingNotice], root: Path) -> None:
    """Write a CSV companion file for analysts."""

    fields = [
        "id",
        "notice_type",
        "ccr_rule_affected",
        "agency_code",
        "publication_date",
        "hearing_date",
        "effective_date",
        "edocket_tracking_number",
        "source_url",
        "source_path",
        "source_section_heading",
        "source_row_number",
        "extraction_method",
        "notice_type_source",
        "summary",
    ]
    rows = []
    for record in records:
        payload = record.model_dump(mode="json")
        rows.append({field: payload.get(field) for field in fields})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(path, output.getvalue(), root)


def _index_rows(
    records: list[RulemakingNotice],
    root: Path,
    index_path: Path,
) -> list[LayerIndexRecord]:
    """Build layer index rows for rulemaking notices."""

    rows = []
    now = datetime.now(timezone.utc)
    existing_by_id = _existing_index_rows(index_path)
    for record in records:
        year = record.publication_date.year
        quarter = _quarter(record.publication_date.month)
        record_path = root / RULEMAKING_LAYER / str(year) / f"register_{year}_Q{quarter}.jsonl"
        meta_path = root / RULEMAKING_LAYER / META_DIR / NOTICE_META_NAME
        source_path = record.source_path or ""
        row_sha = sha256_text(record.model_dump_json())
        existing = existing_by_id.get(record.id)
        last_updated = existing.last_updated if existing and existing.sha256 == row_sha else now
        rows.append(
            LayerIndexRecord(
                id=record.id,
                layer=RULEMAKING_LAYER,
                entity_type="rulemaking_notice",
                title=record.title or record.summary[:100],
                citation=record.ccr_rule_affected,
                path=relative_path(record_path, root),
                meta_path=relative_path(meta_path, root),
                source_url=record.source_url,
                source_path=source_path or str(record.source_url),
                publication_year=year,
                last_updated=last_updated,
                sha256=row_sha,
                tags=record.subject_tags,
                confidence=record.confidence.overall,
            )
        )
    return rows


def _existing_index_rows(index_path: Path) -> dict[str, LayerIndexRecord]:
    """Load existing index rows so unchanged records keep stable timestamps."""

    if not index_path.exists():
        return {}
    rows: dict[str, LayerIndexRecord] = {}
    for payload in iter_jsonl(index_path):
        row = LayerIndexRecord.model_validate(payload)
        rows[row.id] = row
    return rows


def _write_crosswalk(
    path: Path,
    records: list[RulemakingNotice],
    root: Path,
) -> list[CrosswalkEntry]:
    """Write rulemaking-to-regulation crosswalk entries."""

    rows_by_key: dict[str, CrosswalkEntry] = {}
    today = date.today()
    for record in records:
        crosswalk = CrosswalkEntry(
            source_id=record.id,
            source_type="rulemaking_notice",
            target_id=record.ccr_rule_affected,
            target_type="regulation_rule",
            relationship="modified_by",
            confidence=record.confidence.overall,
            source_evidence=record.summary[:240],
            data_retrieved=today,
        )
        rows_by_key[_crosswalk_key(crosswalk)] = crosswalk
    rows = [rows_by_key[key] for key in sorted(rows_by_key)]
    atomic_write_jsonl(path, rows, root)
    return rows


def _quality_report(
    records: list[RulemakingNotice],
    *,
    source_count: int,
    publications_with_notices: int,
    failures: int,
    gaps: list[RegisterExtractionGap],
    quarantine: list[RegisterExtractionQuarantineRecord],
    crosswalk_rows: int,
) -> RegisterExtractionQualityReport:
    """Build an aggregate Register extraction quality report."""

    method_counts: dict[str, int] = defaultdict(int)
    notice_type_counts: dict[str, int] = defaultdict(int)
    confidence_buckets: dict[str, int] = defaultdict(int)
    missing_field_counts: dict[str, int] = defaultdict(int)
    for record in records:
        method_counts[record.extraction_method or "unknown"] += 1
        notice_type_counts[record.notice_type] += 1
        confidence_buckets[_confidence_bucket(record.confidence.overall)] += 1
        for field_name in (
            "agency",
            "hearing_date",
            "effective_date",
            "edocket_tracking_number",
            "source_section_heading",
            "source_row_number",
        ):
            if getattr(record, field_name) in (None, "", []):
                missing_field_counts[field_name] += 1
    return RegisterExtractionQualityReport(
        generated_at=datetime.now(timezone.utc),
        source_publications_total=source_count,
        records_total=len(records),
        publications_with_notices=publications_with_notices,
        publications_without_notices=max(source_count - publications_with_notices, 0),
        extraction_failures=failures,
        edocket_references_total=sum(1 for record in records if record.edocket_tracking_number),
        ccr_crosswalk_rows_total=crosswalk_rows,
        gap_rows_total=len(gaps),
        quarantine_rows_total=len(quarantine),
        method_counts=dict(sorted(method_counts.items())),
        notice_type_counts=dict(sorted(notice_type_counts.items())),
        confidence_buckets=dict(sorted(confidence_buckets.items())),
        missing_field_counts=dict(sorted(missing_field_counts.items())),
    )


def _write_review_samples(
    records: list[RulemakingNotice],
    quarantine: list[RegisterExtractionQuarantineRecord],
    high_path: Path,
    low_path: Path,
    quarantine_path: Path,
    root: Path,
) -> list[Path]:
    """Write bounded review samples for manual QA."""

    high = [record for record in records if record.confidence.overall >= 0.85][:25]
    low = [record for record in records if record.confidence.overall < 0.75][:25]
    quarantine_sample = quarantine[:25]
    atomic_write_jsonl(high_path, high, root)
    atomic_write_jsonl(low_path, low, root)
    atomic_write_jsonl(quarantine_path, quarantine_sample, root)
    return [high_path, low_path, quarantine_path]


def _gap_records_for_publication(
    entry: RegisterDownload,
    source_path: str,
    text: str,
) -> tuple[RegisterExtractionGap, RegisterExtractionQuarantineRecord | None]:
    """Return gap and optional quarantine records for a publication with no notices."""

    ccr_candidates = sorted({_clean(match.group("ccr")) for match in CCR_RE.finditer(text)})
    edocket_candidates = sorted(
        {
            candidate
            for candidate in [
                *(safe_archive_stem(match.group("edocket")) for match in EDOCKET_RE.finditer(text)),
                *(safe_archive_stem(match.group("edocket")) for match in TRACKING_NUM_RE.finditer(text)),
            ]
            if candidate
        }
    )
    source_url = str(entry.source_url or entry.publication.url)
    gap = RegisterExtractionGap(
        publication_date=entry.publication_date,
        source_url=source_url,
        source_path=source_path,
        reason="no_rulemaking_notice_extracted",
        ccr_candidates=ccr_candidates[:50],
        edocket_candidates=edocket_candidates[:50],
    )
    if not ccr_candidates and not edocket_candidates:
        return gap, None
    evidence = _clean_human_text(text)[:1000]
    return gap, RegisterExtractionQuarantineRecord(
        publication_date=entry.publication_date,
        source_url=source_url,
        source_path=source_path,
        reason="source_contains_rulemaking_signals_but_no_notice_was_extracted",
        evidence=evidence,
        ccr_candidates=ccr_candidates[:50],
        edocket_candidates=edocket_candidates[:50],
    )


def _confidence_bucket(confidence: float) -> str:
    """Return a coarse confidence label for reporting."""

    if confidence >= 0.85:
        return "high"
    if confidence >= 0.75:
        return "medium"
    return "low"


def _refresh_master_manifest(root: Path, record_count: int) -> None:
    """Refresh the control-plane manifest entry for the Rulemaking layer."""

    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    if not manifest_path.exists():
        return
    manifest = load_json(manifest_path)
    layers = manifest.get("data_layers", []) if isinstance(manifest, dict) else []
    today = date.today().isoformat()
    if isinstance(layers, list):
        for layer in layers:
            if isinstance(layer, dict) and layer.get("id") == RULEMAKING_LAYER:
                layer["record_count"] = record_count
                layer["last_ingested"] = today if record_count else None
                layer["last_checked"] = today
                layer["staleness_days"] = 0 if record_count else None
                layer["status"] = "ready" if record_count else "empty"
                break
    atomic_write_json(manifest_path, manifest, root)


def _crosswalk_key(row: CrosswalkEntry) -> str:
    """Return a deterministic crosswalk upsert key."""

    target = row.target_id or "|".join(row.target_ids)
    return f"{row.source_id}|{target}|{row.relationship}"


def _paragraphs(text: str) -> list[str]:
    """Return coarse paragraphs from source text."""

    chunks = re.split(r"\n\s*\n|(?=\bNOTICE\b)", text)
    return [_clean(chunk) for chunk in chunks if _clean(chunk)]


def _notice_id(notice: ExtractedNotice) -> str:
    """Return a stable rulemaking notice ID."""

    year = notice.publication_date[:4]
    if notice.edocket_tracking_number:
        return f"RM-{year}-{safe_archive_stem(notice.edocket_tracking_number)}"
    material = "|".join(
        [
            notice.publication_date,
            notice.notice_type,
            notice.ccr_rule_affected,
            notice.agency_code,
            notice.summary,
        ]
    )
    return f"RM-{year}-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:12]}"


def _notice_title(notice: ExtractedNotice) -> str:
    """Return a concise title for one notice."""

    return f"{notice.notice_type.title()} notice for {notice.ccr_citation}"


def _canonical_ccr_id(value: str) -> str:
    """Normalize a CCR citation into the Geode regulation ID form."""

    return re.sub(r"\s+", "_", _clean(value))


def _subject_tags(notice: ExtractedNotice) -> list[str]:
    """Assign conservative subject tags from metadata text."""

    haystack = " ".join(
        part
        for part in [
            notice.summary,
            notice.agency or "",
            notice.agency_code,
            notice.ccr_citation,
            notice.notice_type,
        ]
        if part
    ).casefold()
    tags = {"rulemaking"}
    for tag, keywords in SUBJECT_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            tags.add(tag)
    return sorted(tags)


def _confidence_for(notice: ExtractedNotice) -> float:
    """Return a simple confidence score based on extraction source."""

    if notice.extraction_method == "register_table_row":
        confidence = 0.88
    elif notice.extraction_method == "structured_register_notice_line":
        confidence = 0.82
    else:
        confidence = 0.68
    if notice.edocket_tracking_number:
        confidence += 0.05
    return min(confidence, 0.95)


def _infer_notice_type(text: str) -> str:
    """Infer notice type from free text."""

    lowered = text.casefold()
    for label in ("adopted", "proposed", "emergency", "temporary", "permanent", "repealed"):
        if label in lowered:
            return label
    if "hearing" in lowered:
        return "hearing"
    return "rulemaking"


def _normalize_notice_type(value: str) -> str:
    """Normalize notice-type text."""

    return re.sub(r"[^a-z0-9_]+", "_", value.strip().casefold()).strip("_") or "rulemaking"


def _infer_agency_code(text: str) -> str:
    """Return a conservative agency code from notice text."""

    agency = _infer_agency_name(text) or "UNKNOWN"
    return safe_archive_stem(agency).upper()


def _infer_agency_name(text: str) -> str | None:
    """Extract an agency label when the paragraph exposes one."""

    match = re.search(r"\bAgency:\s*(?P<agency>[^|;\n]+)", text, re.IGNORECASE)
    if match:
        return _clean(match.group("agency"))
    table_cells = _html_table_cells(text)
    if len(table_cells) >= 2:
        return table_cells[1]
    return None


def _summarize_paragraph(paragraph: str) -> str:
    """Return a bounded summary preserving source wording."""

    cleaned = _clean_human_text(paragraph)
    return cleaned[:500]


def _edocket_from_text(text: str) -> str | None:
    """Extract an eDocket tracking number from text when present."""

    tracking_match = TRACKING_NUM_RE.search(text)
    if tracking_match:
        return safe_archive_stem(tracking_match.group("edocket"))
    match = EDOCKET_RE.search(text)
    if not match:
        return None
    return safe_archive_stem(match.group("edocket"))


def _edocket_url_from_text(text: str, source_url: str) -> str | None:
    """Extract an official eDocket URL from text when present."""

    for match in URL_RE.finditer(text):
        url = match.group(0)
        if "edocket" in url.casefold():
            return url
    relative = RELATIVE_EDOCKET_URL_RE.search(text)
    if relative:
        return urljoin(source_url, relative.group("url"))
    return None


def _html_table_cells(text: str) -> list[str]:
    """Extract simple table-cell text from one HTML row fragment."""

    cells = re.findall(r"<td[^>]*>(.*?)</td>", text, flags=re.IGNORECASE | re.DOTALL)
    return [_clean(re.sub(r"<[^>]+>", " ", cell)) for cell in cells if _clean(cell)]


def _date_after_label(text: str, label: str) -> str | None:
    """Find a date close to a named label."""

    match = re.search(label + r"[^0-9]{0,40}(20\d{2}[-_/]\d{1,2}[-_/]\d{1,2})", text, re.I)
    if not match:
        return None
    return _date_text(match.group(1))


def _date_text(value: str | None) -> str | None:
    """Normalize a date-looking string to ISO form."""

    if not value:
        return None
    match = DATE_RE.search(value)
    if not match:
        return None
    return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def _quarter(month: int) -> int:
    """Return calendar quarter for a month number."""

    return ((month - 1) // 3) + 1


def _clean(value: str | None) -> str:
    """Collapse whitespace in source text."""

    return re.sub(r"\s+", " ", value or "").strip()


def _clean_optional(value: str | None) -> str | None:
    """Return cleaned text or ``None``."""

    cleaned = _clean(value)
    return cleaned or None


def _clean_human_text(value: str | None) -> str:
    """Collapse whitespace and remove simple HTML markup from source text."""

    return _clean(re.sub(r"<[^>]+>", " ", value or ""))


def _relative_or_absolute(path: Path, root: Path) -> str:
    """Return a stable source path string."""

    try:
        return relative_path(path, root)
    except ValueError:
        return path.as_posix()


def _print_summary(summary: RulemakingPipelineSummary) -> None:
    """Print a short human-readable summary."""

    print(f"Rulemaking records: {summary.records_total}")
    print(f"Source publications: {summary.source_publications_total}")
    print(f"eDocket references: {summary.edocket_references_total}")
    print(f"Dataset: {summary.dataset_jsonl_path}")
    print(f"Index: {summary.index_path}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
