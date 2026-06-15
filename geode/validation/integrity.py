"""Cross-file integrity checks for Project Geode."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TypeAlias

from pydantic import ValidationError

from geode.constants import CRS_LAYER
from geode.schemas import (
    Agency,
    CrosswalkEntry,
    LayerIndexRecord,
    StatuteSection,
    TimelineEvent,
    ValidationResult,
)
from geode.utils.file_io import iter_jsonl, load_json
from geode.validation.checks import validate_project

IntegrityReport: TypeAlias = ValidationResult


def _merge_result(target: ValidationResult, source: ValidationResult) -> None:
    """Merge one integrity result into another."""

    for issue in source.issues:
        target.add_issue(issue.severity, issue.path, issue.message)


def _empty_result(name: str) -> ValidationResult:
    """Create an empty integrity result."""

    return ValidationResult.empty(layer=name, checked_at=datetime.now(timezone.utc))


def _layer_ids(root: Path, layer: str) -> set[str]:
    """Collect IDs from one layer index."""

    index_path = root / layer / "_index.jsonl"
    ids: set[str] = set()
    if not index_path.exists():
        return ids
    for row in iter_jsonl(index_path):
        entity_id = row.get("id", row.get("entity_id"))
        if entity_id:
            ids.add(str(entity_id))
    return ids


def _all_known_ids(root: Path) -> set[str]:
    """Collect all known entity IDs from indexes and agencies."""

    known_ids: set[str] = set()
    for layer in (
        "01_Statutes_CRS",
        "02_Regulations_CCR",
        "03_Legislation",
        "04_Rulemaking",
        "05_Executive_Orders",
        "06_Session_Laws",
        "07_Supplementary",
    ):
        known_ids.update(_layer_ids(root, layer))
    agency_path = root / "_CONTROL_PLANE" / "AGENCY_REGISTRY.json"
    if agency_path.exists():
        payload = load_json(agency_path)
        agencies = payload.get("agencies", []) if isinstance(payload, dict) else payload
        if isinstance(agencies, list):
            for agency_payload in agencies:
                if isinstance(agency_payload, dict) and agency_payload.get("id"):
                    known_ids.add(str(agency_payload["id"]))
    return known_ids


def check_orphan_regulations(root: Path) -> ValidationResult:
    """Warn for regulation records without enabling-statute crosswalks."""

    result = _empty_result("orphan_regulations")
    regulation_ids = _layer_ids(root, "02_Regulations_CCR")
    if not regulation_ids:
        return result
    linked_sources: set[str] = set()
    for crosswalk_path in sorted((root / "_CROSSWALKS").glob("*.jsonl")):
        for row in iter_jsonl(crosswalk_path):
            if row.get("relationship") in {"authorized_by", "implements", "enabled_by"}:
                linked_sources.add(str(row.get("source_id", "")))
    for regulation_id in sorted(regulation_ids - linked_sources):
        result.add_issue("warning", "02_Regulations_CCR", f"orphan regulation: {regulation_id}")
    return result


def check_dead_crosswalks(root: Path) -> ValidationResult:
    """Warn when crosswalk source or target IDs are unknown."""

    result = _empty_result("dead_crosswalks")
    known_ids = _all_known_ids(root)
    if not known_ids:
        return result
    for crosswalk_path in sorted((root / "_CROSSWALKS").glob("*.jsonl")):
        for row in iter_jsonl(crosswalk_path):
            crosswalk = CrosswalkEntry.model_validate(row)
            if crosswalk.source_id not in known_ids:
                result.add_issue(
                    "warning",
                    crosswalk_path.as_posix(),
                    f"unknown source_id: {crosswalk.source_id}",
                )
            targets = crosswalk.target_ids or ([crosswalk.target_id] if crosswalk.target_id else [])
            for target_id in targets:
                if target_id not in known_ids:
                    result.add_issue(
                        "warning",
                        crosswalk_path.as_posix(),
                        f"unknown target_id: {target_id}",
                    )
    return result


def check_tag_coverage(root: Path) -> ValidationResult:
    """Warn for metadata records without subject tags."""

    result = _empty_result("tag_coverage")
    for meta_path in sorted(root.glob("**/_meta/*.jsonl")):
        for row in iter_jsonl(meta_path):
            if not row.get("subject_tags"):
                result.add_issue("warning", meta_path.as_posix(), "record has no subject tags")
    return result


def check_summary_coverage(root: Path) -> ValidationResult:
    """Warn for non-statute records missing summary fields."""

    result = _empty_result("summary_coverage")
    for meta_path in sorted(root.glob("**/_meta/*.jsonl")):
        for row in iter_jsonl(meta_path):
            summary = row.get("summary", row.get("chunk_level_3_summary"))
            if row.get("entity_type") != "statute_section" and not summary:
                result.add_issue("warning", meta_path.as_posix(), "record has no summary")
    return result


def check_crosswalk_completeness(root: Path) -> ValidationResult:
    """Warn when regulation metadata lists statutes but crosswalks do not."""

    result = _empty_result("crosswalk_completeness")
    expected: set[tuple[str, str]] = set()
    for meta_path in sorted((root / "02_Regulations_CCR").glob("_meta/*.jsonl")):
        for row in iter_jsonl(meta_path):
            regulation_id = str(row.get("id", ""))
            for statute_id in row.get("enabling_statutes", []):
                expected.add((regulation_id, str(statute_id)))
    found: set[tuple[str, str]] = set()
    for crosswalk_path in sorted((root / "_CROSSWALKS").glob("*.jsonl")):
        for row in iter_jsonl(crosswalk_path):
            targets = row.get("target_ids") or [row.get("target_id")]
            for target in targets:
                if target:
                    found.add((str(row.get("source_id", "")), str(target)))
    for regulation_id, statute_id in sorted(expected - found):
        result.add_issue(
            "warning",
            "02_Regulations_CCR",
            f"missing crosswalk: {regulation_id} -> {statute_id}",
        )
    return result


def run_integrity_check(root: Path | None = None) -> IntegrityReport:
    """Run the monthly integrity report interface."""

    return run_integrity_checks((root or Path.cwd()).resolve())


def run_integrity_checks(root: Path) -> ValidationResult:
    """Run cross-layer and cross-file integrity checks."""

    result = validate_project(root, "all")
    checked_at = datetime.now(timezone.utc)
    result.checked_at = checked_at

    index_path = root / CRS_LAYER / "_index.jsonl"
    if not index_path.exists():
        return result

    indexed_ids: set[str] = set()
    meta_paths: set[Path] = set()
    for row in iter_jsonl(index_path):
        try:
            record = LayerIndexRecord.model_validate(row)
        except ValidationError:
            continue
        indexed_ids.add(record.entity_id)
        if record.meta_path:
            meta_paths.add(root / record.meta_path)

    metadata_ids: set[str] = set()
    for meta_path in meta_paths:
        if not meta_path.exists():
            continue
        for row in iter_jsonl(meta_path):
            try:
                section = StatuteSection.model_validate(row)
            except ValidationError:
                continue
            if section.entity_id in metadata_ids:
                result.add_issue(
                    "error",
                    meta_path.as_posix(),
                    f"duplicate metadata ID: {section.entity_id}",
                )
            metadata_ids.add(section.entity_id)

    missing_metadata = indexed_ids - metadata_ids
    missing_index = metadata_ids - indexed_ids
    for entity_id in sorted(missing_metadata):
        result.add_issue("error", CRS_LAYER, f"indexed ID missing from metadata: {entity_id}")
    for entity_id in sorted(missing_index):
        result.add_issue("error", CRS_LAYER, f"metadata ID missing from index: {entity_id}")

    raw_tmp_files = list((root / "_RAW_ARCHIVE").glob("**/*.tmp"))
    for tmp_file in raw_tmp_files:
        result.add_issue("error", tmp_file.as_posix(), "temporary file found in raw archive")

    known_ids = set(indexed_ids) | metadata_ids
    agency_path = root / "_CONTROL_PLANE" / "AGENCY_REGISTRY.json"
    if agency_path.exists():
        payload = load_json(agency_path)
        agencies = payload.get("agencies", []) if isinstance(payload, dict) else payload
        if isinstance(agencies, list):
            for agency_payload in agencies:
                agency = Agency.model_validate(agency_payload)
                known_ids.add(agency.id)

    for crosswalk_path in sorted((root / "_CROSSWALKS").glob("*.jsonl")):
        for row in iter_jsonl(crosswalk_path):
            crosswalk = CrosswalkEntry.model_validate(row)
            if known_ids and crosswalk.source_id not in known_ids:
                result.add_issue(
                    "warning",
                    crosswalk_path.as_posix(),
                    f"unknown source_id: {crosswalk.source_id}",
                )
            targets = crosswalk.target_ids or ([crosswalk.target_id] if crosswalk.target_id else [])
            for target_id in targets:
                if known_ids and target_id not in known_ids:
                    result.add_issue(
                        "warning",
                        crosswalk_path.as_posix(),
                        f"unknown target_id: {target_id}",
                    )

    timeline_path = root / "_CONTROL_PLANE" / "MASTER_TIMELINE_INDEX.jsonl"
    if timeline_path.exists():
        for row in iter_jsonl(timeline_path):
            event = TimelineEvent.model_validate(row)
            if known_ids and event.entity_id not in known_ids:
                result.add_issue(
                    "warning",
                    timeline_path.as_posix(),
                    f"unknown timeline entity_id: {event.entity_id}",
                )
            event_file = root / event.file_path
            if not event_file.exists():
                result.add_issue(
                    "warning",
                    timeline_path.as_posix(),
                    f"timeline file_path missing: {event.file_path}",
                )
    for monthly_result in (
        check_orphan_regulations(root),
        check_dead_crosswalks(root),
        check_tag_coverage(root),
        check_summary_coverage(root),
        check_crosswalk_completeness(root),
    ):
        _merge_result(result, monthly_result)
    return result
