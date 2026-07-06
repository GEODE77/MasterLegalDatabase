"""Tests for the Geode reliance policy."""

from __future__ import annotations

from pathlib import Path

from geode.pipeline.reliance_policy import build_reliance_policy, write_reliance_policy


def test_reliance_policy_defines_roles_criteria_and_limits() -> None:
    """The reliance policy defines roles, approval criteria, and external-use limits."""

    policy = build_reliance_policy()

    assert policy.policy_id == "GEODE-RELIANCE-POLICY"
    assert any(role.may_approve_external_reliance for role in policy.reviewer_roles)
    assert any(role.may_apply_canonical_changes for role in policy.reviewer_roles)
    assert any(
        criterion.required_for == "production_reliance"
        for criterion in policy.approval_criteria
    )
    assert any("legal advice" in limit for limit in policy.external_use_limits)


def test_write_reliance_policy_writes_control_plane_file(tmp_path: Path) -> None:
    """The reliance policy writes to the control plane."""

    policy = write_reliance_policy(tmp_path)

    assert policy.version
    assert (tmp_path / "_CONTROL_PLANE" / "RELIANCE_POLICY.json").exists()
