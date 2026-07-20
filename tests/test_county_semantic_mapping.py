"""Tests for safe county semantic candidate mapping."""

from __future__ import annotations

from pathlib import Path

from geode.pipeline.county_semantic_mapping import build_candidate_mappings
from geode.utils.file_io import atomic_write_jsonl, iter_jsonl


HASH = "a" * 64


def _row(candidate_id: str, section: str) -> dict[str, object]:
    """Create one review candidate."""

    parent = "LOCAL-RULE-CO-COUNTY-TEST"
    return {
        "review_id": f"REVIEW-{candidate_id}",
        "review_disposition": "manual_entity_confirmation",
        "parent_rule_id": parent,
        "source_hash": HASH,
        "candidate_rule_unit": {
            "id": candidate_id,
            "parent_regulation_id": parent,
            "source_section": section,
        },
    }


def test_mapping_links_exact_match_and_reserves_new_id(tmp_path: Path) -> None:
    """Exact sections reuse units and unmatched sections receive reserved IDs."""

    index = tmp_path / "08_County_Authorities" / "_index.jsonl"
    atomic_write_jsonl(index, [
        {
            "id": "LOCAL-RULE-CO-COUNTY-TEST",
            "entity_type": "local_rule",
            "sha256": HASH,
        },
        {
            "id": "LOCAL-RULE-CO-COUNTY-TEST-UNIT-0001",
            "entity_type": "rule_unit",
            "parent_regulation_id": "LOCAL-RULE-CO-COUNTY-TEST",
            "source_section": "Section 1",
            "sha256": HASH,
        },
    ], tmp_path)
    queue = tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
    atomic_write_jsonl(queue, [_row("C-001", "Section 1"), _row("C-002", "Section 2")], tmp_path)

    report = build_candidate_mappings(tmp_path)
    rows = list(iter_jsonl(tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_CANDIDATE_MAP.jsonl"))

    assert report["mapped_existing"] == 1
    assert report["planned_new"] == 1
    assert rows[0]["permanent_rule_unit_id"] == "LOCAL-RULE-CO-COUNTY-TEST-UNIT-0001"
    assert rows[1]["permanent_rule_unit_id"] == "LOCAL-RULE-CO-COUNTY-TEST-UNIT-0002"


def test_mapping_blocks_parent_hash_mismatch(tmp_path: Path) -> None:
    """A candidate from a changed source cannot be connected automatically."""

    index = tmp_path / "08_County_Authorities" / "_index.jsonl"
    atomic_write_jsonl(index, [{
        "id": "LOCAL-RULE-CO-COUNTY-TEST",
        "entity_type": "local_rule",
        "sha256": "b" * 64,
    }], tmp_path)
    queue = tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
    atomic_write_jsonl(queue, [_row("C-001", "Section 1")], tmp_path)

    report = build_candidate_mappings(tmp_path)
    row = next(iter_jsonl(tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_CANDIDATE_MAP.jsonl"))

    assert report["blocked"] == 1
    assert row["mapping_status"] == "blocked"
    assert row["permanent_rule_unit_id"] is None
