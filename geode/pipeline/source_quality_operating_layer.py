"""Build source quality, repair, relationship, and readiness reports."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import (
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    iter_jsonl,
    load_json,
)

SOURCE_STRENGTH_INDEX = Path(CONTROL_PLANE_DIR) / "SOURCE_STRENGTH_INDEX.jsonl"
SOURCE_STRENGTH_REPORT = Path(CONTROL_PLANE_DIR) / "SOURCE_STRENGTH_REPORT.json"
SOURCE_REPAIR_DASHBOARD = Path(CONTROL_PLANE_DIR) / "SOURCE_REPAIR_DASHBOARD.json"
RELATIONSHIP_ACCURACY_REPORT = Path(CONTROL_PLANE_DIR) / "RELATIONSHIP_ACCURACY_AUDIT.json"
RELATIONSHIP_ACCURACY_ROWS = Path(CONTROL_PLANE_DIR) / "RELATIONSHIP_ACCURACY_AUDIT.jsonl"
GOLDEN_SAMPLE_SET = Path(CONTROL_PLANE_DIR) / "GOLDEN_SAMPLE_REVIEW_SET.jsonl"
GOLDEN_SAMPLE_REPORT = Path(CONTROL_PLANE_DIR) / "GOLDEN_SAMPLE_REVIEW_SET_REPORT.json"
FRESHNESS_VERIFICATION_QUEUE = Path(CONTROL_PLANE_DIR) / "FRESHNESS_VERIFICATION_QUEUE.json"
HUMAN_REVIEW_WORKFLOW = Path(CONTROL_PLANE_DIR) / "HUMAN_REVIEW_WORKFLOW_REPORT.json"
MASTER_READINESS_REPORT = Path(CONTROL_PLANE_DIR) / "MASTER_READINESS_REPORT.json"
DOCS_REPORT = Path("docs") / "audits" / "SOURCE_QUALITY_IMPROVEMENT_REPORT_2026-07-02.md"

CROSSWALK_FILES = (
    "regulation_to_statute.jsonl",
    "statute_to_regulation.jsonl",
    "bill_to_statute.jsonl",
    "rulemaking_to_regulation.jsonl",
    "agency_to_statute.jsonl",
    "amendment_history.jsonl",
)

GOLDEN_SAMPLE_TARGETS = {
    "01_Statutes_CRS": 25,
    "02_Regulations_CCR": 25,
    "03_Legislation": 25,
    "04_Rulemaking": 25,
    "05_Executive_Orders": 10,
    "06_Session_Laws": 10,
    "07_Supplementary": 10,
}


def build_source_quality_operating_layer(root: Path) -> dict[str, Any]:
    """Write the source quality operating layer and return its master report."""

    resolved = root.resolve()
    generated_at = datetime.now(timezone.utc).isoformat()
    indexes = _load_layer_indexes(resolved)
    source_accuracy = _load_source_accuracy(resolved)
    strength_rows, strength_report = _build_source_strength(generated_at, indexes, source_accuracy)
    relationship_rows, relationship_report = _build_relationship_accuracy(generated_at, resolved, indexes)
    golden_rows, golden_report = _build_golden_samples(generated_at, indexes, source_accuracy)
    freshness_queue = _build_freshness_queue(generated_at, resolved)
    review_workflow = _build_human_review_workflow(generated_at, resolved, golden_report)
    repair_dashboard = _build_repair_dashboard(
        generated_at,
        resolved,
        source_accuracy,
        relationship_report,
        freshness_queue,
        review_workflow,
    )
    master = _build_master_readiness(
        generated_at,
        strength_report,
        repair_dashboard,
        relationship_report,
        golden_report,
        freshness_queue,
        review_workflow,
    )

    atomic_write_jsonl(resolved / SOURCE_STRENGTH_INDEX, strength_rows, resolved)
    atomic_write_json(resolved / SOURCE_STRENGTH_REPORT, strength_report, resolved)
    atomic_write_json(resolved / SOURCE_REPAIR_DASHBOARD, repair_dashboard, resolved)
    atomic_write_jsonl(resolved / RELATIONSHIP_ACCURACY_ROWS, relationship_rows, resolved)
    atomic_write_json(resolved / RELATIONSHIP_ACCURACY_REPORT, relationship_report, resolved)
    atomic_write_jsonl(resolved / GOLDEN_SAMPLE_SET, golden_rows, resolved)
    atomic_write_json(resolved / GOLDEN_SAMPLE_REPORT, golden_report, resolved)
    atomic_write_json(resolved / FRESHNESS_VERIFICATION_QUEUE, freshness_queue, resolved)
    atomic_write_json(resolved / HUMAN_REVIEW_WORKFLOW, review_workflow, resolved)
    atomic_write_json(resolved / MASTER_READINESS_REPORT, master, resolved)
    _write_docs_report(resolved, master, strength_report, repair_dashboard, relationship_report, freshness_queue)
    return master


def _load_layer_indexes(root: Path) -> dict[str, list[dict[str, Any]]]:
    manifest = _load_dict(root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    indexes: dict[str, list[dict[str, Any]]] = {}
    for layer in manifest.get("data_layers", []):
        if not isinstance(layer, dict):
            continue
        layer_id = str(layer.get("id") or "")
        index_file = str(layer.get("index_file") or "")
        if not layer_id or not index_file:
            continue
        path = root / index_file
        indexes[layer_id] = list(iter_jsonl(path)) if path.exists() else []
    return indexes


def _load_source_accuracy(root: Path) -> dict[str, dict[str, Any]]:
    path = root / CONTROL_PLANE_DIR / "SOURCE_TO_OUTPUT_ACCURACY_RECORDS.jsonl"
    if not path.exists():
        return {}
    return {str(row.get("record_id")): row for row in iter_jsonl(path)}


def _build_source_strength(
    generated_at: str,
    indexes: dict[str, list[dict[str, Any]]],
    accuracy: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    layer_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for layer, index_rows in indexes.items():
        for row in index_rows:
            record_id = str(row.get("id") or "")
            audit = accuracy.get(record_id, {})
            level, score, label = _source_strength_level(row, audit)
            rows.append(
                {
                    "id": record_id,
                    "layer": layer,
                    "citation": row.get("citation"),
                    "source_strength_level": level,
                    "source_strength_score": score,
                    "confidence": row.get("confidence"),
                    "source_url": row.get("source_url"),
                    "source_path": row.get("source_path"),
                    "reliance_label": label,
                    "accuracy_level": audit.get("accuracy_level"),
                    "generated_at": generated_at,
                }
            )
            layer_counts[layer][level] += 1
    total = len(rows)
    score_sum = sum(float(row["source_strength_score"]) for row in rows)
    summary_counts = Counter(row["source_strength_level"] for row in rows)
    report = {
        "generated_at": generated_at,
        "records_scored": total,
        "average_source_strength_score": round(score_sum / total, 4) if total else 0.0,
        "level_counts": dict(sorted(summary_counts.items())),
        "layer_counts": {layer: dict(sorted(counts.items())) for layer, counts in sorted(layer_counts.items())},
        "index_path": SOURCE_STRENGTH_INDEX.as_posix(),
        "boundary": "Source strength measures local evidence depth, not legal correctness or official freshness.",
    }
    return rows, report


def _source_strength_level(row: dict[str, Any], audit: dict[str, Any]) -> tuple[str, float, str]:
    accuracy = str(audit.get("accuracy_level") or "unknown")
    source_path = str(audit.get("source_path") or row.get("source_path") or "")
    source_url = str(row.get("source_url") or "")
    raw_source = _is_raw_archive_path(source_path)
    if accuracy == "high" and raw_source:
        return "direct_full_text_source", 1.0, "source-backed"
    if accuracy == "medium" and raw_source and source_url:
        return "official_listing_plus_document", 0.82, "source-backed-needs-review"
    if accuracy == "medium":
        return "official_listing_only", 0.68, "review-before-reliance"
    if accuracy == "low":
        return "source_weak", 0.35, "repair-before-reliance"
    if accuracy == "not_independent":
        return "structured_output_only", 0.2, "do-not-rely-externally"
    return "source_missing_or_unknown", 0.0, "do-not-rely-externally"


def _is_raw_archive_path(source_path: str) -> bool:
    normalized = source_path.replace("\\", "/")
    return "/_RAW_ARCHIVE/" in normalized or normalized.startswith("_RAW_ARCHIVE/")


def _build_relationship_accuracy(
    generated_at: str,
    root: Path,
    indexes: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    known_ids = {row.get("id") for rows in indexes.values() for row in rows if row.get("id")}
    known_ids.update(_agency_ids(root))
    rows: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    for file_name in CROSSWALK_FILES:
        path = root / "_CROSSWALKS" / file_name
        total = endpoints = evidence = high = source_known = target_known = 0
        if path.exists():
            for line_number, row in enumerate(iter_jsonl(path), start=1):
                source_id = _first_text(row, "source_id", "bill_id", "event_id")
                target_id = _first_text(row, "target_id", "statute_id") or _first_list_text(row.get("target_ids"))
                confidence = float(row.get("confidence") or 0)
                has_evidence = bool(str(row.get("source_evidence") or "").strip())
                source_ok = bool(source_id and source_id in known_ids)
                target_ok = bool(target_id and target_id in known_ids)
                endpoint_ok = bool(source_id and target_id)
                if endpoint_ok:
                    endpoints += 1
                if has_evidence:
                    evidence += 1
                if confidence >= 0.8:
                    high += 1
                if source_ok:
                    source_known += 1
                if target_ok:
                    target_known += 1
                total += 1
                rows.append(
                    {
                        "relationship_id": f"{Path(file_name).stem}:{line_number:06d}",
                        "crosswalk_file": file_name,
                        "source_id": source_id,
                        "target_id": target_id,
                        "relationship": row.get("relationship") or row.get("event_type"),
                        "endpoint_present": endpoint_ok,
                        "source_known": source_ok,
                        "target_known": target_ok,
                        "has_source_evidence": has_evidence,
                        "confidence": confidence,
                        "accuracy_status": "strong" if endpoint_ok and has_evidence and confidence >= 0.8 else "review",
                    }
                )
        file_summaries.append(
            {
                "crosswalk_file": file_name,
                "rows_checked": total,
                "endpoint_coverage": _ratio(endpoints, total),
                "evidence_coverage": _ratio(evidence, total),
                "high_confidence_ratio": _ratio(high, total),
                "known_source_ratio": _ratio(source_known, total),
                "known_target_ratio": _ratio(target_known, total),
                "review_rows": total - min(endpoints, evidence, high),
            }
        )
    strong = sum(1 for row in rows if row["accuracy_status"] == "strong")
    report = {
        "generated_at": generated_at,
        "relationships_checked": len(rows),
        "strong_relationships": strong,
        "review_relationships": len(rows) - strong,
        "file_summaries": file_summaries,
        "rows_path": RELATIONSHIP_ACCURACY_ROWS.as_posix(),
        "boundary": "Relationship accuracy verifies endpoints, evidence, and confidence. It does not interpret legal effect.",
    }
    return rows, report


def _agency_ids(root: Path) -> set[str]:
    registry = _load_dict(root / CONTROL_PLANE_DIR / "AGENCY_REGISTRY.json")
    ids: set[str] = set()
    for item in registry.get("agencies", []):
        if isinstance(item, dict):
            for key in ("id", "agency_id", "code"):
                if item.get(key):
                    ids.add(str(item[key]))
    return ids


def _build_golden_samples(
    generated_at: str,
    indexes: dict[str, list[dict[str, Any]]],
    accuracy: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layer, target in GOLDEN_SAMPLE_TARGETS.items():
        candidates = sorted(
            indexes.get(layer, []),
            key=lambda row: (
                0 if accuracy.get(str(row.get("id")), {}).get("accuracy_level") == "high" else 1,
                str(row.get("id") or ""),
            ),
        )
        if not candidates:
            continue
        step = max(1, len(candidates) // target)
        selected = candidates[::step][:target]
        for row in selected:
            record_id = str(row.get("id") or "")
            rows.append(
                {
                    "sample_id": f"GS-{len(rows)+1:04d}",
                    "record_id": record_id,
                    "layer": layer,
                    "citation": row.get("citation"),
                    "title": row.get("title"),
                    "source_path": row.get("source_path"),
                    "source_url": row.get("source_url"),
                    "accuracy_level": accuracy.get(record_id, {}).get("accuracy_level"),
                    "review_status": "queued",
                    "review_goal": "Manual benchmark review for future regression checks.",
                    "generated_at": generated_at,
                }
            )
    report = {
        "generated_at": generated_at,
        "samples_written": len(rows),
        "target_counts": GOLDEN_SAMPLE_TARGETS,
        "sample_path": GOLDEN_SAMPLE_SET.as_posix(),
        "boundary": "Golden samples are queued for human benchmark review and are not certified yet.",
    }
    return rows, report


def _build_freshness_queue(generated_at: str, root: Path) -> dict[str, Any]:
    report = _load_dict(root / CONTROL_PLANE_DIR / "SOURCE_FRESHNESS_REPORT.json")
    items: list[dict[str, Any]] = []
    refreshed_sources: list[str] = []
    generated_date = generated_at[:10]
    official_sources = {
        "01_Statutes_CRS": "Confirm current OLLS CRS publication year and archive date.",
        "02_Regulations_CCR": "Run SOS CCR current-rule refresh and compare inventory hashes.",
        "03_Legislation": "Run LegiScan/current General Assembly refresh window.",
        "04_Rulemaking": "Run Secretary of State Register/eDocket refresh.",
        "05_Executive_Orders": "Replace EO-2019-007 bad artifact and refresh Governor EO index.",
        "06_Session_Laws": "Confirm session law chapter list and download full chapter artifacts where available.",
        "07_Supplementary": "Refresh AG opinions and COPRRR source pages.",
    }
    for layer in report.get("layers", []):
        if not isinstance(layer, dict):
            continue
        layer_id = str(layer.get("layer_id") or "unknown")
        refresh_completed = _official_refresh_completed(root, layer_id, generated_date)
        if refresh_completed:
            refreshed_sources.append(layer_id)
        items.append(
            {
                "layer_id": layer_id,
                "local_freshness_status": layer.get("freshness_status", "unknown"),
                "last_checked": layer.get("last_checked"),
                "network_refresh_required": not refresh_completed,
                "official_refresh_action": (
                    _completed_refresh_action(layer_id)
                    if refresh_completed
                    else official_sources.get(layer_id, "Run official source refresh.")
                ),
            }
        )
    return {
        "generated_at": generated_at,
        "network_refresh_performed": bool(refreshed_sources),
        "refreshed_sources": refreshed_sources,
        "items": items,
        "pending_items": sum(1 for item in items if item["network_refresh_required"]),
        "boundary": "This queue defines required official freshness checks. It does not claim live freshness.",
    }


def _completed_refresh_action(layer_id: str) -> str:
    actions = {
        "01_Statutes_CRS": "Completed official OLLS CRS publication confirmation and archived SGML rebuild for this run.",
        "02_Regulations_CCR": "Completed official Secretary of State CCR refresh for this run.",
        "04_Rulemaking": "Completed official Secretary of State Register/eDocket refresh for this run.",
        "06_Session_Laws": "Completed official Colorado General Assembly session-law PDF refresh for this run.",
        "07_Supplementary": "Completed official AG opinions and COPRRR supplementary refresh for this run.",
    }
    return actions.get(layer_id, "Completed official source refresh for this run.")


def _official_refresh_completed(root: Path, layer_id: str, generated_date: str) -> bool:
    if layer_id == "01_Statutes_CRS":
        return _crs_refresh_completed(root, generated_date)
    if layer_id == "02_Regulations_CCR":
        return _ccr_refresh_completed(root, generated_date)
    if layer_id == "04_Rulemaking":
        summary = _load_dict(root / "04_Rulemaking" / "_dataset" / "rulemaking_summary.json")
        summary_date = str(summary.get("generated_at") or "")[:10]
        return summary_date == generated_date and summary.get("source_publications_total", 0) > 0
    if layer_id == "06_Session_Laws":
        return _session_law_pdf_refresh_completed(root, generated_date)
    if layer_id == "07_Supplementary":
        return _supplementary_refresh_completed(root, generated_date)
    return False


def _crs_refresh_completed(root: Path, generated_date: str) -> bool:
    summary = _load_dict(root / "01_Statutes_CRS" / "_meta" / "crs_bulk_summary.json")
    confirmation = _load_dict(root / CONTROL_PLANE_DIR / "CRS_OFFICIAL_REFRESH_CONFIRMATION.json")
    layer = _layer_from_manifest(root, "01_Statutes_CRS")
    return (
        str(summary.get("generated_at") or "")[:10] == generated_date
        and str(confirmation.get("generated_at") or "")[:10] == generated_date
        and str(layer.get("last_checked") or "") == generated_date
        and summary.get("failed_files", 1) == 0
        and summary.get("parsed_titles", 0) > 0
        and summary.get("sections_written", 0) > 0
        and confirmation.get("status") == "confirmed_current_publication"
    )


def _ccr_refresh_completed(root: Path, generated_date: str) -> bool:
    summary = _load_dict(root / "_RAW_ARCHIVE" / "ccr" / "ccr_bulk_summary.json")
    completed_date = str(summary.get("completed_at") or "")[:10]
    return (
        completed_date == generated_date
        and summary.get("status") == "completed"
        and summary.get("traversal_validation_status") == "uncapped_discovery_completed"
        and summary.get("field_population_status") == "critical_fields_populated"
        and summary.get("failed", 1) == 0
        and summary.get("blocked", 1) == 0
        and summary.get("normalized_records_total", 0) > 0
    )


def _session_law_pdf_refresh_completed(root: Path, generated_date: str) -> bool:
    summary = _load_dict(root / "06_Session_Laws" / "_meta" / "session_laws_summary.json")
    if summary.get("record_count", 0) == 0:
        return False
    if summary.get("downloaded") != summary.get("record_count"):
        return False
    session_layer = _layer_from_manifest(root, "06_Session_Laws")
    return str(session_layer.get("last_checked") or "") == generated_date


def _layer_from_manifest(root: Path, layer_id: str) -> dict[str, Any]:
    manifest = _load_dict(root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json")
    for layer in manifest.get("data_layers", []):
        if isinstance(layer, dict) and layer.get("id") == layer_id:
            return layer
    return {}


def _supplementary_refresh_completed(root: Path, generated_date: str) -> bool:
    layer = _layer_from_manifest(root, "07_Supplementary")
    if str(layer.get("last_checked") or "") != generated_date:
        return False
    ag = _load_dict(root / "07_Supplementary" / "_meta" / "ag_opinions_summary.json")
    coprrr = _load_dict(root / "07_Supplementary" / "_meta" / "coprrr_reviews_summary.json")
    return (
        ag.get("downloaded", 0) > 0
        and ag.get("failed", 1) == 0
        and coprrr.get("downloaded", 0) > 0
        and coprrr.get("failed", 1) == 0
    )


def _build_human_review_workflow(
    generated_at: str,
    root: Path,
    golden_report: dict[str, Any],
) -> dict[str, Any]:
    assignments = _load_dict(root / CONTROL_PLANE_DIR / "REVIEWER_ASSIGNMENTS.json")
    roles = assignments.get("assignments", []) if isinstance(assignments.get("assignments"), list) else []
    unassigned = [role for role in roles if isinstance(role, dict) and role.get("assignment_status") != "assigned"]
    return {
        "generated_at": generated_at,
        "required_roles": len(roles),
        "unassigned_roles": len(unassigned),
        "golden_samples_queued": golden_report.get("samples_written", 0),
        "review_packet_queue": "02_Regulations_CCR/_meta/rule_units_review_queue.jsonl",
        "decision_log": "02_Regulations_CCR/_meta/rule_units_review_decisions.jsonl",
        "workflow_steps": [
            "Assign named reviewers with effective dates and reliance-policy references.",
            "Review golden samples first to establish benchmark expectations.",
            "Review rule-unit packets and log approve, revise, split, or quarantine decisions.",
            "Apply canonical changes only after validation and snapshot controls pass.",
            "Require legal reviewer approval before external reliance.",
        ],
        "ready_for_reliance": len(unassigned) == 0,
        "boundary": "The workflow is operationally prepared, but real people must be assigned before reliance review is complete.",
    }


def _build_repair_dashboard(
    generated_at: str,
    root: Path,
    accuracy: dict[str, dict[str, Any]],
    relationship_report: dict[str, Any],
    freshness_queue: dict[str, Any],
    review_workflow: dict[str, Any],
) -> dict[str, Any]:
    weak_sources = [
        row for row in accuracy.values()
        if row.get("accuracy_level") in {"low", "metadata_only", "not_independent"}
    ]
    items = [
        {
            "id": "CCR-5_CCR_1002-83",
            "category": "source_depth",
            "status": "closed_by_supporting_inventory" if not weak_sources else "queued",
            "title": "CCR repealed PDF metadata support",
            "next_action": "Keep CCR inventory support in the source-output audit.",
        },
        {
            "id": "EO-2019-007",
            "category": "bad_raw_artifact",
            "status": _eo_2019_007_status(root),
            "title": "Replace bad Executive Order raw artifact",
            "next_action": (
                "Official public download still returns a Google Drive sign-in page; "
                "request a valid copy from the Governor's Office or State Archives."
            ),
        },
        {
            "id": "RULEMAKING-MEDIUM-EVIDENCE",
            "category": "source_depth",
            "status": "queued",
            "title": "Upgrade medium rulemaking evidence",
            "next_action": "Attach eDocket detail pages and supporting documents where available.",
        },
        {
            "id": "SESSION-LAW-FULL-TEXT",
            "category": "source_depth",
            "status": (
                "closed_by_pdf_archive"
                if _session_law_pdf_refresh_completed(root, generated_at[:10])
                else "queued"
            ),
            "title": "Upgrade session law chapter evidence",
            "next_action": (
                "Keep chapter PDFs as the source anchor for session-law records."
                if _session_law_pdf_refresh_completed(root, generated_at[:10])
                else "Preserve full chapter artifacts per session law."
            ),
        },
    ]
    return {
        "generated_at": generated_at,
        "open_items": sum(1 for item in items if not str(item["status"]).startswith("closed")),
        "items": items,
        "relationship_review_rows": relationship_report.get("review_relationships", 0),
        "freshness_refresh_items": freshness_queue.get("pending_items", 0),
        "human_review_ready_for_reliance": review_workflow.get("ready_for_reliance", False),
        "boundary": "This dashboard tracks data-quality operations. It is not a legal approval queue.",
    }


def _eo_2019_007_status(root: Path) -> str:
    recovery = root / "_QUARANTINE" / "eo_recovery" / "EO-2019-007.downloaded.pdf"
    if recovery.exists():
        return "blocked_official_link_returns_sign_in"
    return "blocked_external_source"


def _build_master_readiness(
    generated_at: str,
    strength_report: dict[str, Any],
    repair_dashboard: dict[str, Any],
    relationship_report: dict[str, Any],
    golden_report: dict[str, Any],
    freshness_queue: dict[str, Any],
    review_workflow: dict[str, Any],
) -> dict[str, Any]:
    blockers = []
    if repair_dashboard.get("open_items", 0):
        blockers.append("source_repair_items_open")
    if not review_workflow.get("ready_for_reliance"):
        blockers.append("named_reviewer_assignments_missing")
    if freshness_queue.get("pending_items", 0):
        blockers.append("live_official_freshness_not_verified")
    return {
        "generated_at": generated_at,
        "local_system_usable": True,
        "external_reliance_ready": False,
        "blockers": blockers,
        "source_strength": {
            "records_scored": strength_report.get("records_scored", 0),
            "average_score": strength_report.get("average_source_strength_score", 0),
            "level_counts": strength_report.get("level_counts", {}),
        },
        "relationships": {
            "relationships_checked": relationship_report.get("relationships_checked", 0),
            "strong_relationships": relationship_report.get("strong_relationships", 0),
            "review_relationships": relationship_report.get("review_relationships", 0),
        },
        "golden_samples": golden_report,
        "freshness": {
            "network_refresh_performed": freshness_queue.get("network_refresh_performed", False),
            "items": freshness_queue.get("pending_items", 0),
        },
        "human_review": {
            "required_roles": review_workflow.get("required_roles", 0),
            "unassigned_roles": review_workflow.get("unassigned_roles", 0),
        },
        "boundary": "Local usability is not external reliance readiness. Live freshness and named reviewer approval remain required.",
    }


def _write_docs_report(
    root: Path,
    master: dict[str, Any],
    strength: dict[str, Any],
    repair: dict[str, Any],
    relationships: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    lines = [
        "# Source Quality Improvement Report",
        "",
        f"Generated: {master['generated_at']}",
        "",
        f"- Source-strength records scored: {strength['records_scored']:,}",
        f"- Average source-strength score: {strength['average_source_strength_score']}",
        f"- Source repair open items: {repair['open_items']:,}",
        f"- Relationships checked: {relationships['relationships_checked']:,}",
        f"- Strong relationships: {relationships['strong_relationships']:,}",
        f"- Relationship rows needing review: {relationships['review_relationships']:,}",
        f"- Official freshness refresh items: {len(freshness['items']):,}",
        f"- External reliance ready: {master['external_reliance_ready']}",
        "",
        "## Source Strength Levels",
        "",
    ]
    for level, count in strength["level_counts"].items():
        lines.append(f"- `{level}`: {count:,}")
    lines.extend(["", "## Repair Dashboard", ""])
    for item in repair["items"]:
        lines.append(f"- `{item['id']}` ({item['status']}): {item['next_action']}")
    lines.extend(["", "## Boundary", "", master["boundary"], ""])
    atomic_write_text(root / DOCS_REPORT, "\n".join(lines), root)


def _load_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _first_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            return str(value)
    return None


def _first_list_text(value: object) -> str | None:
    if isinstance(value, list):
        for item in value:
            if item:
                return str(item)
    return None


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def main() -> None:
    """Build source quality operating artifacts."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_source_quality_operating_layer(Path(args.root))
    if args.json:
        print(json.dumps(report, indent=2))
        return
    print(f"Source records scored: {report['source_strength']['records_scored']}")
    print(f"Source repair open items: {len(report['blockers'])}")


if __name__ == "__main__":
    main()
