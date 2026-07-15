"""Build review, OCR, recovery, and metadata-control queues for local authority data."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl, load_json


QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "LOCAL_REVIEW_QUEUE.jsonl"
OCR_QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "LOCAL_OCR_QUEUE.jsonl"
CLASSIFICATION_QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "LOCAL_SOURCE_CLASSIFICATION_QUEUE.jsonl"
METADATA_AUDIT_PATH = Path(CONTROL_PLANE_DIR) / "LOCAL_METADATA_VERSION_AUDIT.json"
SUMMARY_PATH = Path(CONTROL_PLANE_DIR) / "LOCAL_REVIEW_SUMMARY.json"
PROMOTION_QUEUE_PATH = Path(CONTROL_PLANE_DIR) / "LOCAL_PROMOTION_QUEUE.jsonl"


class LocalReviewSummary(BaseModel):
    """Counts and boundaries for the local review control plane."""

    generated_at: datetime
    semantic_review_items: int = Field(ge=0)
    ocr_items: int = Field(ge=0)
    source_classification_items: int = Field(ge=0)
    downloaded_source_review_items: int = Field(ge=0)
    blocked_source_recovery_items: int = Field(ge=0)
    metadata_version_items: int = Field(ge=0)
    total_review_items: int = Field(ge=0)
    answer_safe_local_rule_units: int = Field(ge=0)
    boundary: str


def build_local_review_queues(root: Path, today: date | None = None) -> LocalReviewSummary:
    """Build all remaining local review queues without modifying raw sources."""

    resolved = root.resolve()
    del today  # Reserved for future age-based priority scoring.
    generated_at = datetime.now(timezone.utc)
    review_rows: list[dict[str, Any]] = []
    ocr_rows: list[dict[str, Any]] = []
    classification_rows: list[dict[str, Any]] = []

    quarantine_file = resolved / "_QUARANTINE" / "local_extraction_quarantine.jsonl"
    quarantine_rows = iter_jsonl(quarantine_file) if quarantine_file.exists() else []
    for row in quarantine_rows:
        common = _source_fields(row)
        reason = str(row.get("reason") or "")
        if "OCR" in reason:
            item = {"review_type": "ocr", **common, "reason": reason, "status": "pending"}
            ocr_rows.append(item)
            review_rows.append(item)
        elif row.get("source_category") == "unclassified_local_source":
            item = {
                "review_type": "source_classification",
                **common,
                "reason": reason,
                "status": "pending",
                "suggested_category": _suggest_category(str(row.get("source_path") or "")),
            }
            classification_rows.append(item)
            review_rows.append(item)
        else:
            review_rows.append(
                {
                    "review_type": "quarantine_review",
                    **common,
                    "reason": reason,
                    "status": "pending",
                }
            )

    index_rows: list[dict[str, Any]] = []
    for layer in ("08_County_Authorities", "09_District_Authorities"):
        index_file = resolved / layer / "_index.jsonl"
        if index_file.exists():
            index_rows.extend(iter_jsonl(index_file))
    semantic_items = 0
    answer_safe_units = 0
    for row in index_rows:
        if row.get("entity_type") != "rule_unit":
            continue
        status = str(row.get("semantic_status") or "semantic_ready")
        if status == "semantic_ready":
            answer_safe_units += 1
            continue
        semantic_items += 1
        review_rows.append(
            {
                "review_type": "semantic_rule_unit",
                "status": "pending",
                "rule_unit_id": row.get("id"),
                "parent_source_path": row.get("source_path"),
                "authority_id": row.get("authority_id"),
                "authority_level": row.get("authority_level"),
                "source_category": row.get("source_category"),
                "source_section": row.get("source_section"),
                "source_page": row.get("source_page"),
                "source_page_end": row.get("source_page_end"),
                "source_hash": row.get("sha256"),
                "reason": "Semantic extraction and legal-quality review are pending.",
            }
        )

    coverage = _load_dict(resolved / CONTROL_PLANE_DIR / "COUNTY_SOURCE_COVERAGE.json")
    downloaded_review_items = 0
    blocked_items = 0
    for county in coverage.get("counties", []):
        if not isinstance(county, dict):
            continue
        for category, cell in county.get("source_categories", {}).items():
            if not isinstance(cell, dict):
                continue
            status = str(cell.get("status") or "")
            item = {
                "authority_id": county.get("county_id"),
                "county_name": county.get("county_name"),
                "category": category,
                "source_ids": cell.get("source_ids", []),
                "status": "pending",
                "reason": cell.get("notes") or status,
            }
            if status == "downloaded_unreviewed":
                item["review_type"] = "downloaded_source_review"
                review_rows.append(item)
                downloaded_review_items += 1
            elif status == "blocked":
                item["review_type"] = "blocked_source_recovery"
                review_rows.append(item)
                blocked_items += 1

    metadata_audit = _metadata_version_audit(resolved, index_rows)
    for item in metadata_audit["unreferenced_versioned_files"]:
        review_rows.append({"review_type": "metadata_version", "status": "pending", **item})

    atomic_write_jsonl(resolved / QUEUE_PATH, review_rows, resolved)
    atomic_write_jsonl(resolved / OCR_QUEUE_PATH, ocr_rows, resolved)
    atomic_write_jsonl(resolved / CLASSIFICATION_QUEUE_PATH, classification_rows, resolved)
    atomic_write_json(resolved / METADATA_AUDIT_PATH, metadata_audit, resolved)
    summary = LocalReviewSummary(
        generated_at=generated_at,
        semantic_review_items=semantic_items,
        ocr_items=len(ocr_rows),
        source_classification_items=len(classification_rows),
        downloaded_source_review_items=downloaded_review_items,
        blocked_source_recovery_items=blocked_items,
        metadata_version_items=len(metadata_audit["unreferenced_versioned_files"]),
        total_review_items=len(review_rows),
        answer_safe_local_rule_units=answer_safe_units,
        boundary=(
            "These queues identify work that remains. They do not approve legal meaning, perform OCR, "
            "delete versioned files, or claim that blocked categories have no law."
        ),
    )
    atomic_write_json(resolved / SUMMARY_PATH, summary, resolved)
    _write_promotion_queue_if_available(resolved, index_rows)
    return summary


def _write_promotion_queue_if_available(root: Path, index_rows: list[dict[str, Any]]) -> None:
    """Keep the semantic review queue connected to the promotion control plane."""

    from geode.pipeline.local_promotion import build_local_promotion_queue

    del index_rows
    build_local_promotion_queue(root)


def _source_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Keep review records tied to their preserved source."""

    return {
        "source_id": row.get("source_id"),
        "authority_id": row.get("authority_id"),
        "authority_level": row.get("authority_level"),
        "source_category": row.get("source_category"),
        "source_path": row.get("source_path"),
        "requested_url": row.get("requested_url"),
        "source_hash": row.get("source_hash"),
    }


def _metadata_version_audit(root: Path, index_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Identify generated versioned metadata files that are not active in an index."""

    referenced = {
        str(row.get("meta_path"))
        for row in index_rows
        if row.get("meta_path")
    }
    versioned: list[dict[str, Any]] = []
    for layer in ("08_County_Authorities", "09_District_Authorities"):
        meta_root = root / layer / "_meta"
        if not meta_root.exists():
            continue
        for path in sorted(meta_root.glob("*_20*.jsonl")):
            relative = path.relative_to(root).as_posix()
            if relative not in referenced:
                versioned.append(
                    {
                        "path": relative,
                        "size_bytes": path.stat().st_size,
                        "reason": "Generated version is not referenced by the active index.",
                    }
                )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "unreferenced_versioned_files": versioned,
        "deletion_allowed": False,
        "boundary": "This is a review list only; no metadata file is deleted automatically.",
    }


def _load_dict(path: Path) -> dict[str, Any]:
    """Load a JSON object or return an empty object."""

    if not path.exists():
        return {}
    value = load_json(path)
    return value if isinstance(value, dict) else {}


def _suggest_category(source_path: str) -> str | None:
    """Suggest a category only when the preserved path contains a strong signal."""

    compact = "".join(character for character in source_path.casefold() if character.isalnum())
    suggestions = (
        ("firerestriction", "emergency_fire_restrictions"),
        ("openburn", "environmental_open_burning"),
        ("rightofway", "roads_transportation_access"),
        ("transportation", "roads_transportation_access"),
        ("zoning", "land_use_zoning"),
        ("landuse", "land_use_zoning"),
        ("subdivision", "subdivision_development"),
        ("building", "building_construction"),
        ("ordinance", "county_ordinances"),
        ("resolution", "continuing_resolutions"),
        ("animalcontrol", "animal_control_nuisance"),
    )
    for token, category in suggestions:
        if token in compact:
            return category
    return None


def main() -> int:
    """Run the local review queue builder."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(build_local_review_queues(args.root.resolve()).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
