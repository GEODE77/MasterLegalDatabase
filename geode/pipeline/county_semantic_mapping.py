"""Map county semantic review candidates to permanent rule-unit identities."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl


CONTROL = Path("_CONTROL_PLANE")
QUEUE = CONTROL / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
MAPPING = CONTROL / "COUNTY_SEMANTIC_CANDIDATE_MAP.jsonl"
SUMMARY = CONTROL / "COUNTY_SEMANTIC_CANDIDATE_MAP_SUMMARY.json"


class CandidateMapping(BaseModel):
    """Validated identity link between a review candidate and a permanent unit."""

    review_id: str = Field(min_length=1)
    candidate_rule_unit_id: str = Field(min_length=1)
    permanent_rule_unit_id: str | None = None
    parent_regulation_id: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_section: str = Field(min_length=1)
    mapping_status: str
    mapping_reason: str = Field(min_length=1)


def build_candidate_mappings(root: Path) -> dict[str, Any]:
    """Build safe candidate links and reserve IDs for candidates needing new units.

    A candidate is linked to an existing unit only when its parent, source hash,
    and source section identify exactly one active unit. Otherwise a new unit ID
    is reserved, but no active database record is changed.
    """

    resolved = root.resolve()
    queue_path = resolved / QUEUE
    index_rows = _load_index_rows(resolved)
    units_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in index_rows.values():
        if row.get("entity_type") == "rule_unit":
            parent = str(row.get("parent_regulation_id") or "")
            if not parent:
                parent = str(row.get("id") or "").rsplit("-UNIT-", 1)[0]
            units_by_parent[parent].append(row)

    next_numbers = {
        parent: _next_unit_number(rows) for parent, rows in units_by_parent.items()
    }
    mappings: list[CandidateMapping] = []
    counts: dict[str, int] = defaultdict(int)
    seen_candidates: set[str] = set()
    claimed_existing: set[str] = set()

    for row in iter_jsonl(queue_path):
        if not row.get("review_disposition"):
            continue
        candidate = row.get("candidate_rule_unit") or {}
        candidate_id = str(candidate.get("id") or "")
        review_id = str(row.get("review_id") or "")
        parent = str(row.get("parent_rule_id") or candidate.get("parent_regulation_id") or "")
        source_hash = str(row.get("source_hash") or "")
        source_section = str(candidate.get("source_section") or "")
        if not candidate_id or not review_id or candidate_id in seen_candidates:
            mappings.append(_blocked_mapping(row, "candidate identity is missing or duplicated"))
            counts["blocked"] += 1
            continue
        seen_candidates.add(candidate_id)

        parent_rows = units_by_parent.get(parent, [])
        parent_hashes = {
            str(item.get("sha256") or "") for item in index_rows.values()
            if item.get("id") == parent
        }
        if source_hash not in parent_hashes:
            mappings.append(_mapping_from_row(
                row, None, "blocked", "candidate source hash does not match its active parent"
            ))
            counts["blocked"] += 1
            continue

        matches = [item for item in parent_rows if item.get("source_section") == source_section]
        if len(matches) == 1 and str(matches[0]["id"]) not in claimed_existing:
            permanent_id = str(matches[0]["id"])
            claimed_existing.add(permanent_id)
            mappings.append(_mapping_from_row(
                row, permanent_id, "mapped_existing", "exact parent, source hash, and section match"
            ))
            counts["mapped_existing"] += 1
            continue
        if len(matches) > 1:
            mappings.append(_mapping_from_row(
                row, None, "blocked", "source section matches multiple active units"
            ))
            counts["blocked"] += 1
            continue

        number = next_numbers.setdefault(parent, 1)
        permanent_id = f"{parent}-UNIT-{number:04d}"
        next_numbers[parent] = number + 1
        mappings.append(_mapping_from_row(
            row, permanent_id, "planned_new", "no existing unit has the exact source section"
        ))
        counts["planned_new"] += 1

    atomic_write_jsonl(resolved / MAPPING, mappings, resolved)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_candidates_mapped": len(mappings),
        "mapped_existing": counts["mapped_existing"],
        "planned_new": counts["planned_new"],
        "blocked": counts["blocked"],
        "active_records_changed": 0,
        "promotion_status": "awaiting_reviewer_decisions",
        "boundary": (
            "This step creates identity links only. It does not promote any candidate or "
            "change answer-safe retrieval."
        ),
    }
    atomic_write_json(resolved / SUMMARY, summary, resolved)
    return summary


def _load_index_rows(root: Path) -> dict[str, dict[str, Any]]:
    """Load active county index rows by ID."""

    path = root / "08_County_Authorities" / "_index.jsonl"
    return {str(row.get("id")): row for row in iter_jsonl(path) if row.get("id")}


def _next_unit_number(rows: list[dict[str, Any]]) -> int:
    """Return the first unused numeric suffix for a parent rule."""

    numbers = []
    for row in rows:
        text = str(row.get("id") or "")
        try:
            numbers.append(int(text.rsplit("-UNIT-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return max(numbers, default=0) + 1


def _mapping_from_row(
    row: dict[str, Any], permanent_id: str | None, status: str, reason: str
) -> CandidateMapping:
    """Create a validated mapping from one queue row."""

    candidate = row["candidate_rule_unit"]
    return CandidateMapping(
        review_id=str(row["review_id"]),
        candidate_rule_unit_id=str(candidate["id"]),
        permanent_rule_unit_id=permanent_id,
        parent_regulation_id=str(row.get("parent_rule_id") or candidate["parent_regulation_id"]),
        source_hash=str(row.get("source_hash") or "0" * 64),
        source_section=str(candidate.get("source_section") or "unknown"),
        mapping_status=status,
        mapping_reason=reason,
    )


def _blocked_mapping(row: dict[str, Any], reason: str) -> CandidateMapping:
    """Create a valid blocked mapping even when candidate identity is incomplete."""

    candidate = row.get("candidate_rule_unit") or {}
    return _mapping_from_row({
        **row,
        "review_id": row.get("review_id") or "missing-review-id",
        "parent_rule_id": row.get("parent_rule_id") or candidate.get("parent_regulation_id") or "unknown-parent",
        "source_hash": row.get("source_hash") or "0" * 64,
        "candidate_rule_unit": {
            **candidate,
            "id": candidate.get("id") or "missing-candidate-id",
        },
    }, None, "blocked", reason)


def main() -> int:
    """Build the candidate mapping control-plane files."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(build_candidate_mappings(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
