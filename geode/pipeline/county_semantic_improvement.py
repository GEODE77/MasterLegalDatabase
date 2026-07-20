"""Improve lower-confidence county semantic candidates without auto-approval."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.pipeline.rule_units import score_rule_unit_quality
from geode.schemas import RuleUnit
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl


CONTROL = Path("_CONTROL_PLANE")
QUEUE = CONTROL / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
SUMMARY = CONTROL / "COUNTY_SEMANTIC_IMPROVEMENT_SUMMARY.json"
MODAL_RE = re.compile(
    r"\b(shall not|may not|must not|is prohibited from|are prohibited from|"
    r"is required to|are required to|shall|must|may)\b",
    re.IGNORECASE,
)
CLAUSE_RE = re.compile(
    r"\b(unless|except(?: as provided)?|provided that|subject to)\b[^.;]+",
    re.IGNORECASE,
)
CONDITION_RE = re.compile(
    r"\b(if|when|upon|before|after|within|no later than)\b[^.;]+",
    re.IGNORECASE,
)
NOISE_MARKERS = (
    "skip to",
    "menu",
    "select this as your preferred language",
    "open search",
    "home /",
    "quick links",
)


def _clean(value: str) -> str:
    """Collapse extraction whitespace without changing words."""

    return re.sub(r"\s+", " ", value).strip()


def _source_entity(action: str, current: str) -> str:
    """Derive the shortest source phrase immediately before the legal modal."""

    match = MODAL_RE.search(action)
    if not match:
        return current
    prefix = _clean(action[: match.start()]).rstrip(",:")
    if "," in prefix:
        prefix = prefix.rsplit(",", 1)[-1].strip()
    prefix = re.sub(r"^(upon|if|when|before|after)\b.*?,\s*", "", prefix, flags=re.I)
    if 1 <= len(prefix.split()) <= 24:
        return prefix
    return current


def _improve_row(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Improve one candidate while retaining its pending-review status."""

    candidate = dict(row["candidate_rule_unit"])
    original = RuleUnit.model_validate(candidate)
    action = _clean(original.action_required)
    improvements: list[str] = []
    entity = _source_entity(action, original.regulated_entity)
    clauses = [_clean(match.group(0)) for match in CLAUSE_RE.finditer(action)]
    conditions = [_clean(match.group(0)) for match in CONDITION_RE.finditer(action)]
    if entity != original.regulated_entity:
        candidate["regulated_entity"] = entity
        improvements.append("tightened regulated entity to source phrase")
    if action != original.action_required:
        candidate["action_required"] = action
        improvements.append("normalized source whitespace")
    if clauses and not candidate.get("exceptions"):
        candidate["exceptions"] = clauses
        improvements.append("captured visible exception or limiting clause")
    if conditions and not candidate.get("conditions"):
        candidate["conditions"] = conditions
        improvements.append("captured visible condition or timing clause")
    candidate["plain_english_summary"] = action
    candidate["semantic_status"] = "needs_review"
    candidate_model = RuleUnit.model_validate(candidate)
    quality = score_rule_unit_quality(candidate_model, action)
    text = action.casefold()
    noise = len(action) > 700 and any(marker in text for marker in NOISE_MARKERS)
    disposition = "noise_review" if noise else "semantic_review"
    if noise:
        improvements.append("flagged likely navigation or front-matter noise")
    row["candidate_rule_unit"] = candidate_model.model_dump(mode="json")
    row["original_quality"] = row.get("quality")
    row["quality"] = quality.model_dump(mode="json")
    row["improvements"] = improvements
    row["disposition"] = disposition
    row["status"] = "pending"
    return row, improvements


def improve_county_semantic_candidates(root: Path) -> dict[str, Any]:
    """Review every medium and needs-review candidate and rewrite the queue."""

    resolved = root.resolve()
    path = resolved / QUEUE
    rows: list[dict[str, Any]] = []
    selected = 0
    improved = 0
    dispositions: Counter[str] = Counter()
    quality_levels: Counter[str] = Counter()
    for row in iter_jsonl(path):
        if row.get("quality", {}).get("quality_level") not in {"medium", "needs_review"}:
            rows.append(row)
            continue
        selected += 1
        improved_row, changes = _improve_row(row)
        rows.append(improved_row)
        improved += bool(changes)
        dispositions[str(improved_row["disposition"])] += 1
        quality_levels[str(improved_row["quality"]["quality_level"])] += 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_lower_quality": selected,
        "improved_candidates": improved,
        "dispositions": dict(dispositions),
        "quality_levels_after": dict(quality_levels),
        "promoted": 0,
        "answer_safe": 0,
        "status": "review_required",
        "boundary": (
            "Repairs are source-grounded candidate improvements only. Combined, ambiguous, or noisy "
            "passages remain pending and cannot enter answer-safe retrieval automatically."
        ),
    }
    atomic_write_jsonl(path, rows, resolved)
    atomic_write_json(resolved / SUMMARY, summary, resolved)
    return summary


def main() -> None:
    """Run the county semantic improvement pass."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(improve_county_semantic_candidates(args.root))


if __name__ == "__main__":
    main()
