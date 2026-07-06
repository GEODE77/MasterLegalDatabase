"""Build reviewer assignment slots and operating SOP for Geode review work."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from geode.utils.file_io import atomic_write_json, atomic_write_text, load_json

RELIANCE_POLICY_PATH = Path("_CONTROL_PLANE/RELIANCE_POLICY.json")
REVIEWER_ASSIGNMENTS_PATH = Path("_CONTROL_PLANE/REVIEWER_ASSIGNMENTS.json")
REVIEWER_OPERATIONS_SUMMARY_PATH = Path("_CONTROL_PLANE/REVIEWER_OPERATIONS_SUMMARY.json")
REVIEWER_SOP_PATH = Path("docs/GEODE_REVIEWER_SOP.md")

AssignmentStatus = Literal["unassigned", "assigned"]


class ReviewerAssignment(BaseModel):
    """One reviewer assignment slot."""

    role_id: str
    label: str
    assignment_status: AssignmentStatus
    assigned_to: str | None = None
    name: str | None = None
    email: str | None = None
    effective_date: str | None = None
    revocation_date: str | None = None
    reliance_policy_back_reference: str
    responsibilities: list[str] = Field(default_factory=list)
    escalation_path: list[str] = Field(default_factory=list)
    can_log_decisions: bool
    can_apply_canonical_changes: bool
    can_approve_external_reliance: bool


class ReviewerAssignments(BaseModel):
    """Reviewer assignment registry."""

    generated_at: datetime
    source_policy_id: str
    source_policy_version: str
    assignments: list[ReviewerAssignment]
    assignment_boundary: str


class ReviewerOperationsSummary(BaseModel):
    """Summary for reviewer operations readiness."""

    generated_at: datetime
    assignment_path: str
    sop_path: str
    required_roles: int = Field(ge=0)
    assigned_roles: int = Field(ge=0)
    unassigned_roles: int = Field(ge=0)
    ready_for_human_assignment: bool
    boundary: str


def build_reviewer_assignments(root: Path) -> ReviewerAssignments:
    """Build reviewer assignment slots from the reliance policy."""

    resolved_root = root.resolve()
    policy = _load_policy(resolved_root)
    roles = policy.get("reviewer_roles") if isinstance(policy.get("reviewer_roles"), list) else []
    policy_id = str(policy.get("policy_id") or "unknown")
    policy_version = str(policy.get("version") or "unknown")
    assignments = [
        _assignment_from_role(role, policy_id, policy_version)
        for role in roles
        if isinstance(role, dict)
    ]
    return ReviewerAssignments(
        generated_at=datetime.now(timezone.utc),
        source_policy_id=policy_id,
        source_policy_version=policy_version,
        assignments=assignments,
        assignment_boundary=(
            "Reviewer slots are prepared but no real person is assigned until a project owner "
            "authorizes named reviewers."
        ),
    )


def build_reviewer_operations_summary(assignments: ReviewerAssignments) -> ReviewerOperationsSummary:
    """Build reviewer operations summary."""

    assigned = sum(item.assignment_status == "assigned" for item in assignments.assignments)
    total = len(assignments.assignments)
    return ReviewerOperationsSummary(
        generated_at=datetime.now(timezone.utc),
        assignment_path=REVIEWER_ASSIGNMENTS_PATH.as_posix(),
        sop_path=REVIEWER_SOP_PATH.as_posix(),
        required_roles=total,
        assigned_roles=assigned,
        unassigned_roles=total - assigned,
        ready_for_human_assignment=total > 0,
        boundary=assignments.assignment_boundary,
    )


def write_reviewer_operations(root: Path) -> ReviewerOperationsSummary:
    """Write reviewer assignment slots, SOP, and summary."""

    resolved_root = root.resolve()
    assignments = build_reviewer_assignments(resolved_root)
    summary = build_reviewer_operations_summary(assignments)
    atomic_write_json(resolved_root / REVIEWER_ASSIGNMENTS_PATH, assignments, resolved_root)
    atomic_write_json(resolved_root / REVIEWER_OPERATIONS_SUMMARY_PATH, summary, resolved_root)
    atomic_write_text(resolved_root / REVIEWER_SOP_PATH, _render_sop(assignments), resolved_root)
    return summary


def _assignment_from_role(
    role: dict[str, Any],
    policy_id: str = "GEODE-RELIANCE-POLICY",
    policy_version: str = "unknown",
) -> ReviewerAssignment:
    """Build an unassigned reviewer slot from one policy role."""

    role_id = str(role.get("role_id") or "unknown")
    return ReviewerAssignment(
        role_id=role_id,
        label=str(role.get("label") or role_id),
        assignment_status="unassigned",
        assigned_to=None,
        name=None,
        email=None,
        effective_date=None,
        revocation_date=None,
        reliance_policy_back_reference=f"{policy_id}@{policy_version}#{role_id}",
        responsibilities=_responsibilities_for_role(role_id),
        escalation_path=_escalation_path_for_role(role_id),
        can_log_decisions=bool(role.get("may_log_decisions")),
        can_apply_canonical_changes=bool(role.get("may_apply_canonical_changes")),
        can_approve_external_reliance=bool(role.get("may_approve_external_reliance")),
    )


def _responsibilities_for_role(role_id: str) -> list[str]:
    """Return default responsibilities for one reviewer role."""

    responsibilities = {
        "data_reviewer": [
            "Review packet source fidelity.",
            "Confirm extraction quality issues before logging a decision.",
            "Escalate unclear legal meaning instead of interpreting it.",
        ],
        "corpus_maintainer": [
            "Apply only validated canonical changes.",
            "Confirm snapshot and guarded apply behavior before writing canonical files.",
            "Stop apply work when replacement records fail validation.",
        ],
        "legal_reviewer": [
            "Approve or reject production reliance on reviewed outputs.",
            "Confirm that external guidance preserves citations and reliance boundaries.",
            "Escalate unresolved ambiguity before external use.",
        ],
    }
    return responsibilities.get(role_id, ["Review assigned work under the reliance policy."])


def _escalation_path_for_role(role_id: str) -> list[str]:
    """Return the escalation path for one reviewer role."""

    if role_id == "data_reviewer":
        return ["corpus_maintainer", "legal_reviewer"]
    if role_id == "corpus_maintainer":
        return ["legal_reviewer"]
    if role_id == "legal_reviewer":
        return ["project_owner"]
    return ["project_owner"]


def _render_sop(assignments: ReviewerAssignments) -> str:
    """Render the reviewer operating SOP."""

    lines = [
        "# Geode Reviewer SOP",
        "",
        "## Purpose",
        "",
        (
            "This SOP explains how review packets, review decisions, canonical apply, and "
            "external reliance should be handled."
        ),
        "",
        "## Non-Negotiable Boundaries",
        "",
        "- Do not treat review packets as legal advice.",
        "- Do not assign a reviewer without project-owner authorization.",
        "- Do not change canonical rule units outside the guarded apply path.",
        "- Do not externally rely on pending packets.",
        "- Do not remove source citations or reliance boundaries from reviewed outputs.",
        "",
        "## Reviewer Roles",
        "",
    ]
    for assignment in assignments.assignments:
        lines.extend(
            [
                f"### {assignment.label}",
                "",
                f"- Status: {assignment.assignment_status}",
                f"- Assigned to: {assignment.assigned_to or 'unassigned'}",
                f"- May log decisions: {'yes' if assignment.can_log_decisions else 'no'}",
                (
                    "- May apply canonical changes: "
                    f"{'yes' if assignment.can_apply_canonical_changes else 'no'}"
                ),
                (
                    "- May approve external reliance: "
                    f"{'yes' if assignment.can_approve_external_reliance else 'no'}"
                ),
                "",
                "Responsibilities:",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in assignment.responsibilities)
        lines.extend(["", "Escalation path:", ""])
        lines.extend(f"- {item}" for item in assignment.escalation_path)
        lines.append("")
    lines.extend(
        [
            "## Operating Flow",
            "",
            "1. Start with `/app/review-packets` to select a pending packet.",
            "2. Confirm the source sentence and quality issue.",
            "3. Use `/app/review` to log approve, revise, split, or quarantine decisions.",
            "4. Rebuild the guarded apply proposal after decisions are logged.",
            "5. Apply canonical changes only when replacements validate and authorization exists.",
            "6. Seek legal reviewer approval before external reliance.",
            "",
            "## Current Boundary",
            "",
            assignments.assignment_boundary,
            "",
        ]
    )
    return "\n".join(lines)


def _load_policy(root: Path) -> dict[str, Any]:
    """Load the reliance policy."""

    path = root / RELIANCE_POLICY_PATH
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    """Build or write reviewer operations artifacts."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    summary = (
        write_reviewer_operations(root)
        if args.write
        else build_reviewer_operations_summary(build_reviewer_assignments(root))
    )
    if args.json:
        print(summary.model_dump_json(indent=2))
        return
    print(f"Reviewer roles ready for assignment: {summary.required_roles}")


if __name__ == "__main__":
    main()
