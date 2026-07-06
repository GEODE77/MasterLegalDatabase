"""Bulk CCR raw-document text normalization into regulation records."""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections.abc import Callable, Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.ccr_dataset import CCRDatasetRecord, build_ccr_dataset_records, write_ccr_dataset
from geode.connectors.ccr_identity import canonical_ccr_id, canonical_ccr_number
from geode.connectors.ccr_industry_filter import tag_ccr_record
from geode.constants import CONTROL_PLANE_DIR
from geode.extractors.converter import ConversionResult, convert_to_markdown
from geode.pipeline.pilot import load_pilot_test_set
from geode.pipeline.writer import ensure_project_structure, write_record, write_to_quarantine
from geode.schemas import RegulationRule
from geode.schemas.ontology import COMPLIANCE_KEYWORDS
from geode.utils.file_io import atomic_write_json, atomic_write_text, iter_jsonl, relative_path
from geode.utils.hashing import sha256_text
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)

REGULATIONS_LAYER = "02_Regulations_CCR"
RULES_DIR_NAME = "_rules"
RULE_META_NAME = "ccr_rules_meta.jsonl"
NORMALIZATION_SUMMARY_NAME = "ccr_text_normalization_summary.json"
DEFAULT_SOURCE_URL = "https://www.sos.state.co.us/CCR/Welcome.do"
CCR_ID_RE = re.compile(r"^\d{1,2}_CCR_\d+-\d+(?:-\d+)?$")
CRS_CITATION_RE = re.compile(
    r"(?:CRS-|(?:section|§)?\s*)?"
    r"(?P<title>\d{1,2}(?:\.\d+)?)-"
    r"(?P<article>\d{1,3}(?:\.\d+)?)"
    r"-(?P<section>\d{1,4}(?:\.\d+)?)"
    r"(?:\s*\([^)]+\))*"
    r"(?:\s*,?\s*(?:C\.?\s*R\.?\s*S\.?|Colorado\s+Revised\s+Statutes))?",
    re.IGNORECASE,
)
EFFECTIVE_DATE_RE = re.compile(
    r"\b(?:effective(?:\s+date)?|eff\.)[:\s]+"
    r"(?P<date>"
    r"\d{4}-\d{2}-\d{2}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept\.?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2},\s+\d{4}"
    r")",
    re.IGNORECASE,
)
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
COMPLIANCE_PATTERNS = {
    "permit_required": re.compile(r"\bpermit(?:ted|s|ting)?\b", re.IGNORECASE),
    "license_required": re.compile(r"\blicen[cs](?:e|ed|es|ing)?\b", re.IGNORECASE),
    "registration_required": re.compile(r"\bregistration|register(?:ed|s)?\b", re.IGNORECASE),
    "reporting": re.compile(r"\breport(?:ing|s|ed)?\b", re.IGNORECASE),
    "disclosure": re.compile(r"\bdisclos(?:e|ure|ed|ing)\b", re.IGNORECASE),
    "recordkeeping": re.compile(r"\brecord(?:keeping|s)?\b", re.IGNORECASE),
    "inspection": re.compile(r"\binspect(?:ion|ions|or|ed|s)?\b", re.IGNORECASE),
    "monitoring": re.compile(r"\bmonitor(?:ing|s|ed)?\b", re.IGNORECASE),
    "fees": re.compile(r"\bfee(?:s)?\b", re.IGNORECASE),
    "penalty": re.compile(r"\bpenalt(?:y|ies)\b", re.IGNORECASE),
    "fine": re.compile(r"\bfine(?:s|d)?\b", re.IGNORECASE),
    "training_required": re.compile(r"\btraining\b", re.IGNORECASE),
    "certification_required": re.compile(r"\bcertif(?:y|ied|ication)\b", re.IGNORECASE),
}


class CCRTextNormalizationSummary(BaseModel):
    """Summary for CCR full-text normalization into regulation records."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    records_considered: int = Field(ge=0)
    converted: int = Field(ge=0)
    written: int = Field(ge=0)
    skipped: int = Field(ge=0)
    quarantined: int = Field(ge=0)
    failed: int = Field(ge=0)
    pilot_only: bool = False
    dry_run: bool = False
    rules_dir: str
    meta_path: str
    index_path: str
    summary_path: str
    department_files: list[str] = Field(default_factory=list)
    written_ids: list[str] = Field(default_factory=list)
    skipped_ids: list[str] = Field(default_factory=list)
    quarantined_ids: list[str] = Field(default_factory=list)
    failed_ids: list[str] = Field(default_factory=list)


def normalize_ccr_text_records(
    output_root: Path,
    *,
    max_items: int | None = None,
    record_ids: Iterable[str] | None = None,
    pilot_only: bool = False,
    dry_run: bool = False,
    converter: Callable[[Path], ConversionResult] | None = None,
) -> CCRTextNormalizationSummary:
    """Convert downloaded CCR archive files into validated regulation records.

    Args:
        output_root: Geode output root containing `_RAW_ARCHIVE/ccr` and
            `02_Regulations_CCR/_dataset/ccr_items.jsonl`.
        max_items: Optional cap on downloaded records considered.
        record_ids: Optional explicit canonical record IDs to process.
        pilot_only: When true, process IDs from `_CONTROL_PLANE/PILOT_TEST_SET.json`.
        dry_run: Build records but do not write outputs.
        converter: Optional conversion function for tests.

    Returns:
        Deterministic summary of conversion, writes, skips, and quarantine outcomes.
    """

    if max_items is not None and max_items < 0:
        raise ValueError("max_items cannot be negative")
    root = output_root.resolve()
    ensure_project_structure(root)
    dataset_path = root / REGULATIONS_LAYER / "_dataset" / "ccr_items.jsonl"
    if dry_run and not dataset_path.exists():
        raise ValueError("dry-run requires an existing CCR dataset; rerun without --dry-run first")
    if not dry_run:
        write_ccr_dataset(root)
    records, _, _ = build_ccr_dataset_records(root)
    wanted_ids = _wanted_record_ids(root, record_ids, pilot_only)
    converter = converter or _default_converter
    rules_dir = root / REGULATIONS_LAYER / RULES_DIR_NAME
    meta_path = root / REGULATIONS_LAYER / "_meta" / RULE_META_NAME
    index_path = root / REGULATIONS_LAYER / "_index.jsonl"
    summary_path = root / REGULATIONS_LAYER / "_normalized" / NORMALIZATION_SUMMARY_NAME

    written_records: list[dict[str, Any]] = []
    written_ids: list[str] = []
    skipped_ids: list[str] = []
    quarantined_ids: list[str] = []
    failed_ids: list[str] = []
    converted = 0
    written = 0
    quarantined = 0
    failed = 0
    considered = 0

    for record in records:
        if wanted_ids is not None and record.record_id not in wanted_ids:
            continue
        if max_items is not None and considered >= max_items:
            break
        considered += 1
        raw_path = _raw_path(record, root)
        if raw_path is None:
            skipped_ids.append(record.record_id)
            continue
        if not CCR_ID_RE.match(record.record_id):
            quarantined += 1
            quarantined_ids.append(record.record_id)
            if not dry_run:
                write_to_quarantine(
                    _quarantine_payload(record, raw_path),
                    "cannot build RegulationRule from non-citation CCR ID",
                    root,
                )
            continue
        try:
            conversion = converter(raw_path)
            converted += 1
            regulation = build_regulation_rule_record(record, conversion, root)
            RegulationRule.model_validate(_corpus_record(regulation))
        except Exception as exc:
            failed += 1
            failed_ids.append(record.record_id)
            if not dry_run:
                write_to_quarantine(
                    _quarantine_payload(record, raw_path, error=str(exc)),
                    f"CCR text normalization failed: {exc}",
                    root,
                )
            LOGGER.warning("CCR text normalization failed id=%s error=%s", record.record_id, exc)
            continue
        written_records.append(regulation)
        written_ids.append(record.record_id)
        if dry_run:
            continue
        result = write_record(
            regulation,
            {
                "root": root,
                "layer": REGULATIONS_LAYER,
                "content_path": _rule_markdown_path(record.record_id),
                "meta_path": f"{REGULATIONS_LAYER}/_meta/{RULE_META_NAME}",
            },
        )
        if result.success:
            written += 1

    department_files = []
    if written_records and not dry_run:
        department_files = _write_department_markdown(root, written_records)
    summary = CCRTextNormalizationSummary(
        generated_at=datetime.now(timezone.utc),
        output_root=root.as_posix(),
        records_considered=considered,
        converted=converted,
        written=written if not dry_run else 0,
        skipped=len(skipped_ids),
        quarantined=quarantined,
        failed=failed,
        pilot_only=pilot_only,
        dry_run=dry_run,
        rules_dir=rules_dir.as_posix(),
        meta_path=meta_path.as_posix(),
        index_path=index_path.as_posix(),
        summary_path=summary_path.as_posix(),
        department_files=department_files,
        written_ids=written_ids,
        skipped_ids=skipped_ids,
        quarantined_ids=quarantined_ids,
        failed_ids=failed_ids,
    )
    if not dry_run:
        atomic_write_json(summary_path, summary, root)
    return summary


def build_regulation_rule_record(
    record: CCRDatasetRecord,
    conversion: ConversionResult,
    output_root: Path,
) -> dict[str, Any]:
    """Build a schema-valid CCR `RegulationRule` payload from one dataset row."""

    full_text = conversion.markdown_text.strip()
    if not full_text:
        raise ValueError("converted CCR text is empty")
    ccr_number = record.ccr_citation or canonical_ccr_number(record.record_id)
    if ccr_number is None:
        raise ValueError(f"missing CCR citation for {record.record_id}")
    canonical_id = canonical_ccr_id(ccr_number)
    if canonical_id != record.record_id:
        raise ValueError(f"record ID {record.record_id} does not match {canonical_id}")
    tagged = tag_ccr_record(record)
    effective_date = _extract_effective_date(full_text)
    enabling_statutes = _extract_crs_ids(full_text)
    source_format = _source_format(record)
    source_url = record.document_url or record.source_page_url or DEFAULT_SOURCE_URL
    source_path = _source_path(record, output_root)
    content_path = _rule_markdown_path(record.record_id)
    regulation = {
        "entity_type": "regulation_rule",
        "id": record.record_id,
        "ccr_number": ccr_number,
        "title": _title(record, full_text),
        "department": record.department_normalized or record.department or "Unknown Department",
        "department_code": record.department_number or _leading_number(record.department) or "unknown",
        "agency": record.agency_normalized or record.agency or "Unknown Agency",
        "agency_code": _agency_registry_code(record, output_root),
        "enabling_statutes": enabling_statutes,
        "effective_date": effective_date.isoformat() if effective_date else None,
        "status": "active",
        "full_text": full_text,
        "chunk_level_3_summary": _summary(record, full_text),
        "subject_tags": tagged.topic_tags,
        "industry_tags": tagged.industry_tags,
        "compliance_keywords": _compliance_keywords(full_text),
        "source_url": source_url,
        "source_format": source_format,
        "extraction_method": f"bulk_ccr_text:{conversion.tool_used}",
        "confidence": {
            "overall": _confidence(conversion, effective_date, enabling_statutes),
            "fields": {
                "full_text": 0.8 if full_text else 0.0,
                "effective_date": 0.8 if effective_date else 0.0,
                "enabling_statutes": 0.8 if enabling_statutes else 0.0,
            },
            "route": conversion.conversion_path,
        },
        "source_path": source_path,
        "crosswalks": _crosswalks(record.record_id, enabling_statutes, full_text),
        "timeline_events": _timeline_events(
            record.record_id,
            effective_date,
            enabling_statutes,
            content_path,
        ),
    }
    return regulation


def build_parser() -> argparse.ArgumentParser:
    """Build the CCR text-normalization CLI parser."""

    parser = argparse.ArgumentParser(
        description="Normalize downloaded CCR raw files into regulation records."
    )
    parser.add_argument("--output-root", "--root", dest="output_root", type=Path, default=Path.cwd())
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--record-id", action="append", default=[])
    parser.add_argument("--pilot", action="store_true", help="Process the CCR pilot set IDs only.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CCR text-normalization CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(logging, args.log_level))
    try:
        summary = normalize_ccr_text_records(
            args.output_root,
            max_items=args.max_items,
            record_ids=args.record_id,
            pilot_only=args.pilot,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        _print_summary(summary)
    return 0 if summary.failed == 0 else 2


def _wanted_record_ids(
    root: Path,
    record_ids: Iterable[str] | None,
    pilot_only: bool,
) -> set[str] | None:
    """Return an optional set of IDs to process."""

    selected = {item for item in (record_ids or []) if item}
    if pilot_only:
        selected.update(rule.canonical_id for rule in load_pilot_test_set(root))
    return selected or None


def _default_converter(path: Path) -> ConversionResult:
    """Default conversion adapter for dependency injection in tests."""

    return convert_to_markdown(path, source_url=DEFAULT_SOURCE_URL)


def _raw_path(record: CCRDatasetRecord, root: Path) -> Path | None:
    """Return the resolved raw archive file path for a downloaded CCR row."""

    if record.download_status not in {"downloaded", "skipped_existing"}:
        return None
    if not record.file_path:
        return None
    path = Path(record.file_path)
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        return None
    return path


def _source_path(record: CCRDatasetRecord, root: Path) -> str:
    """Return a root-relative source path when possible."""

    if not record.file_path:
        return ""
    path = Path(record.file_path)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return relative_path(path, root)
    except ValueError:
        return path.as_posix()


def _source_format(record: CCRDatasetRecord) -> str:
    """Return a `RegulationRule` source format from dataset metadata."""

    fmt = (record.source_format or "").lower()
    if fmt in {"pdf", "docx", "doc"}:
        return fmt
    if record.file_path:
        suffix = Path(record.file_path).suffix.lower().lstrip(".")
        if suffix in {"pdf", "docx", "doc"}:
            return suffix
    raise ValueError(f"unsupported CCR source format for {record.record_id}: {fmt or 'unknown'}")


def _title(record: CCRDatasetRecord, full_text: str) -> str:
    """Return the best available title for a regulation record."""

    for value in (record.rule_name, record.title):
        if value and value != record.ccr_citation:
            return value
    heading = _first_heading(full_text)
    if heading:
        return heading[:240]
    return record.ccr_citation or record.record_id


def _first_heading(markdown: str) -> str | None:
    """Return the first Markdown heading text."""

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None


def _summary(record: CCRDatasetRecord, full_text: str) -> str:
    """Return a short non-interpretive summary for the full-text record."""

    title = record.title or record.ccr_citation or record.record_id
    words = " ".join(full_text.split())[:360]
    return f"Converted CCR source text for {title}. Opening text: {words}"


def _extract_crs_ids(text: str) -> list[str]:
    """Extract canonical CRS IDs from converted CCR text."""

    ids: list[str] = []
    for match in CRS_CITATION_RE.finditer(text):
        candidate = (
            f"CRS-{match.group('title')}-{match.group('article')}-{match.group('section')}"
        )
        if candidate not in ids:
            ids.append(candidate)
    return ids


def _extract_effective_date(text: str) -> date | None:
    """Extract an explicit effective date from converted CCR text when present."""

    match = EFFECTIVE_DATE_RE.search(text)
    if match is None:
        return None
    raw = match.group("date").strip().rstrip(".")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    parts = raw.replace(",", "").replace(".", "").split()
    if len(parts) != 3:
        return None
    month = MONTHS.get(parts[0].casefold())
    if month is None:
        return None
    try:
        return date(int(parts[2]), month, int(parts[1]))
    except ValueError:
        return None


def _compliance_keywords(text: str) -> list[str]:
    """Return controlled compliance keywords found in source text."""

    found = [
        keyword
        for keyword, pattern in COMPLIANCE_PATTERNS.items()
        if keyword in COMPLIANCE_KEYWORDS and pattern.search(text)
    ]
    return sorted(dict.fromkeys(found))


def _confidence(
    conversion: ConversionResult,
    effective_date: date | None,
    enabling_statutes: list[str],
) -> float:
    """Return a conservative confidence score for deterministic CCR conversion."""

    score = 0.65
    if conversion.tool_used not in {"unavailable", ""}:
        score += 0.1
    if conversion.warnings:
        score -= 0.1
    if effective_date:
        score += 0.05
    if enabling_statutes:
        score += 0.05
    return max(0.1, min(0.9, round(score, 2)))


def _crosswalks(record_id: str, statutes: list[str], full_text: str) -> list[dict[str, Any]]:
    """Return regulation-to-statute crosswalk specs for extracted CRS references."""

    today = date.today().isoformat()
    return [
        {
            "file": "regulation_to_statute.jsonl",
            "record": {
                "entity_type": "crosswalk_entry",
                "source_id": record_id,
                "source_type": "regulation_rule",
                "target_id": statute_id,
                "target_type": "statute_section",
                "relationship": "cites",
                "confidence": 0.75,
                "source_evidence": _evidence_for_statute(full_text, statute_id),
                "data_retrieved": today,
            },
        }
        for statute_id in statutes
    ]


def _timeline_events(
    record_id: str,
    effective_date: date | None,
    statutes: list[str],
    file_path: str,
) -> list[dict[str, Any]]:
    """Return timeline event specs when the source explicitly provides a date."""

    if effective_date is None or effective_date > date.today():
        return []
    return [
        {
            "id": f"TE-{effective_date.isoformat()}-{_sequence_for(record_id)}",
            "date": effective_date.isoformat(),
            "event_type": "rule_effective",
            "entity_id": record_id,
            "entity_type": "regulation_rule",
            "description": f"{record_id} effective date extracted from CCR source text.",
            "affects": statutes,
            "layer": REGULATIONS_LAYER,
            "file_path": file_path,
        }
    ]


def _evidence_for_statute(full_text: str, statute_id: str) -> str:
    """Return a short source-text evidence snippet for a CRS reference."""

    citation = statute_id.replace("CRS-", "")
    index = full_text.casefold().find(citation.casefold())
    if index < 0:
        return citation
    start = max(0, index - 80)
    end = min(len(full_text), index + len(citation) + 80)
    return " ".join(full_text[start:end].split())


def _sequence_for(value: str) -> str:
    """Return a deterministic three-digit timeline sequence."""

    return f"{(int(sha256_text(value)[:6], 16) % 999) + 1:03d}"


def _leading_number(value: str | None) -> str | None:
    """Return a leading numeric code from agency/department text."""

    if not value:
        return None
    match = re.match(r"\s*(\d[\d,]*)", value)
    return match.group(1).replace(",", "") if match else None


def _agency_registry_code(record: CCRDatasetRecord, root: Path) -> str:
    """Return a Geode agency registry ID for a CCR record when available."""

    department_code = record.department_number or _leading_number(record.department)
    registry_path = root / CONTROL_PLANE_DIR / "AGENCY_REGISTRY.json"
    if registry_path.exists():
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = []
        agencies = payload.get("agencies", []) if isinstance(payload, dict) else payload
        if isinstance(agencies, list):
            by_department = [
                item
                for item in agencies
                if isinstance(item, dict)
                and department_code is not None
                and str(item.get("department_code")) == str(department_code)
            ]
            if by_department:
                return str(by_department[0]["id"])
            normalized_agency = (record.agency_normalized or record.agency or "").casefold()
            for item in agencies:
                if not isinstance(item, dict):
                    continue
                agency_name = str(item.get("agency_name", "")).casefold()
                department = str(item.get("department", "")).casefold()
                if agency_name and agency_name in normalized_agency:
                    return str(item["id"])
                if department and department in normalized_agency:
                    return str(item["id"])
    return _agency_slug(record.agency)


def _agency_slug(value: str | None) -> str:
    """Return a deterministic agency-code fallback from agency text."""

    if not value:
        return "unknown"
    words = re.findall(r"[A-Za-z0-9]+", value)
    initials = "".join(word[0].upper() for word in words[:6])
    return initials or "unknown"


def _rule_markdown_path(record_id: str) -> str:
    """Return the root-relative per-rule Markdown path."""

    return f"{REGULATIONS_LAYER}/{RULES_DIR_NAME}/{_safe_stem(record_id)}.md"


def _write_department_markdown(root: Path, records: list[dict[str, Any]]) -> list[str]:
    """Rebuild department-level CCR Markdown aggregate files for written records."""

    meta_path = root / REGULATIONS_LAYER / "_meta" / RULE_META_NAME
    if meta_path.exists():
        records = [
            row
            for row in iter_jsonl(meta_path)
            if row.get("entity_type") == "regulation_rule" and row.get("full_text")
        ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        department = str(record.get("department") or "unknown")
        grouped.setdefault(department, []).append(record)
    paths: list[str] = []
    for department, department_records in sorted(grouped.items()):
        slug = _safe_stem(department).lower()
        path = root / REGULATIONS_LAYER / f"ccr_dept_{slug}.md"
        lines = [
            "---",
            f'department: "{department}"',
            f"record_count: {len(department_records)}",
            f'generated_at: "{datetime.now(timezone.utc).isoformat()}"',
            "---",
            "",
            f"# CCR Department - {department}",
            "",
        ]
        for record in sorted(department_records, key=lambda item: str(item["id"])):
            lines.extend(
                [
                    f"## {record['ccr_number']} - {record['title']}",
                    "",
                    str(record["full_text"]).rstrip(),
                    "",
                ]
            )
        atomic_write_text(path, "\n".join(lines).rstrip() + "\n", root)
        paths.append(relative_path(path, root))
    return paths


def _safe_stem(value: str) -> str:
    """Return a filesystem-safe stem."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "record"


def _quarantine_payload(
    record: CCRDatasetRecord,
    raw_path: Path | None,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Return a compact quarantine payload for failed CCR normalization."""

    return {
        "id": record.record_id,
        "layer": REGULATIONS_LAYER,
        "source_path": raw_path.as_posix() if raw_path else record.file_path or "",
        "download_status": record.download_status,
        "error": error,
    }


def _corpus_record(record: dict[str, Any]) -> dict[str, Any]:
    """Drop writer-only fields before direct schema validation."""

    return {
        key: value
        for key, value in record.items()
        if key not in {"crosswalks", "timeline_events", "layer", "publication_year", "source_path"}
    }


def _print_summary(summary: CCRTextNormalizationSummary) -> None:
    """Print a concise human-readable normalization summary."""

    print("CCR text normalization summary")
    print(f"Considered: {summary.records_considered}")
    print(f"Converted: {summary.converted}")
    print(f"Written: {summary.written}")
    print(f"Skipped: {summary.skipped}")
    print(f"Quarantined: {summary.quarantined}")
    print(f"Failed: {summary.failed}")
    print(f"Summary: {summary.summary_path}")


if __name__ == "__main__":
    raise SystemExit(main())
