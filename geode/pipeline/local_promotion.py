"""Controlled promotion of preserved local sources into AI-answer evidence."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from geode.pipeline.retrieval_catalog import write_retrieval_catalog
from geode.schemas import RuleUnit
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl


CONTROL = Path("_CONTROL_PLANE")
QUEUE_PATH = CONTROL / "LOCAL_PROMOTION_QUEUE.jsonl"
DECISIONS_PATH = CONTROL / "LOCAL_PROMOTION_DECISIONS.jsonl"
REPORT_PATH = CONTROL / "LOCAL_PROMOTION_REPORT.json"


class PromotionDecision(BaseModel):
    """Reviewer-submitted semantic decision for one local rule unit."""

    rule_unit_id: str = Field(min_length=1)
    decision: Literal["approve", "reject", "needs_revision"]
    reviewer: str = Field(min_length=1)
    reviewed_at: datetime
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_section: str = Field(min_length=1)
    source_page: int | None = Field(default=None, ge=1)
    source_page_end: int | None = Field(default=None, ge=1)
    source_line_start: int | None = Field(default=None, ge=1)
    source_line_end: int | None = Field(default=None, ge=1)
    rule_type: str = Field(min_length=1)
    regulated_entity: str = Field(min_length=1)
    action_required: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    enabling_statute: list[str] = Field(default_factory=list)
    temporal: str | None = None
    penalties: list[str] = Field(default_factory=list)
    plain_english_summary: str = Field(min_length=1)
    subject_tags: list[str] = Field(default_factory=list)
    notes: str = ""


def build_local_promotion_queue(root: Path) -> dict[str, int]:
    """Create reviewer packets for preserved local rule units."""

    resolved = root.resolve()
    rows: list[dict[str, Any]] = []
    for layer in ("08_County_Authorities", "09_District_Authorities"):
        index_path = resolved / layer / "_index.jsonl"
        if not index_path.exists():
            continue
        for row in iter_jsonl(index_path):
            if row.get("entity_type") != "rule_unit":
                continue
            if row.get("semantic_status") == "semantic_ready":
                continue
            rows.append(
                {
                    "rule_unit_id": row.get("id"),
                    "parent_rule_id": str(row.get("id", "")).rsplit("-UNIT-", 1)[0],
                    "authority_id": row.get("authority_id"),
                    "authority_level": row.get("authority_level"),
                    "authority_name": row.get("authority_name"),
                    "county_names": row.get("county_names", []),
                    "district_family": row.get("district_family"),
                    "source_category": row.get("source_category"),
                    "source_path": row.get("source_path"),
                    "source_hash": row.get("sha256"),
                    "source_section": row.get("source_section"),
                    "source_page": row.get("source_page"),
                    "source_page_end": row.get("source_page_end"),
                    "source_line_start": row.get("source_line_start"),
                    "source_line_end": row.get("source_line_end"),
                    "current_status": row.get("semantic_status") or "source_preservation_only",
                    "required_review": [
                        "confirm source is an adopted legal or administrative rule",
                        "rewrite one atomic obligation, permission, or prohibition",
                        "identify regulated entity, conditions, and exceptions",
                        "confirm geography and current version",
                        "preserve exact section and passage location",
                    ],
                }
            )
    atomic_write_jsonl(resolved / QUEUE_PATH, rows, resolved)
    return {"queued": len(rows), "answer_safe": 0}


def apply_local_promotion_decisions(root: Path) -> dict[str, Any]:
    """Apply only validated reviewer decisions and rebuild derived retrieval data."""

    resolved = root.resolve()
    decisions_path = resolved / DECISIONS_PATH
    decisions: list[PromotionDecision] = []
    errors: list[dict[str, str]] = []
    if decisions_path.exists():
        for line_number, row in enumerate(iter_jsonl(decisions_path), start=1):
            try:
                decisions.append(PromotionDecision.model_validate(row))
            except ValidationError as exc:
                errors.append({"line": str(line_number), "error": str(exc)})

    indexes: dict[str, dict[str, Any]] = {}
    for layer in ("08_County_Authorities", "09_District_Authorities"):
        index_path = resolved / layer / "_index.jsonl"
        if index_path.exists():
            for row in iter_jsonl(index_path):
                if row.get("entity_type") == "rule_unit":
                    indexes[str(row.get("id"))] = row

    decisions_by_id = {item.rule_unit_id: item for item in decisions}
    metadata_files = {
        "08_County_Authorities": resolved / "08_County_Authorities" / "_meta" / "local_rule_units.jsonl",
        "09_District_Authorities": resolved / "09_District_Authorities" / "_meta" / "local_rule_units.jsonl",
    }
    promoted: set[str] = set()
    rejected = 0
    needs_revision = 0
    snapshots: list[str] = []

    for layer, metadata_path in metadata_files.items():
        if not metadata_path.exists():
            continue
        records = list(iter_jsonl(metadata_path))
        changed = False
        for record in records:
            record_id = str(record.get("id") or "")
            decision = decisions_by_id.get(record_id)
            if decision is None:
                continue
            index_row = indexes.get(record_id)
            reason = _promotion_blocker(record, index_row, decision)
            if decision.decision == "reject":
                rejected += 1
                record["semantic_status"] = "needs_review"
                changed = True
                continue
            if decision.decision == "needs_revision" or reason:
                needs_revision += 1
                if reason:
                    errors.append({"rule_unit_id": record_id, "error": reason})
                record["semantic_status"] = "needs_review"
                changed = True
                continue
            record.update(
                {
                    "source_section": decision.source_section,
                    "conditions": decision.conditions,
                    "exceptions": decision.exceptions,
                    "enabling_statute": decision.enabling_statute,
                    "temporal": decision.temporal,
                    "penalties": decision.penalties,
                    "rule_type": decision.rule_type,
                    "regulated_entity": decision.regulated_entity,
                    "action_required": decision.action_required,
                    "plain_english_summary": decision.plain_english_summary,
                    "subject_tags": decision.subject_tags,
                    "semantic_status": "semantic_ready",
                    "reviewer": decision.reviewer,
                    "reviewed_at": decision.reviewed_at.isoformat(),
                    "review_notes": decision.notes,
                }
            )
            promoted.add(record_id)
            changed = True
        if changed:
            snapshot = _snapshot_before_write(resolved, metadata_path)
            snapshots.append(snapshot)
            atomic_write_jsonl(metadata_path, records, resolved)

    if promoted:
        _update_indexes(resolved, decisions_by_id, promoted)
        write_retrieval_catalog(resolved)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decisions_received": len(decisions),
        "promoted": len(promoted),
        "rejected": rejected,
        "needs_revision": needs_revision,
        "blocked": len(errors),
        "errors": errors,
        "snapshots": snapshots,
        "boundary": "Only reviewer-approved, source-matched, structured rule units become answer-safe.",
    }
    atomic_write_json(resolved / REPORT_PATH, report, resolved)
    return report


def _promotion_blocker(
    record: dict[str, Any],
    index_row: dict[str, Any] | None,
    decision: PromotionDecision,
) -> str | None:
    """Return the first reason a decision cannot promote a rule unit."""

    if index_row is None:
        return "rule unit is not present in the active index"
    if str(index_row.get("sha256") or "") != decision.source_hash:
        return "reviewed source hash does not match the active preserved source"
    if not decision.source_section or decision.source_section.casefold() == "document-level source":
        return "an exact legal section is required"
    if decision.source_page is None and decision.source_line_start is None:
        return "page or line provenance is required"
    if "not separately specified" in decision.regulated_entity.casefold():
        return "regulated entity must be identified"
    if decision.plain_english_summary.casefold().startswith("source section preserved"):
        return "plain-English legal meaning is still a placeholder"
    try:
        RuleUnit.model_validate({**record, **decision.model_dump(exclude={"rule_unit_id", "decision", "reviewer", "reviewed_at", "source_hash", "source_page", "source_page_end", "source_line_start", "source_line_end", "notes"})})
    except ValidationError as exc:
        return f"promoted rule unit failed schema validation: {exc.errors()[0].get('msg', 'invalid record')}"
    return None


def _update_indexes(
    root: Path,
    decisions: dict[str, PromotionDecision],
    promoted: set[str],
) -> None:
    """Mark promoted units answer-safe in both local indexes."""

    for layer in ("08_County_Authorities", "09_District_Authorities"):
        path = root / layer / "_index.jsonl"
        if not path.exists():
            continue
        rows = list(iter_jsonl(path))
        for row in rows:
            if row.get("id") in promoted:
                decision = decisions[str(row["id"])]
                row["semantic_status"] = "semantic_ready"
                row["source_section"] = decision.source_section
                row["source_page"] = decision.source_page
                row["source_page_end"] = decision.source_page_end
                row["source_line_start"] = decision.source_line_start
                row["source_line_end"] = decision.source_line_end
        atomic_write_jsonl(path, rows, root)


def _snapshot_before_write(root: Path, path: Path) -> str:
    """Copy an active metadata file to a dated snapshot before promotion."""

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / "_SNAPSHOTS" / f"local_promotion_{stamp}" / path.relative_to(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return target.relative_to(root).as_posix()


def main() -> int:
    """Build the queue or apply reviewer decisions."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    result = apply_local_promotion_decisions(root) if args.apply else build_local_promotion_queue(root)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
