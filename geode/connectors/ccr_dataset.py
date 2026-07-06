"""Normalized CCR acquisition dataset writer."""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.archive_paths import download_manifest_path
from geode.connectors.ccr_identity import canonical_ccr_id
from geode.constants import RAW_ARCHIVE_DIR
from geode.pipeline.writer import ensure_project_structure
from geode.schemas import LayerIndexRecord
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, atomic_write_text
from geode.utils.hashing import sha256_text
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)

REGULATIONS_LAYER = "02_Regulations_CCR"
DATASET_DIR_NAME = "_dataset"
NORMALIZED_DIR_NAME = "_normalized"
NORMALIZED_RECORDS_DIR_NAME = "records"
NORMALIZED_META_NAME = "ccr_normalized_meta.jsonl"
NORMALIZED_JSONL_NAME = "ccr_normalized_records.jsonl"
NORMALIZED_SUMMARY_NAME = "ccr_normalization_summary.json"
BULK_QUEUE_NAME = "ccr_bulk_queue.jsonl"
DATASET_JSONL_NAME = "ccr_items.jsonl"
DATASET_CSV_NAME = "ccr_items.csv"
DATASET_SUMMARY_NAME = "ccr_dataset_summary.json"
CCR_WELCOME_URL = "https://www.sos.state.co.us/CCR/Welcome.do"

TERMINAL_DOWNLOAD_STATUSES = {
    "downloaded",
    "skipped_existing",
    "failed",
    "failed_permanent",
    "blocked",
}
PENDING_DOWNLOAD_STATUSES = {"discovered", "indexed", "resolved", "pending_retry", "unknown"}
SOURCE_FORMAT_CONTENT_TYPES = {
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "html": "text/html",
    "json": "application/json",
    "pdf": "application/pdf",
}
DIVISION_KEYWORDS = (
    "board",
    "commission",
    "committee",
    "council",
    "division",
    "office",
    "program",
)
CCR_CITATION_RE = re.compile(
    r"^(?P<department_number>\d+)\s+CCR\s+"
    r"(?P<chapter>[A-Za-z0-9.]+)-(?P<rule_number>[A-Za-z0-9_.-]+)$",
    re.IGNORECASE,
)

CCR_DATASET_COLUMNS = (
    "record_id",
    "title",
    "rule_name",
    "department",
    "department_normalized",
    "agency",
    "agency_normalized",
    "division_board_program",
    "ccr_citation",
    "department_number",
    "chapter",
    "rule_number",
    "source_page_url",
    "document_url",
    "file_path",
    "content_type",
    "source_format",
    "download_status",
    "discovery_timestamp",
    "retrieval_timestamp",
    "checksum_sha256",
    "size_bytes",
    "text_extraction_status",
    "raw_file_exists",
    "notes",
    "error",
)


class CCRDatasetRecord(BaseModel):
    """One normalized CCR acquisition dataset row."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1)
    title: str | None = None
    rule_name: str | None = None
    department: str | None = None
    department_normalized: str | None = None
    agency: str | None = None
    agency_normalized: str | None = None
    division_board_program: str | None = None
    ccr_citation: str | None = None
    department_number: str | None = None
    chapter: str | None = None
    rule_number: str | None = None
    source_page_url: str | None = None
    document_url: str | None = None
    file_path: str | None = None
    content_type: str | None = None
    source_format: str | None = None
    download_status: str = Field(min_length=1)
    discovery_timestamp: datetime | None = None
    retrieval_timestamp: datetime | None = None
    checksum_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    size_bytes: int | None = Field(default=None, ge=0)
    text_extraction_status: str = "not_attempted"
    raw_file_exists: bool = False
    notes: str | None = None
    error: str | None = None


class CCRDatasetSummary(BaseModel):
    """Summary artifact for the normalized CCR acquisition dataset."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    dataset_dir: str
    metadata_jsonl_path: str
    metadata_csv_path: str
    summary_path: str
    normalized_records_dir: str | None = None
    normalized_records_jsonl_path: str | None = None
    normalized_meta_path: str | None = None
    normalized_index_path: str | None = None
    normalized_summary_path: str | None = None
    normalized_records_total: int = Field(default=0, ge=0)
    raw_archive_dir: str
    queue_path: str
    manifest_path: str
    records_total: int = Field(ge=0)
    discovered: int = Field(default=0, ge=0)
    resolved: int = Field(default=0, ge=0)
    downloaded: int = Field(ge=0)
    skipped_existing: int = Field(ge=0)
    pending: int = Field(ge=0)
    failed: int = Field(ge=0)
    failed_permanent: int = Field(default=0, ge=0)
    blocked: int = Field(ge=0)
    pending_retry: int = Field(default=0, ge=0)
    raw_file_missing: int = Field(ge=0)
    queue_events_total: int = Field(ge=0)
    manifest_rows_total: int = Field(ge=0)
    duplicate_queue_events_collapsed: int = Field(ge=0)
    duplicate_manifest_rows_collapsed: int = Field(ge=0)


class CCRNormalizedOutputRecord(BaseModel):
    """One final normalized CCR acquisition record under ``02_Regulations_CCR``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    canonical_item_id: str = Field(min_length=1)
    entity_type: str = "regulation_rule_acquisition"
    title: str | None = None
    rule_name: str | None = None
    department: str | None = None
    department_normalized: str | None = None
    agency: str | None = None
    agency_normalized: str | None = None
    division_board_program: str | None = None
    ccr_citation: str | None = None
    department_number: str | None = None
    chapter: str | None = None
    rule_number: str | None = None
    source_page_url: str | None = None
    document_url: str | None = None
    archive_raw_file_path: str | None = None
    normalized_output_path: str
    metadata_output_path: str
    content_type: str | None = None
    source_format: str | None = None
    discovery_timestamp: datetime | None = None
    retrieval_timestamp: datetime | None = None
    normalization_timestamp: datetime
    normalization_status: str = "normalized"
    status: str = Field(min_length=1)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    size_bytes: int | None = Field(default=None, ge=0)
    raw_file_exists: bool = False
    text_extraction_status: str = "not_attempted"
    text_output_path: str | None = None
    notes: str | None = None
    error: str | None = None


class CCRNormalizationSummary(BaseModel):
    """Summary for final normalized CCR acquisition outputs."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    records_dir: str
    records_jsonl_path: str
    meta_path: str
    index_path: str
    summary_path: str
    records_total: int = Field(ge=0)
    discovered: int = Field(default=0, ge=0)
    resolved: int = Field(default=0, ge=0)
    downloaded: int = Field(ge=0)
    pending: int = Field(ge=0)
    failed: int = Field(ge=0)
    failed_permanent: int = Field(default=0, ge=0)
    blocked: int = Field(ge=0)
    pending_retry: int = Field(default=0, ge=0)
    raw_file_missing: int = Field(ge=0)
    stale_record_files_removed: int = Field(ge=0)


class _QueueState(BaseModel):
    """Latest queue state derived from append-only bulk queue events."""

    model_config = ConfigDict(extra="forbid")

    latest_by_id: dict[str, dict[str, Any]]
    first_timestamp_by_id: dict[str, datetime | None]
    order: list[str]
    row_count: int


class _ManifestState(BaseModel):
    """Latest manifest state derived from append-only download manifest rows."""

    model_config = ConfigDict(extra="forbid")

    latest_by_id: dict[str, dict[str, Any]]
    row_count: int


class _DatasetPaths(BaseModel):
    """Canonical paths for normalized CCR dataset artifacts."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    output_root: Path
    archive_dir: Path
    queue_path: Path
    manifest_path: Path
    dataset_dir: Path
    jsonl_path: Path
    csv_path: Path
    summary_path: Path
    normalized_dir: Path
    normalized_records_dir: Path
    normalized_jsonl_path: Path
    normalized_meta_path: Path
    normalized_index_path: Path
    normalized_summary_path: Path


def write_ccr_dataset(output_root: Path) -> CCRDatasetSummary:
    """Write normalized CCR metadata artifacts from acquisition queue and manifest."""

    paths = _dataset_paths(output_root)
    ensure_project_structure(paths.output_root)
    records, queue_state, manifest_state = build_ccr_dataset_records(paths)
    paths.dataset_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_jsonl(paths.jsonl_path, records, paths.output_root)
    _write_csv(paths.csv_path, records, paths.output_root)
    normalization_summary = write_ccr_normalized_outputs(paths, records)
    summary = _build_summary(
        paths,
        records,
        queue_state,
        manifest_state,
        normalization_summary,
    )
    atomic_write_json(paths.summary_path, summary, paths.output_root)
    LOGGER.info(
        "Wrote CCR normalized dataset records=%s jsonl=%s csv=%s",
        summary.records_total,
        summary.metadata_jsonl_path,
        summary.metadata_csv_path,
    )
    return summary


def write_ccr_normalized_outputs(
    paths_or_output_root: _DatasetPaths | Path,
    records: Iterable[CCRDatasetRecord] | None = None,
) -> CCRNormalizationSummary:
    """Write final normalized CCR acquisition outputs under ``02_Regulations_CCR``."""

    paths = (
        paths_or_output_root
        if isinstance(paths_or_output_root, _DatasetPaths)
        else _dataset_paths(paths_or_output_root)
    )
    ensure_project_structure(paths.output_root)
    normalized_records = list(records or build_ccr_dataset_records(paths)[0])
    now = datetime.now(timezone.utc)
    output_records = [
        _normalized_output_record(record, paths, now) for record in normalized_records
    ]
    paths.normalized_records_dir.mkdir(parents=True, exist_ok=True)
    removed = _prune_stale_record_files(paths.normalized_records_dir, output_records)
    for record in output_records:
        atomic_write_json(
            paths.output_root / record.normalized_output_path,
            record,
            paths.output_root,
        )
    atomic_write_jsonl(paths.normalized_jsonl_path, output_records, paths.output_root)
    atomic_write_jsonl(paths.normalized_meta_path, output_records, paths.output_root)
    atomic_write_jsonl(
        paths.normalized_index_path,
        [
            _layer_index_record(record, paths.output_root)
            for record in output_records
        ],
        paths.output_root,
    )
    summary = _build_normalization_summary(paths, output_records, now, removed)
    atomic_write_json(paths.normalized_summary_path, summary, paths.output_root)
    return summary


def build_ccr_dataset_records(
    paths_or_output_root: _DatasetPaths | Path,
) -> tuple[list[CCRDatasetRecord], _QueueState, _ManifestState]:
    """Build normalized CCR records without writing artifacts."""

    paths = (
        paths_or_output_root
        if isinstance(paths_or_output_root, _DatasetPaths)
        else _dataset_paths(paths_or_output_root)
    )
    queue_state = _load_queue_state(paths.queue_path)
    manifest_state = _load_manifest_state(paths.manifest_path)
    records = [
        _build_record(record_id, queue_state, manifest_state, paths.output_root)
        for record_id in _ordered_record_ids(queue_state, manifest_state)
    ]
    return records, queue_state, manifest_state


def build_parser() -> argparse.ArgumentParser:
    """Build the CCR normalized dataset CLI parser."""

    parser = argparse.ArgumentParser(description="Write normalized CCR acquisition dataset.")
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CCR normalized dataset writer CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(logging, args.log_level))
    summary = write_ccr_dataset(args.output_root)
    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        _print_summary(summary)
    return 0


def _dataset_paths(output_root: Path) -> _DatasetPaths:
    """Return canonical dataset artifact paths for one output root."""

    root = output_root.resolve()
    archive_dir = root / RAW_ARCHIVE_DIR / "ccr"
    dataset_dir = root / REGULATIONS_LAYER / DATASET_DIR_NAME
    return _DatasetPaths(
        output_root=root,
        archive_dir=archive_dir,
        queue_path=archive_dir / BULK_QUEUE_NAME,
        manifest_path=download_manifest_path(archive_dir),
        dataset_dir=dataset_dir,
        jsonl_path=dataset_dir / DATASET_JSONL_NAME,
        csv_path=dataset_dir / DATASET_CSV_NAME,
        summary_path=dataset_dir / DATASET_SUMMARY_NAME,
        normalized_dir=root / REGULATIONS_LAYER / NORMALIZED_DIR_NAME,
        normalized_records_dir=(
            root / REGULATIONS_LAYER / NORMALIZED_DIR_NAME / NORMALIZED_RECORDS_DIR_NAME
        ),
        normalized_jsonl_path=(
            root / REGULATIONS_LAYER / NORMALIZED_DIR_NAME / NORMALIZED_JSONL_NAME
        ),
        normalized_meta_path=root / REGULATIONS_LAYER / "_meta" / NORMALIZED_META_NAME,
        normalized_index_path=root / REGULATIONS_LAYER / "_index.jsonl",
        normalized_summary_path=(
            root / REGULATIONS_LAYER / NORMALIZED_DIR_NAME / NORMALIZED_SUMMARY_NAME
        ),
    )


def _load_queue_state(queue_path: Path) -> _QueueState:
    """Load latest queue events by item ID."""

    latest_by_id: dict[str, dict[str, Any]] = {}
    first_timestamp_by_id: dict[str, datetime | None] = {}
    order: list[str] = []
    row_count = 0
    for row in _iter_jsonl_optional(queue_path):
        row_count += 1
        record_id = _record_id_from_row(row)
        if record_id is None:
            continue
        if record_id not in latest_by_id:
            order.append(record_id)
            first_timestamp_by_id[record_id] = _parse_datetime(row.get("timestamp"))
        latest_by_id[record_id] = row
    return _QueueState(
        latest_by_id=latest_by_id,
        first_timestamp_by_id=first_timestamp_by_id,
        order=order,
        row_count=row_count,
    )


def _load_manifest_state(manifest_path: Path) -> _ManifestState:
    """Load latest download manifest rows by record ID."""

    latest_by_id: dict[str, dict[str, Any]] = {}
    row_count = 0
    for row in _iter_jsonl_optional(manifest_path):
        row_count += 1
        record_id = _record_id_from_row(row)
        if record_id is None:
            continue
        latest_by_id[record_id] = row
    return _ManifestState(latest_by_id=latest_by_id, row_count=row_count)


def _iter_jsonl_optional(path: Path) -> Iterator[dict[str, Any]]:
    """Yield JSONL rows from an optional artifact, skipping empty lines."""

    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
            yield payload


def _ordered_record_ids(queue_state: _QueueState, manifest_state: _ManifestState) -> list[str]:
    """Return deterministic record IDs, preserving queue discovery order first."""

    ordered = list(queue_state.order)
    queued = set(ordered)
    manifest_only = sorted(
        record_id for record_id in manifest_state.latest_by_id if record_id not in queued
    )
    return ordered + manifest_only


def _build_record(
    record_id: str,
    queue_state: _QueueState,
    manifest_state: _ManifestState,
    output_root: Path,
) -> CCRDatasetRecord:
    """Build one normalized dataset row from latest queue and manifest data."""

    queue_row = queue_state.latest_by_id.get(record_id, {})
    manifest_row = manifest_state.latest_by_id.get(record_id, {})
    ccr_citation = _first_string(
        manifest_row.get("ccr_number"),
        queue_row.get("ccr_number"),
        manifest_row.get("document_name"),
    )
    citation_parts = _parse_ccr_citation(ccr_citation)
    department = _first_string(manifest_row.get("department"), queue_row.get("department"))
    agency = _first_string(manifest_row.get("agency"), queue_row.get("agency"))
    department_normalized = _normalize_agency_name(department)
    agency_normalized = _normalize_agency_name(agency)
    source_format = _source_format(manifest_row, queue_row)
    file_path = _first_string(manifest_row.get("archive_path"), queue_row.get("archive_path"))
    raw_file_exists = _path_exists(file_path, output_root)
    status = _download_status(queue_row, manifest_row, raw_file_exists)
    title = _title(manifest_row, queue_row, ccr_citation)
    error = _first_string(manifest_row.get("error"), queue_row.get("error"))
    notes = _notes(status, error, file_path, raw_file_exists)
    return CCRDatasetRecord(
        record_id=record_id,
        title=title,
        rule_name=_rule_name(title, ccr_citation),
        department=department,
        department_normalized=department_normalized,
        agency=agency,
        agency_normalized=agency_normalized,
        division_board_program=_division_board_program(agency_normalized),
        ccr_citation=ccr_citation,
        department_number=citation_parts.get("department_number"),
        chapter=citation_parts.get("chapter"),
        rule_number=citation_parts.get("rule_number"),
        source_page_url=_first_string(
            manifest_row.get("source_page_url"),
            queue_row.get("source_page_url"),
        ),
        document_url=_document_url(manifest_row, queue_row),
        file_path=file_path,
        content_type=_content_type(source_format, file_path),
        source_format=source_format,
        download_status=status,
        discovery_timestamp=queue_state.first_timestamp_by_id.get(record_id),
        retrieval_timestamp=_retrieval_timestamp(queue_row, manifest_row),
        checksum_sha256=_first_string(manifest_row.get("sha256")),
        size_bytes=_int_or_none(manifest_row.get("size_bytes")),
        raw_file_exists=raw_file_exists,
        notes=notes,
        error=error,
    )


def _record_id_from_row(row: dict[str, Any]) -> str | None:
    """Return a stable CCR dataset ID from a queue or manifest row."""

    for key in ("item_id", "document_id"):
        value = _first_string(row.get(key))
        if value:
            return value
    ccr_number = _first_string(row.get("ccr_number"), row.get("document_name"))
    if ccr_number is None:
        return None
    return canonical_ccr_id(
        ccr_number,
        source_page_url=row.get("source_page_url"),
        document_url=row.get("source_url") or row.get("preferred_url"),
    )


def _parse_ccr_citation(ccr_citation: str | None) -> dict[str, str]:
    """Parse CCR citation parts where the source citation is structured."""

    if ccr_citation is None:
        return {}
    match = CCR_CITATION_RE.match(_normalize_space(ccr_citation) or "")
    return match.groupdict() if match else {}


def _normalize_agency_name(value: str | None) -> str | None:
    """Normalize agency-like display names without changing their meaning."""

    text = _normalize_space(value)
    if text is None:
        return None
    return re.sub(r"^\d[\d,]*\s+", "", text).strip() or None


def _division_board_program(agency: str | None) -> str | None:
    """Return a division/board/program value when the agency text clearly carries one."""

    if agency is None:
        return None
    agency_lower = agency.casefold()
    if any(keyword in agency_lower for keyword in DIVISION_KEYWORDS):
        return agency
    return None


def _source_format(manifest_row: dict[str, Any], queue_row: dict[str, Any]) -> str | None:
    """Infer a non-lossy source format from manifest, path, or URL data."""

    manifest_format = _first_string(manifest_row.get("source_format"))
    if manifest_format:
        return manifest_format.lower()
    file_path = _first_string(manifest_row.get("archive_path"), queue_row.get("archive_path"))
    suffix_format = _format_from_suffix(file_path)
    if suffix_format:
        return suffix_format
    document_url = _document_url(manifest_row, queue_row)
    if not document_url:
        return None
    lowered = document_url.casefold()
    if "generaterulepdf" in lowered or lowered.endswith(".pdf"):
        return "pdf"
    if "generateruledocx" in lowered or lowered.endswith(".docx"):
        return "docx"
    if "generateruledoc" in lowered or lowered.endswith(".doc"):
        return "doc"
    return None


def _format_from_suffix(file_path: str | None) -> str | None:
    """Return the lower-case extension format from a file path."""

    if not file_path:
        return None
    suffix = Path(file_path).suffix.strip(".").lower()
    return suffix or None


def _content_type(source_format: str | None, file_path: str | None) -> str | None:
    """Return the expected content type for the known acquisition source format."""

    fmt = source_format or _format_from_suffix(file_path)
    if fmt is None:
        return None
    return SOURCE_FORMAT_CONTENT_TYPES.get(fmt.lower())


def _download_status(
    queue_row: dict[str, Any],
    manifest_row: dict[str, Any],
    raw_file_exists: bool,
) -> str:
    """Return the current normalized download status."""

    queue_status = _first_string(queue_row.get("status"))
    manifest_status = _first_string(manifest_row.get("status"))
    if queue_status == "indexed":
        queue_status = "discovered"
    if manifest_status == "failed":
        manifest_status = "failed_permanent"
    if queue_status == "skipped_existing":
        return "skipped_existing"
    if queue_status in TERMINAL_DOWNLOAD_STATUSES:
        return queue_status
    if manifest_status in TERMINAL_DOWNLOAD_STATUSES:
        return manifest_status
    if raw_file_exists:
        return "downloaded"
    if queue_status:
        return queue_status
    if manifest_status:
        return manifest_status
    return "unknown"


def _title(
    manifest_row: dict[str, Any],
    queue_row: dict[str, Any],
    ccr_citation: str | None,
) -> str | None:
    """Return the best non-lossy title available from source metadata."""

    return _first_string(manifest_row.get("document_name"), queue_row.get("title"), ccr_citation)


def _rule_name(title: str | None, ccr_citation: str | None) -> str | None:
    """Return a rule name only when it is more specific than the citation."""

    if title and ccr_citation and title != ccr_citation:
        return title
    return None


def _document_url(manifest_row: dict[str, Any], queue_row: dict[str, Any]) -> str | None:
    """Return the best available document or attachment URL."""

    return _first_string(
        manifest_row.get("source_url"),
        queue_row.get("preferred_url"),
        queue_row.get("docx_url"),
        queue_row.get("pdf_url"),
    )


def _retrieval_timestamp(
    queue_row: dict[str, Any],
    manifest_row: dict[str, Any],
) -> datetime | None:
    """Return the best retrieval timestamp for terminal download states."""

    manifest_timestamp = _parse_datetime(manifest_row.get("downloaded_at"))
    if manifest_timestamp is not None:
        return manifest_timestamp
    queue_status = _first_string(queue_row.get("status"))
    if queue_status in TERMINAL_DOWNLOAD_STATUSES:
        return _parse_datetime(queue_row.get("timestamp"))
    return None


def _notes(
    status: str,
    error: str | None,
    file_path: str | None,
    raw_file_exists: bool,
) -> str | None:
    """Return a compact operator note for non-happy acquisition states."""

    if error:
        return error
    if status in PENDING_DOWNLOAD_STATUSES:
        return "document content not yet retrieved"
    if file_path and not raw_file_exists and status in {"downloaded", "skipped_existing"}:
        return "manifest points to a missing raw file"
    return None


def _path_exists(file_path: str | None, output_root: Path) -> bool:
    """Return whether a stored file path exists, accepting relative paths."""

    if not file_path:
        return False
    path = Path(file_path)
    if path.is_absolute():
        return path.exists()
    return (output_root / path).exists()


def _parse_datetime(value: object) -> datetime | None:
    """Parse an ISO timestamp from persisted JSON data."""

    text = _first_string(value)
    if text is None:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _first_string(*values: object) -> str | None:
    """Return the first non-empty string-like value."""

    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_space(value: object) -> str | None:
    """Collapse internal whitespace and return null for empty values."""

    text = _first_string(value)
    if text is None:
        return None
    return re.sub(r"\s+", " ", text).strip() or None


def _int_or_none(value: object) -> int | None:
    """Return an integer value when JSON data contains a valid integer."""

    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_summary(
    paths: _DatasetPaths,
    records: list[CCRDatasetRecord],
    queue_state: _QueueState,
    manifest_state: _ManifestState,
    normalization_summary: CCRNormalizationSummary,
) -> CCRDatasetSummary:
    """Build the normalized dataset summary."""

    status_counts = _status_counts(record.download_status for record in records)
    raw_file_missing = sum(
        1
        for record in records
        if record.file_path
        and not record.raw_file_exists
        and record.download_status in {"downloaded", "skipped_existing"}
    )
    return CCRDatasetSummary(
        generated_at=datetime.now(timezone.utc),
        output_root=paths.output_root.as_posix(),
        dataset_dir=paths.dataset_dir.as_posix(),
        metadata_jsonl_path=paths.jsonl_path.as_posix(),
        metadata_csv_path=paths.csv_path.as_posix(),
        summary_path=paths.summary_path.as_posix(),
        normalized_records_dir=normalization_summary.records_dir,
        normalized_records_jsonl_path=normalization_summary.records_jsonl_path,
        normalized_meta_path=normalization_summary.meta_path,
        normalized_index_path=normalization_summary.index_path,
        normalized_summary_path=normalization_summary.summary_path,
        normalized_records_total=normalization_summary.records_total,
        raw_archive_dir=paths.archive_dir.as_posix(),
        queue_path=paths.queue_path.as_posix(),
        manifest_path=paths.manifest_path.as_posix(),
        records_total=len(records),
        discovered=status_counts.get("discovered", 0),
        resolved=status_counts.get("resolved", 0),
        downloaded=status_counts.get("downloaded", 0),
        skipped_existing=status_counts.get("skipped_existing", 0),
        pending=sum(status_counts.get(status, 0) for status in PENDING_DOWNLOAD_STATUSES),
        failed=status_counts.get("failed", 0) + status_counts.get("failed_permanent", 0),
        failed_permanent=status_counts.get("failed_permanent", 0),
        blocked=status_counts.get("blocked", 0),
        pending_retry=status_counts.get("pending_retry", 0),
        raw_file_missing=raw_file_missing,
        queue_events_total=queue_state.row_count,
        manifest_rows_total=manifest_state.row_count,
        duplicate_queue_events_collapsed=max(
            0,
            queue_state.row_count - len(queue_state.latest_by_id),
        ),
        duplicate_manifest_rows_collapsed=max(
            0,
            manifest_state.row_count - len(manifest_state.latest_by_id),
        ),
    )


def _normalized_output_record(
    record: CCRDatasetRecord,
    paths: _DatasetPaths,
    normalized_at: datetime,
) -> CCRNormalizedOutputRecord:
    """Return one final normalized CCR acquisition record."""

    normalized_path = _record_output_path(paths, record.record_id)
    meta_path = paths.normalized_meta_path.resolve().relative_to(paths.output_root).as_posix()
    return CCRNormalizedOutputRecord(
        id=record.record_id,
        canonical_item_id=record.record_id,
        title=record.title,
        rule_name=record.rule_name,
        department=record.department,
        department_normalized=record.department_normalized,
        agency=record.agency,
        agency_normalized=record.agency_normalized,
        division_board_program=record.division_board_program,
        ccr_citation=record.ccr_citation,
        department_number=record.department_number,
        chapter=record.chapter,
        rule_number=record.rule_number,
        source_page_url=record.source_page_url,
        document_url=record.document_url,
        archive_raw_file_path=record.file_path,
        normalized_output_path=normalized_path,
        metadata_output_path=meta_path,
        content_type=record.content_type,
        source_format=record.source_format,
        discovery_timestamp=record.discovery_timestamp,
        retrieval_timestamp=record.retrieval_timestamp,
        normalization_timestamp=normalized_at,
        status=record.download_status,
        checksum_sha256=record.checksum_sha256,
        size_bytes=record.size_bytes,
        raw_file_exists=record.raw_file_exists,
        text_extraction_status=record.text_extraction_status,
        notes=record.notes,
        error=record.error,
    )


def _record_output_path(paths: _DatasetPaths, record_id: str) -> str:
    """Return the root-relative normalized record JSON path."""

    record_path = paths.normalized_records_dir / f"{_safe_record_stem(record_id)}.json"
    return record_path.resolve().relative_to(paths.output_root).as_posix()


def _layer_index_record(
    record: CCRNormalizedOutputRecord,
    output_root: Path,
) -> LayerIndexRecord:
    """Return a layer index row for a normalized CCR acquisition record."""

    source_url = record.source_page_url or record.document_url or CCR_WELCOME_URL
    source_path = record.archive_raw_file_path or record.source_page_url or source_url
    text_for_hash = json.dumps(record.model_dump(mode="json"), sort_keys=True)
    return LayerIndexRecord(
        id=record.id,
        layer=REGULATIONS_LAYER,
        entity_type=record.entity_type,
        title=record.title or record.ccr_citation or record.id,
        citation=record.ccr_citation,
        path=record.normalized_output_path,
        meta_path=record.metadata_output_path,
        source_url=source_url,
        source_path=source_path,
        publication_year=None,
        last_updated=record.normalization_timestamp,
        sha256=sha256_text(text_for_hash),
        tags=_index_tags(record),
        confidence=_index_confidence(record),
    )


def _index_tags(record: CCRNormalizedOutputRecord) -> list[str]:
    """Return compact tags for the layer index."""

    tags = ["ccr", "regulation_rule_acquisition", record.status, record.normalization_status]
    if record.department_normalized:
        tags.append(_tag_slug(record.department_normalized))
    if record.agency_normalized:
        tags.append(_tag_slug(record.agency_normalized))
    return sorted(dict.fromkeys(tag for tag in tags if tag))


def _index_confidence(record: CCRNormalizedOutputRecord) -> float:
    """Return an acquisition-metadata confidence score for the layer index."""

    if record.status in {"downloaded", "skipped_existing"} and record.raw_file_exists:
        return 0.9
    if record.status in {"resolved", "indexed"}:
        return 0.65
    return 0.4


def _build_normalization_summary(
    paths: _DatasetPaths,
    records: list[CCRNormalizedOutputRecord],
    generated_at: datetime,
    stale_removed: int,
) -> CCRNormalizationSummary:
    """Build a summary for final normalized CCR outputs."""

    status_counts = _status_counts(record.status for record in records)
    return CCRNormalizationSummary(
        generated_at=generated_at,
        output_root=paths.output_root.as_posix(),
        records_dir=paths.normalized_records_dir.as_posix(),
        records_jsonl_path=paths.normalized_jsonl_path.as_posix(),
        meta_path=paths.normalized_meta_path.as_posix(),
        index_path=paths.normalized_index_path.as_posix(),
        summary_path=paths.normalized_summary_path.as_posix(),
        records_total=len(records),
        discovered=status_counts.get("discovered", 0),
        resolved=status_counts.get("resolved", 0),
        downloaded=status_counts.get("downloaded", 0)
        + status_counts.get("skipped_existing", 0),
        pending=sum(status_counts.get(status, 0) for status in PENDING_DOWNLOAD_STATUSES),
        failed=status_counts.get("failed", 0) + status_counts.get("failed_permanent", 0),
        failed_permanent=status_counts.get("failed_permanent", 0),
        blocked=status_counts.get("blocked", 0),
        pending_retry=status_counts.get("pending_retry", 0),
        raw_file_missing=sum(
            1
            for record in records
            if record.archive_raw_file_path
            and not record.raw_file_exists
            and record.status in {"downloaded", "skipped_existing"}
        ),
        stale_record_files_removed=stale_removed,
    )


def _prune_stale_record_files(
    records_dir: Path,
    records: list[CCRNormalizedOutputRecord],
) -> int:
    """Remove generated per-record JSON files no longer present in the current run."""

    expected = {
        Path(record.normalized_output_path).name
        for record in records
    }
    removed = 0
    if not records_dir.exists():
        return removed
    for path in records_dir.glob("*.json"):
        if path.name in expected:
            continue
        path.unlink()
        removed += 1
    return removed


def _safe_record_stem(value: str) -> str:
    """Return a filesystem-safe normalized record stem."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "record"


def _tag_slug(value: str) -> str:
    """Return a compact lower-case tag slug for index rows."""

    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _status_counts(statuses: Iterable[str]) -> dict[str, int]:
    """Return counts by normalized download status."""

    counts: dict[str, int] = {}
    for status in statuses:
        counts[status] = counts.get(status, 0) + 1
    return counts


def _write_csv(path: Path, records: list[CCRDatasetRecord], output_root: Path) -> None:
    """Write normalized CCR metadata as CSV with stable columns."""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(CCR_DATASET_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(record.model_dump(mode="json", exclude_none=False))
    atomic_write_text(path, buffer.getvalue(), output_root)


def _print_summary(summary: CCRDatasetSummary) -> None:
    """Print a concise human-readable dataset summary."""

    print("CCR normalized dataset summary")
    print(f"Records: {summary.records_total}")
    print(f"JSONL: {summary.metadata_jsonl_path}")
    print(f"CSV: {summary.metadata_csv_path}")
    print(
        "Downloaded: {downloaded}  Skipped: {skipped_existing}  Pending: {pending}  "
        "Failed: {failed}  Blocked: {blocked}".format(**summary.model_dump(mode="json"))
    )


if __name__ == "__main__":
    raise SystemExit(main())
