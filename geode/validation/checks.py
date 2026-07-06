"""Schema and file integrity validation checks."""

from __future__ import annotations

import json
import re
from datetime import date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from geode.constants import ALL_LAYERS, CONTROL_PLANE_DIR, CRS_LAYER
from geode.schemas import (
    Agency,
    CrosswalkEntry,
    LayerIndexRecord,
    StatuteSection,
    TimelineEvent,
    ValidationResult,
)
from geode.schemas.ontology import (
    COMPLIANCE_KEYWORDS,
    EVENT_TYPES,
    INDUSTRY_TAGS,
    RELATIONSHIP_TYPES,
    RULE_TYPES,
    STATUS_VALUES,
    SUBJECT_TAGS,
)
from geode.schemas.validators import require_official_source_url
from geode.schemas.validators import validate_record
from geode.utils.file_io import iter_jsonl, load_json

OPERATIONAL_RECORD_KEYS = frozenset(
    {"crosswalks", "timeline_events", "layer", "publication_year", "source_path"}
)
CANARY_CITATION_PATTERN = re.compile(
    r"(?:CRS-|C\.R\.S\.?\s*(?:section|§)?\s*)(\d{1,2}(?:\.\d+)?-\d+(?:\.\d+)?-\d+)",
    re.IGNORECASE,
)


def _relative(path: Path, root: Path) -> str:
    """Return a display path for validation messages."""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _new_record_result(name: str = "record") -> ValidationResult:
    """Create a record-level validation result."""

    return ValidationResult.empty(layer=name, checked_at=datetime.now(timezone.utc))


def _merge_result(target: ValidationResult, source: ValidationResult) -> None:
    """Merge issues from one validation result into another."""

    for issue in source.issues:
        target.add_issue(issue.severity, issue.path, issue.message)


def _corpus_record(record: dict[str, Any]) -> dict[str, Any]:
    """Remove operational writer fields before schema validation."""

    return {key: value for key, value in record.items() if key not in OPERATIONAL_RECORD_KEYS}


def _known_entity_ids(root: Path) -> set[str]:
    """Collect known entity IDs from layer indexes and agency registry."""

    known: set[str] = set()
    for layer in ALL_LAYERS:
        index_path = root / layer / "_index.jsonl"
        if not index_path.exists():
            continue
        try:
            for row in iter_jsonl(index_path):
                entity_id = row.get("id", row.get("entity_id"))
                if entity_id:
                    known.add(str(entity_id))
        except (json.JSONDecodeError, ValueError):
            continue
    agency_path = root / CONTROL_PLANE_DIR / "AGENCY_REGISTRY.json"
    if agency_path.exists():
        try:
            payload = load_json(agency_path)
            agencies = payload.get("agencies", []) if isinstance(payload, dict) else payload
            if isinstance(agencies, list):
                for agency in agencies:
                    if isinstance(agency, dict) and agency.get("id"):
                        known.add(str(agency["id"]))
        except (json.JSONDecodeError, ValueError):
            pass
    return known


def _extract_reference_ids(record: dict[str, Any]) -> set[str]:
    """Extract explicit cross-record references from a corpus record."""

    reference_fields = (
        "cross_references_outbound",
        "enabling_statutes",
        "related_regulations",
        "statutes_amended",
        "statutes_created",
        "statutes_repealed",
        "statutes_affected",
        "affects",
        "statutes_cited",
        "statutes_interpreted",
    )
    refs: set[str] = set()
    for field in reference_fields:
        values = record.get(field, [])
        if isinstance(values, str):
            refs.add(values)
        elif isinstance(values, list):
            refs.update(str(value) for value in values if value)
    if record.get("source_id"):
        refs.add(str(record["source_id"]))
    if record.get("target_id"):
        refs.add(str(record["target_id"]))
    if isinstance(record.get("target_ids"), list):
        refs.update(str(value) for value in record["target_ids"] if value)
    return refs


def _date_values(record: dict[str, Any]) -> dict[str, date]:
    """Return parseable date fields from a record."""

    dates: dict[str, date] = {}
    for key, value in record.items():
        if not key.endswith("_date") and key not in {"date", "data_retrieved"}:
            continue
        if value is None:
            continue
        if isinstance(value, date):
            dates[key] = value
            continue
        if isinstance(value, str):
            try:
                dates[key] = date.fromisoformat(value[:10])
            except ValueError:
                continue
    return dates


def _allows_future_date(record: dict[str, Any], field_name: str) -> bool:
    """Return whether a date field may legitimately be future-dated."""

    return record.get("entity_type") == "regulation_rule" and field_name == "effective_date"


def check_schema_compliance(record: dict[str, Any]) -> ValidationResult:
    """Check one record against its Pydantic schema."""

    result = _new_record_result("schema")
    valid, errors = validate_record(_corpus_record(record))
    for error in errors:
        result.add_issue("error", "record", error)
    if valid:
        result.valid = True
    return result


def check_id_uniqueness(
    record: dict[str, Any],
    root: Path | None = None,
    allow_existing: bool = False,
) -> ValidationResult:
    """Check that a record ID is not duplicated across layer indexes."""

    result = _new_record_result("id_uniqueness")
    root = root or Path.cwd()
    record_id = str(record.get("id", record.get("entity_id", "")))
    if not record_id:
        result.add_issue("error", "record", "record id is required")
        return result
    occurrences = 0
    for layer in ALL_LAYERS:
        index_path = root / layer / "_index.jsonl"
        if not index_path.exists():
            continue
        try:
            for row in iter_jsonl(index_path):
                if str(row.get("id", row.get("entity_id", ""))) == record_id:
                    occurrences += 1
        except (json.JSONDecodeError, ValueError) as exc:
            result.add_issue("error", _relative(index_path, root), str(exc))
    if occurrences and not allow_existing:
        result.add_issue("error", "record", f"duplicate ID already exists: {record_id}")
    if occurrences > 1:
        result.add_issue("error", "record", f"ID appears multiple times: {record_id}")
    return result


def check_referential_integrity(
    record: dict[str, Any],
    root: Path | None = None,
) -> ValidationResult:
    """Check that explicit Geode references resolve when an index exists."""

    result = _new_record_result("referential_integrity")
    root = root or Path.cwd()
    known_ids = _known_entity_ids(root)
    if not known_ids:
        return result
    for reference_id in sorted(_extract_reference_ids(_corpus_record(record))):
        should_check = (
            (reference_id.startswith("CRS-") and any(item.startswith("CRS-") for item in known_ids))
            or (
                reference_id.startswith("TE-")
                and any(item.startswith("TE-") for item in known_ids)
            )
            or ("_CCR_" in reference_id and any("_CCR_" in item for item in known_ids))
        )
        if should_check:
            if reference_id not in known_ids:
                result.add_issue("error", "record", f"unknown referenced ID: {reference_id}")
    return result


def check_date_logic(record: dict[str, Any]) -> ValidationResult:
    """Check date ordering, future dates, and Colorado statehood lower bound."""

    result = _new_record_result("date_logic")
    dates = _date_values(_corpus_record(record))
    today = date.today()
    minimum = date(1876, 8, 1)
    for key, value in dates.items():
        if value > today and not _allows_future_date(_corpus_record(record), key):
            result.add_issue("error", "record", f"{key} cannot be in the future")
        if value < minimum:
            result.add_issue("error", "record", f"{key} predates Colorado statehood")
    adopted = dates.get("adopted_date")
    effective = dates.get("effective_date")
    if adopted and effective and effective < adopted:
        result.add_issue("error", "record", "effective_date cannot precede adopted_date")
    return result


def check_text_integrity(record: dict[str, Any]) -> ValidationResult:
    """Check text presence and the mandatory hallucination citation canary."""

    result = _new_record_result("text_integrity")
    corpus = _corpus_record(record)
    full_text = str(corpus.get("full_text", corpus.get("text", ""))).strip()
    if not full_text:
        result.add_issue("error", "record", "full_text must be non-empty")
        return result
    summary = str(
        corpus.get("summary", corpus.get("chunk_level_3_summary", ""))
    )
    full_text_normalized = full_text.casefold()
    for match in CANARY_CITATION_PATTERN.finditer(summary):
        citation = match.group(1)
        if citation.casefold() not in full_text_normalized:
            result.add_issue(
                "error",
                "record",
                f"summary cites absent statute: CRS-{citation}",
            )
    return result


def check_cross_record_consistency(
    record: dict[str, Any],
    root: Path | None = None,
) -> ValidationResult:
    """Check agency and department consistency against the agency registry."""

    result = _new_record_result("cross_record_consistency")
    root = root or Path.cwd()
    corpus = _corpus_record(record)
    agency_code = corpus.get("agency_code")
    department_code = corpus.get("department_code")
    if not agency_code:
        return result
    agency_path = root / CONTROL_PLANE_DIR / "AGENCY_REGISTRY.json"
    if not agency_path.exists():
        result.add_issue("warning", "record", "agency registry is missing")
        return result
    payload = load_json(agency_path)
    agencies = payload.get("agencies", []) if isinstance(payload, dict) else payload
    agency = None
    if isinstance(agencies, list):
        agency = next(
            (
                item
                for item in agencies
                if isinstance(item, dict) and item.get("id") == agency_code
            ),
            None,
        )
    if agency is None:
        result.add_issue("error", "record", f"unknown agency_code: {agency_code}")
        return result
    if department_code and str(agency.get("department_code")) != str(department_code):
        result.add_issue(
            "error",
            "record",
            f"agency {agency_code} is not under department {department_code}",
        )
    return result


def run_all_checks(
    record: dict[str, Any],
    root: Path | None = None,
    allow_existing: bool = False,
) -> ValidationResult:
    """Run all six ingestion checks for one record."""

    root = root or Path.cwd()
    result = _new_record_result("ingestion")
    for check_result in (
        check_schema_compliance(record),
        check_id_uniqueness(record, root, allow_existing=allow_existing),
        check_referential_integrity(record, root),
        check_date_logic(record),
        check_text_integrity(record),
        check_cross_record_consistency(record, root),
    ):
        _merge_result(result, check_result)
    return result


def _validate_json_file(result: ValidationResult, path: Path, root: Path) -> None:
    """Validate that a JSON control-plane file contains a JSON object."""

    if not path.exists():
        result.add_issue("error", _relative(path, root), "required JSON file is missing")
        return
    try:
        load_json(path)
    except (json.JSONDecodeError, ValueError) as exc:
        result.add_issue("error", _relative(path, root), str(exc))


def _require_terms(
    result: ValidationResult,
    path: Path,
    root: Path,
    payload: dict[str, object],
    key: str,
    required: frozenset[str],
) -> None:
    """Ensure a control-plane vocabulary contains required design terms."""

    values = payload.get(key)
    if not isinstance(values, list):
        result.add_issue("error", _relative(path, root), f"{key} must be a list")
        return
    missing = sorted(required - {str(value) for value in values})
    if missing:
        result.add_issue("error", _relative(path, root), f"{key} missing terms: {missing}")


def _flatten_subject_tags(subject_tags: object) -> set[str]:
    """Flatten hierarchical or legacy subject-tag ontology shapes."""

    if isinstance(subject_tags, list):
        return {str(value) for value in subject_tags}
    if not isinstance(subject_tags, dict):
        raise ValueError("subject_tags must be an object or list")
    flattened: set[str] = set()
    for parent, payload in subject_tags.items():
        flattened.add(str(parent))
        if not isinstance(payload, dict):
            raise ValueError(f"subject tag parent {parent} must be an object")
        children = payload.get("children")
        if not isinstance(children, list):
            raise ValueError(f"subject tag parent {parent} must define children")
        flattened.update(str(child) for child in children)
    return flattened


def _flatten_industry_tags(industry_tags: object) -> set[str]:
    """Flatten object-based or legacy industry-tag ontology shapes."""

    if not isinstance(industry_tags, list):
        raise ValueError("industry_tags must be a list")
    flattened: set[str] = set()
    for item in industry_tags:
        if isinstance(item, dict):
            if "tag" not in item:
                raise ValueError("industry tag objects must include tag")
            flattened.add(str(item["tag"]))
        else:
            flattened.add(str(item))
    return flattened


def _validate_ontology(result: ValidationResult, path: Path, root: Path) -> None:
    """Validate controlled vocabulary files against code-level vocabularies."""

    if not path.exists():
        result.add_issue("error", _relative(path, root), "ontology is missing")
        return
    try:
        payload = load_json(path)
    except (json.JSONDecodeError, ValueError) as exc:
        result.add_issue("error", _relative(path, root), str(exc))
        return

    try:
        subject_tags = _flatten_subject_tags(payload.get("subject_tags"))
        industry_tags = _flatten_industry_tags(payload.get("industry_tags"))
    except ValueError as exc:
        result.add_issue("error", _relative(path, root), str(exc))
        return

    missing_subjects = sorted(SUBJECT_TAGS - subject_tags)
    if missing_subjects:
        result.add_issue(
            "error",
            _relative(path, root),
            f"subject_tags missing: {missing_subjects}",
        )
    missing_industries = sorted(INDUSTRY_TAGS - industry_tags)
    if missing_industries:
        result.add_issue(
            "error",
            _relative(path, root),
            f"industry_tags missing: {missing_industries}",
        )
    _require_terms(result, path, root, payload, "compliance_keywords", COMPLIANCE_KEYWORDS)
    for key, required in (
        ("rule_type_enum", RULE_TYPES),
        ("relationship_type_enum", RELATIONSHIP_TYPES),
        ("event_type_enum", EVENT_TYPES),
        ("status_enum", STATUS_VALUES),
    ):
        values = payload.get(key)
        if not isinstance(values, list):
            result.add_issue("error", _relative(path, root), f"{key} must be a list")
            continue
        missing = sorted(required - {str(value) for value in values})
        if missing:
            result.add_issue(
                "error",
                _relative(path, root),
                f"{key} missing: {missing}",
            )


def _validate_master_schema(result: ValidationResult, path: Path, root: Path) -> None:
    """Validate that the master schema declares all design entity types."""

    if not path.exists():
        result.add_issue("error", _relative(path, root), "master schema is missing")
        return
    try:
        payload = load_json(path)
    except (json.JSONDecodeError, ValueError) as exc:
        result.add_issue("error", _relative(path, root), str(exc))
        return
    expected = {
        "statute_section",
        "regulation_rule",
        "bill",
        "rulemaking_notice",
        "executive_order",
        "session_law",
        "ag_opinion",
        "coprrr_review",
        "rule_unit",
        "crosswalk_entry",
        "timeline_event",
        "agency",
    }
    defs = payload.get("$defs", {})
    if not isinstance(defs, dict):
        result.add_issue("error", _relative(path, root), "$defs must be an object")
        return
    found = set(defs)
    missing = sorted(expected - found)
    if missing:
        result.add_issue("error", _relative(path, root), f"entity_types missing: {missing}")


def _validate_agency_registry(result: ValidationResult, path: Path, root: Path) -> None:
    """Validate agency registry records."""

    if not path.exists():
        result.add_issue("error", _relative(path, root), "agency registry is missing")
        return
    try:
        payload = load_json(path)
        agencies = payload.get("agencies", []) if isinstance(payload, dict) else payload
        if not isinstance(agencies, list):
            raise ValueError("agencies must be a list")
        for agency in agencies:
            Agency.model_validate(agency)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        result.add_issue("error", _relative(path, root), str(exc))


def _validate_manifest(result: ValidationResult, path: Path, root: Path) -> None:
    """Validate the Phase 1E master manifest shape."""

    if not path.exists():
        result.add_issue("error", _relative(path, root), "master manifest is missing")
        return
    try:
        payload = load_json(path)
        if not isinstance(payload, dict):
            raise ValueError("master manifest must be an object")
        project = payload.get("project")
        if not isinstance(project, dict):
            raise ValueError("project metadata must be an object")
        for key in ("name", "description", "version", "created_date"):
            if key not in project:
                raise ValueError(f"project.{key} is required")

        layers = payload.get("data_layers")
        if not isinstance(layers, list) or len(layers) != len(ALL_LAYERS):
            raise ValueError("data_layers must contain all seven layers")
        layer_ids = {str(layer.get("id")) for layer in layers if isinstance(layer, dict)}
        missing_layers = sorted(set(ALL_LAYERS) - layer_ids)
        if missing_layers:
            raise ValueError(f"data_layers missing: {missing_layers}")
        for layer in layers:
            if not isinstance(layer, dict):
                raise ValueError("each data_layers entry must be an object")
            for key in (
                "id",
                "path",
                "entity_type",
                "record_count",
                "source",
                "format",
                "last_ingested",
                "currency",
                "index_file",
                "known_gaps",
                "last_checked",
                "staleness_days",
                "status",
            ):
                if key not in layer:
                    raise ValueError(f"data layer {layer.get('id')} missing {key}")

        required_crosswalks = {
            "regulation_to_statute.jsonl",
            "statute_to_regulation.jsonl",
            "bill_to_statute.jsonl",
            "rulemaking_to_regulation.jsonl",
            "agency_to_statute.jsonl",
            "amendment_history.jsonl",
        }
        found_crosswalks = set(payload.get("crosswalks_available", []))
        if required_crosswalks - found_crosswalks:
            raise ValueError("crosswalks_available is incomplete")

        policy = payload.get("freshness_policy")
        if not isinstance(policy, dict):
            raise ValueError("freshness_policy must be an object")
        expected_policy = {
            "statutes": (365, 330),
            "regulations": (45, 30),
            "legislation": (14, 10),
            "rulemaking": (20, 15),
            "exec_orders": (60, 45),
            "session_laws": (365, 330),
            "supplementary": (120, 90),
        }
        for key, (max_days, alert_days) in expected_policy.items():
            actual = policy.get(key)
            if not isinstance(actual, dict):
                raise ValueError(f"freshness_policy.{key} is required")
            if actual.get("max_staleness_days") != max_days:
                raise ValueError(f"freshness_policy.{key}.max_staleness_days mismatch")
            if actual.get("alert_after_days") != alert_days:
                raise ValueError(f"freshness_policy.{key}.alert_after_days mismatch")

        system_info = payload.get("system_info")
        if not isinstance(system_info, dict):
            raise ValueError("system_info must be an object")
        for key in ("pipeline_version", "schema_version", "ontology_version"):
            if key not in system_info:
                raise ValueError(f"system_info.{key} is required")
    except (ValueError, json.JSONDecodeError) as exc:
        result.add_issue("error", _relative(path, root), str(exc))


def _validate_pilot_test_set(result: ValidationResult, path: Path, root: Path) -> None:
    """Validate the canonical Phase 4A pilot test set."""

    if not path.exists():
        result.add_issue("error", _relative(path, root), "pilot test set is missing")
        return
    try:
        payload = load_json(path)
        if not isinstance(payload, dict):
            raise ValueError("pilot test set must be an object")
        rules = payload.get("rules")
        if not isinstance(rules, list):
            raise ValueError("pilot test set rules must be a list")

        from geode.pipeline.pilot import validate_pilot_test_set

        pilot_result = validate_pilot_test_set(rules, root=root)
        display_path = _relative(path, root)
        for issue in pilot_result.issues:
            result.add_issue(issue.severity, f"{display_path}:{issue.path}", issue.message)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        result.add_issue("error", _relative(path, root), str(exc))


def validate_control_plane(root: Path, result: ValidationResult) -> None:
    """Validate core control-plane JSON files."""

    control = root / CONTROL_PLANE_DIR
    _validate_master_schema(result, control / "MASTER_SCHEMA.json", root)
    _validate_ontology(result, control / "ONTOLOGY.json", root)
    _validate_agency_registry(result, control / "AGENCY_REGISTRY.json", root)

    source_registry_path = control / "SOURCE_REGISTRY.json"
    _validate_json_file(result, source_registry_path, root)
    if source_registry_path.exists():
        try:
            registry = load_json(source_registry_path)
            sources = registry.get("sources", []) if isinstance(registry, dict) else registry
            if not isinstance(sources, list):
                raise ValueError("source registry must be a list or contain sources list")
            for source in sources:
                if isinstance(source, dict) and "url" in source:
                    require_official_source_url(str(source["url"]))
                if isinstance(source, dict) and source.get("api_url"):
                    require_official_source_url(str(source["api_url"]))
        except (ValueError, json.JSONDecodeError) as exc:
            result.add_issue("error", _relative(source_registry_path, root), str(exc))

    manifest_path = control / "MASTER_MANIFEST.json"
    _validate_manifest(result, manifest_path, root)
    _validate_pilot_test_set(result, control / "PILOT_TEST_SET.json", root)


def validate_jsonl_file(
    result: ValidationResult,
    path: Path,
    root: Path,
) -> list[dict[str, object]]:
    """Validate JSONL syntax and return parsed rows."""

    if not path.exists():
        result.add_issue("error", _relative(path, root), "required JSONL file is missing")
        return []
    try:
        return list(iter_jsonl(path))
    except (json.JSONDecodeError, ValueError) as exc:
        result.add_issue("error", _relative(path, root), str(exc))
        return []


def validate_crs_layer(root: Path, result: ValidationResult) -> None:
    """Validate the CRS layer index, metadata, and referenced Markdown."""

    layer_root = root / CRS_LAYER
    if not layer_root.exists():
        result.add_issue("error", CRS_LAYER, "CRS layer directory is missing")
        return

    index_path = layer_root / "_index.jsonl"
    rows = validate_jsonl_file(result, index_path, root)
    entity_ids: set[str] = set()
    meta_paths: set[Path] = set()
    for row in rows:
        try:
            record = LayerIndexRecord.model_validate(row)
        except ValidationError as exc:
            result.add_issue("error", _relative(index_path, root), str(exc))
            continue
        if record.entity_id in entity_ids:
            result.add_issue(
                "error",
                _relative(index_path, root),
                f"duplicate ID: {record.entity_id}",
            )
        entity_ids.add(record.entity_id)
        markdown_path = root / record.path
        if not markdown_path.exists():
            result.add_issue("error", record.path, "indexed Markdown file is missing")
        if record.meta_path:
            meta_paths.add(root / record.meta_path)

    for meta_path in sorted(meta_paths):
        meta_rows = validate_jsonl_file(result, meta_path, root)
        for row in meta_rows:
            try:
                StatuteSection.model_validate(row)
            except ValidationError as exc:
                result.add_issue("error", _relative(meta_path, root), str(exc))


def validate_crosswalks(root: Path, result: ValidationResult) -> None:
    """Validate all crosswalk JSONL relationship files."""

    crosswalk_root = root / "_CROSSWALKS"
    if not crosswalk_root.exists():
        result.add_issue("error", "_CROSSWALKS", "crosswalk directory is missing")
        return
    for path in sorted(crosswalk_root.glob("*.jsonl")):
        for row in validate_jsonl_file(result, path, root):
            try:
                CrosswalkEntry.model_validate(row)
            except ValidationError as exc:
                result.add_issue("error", _relative(path, root), str(exc))


def validate_timeline(root: Path, result: ValidationResult) -> None:
    """Validate the master chronological timeline index."""

    timeline_path = root / CONTROL_PLANE_DIR / "MASTER_TIMELINE_INDEX.jsonl"
    ids: set[str] = set()
    for row in validate_jsonl_file(result, timeline_path, root):
        try:
            event = TimelineEvent.model_validate(row)
        except ValidationError as exc:
            result.add_issue("error", _relative(timeline_path, root), str(exc))
            continue
        if event.id in ids:
            result.add_issue(
                "error",
                _relative(timeline_path, root),
                f"duplicate timeline ID: {event.id}",
            )
        ids.add(event.id)


def validate_project(root: Path, layer: str) -> ValidationResult:
    """Validate a Geode project or a single layer."""

    checked_at = datetime.now(timezone.utc)
    result = ValidationResult.empty(layer=layer, checked_at=checked_at)
    validate_control_plane(root, result)

    if layer == "all":
        for layer_name in ALL_LAYERS:
            index_path = root / layer_name / "_index.jsonl"
            if not index_path.exists():
                result.add_issue("error", layer_name, "layer index is missing")
        validate_crs_layer(root, result)
        validate_crosswalks(root, result)
        validate_timeline(root, result)
    elif layer == CRS_LAYER:
        validate_crs_layer(root, result)
    else:
        index_path = root / layer / "_index.jsonl"
        if not index_path.exists():
            result.add_issue("error", layer, "layer index is missing")
        else:
            validate_jsonl_file(result, index_path, root)
    return result
