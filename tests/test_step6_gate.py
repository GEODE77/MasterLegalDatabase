"""Tests for the Step 6 readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.reviewer_operations import write_reviewer_operations
from geode.validation.step6_gate import (
    build_step6_readiness_report,
    write_step6_readiness_report,
)


def test_step6_gate_passes_with_reviewer_operations(tmp_path: Path) -> None:
    """Step 6 passes when backend reviewer operations are present."""

    _write_step6_fixture(tmp_path)

    report = write_step6_readiness_report(tmp_path)

    assert report.ready_for_step_6_completion
    assert not report.blockers
    assert any(item.id == "STEP6-NAME-REVIEWERS" for item in report.deferred_items)
    assert (tmp_path / "_CONTROL_PLANE" / "STEP6_READINESS_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "STEP6_DEFERRED_QUEUE.json").exists()


def test_step6_gate_blocks_without_assignments(tmp_path: Path) -> None:
    """Step 6 blocks when reviewer assignments are missing."""

    _write_step6_fixture(tmp_path, write_assignments=False)

    report = build_step6_readiness_report(tmp_path)

    assert not report.ready_for_step_6_completion
    assert any("Reviewer assignment slots" in blocker for blocker in report.blockers)


def _write_step6_fixture(root: Path, *, write_assignments: bool = True) -> None:
    """Write a minimal Step 6-ready fixture."""

    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "STEP5_READINESS_REPORT.json").write_text(
        json.dumps({"ready_for_step_5_completion": True}),
        encoding="utf-8",
    )
    _write_policy(root)
    if write_assignments:
        write_reviewer_operations(root)


def _write_policy(root: Path) -> None:
    """Write a minimal reliance policy."""

    (root / "_CONTROL_PLANE" / "RELIANCE_POLICY.json").write_text(
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

