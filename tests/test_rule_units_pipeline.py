"""Tests for deterministic CCR rule-unit extraction."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.rule_units import (
    append_rule_unit_review_decision,
    apply_rule_unit_review_decisions,
    build_rule_unit_apply_proposal,
    extract_rule_units_from_markdown,
    generate_ccr_rule_units,
    score_rule_unit_quality,
)
from geode.schemas import RuleUnit
from geode.utils.file_io import iter_jsonl


def test_extract_rule_units_from_markdown_builds_schema_valid_records() -> None:
    """Source-backed mandatory sentences become validated rule units."""

    markdown = """
---
id: "5_CCR_1001-9"
---

#### 5_CCR_1001-9. Air Quality Rule

APPLICABILITY
A stationary source shall submit an annual emissions report within 30 days after
the end of each calendar year.
No owner or operator shall operate the source without a valid permit.
"""

    units = extract_rule_units_from_markdown("5_CCR_1001-9", markdown)

    assert len(units) == 2
    assert all(isinstance(unit, RuleUnit) for unit in units)
    assert units[0].rule_type == "reporting"
    assert units[0].regulated_entity == "A stationary source"
    assert units[0].temporal == "within 30 days"
    assert "air_quality" in units[0].subject_tags
    assert units[1].rule_type == "prohibition"
    assert units[1].regulated_entity == "No owner or operator"


def test_generate_ccr_rule_units_writes_product_readiness_file(project_root: Path) -> None:
    """The pipeline writes validated rule units to the product-read path."""

    rules_dir = project_root / "02_Regulations_CCR" / "_rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (project_root / "02_Regulations_CCR" / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "5_CCR_1001-9",
                "entity_type": "regulation_rule_acquisition",
                "tags": ["air_quality", "reporting"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (rules_dir / "5_CCR_1001-9.md").write_text(
        """
#### 5_CCR_1001-9. Air Quality Rule

RECORDKEEPING
The owner or operator shall maintain monitoring records for five years.
""",
        encoding="utf-8",
    )

    summary = generate_ccr_rule_units(project_root)
    rows = list(iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units.jsonl"))
    quality_rows = list(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_quality.jsonl")
    )
    review_rows = list(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl")
    )

    assert summary.rule_units == 1
    assert summary.records_with_units == 1
    assert summary.quality_path == "02_Regulations_CCR/_meta/rule_units_quality.jsonl"
    assert summary.review_queue_path == "02_Regulations_CCR/_meta/rule_units_review_queue.jsonl"
    assert summary.review_summary_path == "02_Regulations_CCR/_meta/rule_units_review_summary.json"
    assert summary.high_quality_units == 1
    assert summary.review_queue_items == 0
    assert rows[0]["entity_type"] == "rule_unit"
    assert rows[0]["parent_regulation_id"] == "5_CCR_1001-9"
    assert rows[0]["rule_type"] == "obligation"
    assert rows[0]["subject_tags"] == ["recordkeeping", "air_quality", "reporting"]
    assert rows[0]["confidence"]["fields"]["quality_gate"] == 1.0
    assert quality_rows[0]["quality_level"] == "high"
    assert review_rows == []
    RuleUnit.model_validate(rows[0])


def test_extract_rule_units_skips_front_matter_definition_language() -> None:
    """Definitions introductions should not become compliance rule units."""

    markdown = """
#### 1_CCR_101-1. Fiscal Rule

DEFINITIONS
The following general definitions shall apply to these Fiscal Rules.

RESPONSIBILITY
Each State Agency shall maintain documentation before approving payment.
"""

    units = extract_rule_units_from_markdown("1_CCR_101-1", markdown)

    assert len(units) == 1
    assert units[0].source_section == "RESPONSIBILITY"
    assert units[0].regulated_entity == "Each State Agency"


def test_quality_gate_flags_multi_action_and_missing_exception_capture() -> None:
    """Quality scoring marks valid but risky rule units for review."""

    unit = RuleUnit(
        id="5_CCR_1001-9_RU_0001",
        parent_regulation_id="5_CCR_1001-9",
        source_section="Reporting",
        rule_type="reporting",
        regulated_entity="The owner or operator",
        action_required=(
            "The owner or operator shall submit a report and shall maintain records "
            "unless the division grants an exemption."
        ),
        subject_tags=["reporting", "recordkeeping"],
        plain_english_summary=(
            "The owner or operator shall submit a report and shall maintain records "
            "unless the division grants an exemption."
        ),
        confidence={"overall": 0.82},
    )

    quality = score_rule_unit_quality(unit, unit.action_required)

    assert quality.quality_level == "medium"
    assert quality.atomicity < 1.0
    assert quality.exception_capture < 1.0
    assert "possible multiple legal actions" in quality.issues
    assert "exception language appears in source but no exception was captured" in quality.issues


def test_quality_gate_flags_unclear_entity_and_source_mismatch() -> None:
    """Low-quality valid records are separated for later review."""

    unit = RuleUnit(
        id="5_CCR_1001-9_RU_0002",
        parent_regulation_id="5_CCR_1001-9",
        source_section="Applicability",
        rule_type="obligation",
        regulated_entity="person",
        action_required="A permit holder shall submit an annual report.",
        subject_tags=["reporting"],
        plain_english_summary="A permit holder shall submit an annual report.",
        confidence={"overall": 0.82},
    )

    quality = score_rule_unit_quality(unit, "Different source text.")

    assert quality.quality_level == "needs_review"
    assert quality.source_fidelity == 0.2
    assert quality.entity_clarity < 1.0
    assert "regulated entity is too broad" in quality.issues


def test_generate_ccr_rule_units_writes_needs_review_queue(project_root: Path) -> None:
    """Needs-review records become pending review tasks with preserved source text."""

    rules_dir = project_root / "02_Regulations_CCR" / "_rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (project_root / "02_Regulations_CCR" / "_index.jsonl").write_text(
        json.dumps({"id": "5_CCR_1001-9"}) + "\n",
        encoding="utf-8",
    )
    (rules_dir / "5_CCR_1001-9.md").write_text(
        """
APPLICABILITY
person shall submit an annual report to the division before operating the facility.
""",
        encoding="utf-8",
    )

    summary = generate_ccr_rule_units(project_root)
    queue_path = project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl"
    queue_rows = list(iter_jsonl(queue_path))

    assert summary.review_queue_items == 1
    assert queue_rows[0]["status"] == "pending"
    assert queue_rows[0]["allowed_outcomes"] == ["approve", "split", "revise", "quarantine"]
    assert queue_rows[0]["suggested_outcomes"] == ["revise"]
    assert queue_rows[0]["source_sentence"] == queue_rows[0]["current_rule_unit"]["action_required"]
    assert "quality" in queue_rows[0]


def test_append_rule_unit_review_decision_preserves_original_record(project_root: Path) -> None:
    """Review decisions append without mutating the generated queue."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)
    queue_path = project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl"
    original_queue_rows = list(iter_jsonl(queue_path))

    decision = append_rule_unit_review_decision(
        project_root,
        review_id=original_queue_rows[0]["review_id"],
        outcome="quarantine",
        decided_by="unit-test",
        rationale="Regulated entity was too broad to approve.",
    )
    decision_rows = list(
        iter_jsonl(
            project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_decisions.jsonl"
        )
    )
    unchanged_queue_rows = list(iter_jsonl(queue_path))

    assert len(decision_rows) == 1
    assert decision.outcome == "quarantine"
    assert decision.source_sentence == original_queue_rows[0]["source_sentence"]
    assert decision.previous_rule_unit == original_queue_rows[0]["current_rule_unit"]
    assert unchanged_queue_rows == original_queue_rows


def test_append_rule_unit_review_decision_requires_valid_outcome(project_root: Path) -> None:
    """Decision logging rejects outcomes outside the review contract."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)
    review_id = next(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl")
    )["review_id"]

    try:
        append_rule_unit_review_decision(
            project_root,
            review_id=review_id,
            outcome="defer",  # type: ignore[arg-type]
            decided_by="unit-test",
            rationale="Not a supported outcome.",
        )
    except ValueError as exc:
        assert "not allowed" in str(exc)
    else:
        raise AssertionError("invalid outcome was accepted")


def test_append_rule_unit_review_decision_requires_replacements_for_revise(
    project_root: Path,
) -> None:
    """Revise and split outcomes must include proposed replacement records."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)
    review_id = next(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl")
    )["review_id"]

    try:
        append_rule_unit_review_decision(
            project_root,
            review_id=review_id,
            outcome="revise",
            decided_by="unit-test",
            rationale="Entity should be narrowed.",
        )
    except ValueError as exc:
        assert "proposed_rule_units" in str(exc)
    else:
        raise AssertionError("revise decision without replacement was accepted")


def test_build_rule_unit_apply_proposal_quarantines_without_mutating_source(
    project_root: Path,
) -> None:
    """Apply proposal can remove a quarantined item without editing source JSONL."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)
    queue_row = next(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl")
    )
    before_rows = list(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units.jsonl")
    )
    append_rule_unit_review_decision(
        project_root,
        review_id=queue_row["review_id"],
        outcome="quarantine",
        decided_by="unit-test",
        rationale="Entity capture is too broad.",
    )

    proposal = build_rule_unit_apply_proposal(project_root)
    after_rows = list(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units.jsonl")
    )

    assert proposal.ready_to_apply
    assert proposal.changes[0].action == "remove"
    assert proposal.resulting_rule_units == proposal.source_rule_units - 1
    assert after_rows == before_rows


def test_build_rule_unit_apply_proposal_revises_with_valid_replacement(project_root: Path) -> None:
    """Revise decisions produce a replace proposal when replacement validates."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)
    queue_row = next(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl")
    )
    replacement = {
        **queue_row["current_rule_unit"],
        "id": f"{queue_row['rule_unit_id']}_REV_0001",
        "regulated_entity": "A permit holder",
        "action_required": queue_row["source_sentence"],
        "plain_english_summary": queue_row["source_sentence"],
    }
    append_rule_unit_review_decision(
        project_root,
        review_id=queue_row["review_id"],
        outcome="revise",
        decided_by="unit-test",
        rationale="Narrow regulated entity to source-backed phrase.",
        proposed_rule_units=[replacement],
    )

    proposal = build_rule_unit_apply_proposal(project_root)

    assert proposal.ready_to_apply
    assert proposal.changes[0].action == "replace"
    assert proposal.changes[0].proposed_rule_unit_ids == [replacement["id"]]
    assert proposal.resulting_rule_units == proposal.source_rule_units


def test_build_rule_unit_apply_proposal_rejects_invalid_replacement(project_root: Path) -> None:
    """Invalid replacement records block the apply proposal."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)
    queue_row = next(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl")
    )
    replacement = {
        **queue_row["current_rule_unit"],
        "id": f"{queue_row['rule_unit_id']}_BAD",
        "subject_tags": ["invented_tag"],
    }
    append_rule_unit_review_decision(
        project_root,
        review_id=queue_row["review_id"],
        outcome="revise",
        decided_by="unit-test",
        rationale="Replacement intentionally invalid for test.",
        proposed_rule_units=[replacement],
    )

    proposal = build_rule_unit_apply_proposal(project_root)

    assert not proposal.ready_to_apply
    assert proposal.changes[0].action == "invalid"
    assert proposal.validation_errors


def test_apply_rule_unit_review_decisions_refuses_no_decisions(project_root: Path) -> None:
    """Apply step does not rewrite rule units when no decisions exist."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)

    try:
        apply_rule_unit_review_decisions(project_root)
    except ValueError as exc:
        assert "no review decisions" in str(exc)
    else:
        raise AssertionError("apply accepted an empty decision log")


def test_apply_rule_unit_review_decisions_quarantines_with_snapshot(project_root: Path) -> None:
    """A quarantine decision removes the rule unit and snapshots the prior JSONL."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)
    queue_row = next(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl")
    )
    append_rule_unit_review_decision(
        project_root,
        review_id=queue_row["review_id"],
        outcome="quarantine",
        decided_by="unit-test",
        rationale="Entity capture is too broad.",
    )

    result = apply_rule_unit_review_decisions(project_root)
    rows = list(iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units.jsonl"))
    snapshots = list((project_root / "_SNAPSHOTS").rglob("rule_units.jsonl"))

    assert result.applied
    assert result.changes_applied == 1
    assert result.resulting_rule_units == 0
    assert rows == []
    assert snapshots


def test_apply_rule_unit_review_decisions_revises_with_valid_replacement(
    project_root: Path,
) -> None:
    """A revise decision replaces one rule unit with its validated replacement."""

    _write_needs_review_fixture(project_root)
    generate_ccr_rule_units(project_root)
    queue_row = next(
        iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl")
    )
    replacement = {
        **queue_row["current_rule_unit"],
        "id": f"{queue_row['rule_unit_id']}_REV_0001",
        "regulated_entity": "A permit holder",
        "action_required": queue_row["source_sentence"],
        "plain_english_summary": queue_row["source_sentence"],
    }
    append_rule_unit_review_decision(
        project_root,
        review_id=queue_row["review_id"],
        outcome="revise",
        decided_by="unit-test",
        rationale="Narrow regulated entity to source-backed phrase.",
        proposed_rule_units=[replacement],
    )

    result = apply_rule_unit_review_decisions(project_root)
    rows = list(iter_jsonl(project_root / "02_Regulations_CCR" / "_meta" / "rule_units.jsonl"))

    assert result.applied
    assert result.source_rule_units == 1
    assert result.resulting_rule_units == 1
    assert rows[0]["id"] == replacement["id"]
    assert rows[0]["regulated_entity"] == "A permit holder"


def test_generate_ccr_rule_units_dry_run_does_not_write(project_root: Path) -> None:
    """Dry runs validate extraction without creating the product-read file."""

    rules_dir = project_root / "02_Regulations_CCR" / "_rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (project_root / "02_Regulations_CCR" / "_index.jsonl").write_text(
        json.dumps({"id": "1_CCR_101-1"}) + "\n",
        encoding="utf-8",
    )
    (rules_dir / "1_CCR_101-1.md").write_text(
        "A State Agency shall document each commitment voucher before payment.",
        encoding="utf-8",
    )

    summary = generate_ccr_rule_units(project_root, dry_run=True)

    assert summary.rule_units == 1
    assert not (project_root / "02_Regulations_CCR" / "_meta" / "rule_units.jsonl").exists()
    assert not (project_root / "02_Regulations_CCR" / "_meta" / "rule_units_quality.jsonl").exists()
    assert not (
        project_root / "02_Regulations_CCR" / "_meta" / "rule_units_review_queue.jsonl"
    ).exists()


def _write_needs_review_fixture(project_root: Path) -> None:
    """Write one fixture record that produces a needs-review queue item."""

    rules_dir = project_root / "02_Regulations_CCR" / "_rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (project_root / "02_Regulations_CCR" / "_index.jsonl").write_text(
        json.dumps({"id": "5_CCR_1001-9"}) + "\n",
        encoding="utf-8",
    )
    (rules_dir / "5_CCR_1001-9.md").write_text(
        """
APPLICABILITY
person shall submit an annual report to the division before operating the facility.
""",
        encoding="utf-8",
    )
