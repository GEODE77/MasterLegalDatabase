"""Create grounded semantic candidates for county rule-unit review."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.pipeline.rule_units import extract_rule_units_from_markdown, score_rule_unit_quality
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl


CONTROL = Path("_CONTROL_PLANE")
QUEUE = CONTROL / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
SUMMARY = CONTROL / "COUNTY_SEMANTIC_REVIEW_SUMMARY.json"


def build_county_semantic_review(root: Path, max_units_per_rule: int = 24) -> dict[str, Any]:
    """Create source-linked deterministic candidates without changing canonical data."""

    resolved = root.resolve()
    source_path = resolved / "08_County_Authorities" / "_meta" / "local_rules.jsonl"
    candidates: list[dict[str, Any]] = []
    rules_seen = 0
    rules_with_candidates = 0
    quality_levels: Counter[str] = Counter()
    for rule in iter_jsonl(source_path):
        rules_seen += 1
        units = extract_rule_units_from_markdown(
            str(rule["id"]),
            str(rule["full_text"]),
            max_units=max_units_per_rule,
        )
        if units:
            rules_with_candidates += 1
        for unit in units:
            quality = score_rule_unit_quality(unit, str(rule["full_text"]))
            quality_levels[quality.quality_level] += 1
            candidate = unit.model_dump(mode="json")
            candidate["semantic_status"] = "needs_review"
            candidates.append(
                {
                    "review_id": f"COUNTY-SEM-{unit.id}",
                    "status": "pending",
                    "review_type": "county_semantic_candidate",
                    "authority_id": rule.get("authority_id"),
                    "authority_name": rule.get("authority_name"),
                    "source_category": rule.get("source_category"),
                    "source_path": rule.get("source_path"),
                    "source_url": rule.get("source_url"),
                    "source_hash": rule.get("source_hash"),
                    "parent_rule_id": rule.get("id"),
                    "candidate_rule_unit": candidate,
                    "quality": quality.model_dump(mode="json"),
                    "required_review": [
                        "confirm the passage is an adopted rule, ordinance, or binding requirement",
                        "confirm the candidate states one atomic legal action",
                        "confirm the regulated entity, conditions, and exceptions",
                        "confirm the exact source passage and current status",
                    ],
                }
            )

    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at": generated_at,
        "layer": "08_County_Authorities",
        "rules_seen": rules_seen,
        "rules_with_candidates": rules_with_candidates,
        "candidate_rule_units": len(candidates),
        "quality_levels": dict(quality_levels),
        "promoted": 0,
        "answer_safe": 0,
        "status": "review_required",
        "boundary": (
            "Candidates are source-grounded drafts only. They remain outside answer-safe retrieval "
            "until a reviewer approves the exact passage, meaning, exceptions, and current status."
        ),
    }
    atomic_write_jsonl(resolved / QUEUE, candidates, resolved)
    atomic_write_json(resolved / SUMMARY, report, resolved)
    return report


def main() -> None:
    """Run the county semantic candidate review pass."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--max-units-per-rule", type=int, default=24)
    args = parser.parse_args()
    print(build_county_semantic_review(args.root, args.max_units_per_rule))


if __name__ == "__main__":
    main()
