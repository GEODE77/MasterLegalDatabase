"""Tests for automated county semantic review."""

from __future__ import annotations

from pathlib import Path

from geode.pipeline.automated_county_review import review_county_candidates
from geode.utils.file_io import atomic_write_jsonl, iter_jsonl


HASH = "a" * 64


def test_automated_review_promotes_only_source_grounded_actor(tmp_path: Path) -> None:
    """A clear, source-grounded obligation is promoted automatically."""

    source = tmp_path / "source.txt"
    source.write_text("Owners of facilities shall obtain a permit before operating.", encoding="utf-8")
    parent = "LOCAL-RULE-CO-COUNTY-TEST"
    parent_row = {
        "id": parent,
        "entity_type": "local_rule",
        "sha256": HASH,
        "source_url": "https://county.example.gov/rules",
        "source_path": "source.txt",
        "tags": ["county_codes"],
        "last_updated": "2026-07-15T00:00:00Z",
    }
    candidate = {
        "entity_type": "rule_unit",
        "id": f"{parent}_RU_0001",
        "parent_regulation_id": parent,
        "source_section": "Section 1",
        "rule_type": "obligation",
        "regulated_entity": "Owners of facilities",
        "action_required": "Owners of facilities shall obtain a permit before operating.",
        "conditions": [],
        "exceptions": [],
        "enabling_statute": [],
        "temporal": "before operating",
        "penalties": [],
        "plain_english_summary": "Owners of facilities shall obtain a permit before operating.",
        "subject_tags": ["permitting"],
        "confidence": {"overall": 0.9, "fields": {}, "route": "automated_review"},
        "semantic_status": "needs_review",
    }
    queue = tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
    atomic_write_jsonl(queue, [{
        "review_id": "REVIEW-1",
        "review_disposition": "manual_entity_confirmation",
        "parent_rule_id": parent,
        "source_hash": HASH,
        "source_path": "source.txt",
        "source_url": "https://county.example.gov/rules",
        "source_category": "county_codes",
        "candidate_rule_unit": candidate,
    }], tmp_path)
    atomic_write_jsonl(tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_CANDIDATE_MAP.jsonl", [{
        "review_id": "REVIEW-1",
        "candidate_rule_unit_id": candidate["id"],
        "permanent_rule_unit_id": f"{parent}-UNIT-0001",
        "parent_regulation_id": parent,
        "source_hash": HASH,
        "source_section": "Section 1",
        "mapping_status": "planned_new",
        "mapping_reason": "test",
    }], tmp_path)
    atomic_write_jsonl(tmp_path / "08_County_Authorities" / "_index.jsonl", [parent_row], tmp_path)
    atomic_write_jsonl(tmp_path / "08_County_Authorities" / "_meta" / "local_rule_units.jsonl", [], tmp_path)

    summary = review_county_candidates(tmp_path, apply=True)
    assert summary["auto_approved"] == 1
    promoted = next(iter_jsonl(tmp_path / "08_County_Authorities" / "_meta" / "local_rule_units.jsonl"))

    assert summary["auto_approved"] == 1
    assert summary["applied"] == 1
    assert promoted["semantic_status"] == "semantic_ready"


def test_automated_review_quarantines_object_without_responsible_party(tmp_path: Path) -> None:
    """A sentence about an object is not promoted as a duty on an unknown party."""

    source = tmp_path / "source.txt"
    source.write_text("Racks shall be mounted to concrete.", encoding="utf-8")
    parent = "LOCAL-RULE-CO-COUNTY-TEST"
    candidate = {
        "id": f"{parent}_RU_0001",
        "parent_regulation_id": parent,
        "source_section": "Section 1",
        "rule_type": "obligation",
        "regulated_entity": "Racks",
        "action_required": "Racks shall be mounted to concrete.",
        "subject_tags": ["compliance"],
    }
    queue = tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"
    atomic_write_jsonl(queue, [{
        "review_id": "REVIEW-1",
        "review_disposition": "manual_entity_confirmation",
        "parent_rule_id": parent,
        "source_hash": HASH,
        "source_path": "source.txt",
        "source_url": "https://county.example.gov/rules",
        "source_category": "county_codes",
        "candidate_rule_unit": candidate,
    }], tmp_path)
    atomic_write_jsonl(tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_CANDIDATE_MAP.jsonl", [{
        "review_id": "REVIEW-1",
        "candidate_rule_unit_id": candidate["id"],
        "permanent_rule_unit_id": f"{parent}-UNIT-0001",
        "parent_regulation_id": parent,
        "source_hash": HASH,
        "source_section": "Section 1",
        "mapping_status": "planned_new",
        "mapping_reason": "test",
    }], tmp_path)
    atomic_write_jsonl(tmp_path / "08_County_Authorities" / "_index.jsonl", [{
        "id": parent,
        "entity_type": "local_rule",
        "sha256": HASH,
        "last_updated": "2026-07-15T00:00:00Z",
    }], tmp_path)

    summary = review_county_candidates(tmp_path)

    assert summary["auto_approved"] == 0
    assert summary["auto_quarantined"] == 1
