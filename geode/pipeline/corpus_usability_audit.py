"""Audit whether Geode corpus records are identifiable and usable."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl, load_json

try:
    import orjson
except ImportError:  # pragma: no cover - exercised only when optional speedup is absent.
    orjson = None  # type: ignore[assignment]

AUDIT_REPORT_PATH = Path(CONTROL_PLANE_DIR) / "CORPUS_USABILITY_AUDIT.json"
AUDIT_ISSUES_PATH = Path(CONTROL_PLANE_DIR) / "CORPUS_USABILITY_ISSUES.jsonl"
AUDIT_QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "CORPUS_USABILITY_REPAIR_QUEUE.json"
DOCS_REPORT_PATH = Path("docs") / "audits" / "CORPUS_USABILITY_AUDIT_2026-07-01.md"

REQUIRED_INDEX_FIELDS = (
    "id",
    "layer",
    "entity_type",
    "title",
    "citation",
    "path",
    "source_url",
    "source_path",
    "last_updated",
    "sha256",
    "confidence",
)

CROSSWALK_FILES = (
    "regulation_to_statute.jsonl",
    "statute_to_regulation.jsonl",
    "bill_to_statute.jsonl",
    "rulemaking_to_regulation.jsonl",
    "agency_to_statute.jsonl",
    "amendment_history.jsonl",
)


class CorpusUsabilityIssue(BaseModel):
    """One usability issue found in the corpus."""

    issue_id: str
    severity: str
    category: str
    layer: str | None = None
    record_id: str | None = None
    path: str | None = None
    field: str | None = None
    detail: str
    next_action: str


class LayerUsabilitySummary(BaseModel):
    """Usability summary for one layer."""

    layer: str
    index_path: str
    manifest_record_count: int = Field(ge=0)
    index_records_checked: int = Field(ge=0)
    retrievable_records: int = Field(ge=0)
    records_with_required_identity: int = Field(ge=0)
    records_with_source_anchor: int = Field(ge=0)
    records_with_content_anchor: int = Field(ge=0)
    errors: int = Field(ge=0)
    warnings: int = Field(ge=0)


class CrosswalkUsabilitySummary(BaseModel):
    """Usability summary for relationship files."""

    crosswalk_file: str
    rows_checked: int = Field(ge=0)
    rows_with_source_and_target: int = Field(ge=0)
    rows_with_relationship_label: int = Field(ge=0)
    rows_with_evidence: int = Field(ge=0)
    errors: int = Field(ge=0)
    warnings: int = Field(ge=0)


class JsonlAddressabilitySummary(BaseModel):
    """Addressability summary for any JSONL database file."""

    path: str
    rows_checked: int = Field(ge=0)
    rows_with_primary_identifier: int = Field(ge=0)
    rows_addressable_by_file_line: int = Field(ge=0)
    invalid_rows: int = Field(ge=0)


class CorpusUsabilityAudit(BaseModel):
    """Top-level corpus usability audit."""

    generated_at: datetime
    total_index_records_checked: int = Field(ge=0)
    total_retrievable_records: int = Field(ge=0)
    total_crosswalk_rows_checked: int = Field(ge=0)
    total_jsonl_files_checked: int = Field(ge=0)
    total_jsonl_rows_checked: int = Field(ge=0)
    total_jsonl_rows_with_primary_identifier: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    ready_for_request_identification: bool
    ready_for_basic_use: bool
    layer_summaries: list[LayerUsabilitySummary]
    crosswalk_summaries: list[CrosswalkUsabilitySummary]
    jsonl_addressability_summaries: list[JsonlAddressabilitySummary]
    issue_path: str
    repair_queue_path: str
    boundary: str


@dataclass(frozen=True)
class LayerDefinition:
    """One layer from the manifest."""

    id: str
    index_file: str
    record_count: int


def build_corpus_usability_audit(
    root: Path,
) -> tuple[CorpusUsabilityAudit, list[CorpusUsabilityIssue], dict[str, Any]]:
    """Build the corpus usability audit without writing artifacts."""

    resolved_root = root.resolve()
    issue_builder = IssueBuilder()
    retrieval_ids = _load_retrieval_ids(resolved_root)
    manifest_layers = _manifest_layers(resolved_root)
    layer_summaries: list[LayerUsabilitySummary] = []

    for layer in manifest_layers:
        layer_summaries.append(
            _audit_layer(resolved_root, layer, retrieval_ids, issue_builder)
        )

    crosswalk_summaries = [
        _audit_crosswalk(resolved_root, file_name, issue_builder)
        for file_name in CROSSWALK_FILES
    ]
    jsonl_summaries = _audit_jsonl_addressability(resolved_root, issue_builder)

    issues = issue_builder.issues
    severity_counts = Counter(issue.severity for issue in issues)
    total_index_records = sum(summary.index_records_checked for summary in layer_summaries)
    total_retrievable = sum(summary.retrievable_records for summary in layer_summaries)
    total_crosswalk_rows = sum(summary.rows_checked for summary in crosswalk_summaries)
    total_jsonl_rows = sum(summary.rows_checked for summary in jsonl_summaries)
    total_jsonl_primary_ids = sum(
        summary.rows_with_primary_identifier for summary in jsonl_summaries
    )
    audit = CorpusUsabilityAudit(
        generated_at=datetime.now(timezone.utc),
        total_index_records_checked=total_index_records,
        total_retrievable_records=total_retrievable,
        total_crosswalk_rows_checked=total_crosswalk_rows,
        total_jsonl_files_checked=len(jsonl_summaries),
        total_jsonl_rows_checked=total_jsonl_rows,
        total_jsonl_rows_with_primary_identifier=total_jsonl_primary_ids,
        issue_count=len(issues),
        error_count=severity_counts.get("error", 0),
        warning_count=severity_counts.get("warning", 0),
        ready_for_request_identification=total_index_records > 0
        and total_index_records == total_retrievable
        and severity_counts.get("error", 0) == 0,
        ready_for_basic_use=total_index_records > 0 and severity_counts.get("error", 0) == 0,
        layer_summaries=layer_summaries,
        crosswalk_summaries=crosswalk_summaries,
        jsonl_addressability_summaries=jsonl_summaries,
        issue_path=AUDIT_ISSUES_PATH.as_posix(),
        repair_queue_path=AUDIT_QUEUE_PATH.as_posix(),
        boundary=(
            "This audit checks local corpus usability: identifiers, source anchors, content "
            "anchors, retrieval visibility, and relationship row basics. It does not certify "
            "legal correctness or official-source freshness."
        ),
    )
    queue = _repair_queue(audit, issues)
    return audit, issues, queue


def write_corpus_usability_audit(root: Path) -> CorpusUsabilityAudit:
    """Write corpus usability audit artifacts."""

    resolved_root = root.resolve()
    audit, issues, queue = build_corpus_usability_audit(resolved_root)
    atomic_write_json(resolved_root / AUDIT_REPORT_PATH, audit, resolved_root)
    atomic_write_jsonl(resolved_root / AUDIT_ISSUES_PATH, issues, resolved_root)
    atomic_write_json(resolved_root / AUDIT_QUEUE_PATH, queue, resolved_root)
    _write_docs_report(resolved_root, audit)
    return audit


def _audit_layer(
    root: Path,
    layer: LayerDefinition,
    retrieval_ids: set[str],
    issue_builder: "IssueBuilder",
) -> LayerUsabilitySummary:
    index_path = root / layer.index_file
    rows = _read_jsonl(index_path, issue_builder, layer.id)
    retrievable = 0
    required_identity = 0
    source_anchor = 0
    content_anchor = 0
    issue_start = len(issue_builder.issues)

    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        record_id = _optional_str(row.get("id"))
        row_path = _optional_str(row.get("path"))
        display_path = layer.index_file

        if record_id and record_id in seen_ids:
            issue_builder.add(
                "error",
                "duplicate_id",
                layer.id,
                record_id,
                display_path,
                "id",
                f"Duplicate record id in layer index: {record_id}.",
                "Keep one canonical row per record id.",
            )
        if record_id:
            seen_ids.add(record_id)

        missing_required = [
            field
            for field in REQUIRED_INDEX_FIELDS
            if _is_missing(row.get(field))
        ]
        if missing_required:
            for field in missing_required:
                issue_builder.add(
                    "error" if field in {"id", "path"} else "warning",
                    "missing_required_field",
                    layer.id,
                    record_id,
                    display_path,
                    field,
                    f"Record is missing required usability field: {field}.",
                    "Backfill the field from source-backed metadata.",
                )
        else:
            required_identity += 1

        if record_id and record_id in retrieval_ids:
            retrievable += 1
        else:
            issue_builder.add(
                "error",
                "missing_retrieval_catalog_entry",
                layer.id,
                record_id,
                display_path,
                "id",
                "Record is not present in the retrieval catalog.",
                "Rebuild the retrieval catalog and investigate records still missing afterward.",
            )

        if _has_source_anchor(row):
            source_anchor += 1
        else:
            issue_builder.add(
                "warning",
                "missing_source_anchor",
                layer.id,
                record_id,
                display_path,
                "source_url",
                "Record does not have both a source URL and source path.",
                "Backfill source URL and source path before relying on this record externally.",
            )

        if row_path and _content_anchor_exists(root, row, record_id):
            content_anchor += 1
        else:
            issue_builder.add(
                "error",
                "missing_content_anchor",
                layer.id,
                record_id,
                row_path or display_path,
                "path",
                "Record path is missing, unreadable, or does not contain the record id.",
                "Repair the path or rebuild the layer index from the canonical content file.",
            )

        _check_confidence(row, layer.id, record_id, display_path, issue_builder)
        _check_hash(row, layer.id, record_id, display_path, issue_builder)
        _check_source_path(root, row, layer.id, record_id, display_path, issue_builder)

    layer_issues = issue_builder.issues[issue_start:]
    counts = Counter(issue.severity for issue in layer_issues)
    if layer.record_count and layer.record_count != len(rows):
        issue_builder.add(
            "warning",
            "manifest_count_mismatch",
            layer.id,
            None,
            layer.index_file,
            "record_count",
            f"Manifest says {layer.record_count} records, but index has {len(rows)}.",
            "Rebuild the manifest after confirming the index is canonical.",
        )
        counts["warning"] += 1
    return LayerUsabilitySummary(
        layer=layer.id,
        index_path=layer.index_file,
        manifest_record_count=layer.record_count,
        index_records_checked=len(rows),
        retrievable_records=retrievable,
        records_with_required_identity=required_identity,
        records_with_source_anchor=source_anchor,
        records_with_content_anchor=content_anchor,
        errors=counts.get("error", 0),
        warnings=counts.get("warning", 0),
    )


def _audit_crosswalk(
    root: Path,
    file_name: str,
    issue_builder: "IssueBuilder",
) -> CrosswalkUsabilitySummary:
    path = root / "_CROSSWALKS" / file_name
    rows = _read_jsonl(path, issue_builder, "_CROSSWALKS")
    source_target = 0
    relationship_label = 0
    evidence = 0
    issue_start = len(issue_builder.issues)

    for row_number, row in enumerate(rows, start=1):
        source_id = _primary_source(row)
        target_id = _primary_target(row)
        relationship = _optional_str(row.get("relationship") or row.get("event_type"))
        record_id = f"{Path(file_name).stem}:{row_number:06d}"
        if source_id and target_id:
            source_target += 1
        else:
            issue_builder.add(
                "error",
                "crosswalk_missing_endpoint",
                "_CROSSWALKS",
                record_id,
                f"_CROSSWALKS/{file_name}",
                "source_id/target_id",
                "Relationship row is missing a source or target identifier.",
                "Backfill the missing endpoint or remove the unusable relationship row.",
            )
        if relationship:
            relationship_label += 1
        else:
            issue_builder.add(
                "warning",
                "crosswalk_missing_relationship",
                "_CROSSWALKS",
                record_id,
                f"_CROSSWALKS/{file_name}",
                "relationship",
                "Relationship row does not have a clear relationship label.",
                "Add a source-backed relationship or event type.",
            )
        if _optional_str(row.get("source_evidence")):
            evidence += 1
        else:
            issue_builder.add(
                "warning",
                "crosswalk_missing_evidence",
                "_CROSSWALKS",
                record_id,
                f"_CROSSWALKS/{file_name}",
                "source_evidence",
                "Relationship row lacks evidence text.",
                "Backfill source evidence before using this relationship externally.",
            )

    crosswalk_issues = issue_builder.issues[issue_start:]
    counts = Counter(issue.severity for issue in crosswalk_issues)
    return CrosswalkUsabilitySummary(
        crosswalk_file=file_name,
        rows_checked=len(rows),
        rows_with_source_and_target=source_target,
        rows_with_relationship_label=relationship_label,
        rows_with_evidence=evidence,
        errors=counts.get("error", 0),
        warnings=counts.get("warning", 0),
    )


def _audit_jsonl_addressability(
    root: Path,
    issue_builder: "IssueBuilder",
) -> list[JsonlAddressabilitySummary]:
    summaries: list[JsonlAddressabilitySummary] = []
    for path in sorted(root.rglob("*.jsonl")):
        if _is_skipped_jsonl_path(root, path):
            continue
        relative = path.relative_to(root).as_posix()
        rows_checked = 0
        primary_ids = 0
        invalid_rows = 0
        if path.stat().st_size == 0:
            summaries.append(
                JsonlAddressabilitySummary(
                    path=relative,
                    rows_checked=0,
                    rows_with_primary_identifier=0,
                    rows_addressable_by_file_line=0,
                    invalid_rows=0,
                )
            )
            continue
        with path.open("rb") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    invalid_rows += 1
                    issue_builder.add(
                        "error",
                        "invalid_jsonl_row",
                        _jsonl_layer(relative),
                        f"{relative}:{line_number}",
                        relative,
                        None,
                        "Blank JSONL row cannot be addressed as a record.",
                        "Remove the blank line or replace it with a valid JSON object.",
                    )
                    continue
                try:
                    payload = _loads_jsonl_row(stripped)
                except (json.JSONDecodeError, ValueError) as exc:
                    invalid_rows += 1
                    issue_builder.add(
                        "error",
                        "invalid_jsonl_row",
                        _jsonl_layer(relative),
                        f"{relative}:{line_number}",
                        relative,
                        None,
                        f"JSONL row could not be parsed: {exc}",
                        "Repair the malformed JSONL row.",
                    )
                    continue
                if not isinstance(payload, dict):
                    invalid_rows += 1
                    issue_builder.add(
                        "error",
                        "invalid_jsonl_row",
                        _jsonl_layer(relative),
                        f"{relative}:{line_number}",
                        relative,
                        None,
                        "JSONL row is not an object.",
                        "Replace the row with a JSON object.",
                    )
                    continue
                rows_checked += 1
                if _row_primary_identifier(payload):
                    primary_ids += 1
        summaries.append(
            JsonlAddressabilitySummary(
                path=relative,
                rows_checked=rows_checked,
                rows_with_primary_identifier=primary_ids,
                rows_addressable_by_file_line=rows_checked,
                invalid_rows=invalid_rows,
            )
        )
    return summaries


def _is_skipped_jsonl_path(root: Path, path: Path) -> bool:
    parts = set(path.relative_to(root).parts)
    return bool(parts & {".git", "node_modules", ".next", "_RAW_ARCHIVE"})


def _row_primary_identifier(row: dict[str, Any]) -> str | None:
    for key in (
        "id",
        "entity_id",
        "rule_unit_id",
        "manifest_row_id",
        "review_id",
        "issue_id",
        "relationship_id",
        "event_id",
        "task_id",
        "record_id",
        "bill_id",
        "statute_id",
        "source_id",
        "tracking_number",
        "document_url",
        "crosswalk_file",
        "archive_path",
        "snapshot_path",
        "path",
        "generated_at",
    ):
        value = _optional_str(row.get(key))
        if value:
            return value
    return None


def _loads_jsonl_row(raw_line: bytes) -> Any:
    if orjson is not None:
        return orjson.loads(raw_line)
    return json.loads(raw_line.decode("utf-8"))


def _jsonl_layer(relative_path: str) -> str | None:
    return relative_path.split("/", 1)[0] if "/" in relative_path else None


def _content_anchor_exists(root: Path, row: dict[str, Any], record_id: str | None) -> bool:
    row_path = _optional_str(row.get("path"))
    if not row_path:
        return False
    path = root / row_path
    if not path.exists() or path.stat().st_size == 0:
        return False
    if not record_id:
        return False
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            return record_id in _json_ids(path.resolve().as_posix())
        if suffix == ".jsonl":
            return record_id in _jsonl_ids(path.resolve().as_posix())
        if suffix == ".md":
            text = _file_text(path.resolve().as_posix())
            return record_id in text or _display_citation(row, record_id) in text
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    return False


@lru_cache(maxsize=2048)
def _file_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


@lru_cache(maxsize=2048)
def _jsonl_ids(path: str) -> frozenset[str]:
    return frozenset(
        str(item.get("id") or item.get("entity_id") or "")
        for item in iter_jsonl(Path(path))
        if item.get("id") or item.get("entity_id")
    )


@lru_cache(maxsize=2048)
def _json_ids(path: str) -> frozenset[str]:
    return frozenset(_record_payload_ids(load_json(Path(path))))


def _record_payload_ids(payload: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(payload, dict):
        entity_id = _optional_str(payload.get("id") or payload.get("entity_id"))
        if entity_id:
            ids.add(entity_id)
        for value in payload.values():
            ids.update(_record_payload_ids(value))
    if isinstance(payload, list):
        for item in payload:
            ids.update(_record_payload_ids(item))
    return ids


def _display_citation(row: dict[str, Any], record_id: str) -> str:
    citation = _optional_str(row.get("citation"))
    if citation:
        return citation.replace("CRS-", "")
    if record_id.startswith("CRS-"):
        return record_id.removeprefix("CRS-")
    return record_id


def _check_confidence(
    row: dict[str, Any],
    layer: str,
    record_id: str | None,
    path: str,
    issue_builder: "IssueBuilder",
) -> None:
    confidence = row.get("confidence")
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        issue_builder.add(
            "warning",
            "invalid_confidence",
            layer,
            record_id,
            path,
            "confidence",
            "Confidence is missing or not numeric.",
            "Set confidence to a number between 0 and 1.",
        )
        return
    if value < 0 or value > 1:
        issue_builder.add(
            "warning",
            "invalid_confidence",
            layer,
            record_id,
            path,
            "confidence",
            "Confidence is outside the expected 0 to 1 range.",
            "Clamp or recompute confidence using the scoring policy.",
        )


def _check_hash(
    row: dict[str, Any],
    layer: str,
    record_id: str | None,
    path: str,
    issue_builder: "IssueBuilder",
) -> None:
    value = _optional_str(row.get("sha256"))
    if value and len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value):
        return
    issue_builder.add(
        "warning",
        "invalid_hash",
        layer,
        record_id,
        path,
        "sha256",
        "Record hash is missing or not a valid SHA-256 value.",
        "Recompute the record hash from the canonical record payload.",
    )


def _check_source_path(
    root: Path,
    row: dict[str, Any],
    layer: str,
    record_id: str | None,
    path: str,
    issue_builder: "IssueBuilder",
) -> None:
    source_path = _optional_str(row.get("source_path"))
    if not source_path:
        return
    candidate = Path(source_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    if candidate.exists():
        return
    issue_builder.add(
        "warning",
        "source_path_missing_locally",
        layer,
        record_id,
        path,
        "source_path",
        "Source path is recorded but does not exist locally.",
        "Confirm whether the source path should be relative to the repo or backfill the raw archive path.",
    )


def _repair_queue(audit: CorpusUsabilityAudit, issues: list[CorpusUsabilityIssue]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        grouped[issue.category].append(issue.model_dump(mode="json"))
    return {
        "generated_at": audit.generated_at.isoformat(),
        "open_items": len(issues),
        "error_items": audit.error_count,
        "warning_items": audit.warning_count,
        "groups": dict(sorted(grouped.items())),
        "boundary": "Repair items are local corpus usability work, not legal conclusions.",
    }


def _write_docs_report(root: Path, audit: CorpusUsabilityAudit) -> None:
    lines = [
        "# Corpus Usability Audit",
        "",
        f"Generated: {audit.generated_at.isoformat()}",
        "",
        "This audit checks whether records can be identified and retrieved when requested.",
        "",
        f"- Index records checked: {audit.total_index_records_checked:,}",
        f"- Records in retrieval catalog: {audit.total_retrievable_records:,}",
        f"- Crosswalk rows checked: {audit.total_crosswalk_rows_checked:,}",
        f"- JSONL files checked: {audit.total_jsonl_files_checked:,}",
        f"- JSONL rows checked: {audit.total_jsonl_rows_checked:,}",
        f"- JSONL rows with primary identifiers: {audit.total_jsonl_rows_with_primary_identifier:,}",
        f"- Errors: {audit.error_count:,}",
        f"- Warnings: {audit.warning_count:,}",
        f"- Ready for request identification: {audit.ready_for_request_identification}",
        f"- Ready for basic use: {audit.ready_for_basic_use}",
        "",
        "## Layer Summary",
        "",
        "| Layer | Records | Retrievable | Identity Complete | Source Anchored | Content Anchored | Errors | Warnings |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in audit.layer_summaries:
        lines.append(
            "| "
            f"{summary.layer} | "
            f"{summary.index_records_checked:,} | "
            f"{summary.retrievable_records:,} | "
            f"{summary.records_with_required_identity:,} | "
            f"{summary.records_with_source_anchor:,} | "
            f"{summary.records_with_content_anchor:,} | "
            f"{summary.errors:,} | "
            f"{summary.warnings:,} |"
        )
    lines.extend(
        [
            "",
            "## Crosswalk Summary",
            "",
            "| File | Rows | Endpoints Present | Labels Present | Evidence Present | Errors | Warnings |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for summary in audit.crosswalk_summaries:
        lines.append(
            "| "
            f"{summary.crosswalk_file} | "
            f"{summary.rows_checked:,} | "
            f"{summary.rows_with_source_and_target:,} | "
            f"{summary.rows_with_relationship_label:,} | "
            f"{summary.rows_with_evidence:,} | "
            f"{summary.errors:,} | "
            f"{summary.warnings:,} |"
        )
    lines.extend(
        [
            "",
            "## JSONL Addressability",
            "",
            "Every valid JSONL row is addressable by file and line number. Rows with a primary ID are also directly addressable by that ID.",
            "",
            "| File | Rows | Primary IDs | File-Line Addressable | Invalid Rows |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for summary in audit.jsonl_addressability_summaries:
        lines.append(
            "| "
            f"{summary.path} | "
            f"{summary.rows_checked:,} | "
            f"{summary.rows_with_primary_identifier:,} | "
            f"{summary.rows_addressable_by_file_line:,} | "
            f"{summary.invalid_rows:,} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Machine report: `{AUDIT_REPORT_PATH.as_posix()}`",
            f"- Issue rows: `{AUDIT_ISSUES_PATH.as_posix()}`",
            f"- Repair queue: `{AUDIT_QUEUE_PATH.as_posix()}`",
            "",
            "## Boundary",
            "",
            audit.boundary,
            "",
        ]
    )
    from geode.utils.file_io import atomic_write_text

    atomic_write_text(root / DOCS_REPORT_PATH, "\n".join(lines), root)


def _manifest_layers(root: Path) -> list[LayerDefinition]:
    manifest = _load_dict(root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    layers = manifest.get("data_layers") if isinstance(manifest.get("data_layers"), list) else []
    definitions: list[LayerDefinition] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        layer_id = _optional_str(layer.get("id"))
        index_file = _optional_str(layer.get("index_file"))
        if not layer_id or not index_file:
            continue
        definitions.append(
            LayerDefinition(
                id=layer_id,
                index_file=index_file,
                record_count=_optional_int(layer.get("record_count")) or 0,
            )
        )
    return definitions


def _load_retrieval_ids(root: Path) -> set[str]:
    path = root / CONTROL_PLANE_DIR / "RETRIEVAL_CATALOG.jsonl"
    if not path.exists():
        return set()
    return {str(row.get("id")) for row in iter_jsonl(path) if row.get("id")}


def _read_jsonl(path: Path, issue_builder: "IssueBuilder", layer: str) -> list[dict[str, Any]]:
    if not path.exists():
        issue_builder.add(
            "error",
            "missing_file",
            layer,
            None,
            _display_path(path),
            None,
            "Expected JSONL file is missing.",
            "Rebuild or restore the missing file.",
        )
        return []
    if path.stat().st_size == 0:
        return []
    try:
        return list(iter_jsonl(path))
    except (json.JSONDecodeError, ValueError) as exc:
        issue_builder.add(
            "error",
            "invalid_jsonl",
            layer,
            None,
            _display_path(path),
            None,
            f"JSONL file could not be read: {exc}",
            "Repair the malformed JSONL row and rerun the audit.",
        )
        return []


def _load_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _has_source_anchor(row: dict[str, Any]) -> bool:
    return bool(_optional_str(row.get("source_url")) and _optional_str(row.get("source_path")))


def _primary_target(row: dict[str, Any]) -> str | None:
    target_id = _optional_str(row.get("target_id") or row.get("statute_id"))
    if target_id:
        return target_id
    target_ids = row.get("target_ids")
    if isinstance(target_ids, list):
        for value in target_ids:
            text = _optional_str(value)
            if text:
                return text
    return None


def _primary_source(row: dict[str, Any]) -> str | None:
    return _optional_str(row.get("source_id") or row.get("bill_id") or row.get("event_id"))


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _display_path(path: Path) -> str:
    return path.as_posix()


class IssueBuilder:
    """Build numbered audit issues."""

    def __init__(self) -> None:
        self.issues: list[CorpusUsabilityIssue] = []

    def add(
        self,
        severity: str,
        category: str,
        layer: str | None,
        record_id: str | None,
        path: str | None,
        field: str | None,
        detail: str,
        next_action: str,
    ) -> None:
        self.issues.append(
            CorpusUsabilityIssue(
                issue_id=f"CUA-{len(self.issues) + 1:06d}",
                severity=severity,
                category=category,
                layer=layer,
                record_id=record_id,
                path=path,
                field=field,
                detail=detail,
                next_action=next_action,
            )
        )


def main() -> None:
    """Run the corpus usability audit."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Rebuild the audit without writing artifacts. By default, status uses the latest report.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.write:
        audit = write_corpus_usability_audit(root)
    elif args.refresh:
        audit = build_corpus_usability_audit(root)[0]
    else:
        audit = _load_existing_audit(root) or build_corpus_usability_audit(root)[0]
    if args.json:
        print(audit.model_dump_json(indent=2))
        return
    print(f"Index records checked: {audit.total_index_records_checked}")
    print(f"Issues: {audit.issue_count}")


def _load_existing_audit(root: Path) -> CorpusUsabilityAudit | None:
    """Load the latest written audit report when present."""

    path = root / AUDIT_REPORT_PATH
    if not path.exists():
        return None
    try:
        payload = load_json(path)
        return CorpusUsabilityAudit.model_validate(payload)
    except (OSError, ValueError, TypeError):
        return None


if __name__ == "__main__":
    main()
