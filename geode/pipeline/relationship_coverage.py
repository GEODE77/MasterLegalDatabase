"""Measure crosswalk relationship coverage before building a visual graph."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl, load_json

RELATIONSHIP_COVERAGE_PATH = Path(CONTROL_PLANE_DIR) / "RELATIONSHIP_COVERAGE.jsonl"
RELATIONSHIP_COVERAGE_SUMMARY_PATH = (
    Path(CONTROL_PLANE_DIR) / "RELATIONSHIP_COVERAGE_SUMMARY.jsonl"
)
RELATIONSHIP_COVERAGE_REPORT_PATH = Path(CONTROL_PLANE_DIR) / "RELATIONSHIP_COVERAGE_REPORT.json"

CROSSWALK_FILES = (
    "regulation_to_statute.jsonl",
    "statute_to_regulation.jsonl",
    "rulemaking_to_regulation.jsonl",
    "bill_to_statute.jsonl",
    "agency_to_statute.jsonl",
    "amendment_history.jsonl",
)


class CrosswalkCoverageRecord(BaseModel):
    """Coverage details for one crosswalk file."""

    crosswalk_file: str
    source_type: str | None = None
    target_type: str | None = None
    relationship_count: int = Field(ge=0)
    unique_source_count: int = Field(ge=0)
    unique_target_count: int = Field(ge=0)
    missing_source_count: int = Field(ge=0)
    missing_target_count: int = Field(ge=0)
    missing_evidence_count: int = Field(ge=0)
    low_confidence_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    relationship_types: dict[str, int] = Field(default_factory=dict)
    confidence_average: float | None = None
    coverage_status: str


class RelationshipCoverageRecord(BaseModel):
    """Coverage details for one relationship row."""

    relationship_id: str
    crosswalk_file: str
    source_id: str | None = None
    source_type: str | None = None
    target_id: str | None = None
    target_type: str | None = None
    relationship: str
    confidence: float = Field(ge=0.0, le=1.0)
    has_source_evidence: bool
    source_evidence_excerpt: str | None = None
    supporting_id: str | None = None
    source_url: str | None = None
    data_retrieved: str | None = None
    duplicate_key: str


class RelationshipCoverageReport(BaseModel):
    """Summary report for relationship graph readiness."""

    generated_at: datetime
    coverage_path: str
    summary_path: str
    crosswalk_files_checked: int = Field(ge=0)
    total_relationships: int = Field(ge=0)
    total_duplicate_relationships: int = Field(ge=0)
    total_missing_evidence: int = Field(ge=0)
    total_low_confidence: int = Field(ge=0)
    ccr_regulations_total: int = Field(ge=0)
    ccr_regulations_with_relationships: int = Field(ge=0)
    ccr_relationship_coverage_ratio: float = Field(ge=0.0, le=1.0)
    structured_relationship_panel_ready: bool
    visual_graph_ready: bool
    visual_graph_deferred_reason: str
    coverage_records: list[CrosswalkCoverageRecord]
    recommended_next_actions: list[str] = Field(default_factory=list)


def build_relationship_coverage(
    root: Path,
) -> tuple[list[RelationshipCoverageRecord], list[CrosswalkCoverageRecord], RelationshipCoverageReport]:
    """Build crosswalk coverage records and summary report."""

    resolved_root = root.resolve()
    records: list[RelationshipCoverageRecord] = []
    summary_records: list[CrosswalkCoverageRecord] = []
    for name in CROSSWALK_FILES:
        relationship_rows, summary = _crosswalk_coverage(resolved_root, name)
        records.extend(relationship_rows)
        summary_records.append(summary)
    total_relationships = sum(record.relationship_count for record in summary_records)
    ccr_total, ccr_covered = _ccr_relationship_coverage(resolved_root)
    coverage_ratio = ccr_covered / ccr_total if ccr_total else 0.0
    missing_evidence = sum(record.missing_evidence_count for record in summary_records)
    low_confidence = sum(record.low_confidence_count for record in summary_records)
    duplicate_count = sum(record.duplicate_count for record in summary_records)
    empty_files = [
        record.crosswalk_file for record in summary_records if record.relationship_count == 0
    ]
    report = RelationshipCoverageReport(
        generated_at=datetime.now(timezone.utc),
        coverage_path=RELATIONSHIP_COVERAGE_PATH.as_posix(),
        summary_path=RELATIONSHIP_COVERAGE_SUMMARY_PATH.as_posix(),
        crosswalk_files_checked=len(summary_records),
        total_relationships=total_relationships,
        total_duplicate_relationships=duplicate_count,
        total_missing_evidence=missing_evidence,
        total_low_confidence=low_confidence,
        ccr_regulations_total=ccr_total,
        ccr_regulations_with_relationships=ccr_covered,
        ccr_relationship_coverage_ratio=round(coverage_ratio, 4),
        structured_relationship_panel_ready=total_relationships > 0 and ccr_covered > 0,
        visual_graph_ready=False,
        visual_graph_deferred_reason=(
            "Relationship coverage is measurable, but agency, amendment, and review-confirmed "
            "relationship layers are not complete enough for a visual graph."
        ),
        coverage_records=summary_records,
        recommended_next_actions=_recommended_next_actions(empty_files, missing_evidence, low_confidence),
    )
    return records, summary_records, report


def write_relationship_coverage(root: Path) -> RelationshipCoverageReport:
    """Write relationship coverage artifacts to the control plane."""

    resolved_root = root.resolve()
    records, summary_records, report = build_relationship_coverage(resolved_root)
    atomic_write_jsonl(resolved_root / RELATIONSHIP_COVERAGE_PATH, records, resolved_root)
    atomic_write_jsonl(
        resolved_root / RELATIONSHIP_COVERAGE_SUMMARY_PATH,
        summary_records,
        resolved_root,
    )
    atomic_write_json(resolved_root / RELATIONSHIP_COVERAGE_REPORT_PATH, report, resolved_root)
    return report


def _crosswalk_coverage(
    root: Path,
    file_name: str,
) -> tuple[list[RelationshipCoverageRecord], CrosswalkCoverageRecord]:
    """Build coverage details for one crosswalk JSONL file."""

    path = root / "_CROSSWALKS" / file_name
    rows = list(iter_jsonl(path)) if path.exists() and path.stat().st_size > 0 else []
    relationship_rows: list[RelationshipCoverageRecord] = []
    source_ids: set[str] = set()
    target_ids: set[str] = set()
    source_types = Counter[str]()
    target_types = Counter[str]()
    relationship_types = Counter[str]()
    seen_edges: set[tuple[str, str, str]] = set()
    duplicate_count = 0
    missing_source_count = 0
    missing_target_count = 0
    missing_evidence_count = 0
    low_confidence_count = 0
    confidence_total = 0.0
    confidence_count = 0

    for index, row in enumerate(rows, start=1):
        source_id = _primary_source(row)
        target_id = _primary_target(row)
        relationship = _as_str(row.get("relationship") or row.get("event_type"), "related")
        if source_id:
            source_ids.add(source_id)
        else:
            missing_source_count += 1
        if target_id:
            target_ids.add(target_id)
        else:
            missing_target_count += 1
        source_type = _optional_str(row.get("source_type"))
        target_type = _optional_str(row.get("target_type"))
        if source_type:
            source_types[source_type] += 1
        if target_type:
            target_types[target_type] += 1
        relationship_types[relationship] += 1
        confidence = _confidence(row.get("confidence"))
        confidence_total += confidence
        confidence_count += 1
        if confidence < 0.5:
            low_confidence_count += 1
        if not _optional_str(row.get("source_evidence")):
            missing_evidence_count += 1
        edge = (
            source_id or "",
            target_id or "",
            relationship,
            _optional_str(row.get("supporting_regulation_id") or row.get("event_id")) or "",
        )
        if edge in seen_edges:
            duplicate_count += 1
        seen_edges.add(edge)
        relationship_rows.append(
            RelationshipCoverageRecord(
                relationship_id=f"{Path(file_name).stem}:{index:06d}",
                crosswalk_file=file_name,
                source_id=source_id,
                source_type=source_type,
                target_id=target_id,
                target_type=target_type,
                relationship=relationship,
                confidence=confidence,
                has_source_evidence=bool(_optional_str(row.get("source_evidence"))),
                source_evidence_excerpt=_truncate(_optional_str(row.get("source_evidence")), 240),
                supporting_id=_optional_str(row.get("supporting_regulation_id") or row.get("event_id")),
                source_url=_optional_str(row.get("source_url")),
                data_retrieved=_optional_str(row.get("data_retrieved")),
                duplicate_key="|".join(edge),
            )
        )

    confidence_average = round(confidence_total / confidence_count, 4) if confidence_count else None
    summary = CrosswalkCoverageRecord(
        crosswalk_file=file_name,
        source_type=_most_common(source_types),
        target_type=_most_common(target_types),
        relationship_count=len(rows),
        unique_source_count=len(source_ids),
        unique_target_count=len(target_ids),
        missing_source_count=missing_source_count,
        missing_target_count=missing_target_count,
        missing_evidence_count=missing_evidence_count,
        low_confidence_count=low_confidence_count,
        duplicate_count=duplicate_count,
        relationship_types=dict(sorted(relationship_types.items())),
        confidence_average=confidence_average,
        coverage_status=_coverage_status(len(rows), missing_evidence_count, low_confidence_count),
    )
    return relationship_rows, summary


def _ccr_relationship_coverage(root: Path) -> tuple[int, int]:
    """Return total CCR regulations and how many have any relationship edge."""

    manifest = _load_dict(root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    ccr_index = _ccr_index_path(manifest)
    regulation_ids = {
        row["id"]
        for row in _read_jsonl_if_present(root / ccr_index)
        if isinstance(row.get("id"), str) and row.get("id")
    }
    related_ids: set[str] = set()
    for row in _read_jsonl_if_present(root / "_CROSSWALKS" / "regulation_to_statute.jsonl"):
        source_id = _optional_str(row.get("source_id"))
        if source_id in regulation_ids:
            related_ids.add(source_id)
    for row in _read_jsonl_if_present(root / "_CROSSWALKS" / "statute_to_regulation.jsonl"):
        target_id = _optional_str(row.get("target_id"))
        if target_id in regulation_ids:
            related_ids.add(target_id)
    for row in _read_jsonl_if_present(root / "_CROSSWALKS" / "rulemaking_to_regulation.jsonl"):
        target_id = _optional_str(row.get("target_id"))
        if target_id in regulation_ids:
            related_ids.add(target_id)
    return len(regulation_ids), len(related_ids)


def _ccr_index_path(manifest: dict[str, Any]) -> Path:
    """Return the CCR index path from the manifest."""

    layers = manifest.get("data_layers") if isinstance(manifest.get("data_layers"), list) else []
    for layer in layers:
        if isinstance(layer, dict) and layer.get("id") == "02_Regulations_CCR":
            return Path(_as_str(layer.get("index_file"), "02_Regulations_CCR/_index.jsonl"))
    return Path("02_Regulations_CCR/_index.jsonl")


def _recommended_next_actions(
    empty_files: list[str],
    missing_evidence: int,
    low_confidence: int,
) -> list[str]:
    """Return practical next actions for relationship work."""

    actions = [
        "Keep the relationship view structured in Explore instead of adding a visual graph now.",
        "Use relationship coverage to prioritize crosswalk cleanup before graph design.",
    ]
    if empty_files:
        actions.append(f"Populate empty relationship files: {', '.join(empty_files)}.")
    if missing_evidence:
        actions.append("Backfill source evidence for relationship records that lack evidence text.")
    if low_confidence:
        actions.append("Review low-confidence relationship records before relying on them externally.")
    return actions


def _read_jsonl_if_present(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file if it exists and is non-empty."""

    if not path.exists() or path.stat().st_size == 0:
        return []
    return list(iter_jsonl(path))


def _load_dict(path: Path) -> dict[str, Any]:
    """Load a JSON object, returning an empty object if absent."""

    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _primary_target(row: dict[str, Any]) -> str | None:
    """Return the primary target id for a crosswalk row."""

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
    """Return the primary source id for a crosswalk row."""

    return _optional_str(row.get("source_id") or row.get("bill_id") or row.get("event_id"))


def _confidence(value: object) -> float:
    """Normalize confidence to a 0-1 float."""

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(confidence, 0.0), 1.0)


def _coverage_status(row_count: int, missing_evidence: int, low_confidence: int) -> str:
    """Return a simple health label for a crosswalk file."""

    if row_count == 0:
        return "empty"
    risk_ratio = (missing_evidence + low_confidence) / row_count
    if risk_ratio >= 0.5:
        return "needs_review"
    if risk_ratio > 0:
        return "usable_with_warnings"
    return "usable"


def _most_common(counter: Counter[str]) -> str | None:
    """Return the most common counter key."""

    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _as_str(value: object, fallback: str) -> str:
    """Convert a value to a non-empty string."""

    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _optional_str(value: object) -> str | None:
    """Convert a value to a non-empty optional string."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truncate(value: str | None, limit: int) -> str | None:
    """Return a compact evidence excerpt."""

    if value is None or len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def main() -> None:
    """Build or write the relationship coverage report."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    if args.write:
        report = write_relationship_coverage(root)
    else:
        _, _, report = build_relationship_coverage(root)
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Relationship records: {report.total_relationships}")


if __name__ == "__main__":
    main()
