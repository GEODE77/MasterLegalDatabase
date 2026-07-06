"""Tests for reviewer operations artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.reviewer_operations import (
    build_reviewer_assignments,
    write_reviewer_operations,
)


def test_reviewer_assignments_create_unassigned_role_slots(tmp_path: Path) -> None:
    """Reviewer operations prepare role slots without inventing people."""

    _write_policy(tmp_path)

    assignments = build_reviewer_assignments(tmp_path)

    assert len(assignments.assignments) == 3
    assert {item.role_id for item in assignments.assignments} == {
        "corpus_maintainer",
        "data_reviewer",
        "legal_reviewer",
    }
    assert all(item.assignment_status == "unassigned" for item in assignments.assignments)
    assert all(item.assigned_to is None for item in assignments.assignments)
    assert all(item.name is None for item in assignments.assignments)
    assert all(item.email is None for item in assignments.assignments)
    assert all(item.effective_date is None for item in assignments.assignments)
    assert all(item.reliance_policy_back_reference for item in assignments.assignments)


def test_write_reviewer_operations_writes_assignment_summary_and_sop(tmp_path: Path) -> None:
    """Reviewer operations write the registry, summary, and SOP."""

    _write_policy(tmp_path)

    summary = write_reviewer_operations(tmp_path)

    assert summary.required_roles == 3
    assert summary.unassigned_roles == 3
    assert summary.ready_for_human_assignment
    assert (tmp_path / "_CONTROL_PLANE" / "REVIEWER_ASSIGNMENTS.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "REVIEWER_OPERATIONS_SUMMARY.json").exists()
    assert (tmp_path / "docs" / "GEODE_REVIEWER_SOP.md").exists()


def _write_policy(root: Path) -> None:
    """Write a minimal reliance policy."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "RELIANCE_POLICY.json").write_text(
        json.dumps(
            {
                "policy_id": "GEODE-RELIANCE-POLICY",
                "version": "test",
                "reviewer_roles": [
                    {
                        "role_id": "data_reviewer",
                        "label": "Data Reviewer",
                        "may_log_decisions": True,
                    },
                    {
                        "role_id": "corpus_maintainer",
                        "label": "Corpus Maintainer",
                        "may_apply_canonical_changes": True,
                        "may_log_decisions": True,
                    },
                    {
                        "role_id": "legal_reviewer",
                        "label": "Legal Reviewer",
                        "may_approve_external_reliance": True,
                        "may_log_decisions": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
