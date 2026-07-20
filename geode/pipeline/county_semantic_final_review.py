"""Resolve what can be resolved in the remaining county semantic review queue."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl


CONTROL = Path("_CONTROL_PLANE")
QUEUE = CONTROL / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
SUMMARY = CONTROL / "COUNTY_SEMANTIC_FINAL_REVIEW_SUMMARY.json"
CLAUSE_RE = re.compile(
    r"\b(?:unless|except(?: as provided)?|provided that|subject to)\b[^.;]+(?:[.;]|$)",
    re.IGNORECASE,
)
MODAL_RE = re.compile(
    r"\b(?:shall not|may not|must not|is prohibited from|are prohibited from|"
    r"is required to|are required to|shall|must|may)\b",
    re.IGNORECASE,
)


def _split_proposals(action: str) -> list[str]:
    """Return source-text segments that may represent separate legal actions."""

    parts = [part.strip(" ,") for part in re.split(r";\s*", action) if part.strip(" ,")]
    if len(parts) == 1:
        parts = [
            part.strip(" ,")
            for part in re.split(r"\s+,?\s+and\s+(?=[A-Z])", action)
            if part.strip(" ,")
        ]
    proposals = [part for part in parts if MODAL_RE.search(part)]
    return proposals if len(proposals) > 1 else []


def review_remaining_county_candidates(root: Path) -> dict[str, Any]:
    """Review all remaining candidates and preserve unresolved questions explicitly."""

    resolved = root.resolve()
    path = resolved / QUEUE
    rows: list[dict[str, Any]] = []
    reviewed = 0
    entity_confirmations = 0
    split_proposals = 0
    exception_captures = 0
    for row in iter_jsonl(path):
        if row.get("quality", {}).get("quality_level") != "needs_review":
            rows.append(row)
            continue
        reviewed += 1
        candidate = row["candidate_rule_unit"]
        action = str(candidate.get("action_required") or "").strip()
        clauses = [match.group(0).strip() for match in CLAUSE_RE.finditer(action)]
        if clauses and not candidate.get("exceptions"):
            candidate["exceptions"] = clauses
            exception_captures += 1
        proposals = _split_proposals(action)
        if proposals:
            row["split_proposals"] = proposals
            split_proposals += 1
        issues = list(row.get("quality", {}).get("issues", []))
        if "regulated entity is too broad" in issues:
            row["review_disposition"] = "manual_entity_confirmation"
            row["unresolved_reason"] = (
                "The source names a broad object or group; the responsible regulated party "
                "cannot be added without source support."
            )
            entity_confirmations += 1
        elif proposals:
            row["review_disposition"] = "manual_atomic_split"
            row["unresolved_reason"] = (
                "The source contains multiple possible actions; each proposed segment requires "
                "confirmation before promotion."
            )
        else:
            row["review_disposition"] = "manual_source_review"
            row["unresolved_reason"] = (
                "The candidate remains ambiguous after deterministic source-grounded review."
            )
        candidate["semantic_status"] = "needs_review"
        row["candidate_rule_unit"] = candidate
        rows.append(row)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_remaining_candidates": reviewed,
        "entity_confirmations_required": entity_confirmations,
        "manual_atomic_split_proposals": split_proposals,
        "exception_captures": exception_captures,
        "promoted": 0,
        "answer_safe": 0,
        "status": "review_required",
        "boundary": (
            "No responsible party or legal meaning is inferred. Remaining candidates have explicit "
            "review dispositions and source-preserving split or exception proposals."
        ),
    }
    atomic_write_jsonl(path, rows, resolved)
    atomic_write_json(resolved / SUMMARY, summary, resolved)
    return summary


def main() -> None:
    """Run the final county semantic review pass."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(review_remaining_county_candidates(args.root))


if __name__ == "__main__":
    main()
