"""Audit county records for structural integrity, readability, and AI readiness."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from geode.schemas import LocalAuthority, LocalRule, RuleUnit
from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json


T = TypeVar("T", bound=BaseModel)
REPLACEMENT = "\ufffd"
MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â€™", "â€œ", "â€”")


def _validate_rows(path: Path, model: type[T]) -> tuple[list[dict[str, Any]], int]:
    """Validate JSONL rows and return valid rows plus the failure count."""

    valid: list[dict[str, Any]] = []
    failures = 0
    for row in iter_jsonl(path):
        try:
            model.model_validate(row)
        except (ValidationError, TypeError, ValueError):
            failures += 1
        else:
            valid.append(row)
    return valid, failures


def _contains_bad_text(values: Iterable[object]) -> bool:
    """Return whether any text contains replacement characters or common mojibake."""

    return any(
        marker in str(value)
        for value in values
        if value is not None
        for marker in (REPLACEMENT, *MOJIBAKE_MARKERS)
    )


def _marker_counts(values: Iterable[object]) -> Counter[str]:
    """Count replacement characters and suspected mojibake in text fields."""

    counts: Counter[str] = Counter()
    for value in values:
        text = str(value) if value is not None else ""
        for marker in (REPLACEMENT, *MOJIBAKE_MARKERS):
            counts[marker] += text.count(marker)
    return counts


def _sha256(path: Path) -> str:
    """Hash a preserved source file without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_audit(root: Path) -> dict[str, Any]:
    """Build a durable audit of the active county data layer."""

    layer = root / "08_County_Authorities"
    meta = layer / "_meta"
    authority_rows, authority_schema_errors = _validate_rows(
        meta / "local_authorities.jsonl", LocalAuthority
    )
    rule_rows, rule_schema_errors = _validate_rows(meta / "local_rules.jsonl", LocalRule)
    unit_rows, unit_schema_errors = _validate_rows(meta / "local_rule_units.jsonl", RuleUnit)

    authority_ids = {str(row.get("id")) for row in authority_rows}
    rule_ids = {str(row.get("id")) for row in rule_rows}
    source_path_errors = 0
    source_hash_errors = 0
    bad_rule_text = 0
    generic_summaries = 0
    for row in rule_rows:
        source = root / str(row["source_path"])
        if not source.is_file():
            source_path_errors += 1
        elif _sha256(source) != str(row["source_hash"]):
            source_hash_errors += 1
        if _contains_bad_text((row.get("title"), row.get("full_text"), row.get("summary"))):
            bad_rule_text += 1
        if str(row.get("summary", "")).startswith("Source document titled "):
            generic_summaries += 1

    orphan_rules = sum(1 for row in rule_rows if str(row.get("authority_id")) not in authority_ids)
    orphan_units = sum(
        1 for row in unit_rows if str(row.get("parent_regulation_id")) not in rule_ids
    )
    unit_bad_text = sum(
        1
        for row in unit_rows
        if _contains_bad_text(
            (
                row.get("source_section"),
                row.get("regulated_entity"),
                row.get("action_required"),
                row.get("plain_english_summary"),
            )
        )
    )
    rule_marker_counts = _marker_counts(
        value for row in rule_rows for value in (row.get("title"), row.get("full_text"), row.get("summary"))
    )
    unit_marker_counts = _marker_counts(
        value
        for row in unit_rows
        for value in (
            row.get("source_section"),
            row.get("regulated_entity"),
            row.get("action_required"),
            row.get("plain_english_summary"),
        )
    )
    rule_semantic = Counter(str(row.get("semantic_status")) for row in rule_rows)
    unit_semantic = Counter(str(row.get("semantic_status")) for row in unit_rows)
    rule_status = Counter(str(row.get("status")) for row in rule_rows)
    source_formats = Counter(str(row.get("source_format")) for row in rule_rows)
    semantic_summary_path = root / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_REVIEW_SUMMARY.json"
    semantic_summary = load_json(semantic_summary_path) if semantic_summary_path.exists() else {}
    improvement_path = root / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_IMPROVEMENT_SUMMARY.json"
    improvement_summary = load_json(improvement_path) if improvement_path.exists() else {}
    final_review_path = root / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_FINAL_REVIEW_SUMMARY.json"
    final_review_summary = load_json(final_review_path) if final_review_path.exists() else {}
    automated_review_path = root / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_AUTOMATED_REVIEW_SUMMARY.json"
    automated_review_summary = load_json(automated_review_path) if automated_review_path.exists() else {}
    checks = {
        "schema_valid": not any((authority_schema_errors, rule_schema_errors, unit_schema_errors)),
        "source_files_present": source_path_errors == 0,
        "source_hashes_match": source_hash_errors == 0,
        "relationships_resolve": orphan_rules == 0 and orphan_units == 0,
        "text_readable": bad_rule_text == 0 and unit_bad_text == 0,
        "semantic_interpretation_complete": (
            rule_semantic.get("semantic_ready", 0) == len(rule_rows)
            and unit_semantic.get("semantic_ready", 0) == len(unit_rows)
            and generic_summaries == 0
        ),
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer": "08_County_Authorities",
        "scope": "Active county authority, rule, and atomic rule-unit records.",
        "counts": {
            "authorities": len(authority_rows),
            "rules": len(rule_rows),
            "rule_units": len(unit_rows),
        },
        "schema_errors": {
            "authorities": authority_schema_errors,
            "rules": rule_schema_errors,
            "rule_units": unit_schema_errors,
        },
        "source_integrity": {
            "missing_source_files": source_path_errors,
            "source_hash_mismatches": source_hash_errors,
        },
        "relationship_integrity": {
            "orphan_rules": orphan_rules,
            "orphan_rule_units": orphan_units,
        },
        "readability": {
            "rules_with_encoding_markers": bad_rule_text,
            "rule_units_with_encoding_markers": unit_bad_text,
            "replacement_characters": rule_marker_counts[REPLACEMENT]
            + unit_marker_counts[REPLACEMENT],
            "suspected_mojibake_characters": sum(
                rule_marker_counts[marker] + unit_marker_counts[marker]
                for marker in MOJIBAKE_MARKERS
            ),
            "source_formats": dict(source_formats),
        },
        "semantic_readiness": {
            "rule_statuses": dict(rule_status),
            "rule_semantic_statuses": dict(rule_semantic),
            "unit_semantic_statuses": dict(unit_semantic),
            "generic_rule_summaries": generic_summaries,
            "candidate_review": {
                "candidate_rule_units": int(semantic_summary.get("candidate_rule_units", 0)),
                "promoted": int(semantic_summary.get("promoted", 0)),
                "answer_safe": int(semantic_summary.get("answer_safe", 0)),
                "status": semantic_summary.get("status", "not_run"),
            },
            "improvement": {
                "reviewed_lower_quality": int(
                    improvement_summary.get("reviewed_lower_quality", 0)
                ),
                "improved_candidates": int(improvement_summary.get("improved_candidates", 0)),
                "quality_levels_after": improvement_summary.get("quality_levels_after", {}),
                "status": improvement_summary.get("status", "not_run"),
            },
            "final_review": {
                "reviewed_remaining_candidates": int(
                    final_review_summary.get("reviewed_remaining_candidates", 0)
                ),
                "entity_confirmations_required": int(
                    final_review_summary.get("entity_confirmations_required", 0)
                ),
                "manual_atomic_split_proposals": int(
                    final_review_summary.get("manual_atomic_split_proposals", 0)
                ),
                "exception_captures": int(final_review_summary.get("exception_captures", 0)),
                "status": final_review_summary.get("status", "not_run"),
            },
            "automated_review": {
                "candidates_reviewed": int(automated_review_summary.get("candidates_reviewed", 0)),
                "auto_approved": int(automated_review_summary.get("auto_approved", 0)),
                "auto_quarantined": int(automated_review_summary.get("auto_quarantined", 0)),
                "applied": int(automated_review_summary.get("applied", 0)),
                "status": automated_review_summary.get("status", "not_run"),
            },
            "boundary": (
                "Source-preserved records are traceable and readable, but are not treated as "
                "AI-interpreted legal meaning until grounded semantic review promotes them."
            ),
        },
        "checks": checks,
        "ai_ready": all(checks.values()),
    }
    return report


def run_audit(root: Path) -> Path:
    """Write the county audit report to the control plane."""

    resolved = root.resolve()
    path = resolved / "_CONTROL_PLANE" / "COUNTY_DATA_AUDIT.json"
    atomic_write_json(path, build_audit(resolved), resolved)
    return path


def main() -> None:
    """Run the county data audit from the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(run_audit(args.root))


if __name__ == "__main__":
    main()
