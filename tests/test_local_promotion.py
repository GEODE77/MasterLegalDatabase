"""Tests for controlled promotion of local rule units."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from geode.pipeline.local_promotion import (
    apply_local_promotion_decisions,
    build_local_promotion_queue,
)
from geode.utils.file_io import atomic_write_jsonl, iter_jsonl


RULE_ID = "LOCAL-RULE-CO-COUNTY-TEST-UNIT-0001"
SOURCE_HASH = "a" * 64


def _make_project(root: Path) -> None:
    """Create one valid preserved local rule unit and index row."""

    metadata = root / "08_County_Authorities" / "_meta" / "local_rule_units.jsonl"
    index = root / "08_County_Authorities" / "_index.jsonl"
    atomic_write_jsonl(
        metadata,
        [{
            "entity_type": "rule_unit",
            "id": RULE_ID,
            "parent_regulation_id": "LOCAL-RULE-CO-COUNTY-TEST",
            "source_section": "Document-level source",
            "rule_type": "standard",
            "regulated_entity": "Not separately specified in source section",
            "action_required": "Preserved source text",
            "conditions": [],
            "exceptions": [],
            "enabling_statute": [],
            "temporal": None,
            "penalties": [],
            "plain_english_summary": "Source section preserved; semantic extraction remains pending.",
            "subject_tags": ["compliance"],
            "confidence": {"overall": 0.45, "fields": {}, "route": "source_preservation_only"},
            "semantic_status": "source_preservation_only",
        }],
        root,
    )
    atomic_write_jsonl(
        index,
        [{
            "id": RULE_ID,
            "entity_type": "rule_unit",
            "authority_id": "CO-COUNTY-TEST",
            "authority_level": "county",
            "authority_name": "Test County",
            "source_category": "county_codes",
            "source_path": "_RAW_ARCHIVE/local/county/test.pdf",
            "sha256": SOURCE_HASH,
            "source_section": "Document-level source",
            "source_page": 1,
            "source_line_start": 1,
            "semantic_status": "source_preservation_only",
        }],
        root,
    )


def _decision(root: Path, **updates: object) -> None:
    """Write one reviewer decision."""

    row = {
        "rule_unit_id": RULE_ID,
        "decision": "approve",
        "reviewer": "reviewer-1",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "source_hash": SOURCE_HASH,
        "source_section": "Section 12-4",
        "source_page": 1,
        "source_line_start": 1,
        "rule_type": "obligation",
        "regulated_entity": "Owners of commercial facilities",
        "action_required": "Must obtain a county permit before operating the facility.",
        "conditions": [],
        "exceptions": [],
        "enabling_statute": [],
        "temporal": None,
        "penalties": [],
        "plain_english_summary": "Commercial facility owners must obtain a county permit before operating.",
        "subject_tags": ["compliance"],
        "notes": "Checked against the exact adopted section.",
    }
    row.update(updates)
    atomic_write_jsonl(root / "_CONTROL_PLANE" / "LOCAL_PROMOTION_DECISIONS.jsonl", [row], root)


def test_promotion_requires_review_and_updates_answer_safety(tmp_path: Path) -> None:
    """A valid reviewer decision promotes one unit and preserves a snapshot."""

    _make_project(tmp_path)
    assert build_local_promotion_queue(tmp_path) == {"queued": 1, "answer_safe": 0}
    _decision(tmp_path)
    report = apply_local_promotion_decisions(tmp_path)
    assert report["promoted"] == 1
    assert report["blocked"] == 0
    assert report["snapshots"]
    promoted = next(iter_jsonl(tmp_path / "08_County_Authorities" / "_meta" / "local_rule_units.jsonl"))
    assert promoted["semantic_status"] == "semantic_ready"


def test_promotion_blocks_source_hash_mismatch(tmp_path: Path) -> None:
    """A decision for a different preserved source cannot promote."""

    _make_project(tmp_path)
    _decision(tmp_path, source_hash="b" * 64)
    report = apply_local_promotion_decisions(tmp_path)
    assert report["promoted"] == 0
    assert report["blocked"] == 1
