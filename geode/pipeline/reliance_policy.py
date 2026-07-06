"""Build the production reliance policy for reviewed Geode outputs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from geode.utils.file_io import atomic_write_json

RELIANCE_POLICY_PATH = Path("_CONTROL_PLANE/RELIANCE_POLICY.json")
RELIANCE_POLICY_VERSION = "2026-07-01"

ApprovalLevel = Literal["research_only", "internal_review", "production_reliance"]


class ReviewerRole(BaseModel):
    """One reviewer role in the reliance workflow."""

    role_id: str
    label: str
    may_log_decisions: bool
    may_apply_canonical_changes: bool
    may_approve_external_reliance: bool
    description: str


class ApprovalCriterion(BaseModel):
    """One criterion required before an output can be relied on."""

    criterion_id: str
    label: str
    required_for: ApprovalLevel
    description: str


class RelianceBoundary(BaseModel):
    """Boundary text for a class of output."""

    output_type: str
    default_level: ApprovalLevel
    boundary: str


class ReliancePolicy(BaseModel):
    """Machine-readable reliance policy for Geode review outputs."""

    policy_id: str
    version: str
    generated_at: datetime
    purpose: str
    reviewer_roles: list[ReviewerRole] = Field(min_length=1)
    approval_criteria: list[ApprovalCriterion] = Field(min_length=1)
    reliance_boundaries: list[RelianceBoundary] = Field(min_length=1)
    external_use_limits: list[str] = Field(min_length=1)
    canonical_change_rules: list[str] = Field(min_length=1)
    approval_levels: list[ApprovalLevel] = Field(min_length=1)


def build_reliance_policy() -> ReliancePolicy:
    """Build the current production reliance policy."""

    return ReliancePolicy(
        policy_id="GEODE-RELIANCE-POLICY",
        version=RELIANCE_POLICY_VERSION,
        generated_at=datetime.now(timezone.utc),
        purpose=(
            "Define when Geode review outputs are research-only, when they are ready for "
            "internal review, and when they may support externally relied-on guidance."
        ),
        approval_levels=["research_only", "internal_review", "production_reliance"],
        reviewer_roles=[
            ReviewerRole(
                role_id="data_reviewer",
                label="Data Reviewer",
                may_log_decisions=True,
                may_apply_canonical_changes=False,
                may_approve_external_reliance=False,
                description="Reviews source fidelity, extraction quality, and packet completeness.",
            ),
            ReviewerRole(
                role_id="corpus_maintainer",
                label="Corpus Maintainer",
                may_log_decisions=True,
                may_apply_canonical_changes=True,
                may_approve_external_reliance=False,
                description="Applies reviewed canonical changes through guarded commands only.",
            ),
            ReviewerRole(
                role_id="legal_reviewer",
                label="Legal Reviewer",
                may_log_decisions=True,
                may_apply_canonical_changes=False,
                may_approve_external_reliance=True,
                description="Approves whether reviewed outputs may support externally relied-on guidance.",
            ),
        ],
        approval_criteria=[
            ApprovalCriterion(
                criterion_id="source_fidelity",
                label="Source fidelity",
                required_for="internal_review",
                description="Every claim must be traceable to the cited source sentence or document.",
            ),
            ApprovalCriterion(
                criterion_id="canonical_validation",
                label="Canonical validation",
                required_for="internal_review",
                description="Any canonical change must validate against the rule-unit schema.",
            ),
            ApprovalCriterion(
                criterion_id="review_decision_logged",
                label="Review decision logged",
                required_for="internal_review",
                description="A packet must have an append-only review decision before canonical apply.",
            ),
            ApprovalCriterion(
                criterion_id="legal_reviewer_approval",
                label="Legal reviewer approval",
                required_for="production_reliance",
                description="Externally relied-on guidance requires explicit legal reviewer approval.",
            ),
        ],
        reliance_boundaries=[
            RelianceBoundary(
                output_type="review_packet",
                default_level="research_only",
                boundary=(
                    "Review packets organize extraction review. They are not legal advice and do "
                    "not change canonical law."
                ),
            ),
            RelianceBoundary(
                output_type="compliance_path",
                default_level="research_only",
                boundary=(
                    "Compliance paths are source-backed review workflows and do not replace legal review."
                ),
            ),
            RelianceBoundary(
                output_type="canonical_rule_unit",
                default_level="internal_review",
                boundary=(
                    "Canonical rule units are structured extraction records. External reliance still "
                    "requires legal reviewer approval."
                ),
            ),
        ],
        external_use_limits=[
            "Do not present Geode outputs as legal advice.",
            "Do not externally rely on pending review packets.",
            "Do not apply canonical changes without validated review decisions.",
            "Do not treat popularity, score, or confidence as legal authority.",
            "Do not remove the source citation or reliance boundary from exported guidance.",
        ],
        canonical_change_rules=[
            "Canonical changes must use the guarded apply path.",
            "The prior canonical file must be snapshotted before replacement.",
            "Replacement rule units must pass schema validation before apply.",
            "Approve-only decisions do not rewrite canonical rule units.",
        ],
    )


def write_reliance_policy(root: Path) -> ReliancePolicy:
    """Write the current reliance policy to the control plane."""

    resolved_root = root.resolve()
    policy = build_reliance_policy()
    atomic_write_json(resolved_root / RELIANCE_POLICY_PATH, policy, resolved_root)
    return policy


def main() -> None:
    """Build or write the reliance policy."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    policy = write_reliance_policy(Path(args.root)) if args.write else build_reliance_policy()
    if args.json:
        print(policy.model_dump_json(indent=2))
        return
    print(f"Reliance policy: {policy.policy_id} {policy.version}")


if __name__ == "__main__":
    main()
