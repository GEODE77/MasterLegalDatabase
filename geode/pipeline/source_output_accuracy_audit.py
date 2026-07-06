"""Audit whether structured Geode records match their recorded source files."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR, RAW_ARCHIVE_DIR
from geode.utils.file_io import (
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    iter_jsonl,
    load_json,
)

try:
    import fitz
except ImportError:  # pragma: no cover - optional dependency in unusual environments.
    fitz = None  # type: ignore[assignment]

try:
    from docx import Document
except ImportError:  # pragma: no cover - optional dependency in unusual environments.
    Document = None  # type: ignore[assignment]


AUDIT_REPORT_PATH = Path(CONTROL_PLANE_DIR) / "SOURCE_TO_OUTPUT_ACCURACY_AUDIT.json"
AUDIT_RECORDS_PATH = Path(CONTROL_PLANE_DIR) / "SOURCE_TO_OUTPUT_ACCURACY_RECORDS.jsonl"
AUDIT_QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "SOURCE_TO_OUTPUT_ACCURACY_REPAIR_QUEUE.json"
DOCS_REPORT_PATH = Path("docs") / "audits" / "SOURCE_TO_OUTPUT_ACCURACY_AUDIT_2026-07-01.md"

DEFAULT_PDF_PAGE_LIMIT = 6
LOW_EVIDENCE_SAMPLE_LIMIT = 40


class SourceOutputAccuracyRecord(BaseModel):
    """One source-to-output accuracy result."""

    record_id: str
    layer: str
    citation: str | None = None
    title: str | None = None
    source_path: str | None = None
    output_path: str | None = None
    source_relation: str
    source_exists: bool
    output_exists: bool
    output_record_found: bool
    source_text_checked: bool
    source_extract_kind: str
    evidence_terms_checked: int = Field(ge=0)
    evidence_terms_matched: int = Field(ge=0)
    evidence_ratio: float = Field(ge=0.0, le=1.0)
    matched_terms: list[str]
    missing_terms: list[str]
    output_identity_ok: bool
    raw_hash_matches_output_metadata: bool | None = None
    accuracy_level: str
    issue: str | None = None


class SourceOutputLayerSummary(BaseModel):
    """Source-to-output accuracy summary for one layer."""

    layer: str
    records_checked: int = Field(ge=0)
    independent_source_records: int = Field(ge=0)
    source_text_checked: int = Field(ge=0)
    high_accuracy: int = Field(ge=0)
    medium_accuracy: int = Field(ge=0)
    low_accuracy: int = Field(ge=0)
    metadata_only: int = Field(ge=0)
    not_independent: int = Field(ge=0)
    missing_source: int = Field(ge=0)
    missing_output: int = Field(ge=0)
    output_record_missing: int = Field(ge=0)
    hash_mismatch: int = Field(ge=0)


class SourceOutputAccuracyAudit(BaseModel):
    """Top-level source-to-output accuracy audit."""

    generated_at: datetime
    total_records_checked: int = Field(ge=0)
    independent_source_records: int = Field(ge=0)
    source_text_checked: int = Field(ge=0)
    high_accuracy: int = Field(ge=0)
    medium_accuracy: int = Field(ge=0)
    low_accuracy: int = Field(ge=0)
    metadata_only: int = Field(ge=0)
    not_independent: int = Field(ge=0)
    missing_source: int = Field(ge=0)
    missing_output: int = Field(ge=0)
    output_record_missing: int = Field(ge=0)
    hash_mismatch: int = Field(ge=0)
    layer_summaries: list[SourceOutputLayerSummary]
    records_path: str
    repair_queue_path: str
    boundary: str


@dataclass(frozen=True)
class EvidenceTerm:
    """A label and text value to verify against raw source text."""

    label: str
    value: str


def build_source_output_accuracy_audit(
    root: Path,
    pdf_page_limit: int = DEFAULT_PDF_PAGE_LIMIT,
) -> tuple[SourceOutputAccuracyAudit, list[SourceOutputAccuracyRecord], dict[str, Any]]:
    """Build the source-to-output accuracy audit."""

    resolved_root = root.resolve()
    records: list[SourceOutputAccuracyRecord] = []
    for index_row in _iter_index_rows(resolved_root):
        records.append(_audit_record(resolved_root, index_row, pdf_page_limit))

    layer_summaries = _layer_summaries(records)
    level_counts = Counter(record.accuracy_level for record in records)
    audit = SourceOutputAccuracyAudit(
        generated_at=datetime.now(timezone.utc),
        total_records_checked=len(records),
        independent_source_records=sum(
            1 for record in records if record.source_relation == "raw_archive_source"
        ),
        source_text_checked=sum(1 for record in records if record.source_text_checked),
        high_accuracy=level_counts.get("high", 0),
        medium_accuracy=level_counts.get("medium", 0),
        low_accuracy=level_counts.get("low", 0),
        metadata_only=level_counts.get("metadata_only", 0),
        not_independent=level_counts.get("not_independent", 0),
        missing_source=sum(1 for record in records if not record.source_exists),
        missing_output=sum(1 for record in records if not record.output_exists),
        output_record_missing=sum(1 for record in records if not record.output_record_found),
        hash_mismatch=sum(1 for record in records if record.raw_hash_matches_output_metadata is False),
        layer_summaries=layer_summaries,
        records_path=AUDIT_RECORDS_PATH.as_posix(),
        repair_queue_path=AUDIT_QUEUE_PATH.as_posix(),
        boundary=(
            "This audit compares Geode's local structured output to the local source files "
            "recorded for each item. It does not prove the source file is the newest official "
            "law, and PDF text checks are identity/evidence checks rather than full legal "
            "redlines."
        ),
    )
    queue = _repair_queue(audit, records)
    return audit, records, queue


def write_source_output_accuracy_audit(
    root: Path,
    pdf_page_limit: int = DEFAULT_PDF_PAGE_LIMIT,
) -> SourceOutputAccuracyAudit:
    """Write source-to-output accuracy audit artifacts."""

    resolved_root = root.resolve()
    audit, records, queue = build_source_output_accuracy_audit(resolved_root, pdf_page_limit)
    atomic_write_json(resolved_root / AUDIT_REPORT_PATH, audit, resolved_root)
    atomic_write_jsonl(resolved_root / AUDIT_RECORDS_PATH, records, resolved_root)
    atomic_write_json(resolved_root / AUDIT_QUEUE_PATH, queue, resolved_root)
    _write_docs_report(resolved_root, audit, records)
    return audit


def _audit_record(
    root: Path,
    index_row: dict[str, Any],
    pdf_page_limit: int,
) -> SourceOutputAccuracyRecord:
    record_id = _optional_str(index_row.get("id")) or "UNKNOWN"
    layer = _optional_str(index_row.get("layer")) or "UNKNOWN"
    output_path_text = _optional_str(index_row.get("path"))
    source_path_text = _optional_str(index_row.get("source_path"))
    output_path = _resolve_optional_path(root, output_path_text)
    source_path = _resolve_optional_path(root, source_path_text)
    source_relation = _source_relation(root, source_path, output_path)

    output_payload = _load_output_payload(root, index_row)
    output_exists = bool(output_path and output_path.exists())
    output_record_found = bool(output_payload)
    source_exists = bool(source_path and source_path.exists())
    source_text = ""
    source_extract_kind = "missing_source"
    if source_exists and source_path:
        section_num = _optional_str(output_payload.get("section_num"))
        if layer == "01_Statutes_CRS" and section_num:
            source_text = _crs_section_text(source_path.resolve().as_posix(), section_num)
            source_extract_kind = "crs_section_sgml" if source_text else "crs_section_not_found"
        if not source_text:
            source_text, source_extract_kind = _source_text(source_path, pdf_page_limit)
        if layer == "02_Regulations_CCR":
            support_text = _ccr_inventory_source_text(root, record_id)
            if support_text:
                source_text = " ".join(part for part in [source_text, support_text] if part)
                source_extract_kind = f"{source_extract_kind}+ccr_inventory"
        if layer == "06_Session_Laws":
            support_text = _session_law_listing_source_text(root, record_id)
            if support_text:
                source_text = " ".join(part for part in [source_text, support_text] if part)
                source_extract_kind = f"{source_extract_kind}+session_law_listing"

    terms = _evidence_terms(index_row, output_payload)
    matched_terms, missing_terms = _match_terms(source_text, terms)
    evidence_total = len(terms)
    evidence_matched = len(matched_terms)
    evidence_ratio = round(evidence_matched / evidence_total, 3) if evidence_total else 0.0
    output_identity_ok = _output_identity_ok(index_row, output_payload)
    raw_hash_match = _raw_hash_matches_output_metadata(source_path, output_payload)
    accuracy_level, issue = _accuracy_level(
        source_relation=source_relation,
        source_exists=source_exists,
        output_exists=output_exists,
        output_record_found=output_record_found,
        source_text_checked=bool(source_text),
        evidence_matched=evidence_matched,
        evidence_ratio=evidence_ratio,
        output_identity_ok=output_identity_ok,
        raw_hash_match=raw_hash_match,
    )
    return SourceOutputAccuracyRecord(
        record_id=record_id,
        layer=layer,
        citation=_optional_str(index_row.get("citation")),
        title=_optional_str(index_row.get("title")),
        source_path=source_path_text,
        output_path=output_path_text,
        source_relation=source_relation,
        source_exists=source_exists,
        output_exists=output_exists,
        output_record_found=output_record_found,
        source_text_checked=bool(source_text),
        source_extract_kind=source_extract_kind,
        evidence_terms_checked=evidence_total,
        evidence_terms_matched=evidence_matched,
        evidence_ratio=evidence_ratio,
        matched_terms=matched_terms[:20],
        missing_terms=missing_terms[:20],
        output_identity_ok=output_identity_ok,
        raw_hash_matches_output_metadata=raw_hash_match,
        accuracy_level=accuracy_level,
        issue=issue,
    )


def _iter_index_rows(root: Path) -> list[dict[str, Any]]:
    manifest = _load_dict(root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    rows: list[dict[str, Any]] = []
    for layer in manifest.get("data_layers", []):
        if not isinstance(layer, dict):
            continue
        index_file = _optional_str(layer.get("index_file"))
        if not index_file:
            continue
        path = root / index_file
        if not path.exists():
            continue
        rows.extend(iter_jsonl(path))
    return rows


def _load_output_payload(root: Path, index_row: dict[str, Any]) -> dict[str, Any]:
    record_id = _optional_str(index_row.get("id"))
    output_path_text = _optional_str(index_row.get("path"))
    if not output_path_text:
        return {}
    output_path = root / output_path_text
    if not output_path.exists():
        return {}
    meta_path_text = _optional_str(index_row.get("meta_path"))
    if meta_path_text:
        meta_payload = _jsonl_record(root, meta_path_text, record_id)
        if meta_payload:
            return meta_payload
    suffix = output_path.suffix.lower()
    if suffix == ".json":
        payload = load_json(output_path)
        return payload if isinstance(payload, dict) else {}
    if suffix == ".jsonl":
        return _jsonl_record(root, output_path_text, record_id)
    if suffix in {".md", ".txt"}:
        return {
            "id": record_id,
            "title": index_row.get("title"),
            "citation": index_row.get("citation"),
            "text": _text_file(output_path.as_posix()),
        }
    return {}


@lru_cache(maxsize=4096)
def _jsonl_records_by_id(path_text: str) -> dict[str, dict[str, Any]]:
    path = Path(path_text)
    records: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        for key in ("id", "entity_id", "record_id"):
            value = _optional_str(row.get(key))
            if value:
                records[value] = row
                break
    return records


def _jsonl_record(root: Path, path_text: str, record_id: str | None) -> dict[str, Any]:
    if not record_id:
        return {}
    path = root / path_text
    if not path.exists():
        return {}
    return _jsonl_records_by_id(path.resolve().as_posix()).get(record_id, {})


def _source_text(path: Path, pdf_page_limit: int) -> tuple[str, str]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            return _pdf_text(path.resolve().as_posix(), pdf_page_limit), "pdf_first_pages"
        if suffix == ".docx":
            return _docx_text(path.resolve().as_posix()), "docx_text"
        if suffix == ".json":
            payload = load_json(path)
            return _normalize_source_text(json.dumps(payload, ensure_ascii=False)), "json_text"
        if suffix in {".txt", ".sgml", ".xml", ".html", ".htm", ".md"}:
            return _normalize_source_text(_text_file(path.resolve().as_posix())), "text"
    except (OSError, ValueError, json.JSONDecodeError):
        return "", "extract_failed"
    return "", "unsupported_format"


@lru_cache(maxsize=2048)
def _text_file(path_text: str) -> str:
    return Path(path_text).read_text(encoding="utf-8", errors="ignore")


@lru_cache(maxsize=2048)
def _pdf_text(path_text: str, page_limit: int) -> str:
    if fitz is None:
        return ""
    parts: list[str] = []
    with fitz.open(Path(path_text)) as document:
        for page_index, page in enumerate(document):
            if page_index >= page_limit:
                break
            parts.append(page.get_text("text"))
    return _normalize_source_text("\n".join(parts))


@lru_cache(maxsize=512)
def _docx_text(path_text: str) -> str:
    if Document is None:
        return ""
    document = Document(path_text)
    return _normalize_source_text("\n".join(paragraph.text for paragraph in document.paragraphs))


@lru_cache(maxsize=128)
def _crs_sections_by_number(path_text: str) -> dict[str, str]:
    text = Path(path_text).read_text(encoding="utf-8", errors="ignore")
    sections: dict[str, str] = {}
    pattern = re.compile(r"<SECTION_TEXT\b[^>]*>.*?(?=<SECTION_TEXT\b|<SOURCE_NOTE>|$)", re.S)
    section_number_pattern = re.compile(r"<RHFTO>\s*([^<]+?)\s*</RHFTO>", re.S)
    for match in pattern.finditer(text):
        raw_section = match.group(0)
        number_match = section_number_pattern.search(raw_section)
        if not number_match:
            continue
        section_num = " ".join(number_match.group(1).split())
        sections[section_num] = _normalize_source_text(raw_section)
    return sections


def _crs_section_text(path_text: str, section_num: str) -> str:
    return _crs_sections_by_number(path_text).get(section_num, "")


@lru_cache(maxsize=1)
def _ccr_inventory_by_item(root_text: str) -> dict[str, str]:
    inventory_path = Path(root_text) / "02_Regulations_CCR" / "_inventory" / "ccr_inventory_manifest.jsonl"
    if not inventory_path.exists():
        return {}
    records: dict[str, list[str]] = {}
    for row in iter_jsonl(inventory_path):
        item_id = _optional_str(row.get("item_id"))
        if not item_id:
            continue
        values = [
            row.get("ccr_number"),
            row.get("department_name"),
            row.get("agency_name"),
            row.get("rule_detail_url"),
            row.get("browse_source_url"),
            row.get("source_page_url"),
            row.get("download_url"),
            row.get("rule_id"),
            row.get("inventory_status"),
            row.get("queue_status"),
        ]
        records.setdefault(item_id, []).extend(str(value) for value in values if value)
    return {key: _normalize_source_text(" ".join(values)) for key, values in records.items()}


def _ccr_inventory_source_text(root: Path, record_id: str) -> str:
    return _ccr_inventory_by_item(root.resolve().as_posix()).get(record_id, "")


@lru_cache(maxsize=1)
def _session_law_listing_by_id(root_text: str) -> dict[str, str]:
    pages_dir = Path(root_text) / RAW_ARCHIVE_DIR / "crs" / "session_laws" / "pages"
    if not pages_dir.exists():
        return {}
    try:
        from geode.connectors.session_laws import SESSION_LAWS_URL, parse_session_law_page
    except ImportError:
        return {}
    records: dict[str, str] = {}
    for page_path in sorted(pages_dir.glob("session_laws_page_*.html")):
        page_number = _session_law_page_number(page_path)
        page_url = SESSION_LAWS_URL if page_number == 1 else f"{SESSION_LAWS_URL}?page={page_number}"
        try:
            rows = parse_session_law_page(_text_file(page_path.resolve().as_posix()), page_url)
        except ValueError:
            continue
        for row in rows:
            values = [
                row.entity_id,
                row.bill_id,
                row.chapter,
                row.effective_date.isoformat() if row.effective_date else None,
                row.page_number,
                row.session_year,
                row.source_url,
                row.title,
            ]
            records[row.entity_id] = _normalize_source_text(" ".join(str(value) for value in values if value))
    return records


def _session_law_listing_source_text(root: Path, record_id: str) -> str:
    return _session_law_listing_by_id(root.resolve().as_posix()).get(record_id, "")


def _session_law_page_number(path: Path) -> int:
    match = re.search(r"session_laws_page_(\d+)", path.stem)
    return int(match.group(1)) if match else 1


def _normalize_source_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return _normal(text)


def _evidence_terms(
    index_row: dict[str, Any],
    output_payload: dict[str, Any],
) -> list[EvidenceTerm]:
    terms: list[EvidenceTerm] = []
    for label, value in (
        ("record_id", index_row.get("id")),
        ("citation", index_row.get("citation")),
        ("title", index_row.get("title")),
    ):
        _add_term(terms, label, value)
    for key in (
        "section_num",
        "section_heading",
        "ccr_citation",
        "department_normalized",
        "agency_normalized",
        "bill_number",
        "title",
        "source_evidence",
        "agency",
        "summary",
        "effective_date",
        "publication_date",
        "status_date",
        "introduced_date",
        "citation",
    ):
        _add_term(terms, key, output_payload.get(key))
    full_text = _optional_str(output_payload.get("full_text"))
    if full_text:
        _add_term(terms, "full_text_opening", " ".join(full_text.split()[:16]))
    return _dedupe_terms(terms)


def _add_term(terms: list[EvidenceTerm], label: str, value: object) -> None:
    text = _optional_str(value)
    if not text:
        return
    text = text.strip()
    if len(_normal(text)) < 3:
        return
    terms.append(EvidenceTerm(label=label, value=text[:300]))


def _dedupe_terms(terms: list[EvidenceTerm]) -> list[EvidenceTerm]:
    seen: set[str] = set()
    deduped: list[EvidenceTerm] = []
    for term in terms:
        key = _normal(term.value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(term)
    return deduped


def _match_terms(source_text: str, terms: list[EvidenceTerm]) -> tuple[list[str], list[str]]:
    if not source_text:
        return [], [f"{term.label}: {term.value}" for term in terms]
    matched: list[str] = []
    missing: list[str] = []
    for term in terms:
        needle = _normal(term.value)
        if needle and needle in source_text:
            matched.append(f"{term.label}: {term.value}")
        else:
            missing.append(f"{term.label}: {term.value}")
    return matched, missing


def _output_identity_ok(index_row: dict[str, Any], output_payload: dict[str, Any]) -> bool:
    if not output_payload:
        return False
    record_id = _optional_str(index_row.get("id"))
    if record_id:
        for key in ("id", "entity_id", "record_id", "canonical_item_id"):
            if _optional_str(output_payload.get(key)) == record_id:
                return True
    citation = _optional_str(index_row.get("citation"))
    output_text = _normal(json.dumps(output_payload, ensure_ascii=False))
    return bool(citation and _normal(citation) in output_text)


def _raw_hash_matches_output_metadata(
    source_path: Path | None,
    output_payload: dict[str, Any],
) -> bool | None:
    if not source_path or not source_path.exists():
        return None
    expected = _optional_str(
        output_payload.get("checksum_sha256")
        or output_payload.get("source_sha256")
        or output_payload.get("raw_sha256")
    )
    if not expected:
        return None
    import hashlib

    actual = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return actual.lower() == expected.lower()


def _accuracy_level(
    *,
    source_relation: str,
    source_exists: bool,
    output_exists: bool,
    output_record_found: bool,
    source_text_checked: bool,
    evidence_matched: int,
    evidence_ratio: float,
    output_identity_ok: bool,
    raw_hash_match: bool | None,
) -> tuple[str, str | None]:
    if not source_exists:
        return "missing_source", "Recorded source file is missing locally."
    if not output_exists:
        return "missing_output", "Recorded output file is missing locally."
    if not output_record_found:
        return "missing_output_record", "Output file exists but the record was not found inside it."
    if raw_hash_match is False:
        return "low", "Raw file hash does not match the checksum stored in output metadata."
    if source_relation == "output_self_reference":
        return "not_independent", "Source path points to the structured output, not raw evidence."
    if not source_text_checked:
        return "metadata_only", "Source file exists but text could not be extracted for comparison."
    if evidence_matched >= 2 and evidence_ratio >= 0.5 and output_identity_ok:
        return "high", None
    if evidence_matched >= 1 and output_identity_ok:
        return "medium", "Some source evidence matched, but the match is not strong."
    return "low", "No strong source evidence terms matched the structured output."


def _source_relation(root: Path, source_path: Path | None, output_path: Path | None) -> str:
    if not source_path:
        return "missing_source_path"
    if output_path and source_path.exists() and output_path.exists():
        try:
            if source_path.resolve() == output_path.resolve():
                return "output_self_reference"
        except OSError:
            pass
    try:
        if source_path.resolve().is_relative_to((root / RAW_ARCHIVE_DIR).resolve()):
            return "raw_archive_source"
    except OSError:
        return "unresolved_source"
    return "local_non_raw_source"


def _layer_summaries(records: list[SourceOutputAccuracyRecord]) -> list[SourceOutputLayerSummary]:
    grouped: dict[str, list[SourceOutputAccuracyRecord]] = defaultdict(list)
    for record in records:
        grouped[record.layer].append(record)
    summaries: list[SourceOutputLayerSummary] = []
    for layer, layer_records in sorted(grouped.items()):
        counts = Counter(record.accuracy_level for record in layer_records)
        summaries.append(
            SourceOutputLayerSummary(
                layer=layer,
                records_checked=len(layer_records),
                independent_source_records=sum(
                    1 for record in layer_records if record.source_relation == "raw_archive_source"
                ),
                source_text_checked=sum(1 for record in layer_records if record.source_text_checked),
                high_accuracy=counts.get("high", 0),
                medium_accuracy=counts.get("medium", 0),
                low_accuracy=counts.get("low", 0),
                metadata_only=counts.get("metadata_only", 0),
                not_independent=counts.get("not_independent", 0),
                missing_source=sum(1 for record in layer_records if not record.source_exists),
                missing_output=sum(1 for record in layer_records if not record.output_exists),
                output_record_missing=sum(
                    1 for record in layer_records if not record.output_record_found
                ),
                hash_mismatch=sum(
                    1 for record in layer_records
                    if record.raw_hash_matches_output_metadata is False
                ),
            )
        )
    return summaries


def _repair_queue(
    audit: SourceOutputAccuracyAudit,
    records: list[SourceOutputAccuracyRecord],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.accuracy_level in {
            "high",
            "medium",
            "metadata_only",
        }:
            continue
        key = record.accuracy_level
        if len(grouped[key]) >= LOW_EVIDENCE_SAMPLE_LIMIT:
            continue
        grouped[key].append(record.model_dump(mode="json"))
    return {
        "generated_at": audit.generated_at.isoformat(),
        "open_groups": len(grouped),
        "sample_limit_per_group": LOW_EVIDENCE_SAMPLE_LIMIT,
        "groups": dict(sorted(grouped.items())),
        "boundary": "Repair items are source-to-output accuracy work, not legal conclusions.",
    }


def _write_docs_report(
    root: Path,
    audit: SourceOutputAccuracyAudit,
    records: list[SourceOutputAccuracyRecord],
) -> None:
    lines = [
        "# Source-To-Output Accuracy Audit",
        "",
        f"Generated: {audit.generated_at.isoformat()}",
        "",
        "This audit compares Geode output records to the local source files recorded for them.",
        "",
        f"- Records checked: {audit.total_records_checked:,}",
        f"- Independent raw-archive source records: {audit.independent_source_records:,}",
        f"- Source text checked: {audit.source_text_checked:,}",
        f"- High accuracy: {audit.high_accuracy:,}",
        f"- Medium accuracy: {audit.medium_accuracy:,}",
        f"- Low accuracy: {audit.low_accuracy:,}",
        f"- Metadata only: {audit.metadata_only:,}",
        f"- Not independently source-checkable: {audit.not_independent:,}",
        f"- Missing source files: {audit.missing_source:,}",
        f"- Missing output files: {audit.missing_output:,}",
        f"- Output record missing inside output file: {audit.output_record_missing:,}",
        f"- Raw hash mismatches: {audit.hash_mismatch:,}",
        "",
        "## Layer Summary",
        "",
        "| Layer | Records | Raw Source | Text Checked | High | Medium | Low | Metadata Only | Not Independent | Missing Source | Missing Output | Missing Record | Hash Mismatch |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in audit.layer_summaries:
        lines.append(
            "| "
            f"{summary.layer} | "
            f"{summary.records_checked:,} | "
            f"{summary.independent_source_records:,} | "
            f"{summary.source_text_checked:,} | "
            f"{summary.high_accuracy:,} | "
            f"{summary.medium_accuracy:,} | "
            f"{summary.low_accuracy:,} | "
            f"{summary.metadata_only:,} | "
            f"{summary.not_independent:,} | "
            f"{summary.missing_source:,} | "
            f"{summary.missing_output:,} | "
            f"{summary.output_record_missing:,} | "
            f"{summary.hash_mismatch:,} |"
        )
    lines.extend(
        [
            "",
            "## Lowest-Evidence Samples",
            "",
        ]
    )
    low_records = [record for record in records if record.accuracy_level in {"low", "not_independent"}]
    for record in low_records[:40]:
        lines.append(
            f"- `{record.record_id}` ({record.layer}): {record.accuracy_level}. "
            f"{record.issue or 'Review source evidence.'}"
        )
    if not low_records:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Machine report: `{AUDIT_REPORT_PATH.as_posix()}`",
            f"- Per-record rows: `{AUDIT_RECORDS_PATH.as_posix()}`",
            f"- Repair queue: `{AUDIT_QUEUE_PATH.as_posix()}`",
            "",
            "## Boundary",
            "",
            audit.boundary,
            "",
        ]
    )
    atomic_write_text(root / DOCS_REPORT_PATH, "\n".join(lines), root)


def _resolve_optional_path(root: Path, path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else root / path


def _load_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normal(text: str) -> str:
    text = html.unescape(text).lower()
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    """Run the source-to-output accuracy audit."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Rebuild without writing. By default, status uses the latest written report.",
    )
    parser.add_argument("--pdf-page-limit", type=int, default=DEFAULT_PDF_PAGE_LIMIT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.write:
        audit = write_source_output_accuracy_audit(root, args.pdf_page_limit)
    elif args.refresh:
        audit = build_source_output_accuracy_audit(root, args.pdf_page_limit)[0]
    else:
        audit = _load_existing_audit(root) or build_source_output_accuracy_audit(
            root,
            args.pdf_page_limit,
        )[0]
    if args.json:
        print(audit.model_dump_json(indent=2))
        return
    print(f"Records checked: {audit.total_records_checked}")
    print(f"High accuracy: {audit.high_accuracy}")
    print(f"Medium accuracy: {audit.medium_accuracy}")
    print(f"Low accuracy: {audit.low_accuracy}")


def _load_existing_audit(root: Path) -> SourceOutputAccuracyAudit | None:
    """Load the latest written source-to-output audit when present."""

    path = root / AUDIT_REPORT_PATH
    if not path.exists():
        return None
    try:
        payload = load_json(path)
        return SourceOutputAccuracyAudit.model_validate(payload)
    except (OSError, TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
