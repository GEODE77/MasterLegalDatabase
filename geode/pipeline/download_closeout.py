"""Download closeout checklist for Project Geode."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Sequence

from geode.validation.secret_safety import format_findings, scan_paths, scan_staged


PASS = "pass"
WARN = "warn"
FAIL = "fail"


@dataclass(frozen=True)
class CloseoutCheck:
    """One download closeout check result."""

    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class CloseoutReport:
    """Download closeout checklist report."""

    generated_at: str
    overall_status: str
    checks: list[CloseoutCheck]


def run_closeout(root: Path, today: date | None = None) -> CloseoutReport:
    """Run all download closeout checks."""

    resolved_root = root.resolve()
    check_date = today or datetime.now(UTC).date()
    checks = [
        check_no_secrets(resolved_root),
        check_no_pending_downloads(resolved_root),
        check_dashboard_updated(resolved_root, check_date),
        check_git_pushed(resolved_root),
    ]
    return CloseoutReport(
        generated_at=datetime.now(UTC).isoformat(),
        overall_status=overall_status(checks),
        checks=checks,
    )


def check_no_secrets(root: Path) -> CloseoutCheck:
    """Confirm changed and staged files do not contain likely secrets."""

    findings = scan_staged(root)
    findings.extend(scan_paths(root / path for path in changed_working_tree_paths(root)))
    if findings:
        return CloseoutCheck(
            name="no_secrets",
            status=FAIL,
            detail=format_findings(findings),
        )
    return CloseoutCheck(
        name="no_secrets",
        status=PASS,
        detail="No likely API keys or tokens found in staged or changed text files.",
    )


def check_no_pending_downloads(root: Path) -> CloseoutCheck:
    """Confirm download queues do not have active retry work."""

    problems: list[str] = []
    warnings: list[str] = []
    summary_path = root / "03_Legislation" / "_documents" / "bill_document_summary.json"
    if summary_path.exists():
        summary = read_json(summary_path)
        for field in ("pending", "pending_retry", "run_failed"):
            value = int(summary.get(field, 0) or 0)
            if value:
                problems.append(f"{summary_path}: {field} is {value}.")
    else:
        warnings.append(f"{summary_path} does not exist.")

    blocked_queue_path = root / "_CONTROL_PLANE" / "BLOCKED_DOWNLOAD_QUEUE.json"
    if blocked_queue_path.exists():
        blocked_queue = read_json(blocked_queue_path)
        open_items = int(blocked_queue.get("open_items", 0) or 0)
        if open_items:
            warnings.append(
                f"{blocked_queue_path}: {open_items} known blocked download item remains."
            )

    freshness_path = root / "_CONTROL_PLANE" / "FRESHNESS_VERIFICATION_QUEUE.json"
    if freshness_path.exists():
        freshness = read_json(freshness_path)
        pending_items = int(freshness.get("pending_items", 0) or 0)
        if pending_items:
            warnings.append(
                f"{freshness_path}: {pending_items} known future freshness item remains."
            )

    if problems:
        return CloseoutCheck(name="no_pending_downloads", status=FAIL, detail=" ".join(problems))
    if warnings:
        return CloseoutCheck(name="no_pending_downloads", status=WARN, detail=" ".join(warnings))
    return CloseoutCheck(
        name="no_pending_downloads",
        status=PASS,
        detail="No active pending or retry downloads found in known download summaries.",
    )


def check_dashboard_updated(root: Path, today: date) -> CloseoutCheck:
    """Confirm the next-download dashboard was updated today."""

    dashboard_path = root / "_CONTROL_PLANE" / "NEXT_DOWNLOAD_DASHBOARD.json"
    if not dashboard_path.exists():
        return CloseoutCheck(
            name="dashboard_updated",
            status=FAIL,
            detail=f"{dashboard_path} does not exist.",
        )
    dashboard = read_json(dashboard_path)
    generated_at = str(dashboard.get("generated_at", ""))
    next_actions = dashboard.get("next_actions", [])
    recommendation = dashboard.get("overall_recommendation")
    if not generated_at.startswith(today.isoformat()):
        return CloseoutCheck(
            name="dashboard_updated",
            status=FAIL,
            detail=f"{dashboard_path} generated_at is {generated_at}, not {today.isoformat()}.",
        )
    if not recommendation or not isinstance(next_actions, list) or not next_actions:
        return CloseoutCheck(
            name="dashboard_updated",
            status=FAIL,
            detail=f"{dashboard_path} is missing the next recommendation or next actions.",
        )
    return CloseoutCheck(
        name="dashboard_updated",
        status=PASS,
        detail="Next download dashboard is dated today and has a next recommendation.",
    )


def check_git_pushed(root: Path) -> CloseoutCheck:
    """Confirm local branch has no unpushed or uncommitted closeout work."""

    status = git(root, ["status", "--porcelain"])
    if status:
        return CloseoutCheck(
            name="git_pushed",
            status=FAIL,
            detail="Working tree has uncommitted changes.",
        )

    upstream = git(root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if not upstream:
        return CloseoutCheck(name="git_pushed", status=FAIL, detail="Current branch has no upstream.")

    local_head = git(root, ["rev-parse", "HEAD"])
    upstream_head = git(root, ["rev-parse", "@{u}"])
    if local_head != upstream_head:
        return CloseoutCheck(
            name="git_pushed",
            status=FAIL,
            detail=f"Local HEAD is not pushed to {upstream}.",
        )
    return CloseoutCheck(
        name="git_pushed",
        status=PASS,
        detail=f"Current branch is clean and matches {upstream}.",
    )


def changed_working_tree_paths(root: Path) -> list[Path]:
    """Return changed or untracked working-tree paths."""

    changed = git(root, ["diff", "--name-only", "--diff-filter=ACMRT"]).splitlines()
    untracked = git(root, ["ls-files", "--others", "--exclude-standard"]).splitlines()
    return [Path(path) for path in [*changed, *untracked] if path.strip()]


def overall_status(checks: Sequence[CloseoutCheck]) -> str:
    """Return the combined checklist status."""

    if any(check.status == FAIL for check in checks):
        return FAIL
    if any(check.status == WARN for check in checks):
        return WARN
    return PASS


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file."""

    return json.loads(path.read_text(encoding="utf-8"))


def git(root: Path, args: Sequence[str]) -> str:
    """Run a Git command and return trimmed output."""

    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def report_to_text(report: CloseoutReport) -> str:
    """Format a closeout report for people."""

    lines = [
        f"Download closeout checklist: {report.overall_status.upper()}",
        f"Generated at: {report.generated_at}",
    ]
    for check in report.checks:
        lines.append(f"- {check.name}: {check.status.upper()} - {check.detail}")
    return "\n".join(lines)


def write_report(path: Path, report: CloseoutReport) -> None:
    """Write the closeout report as JSON."""

    payload = {
        "generated_at": report.generated_at,
        "overall_status": report.overall_status,
        "checks": [asdict(check) for check in report.checks],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--write-report", type=Path, help="Optional JSON report output path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the download closeout checklist."""

    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_closeout(args.root)
    if args.write_report:
        write_report(args.write_report, report)
    if args.json:
        print(json.dumps({"overall_status": report.overall_status, "checks": [asdict(check) for check in report.checks]}, indent=2))
    else:
        print(report_to_text(report))
    if report.overall_status == FAIL:
        return 1
    if args.strict and report.overall_status == WARN:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
