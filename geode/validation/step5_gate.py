"""Step 5 readiness gate for production reliance policy."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, load_json

STEP5_REPORT_NAME = "STEP5_READINESS_REPORT.json"
STEP5_QUEUE_NAME = "STEP5_DEFERRED_QUEUE.json"


class Step5Check(BaseModel):
    """One Step 5 readiness check."""

    name: str
    ready: bool
    detail: str


class Step5DeferredItem(BaseModel):
    """A Step 5 item that remains queued after the policy foundation is ready."""

    id: str
    title: str
    reason: str
    next_action: str


class Step5ReadinessReport(BaseModel):
    """Overall Step 5 readiness report."""

    generated_at: datetime
    ready_for_step_5_completion: bool
    checks: list[Step5Check]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    deferred_items: list[Step5DeferredItem] = Field(default_factory=list)
    next_step: str


def build_step5_readiness_report(root: Path) -> Step5ReadinessReport:
    """Build the Step 5 gate report from reliance-policy evidence."""

    resolved_root = root.resolve()
    checks = [
        _check_step4_ready(resolved_root),
        _check_policy_exists(resolved_root),
        _check_roles(resolved_root),
        _check_approval_criteria(resolved_root),
        _check_external_limits(resolved_root),
        _check_policy_api(resolved_root),
        _check_policy_ui(resolved_root),
    ]
    blockers = [check.detail for check in checks if not check.ready]
    warnings = _warnings()
    deferred_items = _deferred_items()
    ready = not blockers
    next_step = (
        "Step 5 reliance policy is complete; review packets can now be worked under explicit boundaries."
        if ready
        else "Finish the blocking Step 5 checks, then rerun this gate."
    )
    return Step5ReadinessReport(
        generated_at=datetime.now(timezone.utc),
        ready_for_step_5_completion=ready,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        deferred_items=deferred_items,
        next_step=next_step,
    )


def write_step5_readiness_report(root: Path) -> Step5ReadinessReport:
    """Write the Step 5 report and deferred queue to the control plane."""

    resolved_root = root.resolve()
    report = build_step5_readiness_report(resolved_root)
    atomic_write_json(resolved_root / CONTROL_PLANE_DIR / STEP5_REPORT_NAME, report, resolved_root)
    atomic_write_json(
        resolved_root / CONTROL_PLANE_DIR / STEP5_QUEUE_NAME,
        {
            "generated_at": report.generated_at.isoformat(),
            "items": [item.model_dump(mode="json") for item in report.deferred_items],
        },
        resolved_root,
    )
    return report


def _check_step4_ready(root: Path) -> Step5Check:
    """Check that Step 4 passed before Step 5 is marked complete."""

    report_path = root / CONTROL_PLANE_DIR / "STEP4_READINESS_REPORT.json"
    if not report_path.exists():
        return Step5Check(
            name="Step 4 gate",
            ready=False,
            detail="Step 4 readiness report is missing.",
        )
    payload = load_json(report_path)
    ready = bool(payload.get("ready_for_step_4_completion")) if isinstance(payload, dict) else False
    return Step5Check(
        name="Step 4 gate",
        ready=ready,
        detail="Step 4 gate is clean." if ready else "Step 4 gate is not complete.",
    )


def _check_policy_exists(root: Path) -> Step5Check:
    """Check that the reliance policy exists."""

    policy = _policy(root)
    ready = bool(policy.get("policy_id") and policy.get("version"))
    return Step5Check(
        name="Reliance policy",
        ready=ready,
        detail=(
            "Reliance policy exists with ID and version."
            if ready
            else "Reliance policy is missing ID or version."
        ),
    )


def _check_roles(root: Path) -> Step5Check:
    """Check reviewer role coverage."""

    roles = _policy(root).get("reviewer_roles") or []
    has_legal = any(
        isinstance(role, dict) and role.get("may_approve_external_reliance") for role in roles
    )
    has_maintainer = any(
        isinstance(role, dict) and role.get("may_apply_canonical_changes") for role in roles
    )
    ready = len(roles) >= 3 and has_legal and has_maintainer
    return Step5Check(
        name="Reviewer roles",
        ready=ready,
        detail=(
            "Reviewer roles cover data review, canonical apply, and external reliance approval."
            if ready
            else "Reviewer roles do not cover all required approvals."
        ),
    )


def _check_approval_criteria(root: Path) -> Step5Check:
    """Check approval criteria for internal and external reliance."""

    criteria = _policy(root).get("approval_criteria") or []
    required_for = {
        criterion.get("required_for")
        for criterion in criteria
        if isinstance(criterion, dict)
    }
    ready = "internal_review" in required_for and "production_reliance" in required_for
    return Step5Check(
        name="Approval criteria",
        ready=ready,
        detail=(
            "Approval criteria cover internal review and production reliance."
            if ready
            else "Approval criteria do not cover both internal review and production reliance."
        ),
    )


def _check_external_limits(root: Path) -> Step5Check:
    """Check external use limits and canonical change rules."""

    policy = _policy(root)
    limits = policy.get("external_use_limits") or []
    rules = policy.get("canonical_change_rules") or []
    limit_text = " ".join(str(limit) for limit in limits).lower()
    rules_text = " ".join(str(rule) for rule in rules).lower()
    ready = (
        "legal advice" in limit_text
        and "canonical changes" in limit_text
        and "guarded apply" in rules_text
        and "schema validation" in rules_text
    )
    return Step5Check(
        name="External-use limits",
        ready=ready,
        detail=(
            "External-use limits and canonical-change rules are explicit."
            if ready
            else "External-use limits or canonical-change rules are incomplete."
        ),
    )


def _check_policy_api(root: Path) -> Step5Check:
    """Check that product API access exists for the reliance policy."""

    route = root / "geode" / "web" / "src" / "app" / "api" / "product" / "reliance-policy" / "route.ts"
    return _check_file_markers("Reliance policy API", route, ("getReliancePolicy", "policy"))


def _check_policy_ui(root: Path) -> Step5Check:
    """Check that product UI access exists for the reliance policy."""

    page = root / "geode" / "web" / "src" / "app" / "app" / "reliance-policy" / "page.tsx"
    return _check_file_markers(
        "Reliance policy UI",
        page,
        ("Reliance Policy", "reviewerRoles", "external reliance"),
    )


def _check_file_markers(name: str, path: Path, markers: tuple[str, ...]) -> Step5Check:
    """Check that a file exists and contains required implementation markers."""

    ready = _file_has_markers(path, markers)
    return Step5Check(
        name=name,
        ready=ready,
        detail=(
            f"{name} implementation markers are present."
            if ready
            else f"{name} implementation markers are missing."
        ),
    )


def _file_has_markers(path: Path, markers: tuple[str, ...]) -> bool:
    """Return whether a file contains all required markers."""

    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return all(marker in content for marker in markers)


def _policy(root: Path) -> dict[str, object]:
    """Load the reliance policy as a dictionary."""

    path = root / CONTROL_PLANE_DIR / "RELIANCE_POLICY.json"
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _warnings() -> list[str]:
    """Return non-blocking Step 5 warnings."""

    return [
        "The policy defines approval boundaries, but actual packet decisions remain pending.",
    ]


def _deferred_items() -> list[Step5DeferredItem]:
    """Return queued work after reliance policy is ready."""

    return [
        Step5DeferredItem(
            id="STEP5-ASSIGN-REVIEWERS",
            title="Assign real reviewers to roles",
            reason="The policy defines roles, but named reviewers have not been assigned.",
            next_action="Assign data reviewers, corpus maintainers, and legal reviewers.",
        ),
        Step5DeferredItem(
            id="STEP5-WORK-PACKETS",
            title="Work the formal review packets",
            reason="The 532 review packets still require actual decisions.",
            next_action="Use /app/review-packets and /app/review to log packet decisions.",
        ),
        Step5DeferredItem(
            id="STEP5-PUBLISH-RELIANCE-SOP",
            title="Publish an operating SOP",
            reason="The machine-readable policy exists, but operational SOP training is separate.",
            next_action="Write reviewer training and escalation instructions for production use.",
        ),
    ]


def main() -> None:
    """Run the Step 5 gate."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    report = write_step5_readiness_report(root) if args.write else build_step5_readiness_report(root)
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Ready for Step 5 completion: {report.ready_for_step_5_completion}")
    for check in report.checks:
        status = "ready" if check.ready else "blocked"
        print(f"- {check.name}: {status} - {check.detail}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
