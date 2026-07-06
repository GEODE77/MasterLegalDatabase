"""Step 9 readiness gate for relationship coverage before visual graph work."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json

STEP9_REPORT_NAME = "STEP9_READINESS_REPORT.json"
STEP9_QUEUE_NAME = "STEP9_DEFERRED_QUEUE.json"


class Step9Check(BaseModel):
    """One Step 9 readiness check."""

    name: str
    ready: bool
    detail: str


class Step9DeferredItem(BaseModel):
    """A Step 9 item that remains queued after relationship coverage exists."""

    id: str
    title: str
    reason: str
    next_action: str


class Step9ReadinessReport(BaseModel):
    """Overall Step 9 readiness report."""

    generated_at: datetime
    ready_for_step_9_completion: bool
    checks: list[Step9Check]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    deferred_items: list[Step9DeferredItem] = Field(default_factory=list)
    next_step: str


def build_step9_readiness_report(root: Path) -> Step9ReadinessReport:
    """Build the Step 9 gate report from relationship coverage evidence."""

    resolved_root = root.resolve()
    checks = [
        _check_step8_ready(resolved_root),
        _check_coverage_jsonl(resolved_root),
        _check_coverage_report(resolved_root),
        _check_structured_panel(resolved_root),
        _check_visual_graph_deferred(resolved_root),
        _check_relationship_api(resolved_root),
        _check_relationship_ui(resolved_root),
    ]
    blockers = [check.detail for check in checks if not check.ready]
    warnings = _warnings(resolved_root)
    deferred_items = _deferred_items(resolved_root)
    ready = not blockers
    next_step = (
        "Step 9 relationship coverage is complete; visual graph work remains deferred."
        if ready
        else "Finish the blocking Step 9 checks, then rerun this gate."
    )
    return Step9ReadinessReport(
        generated_at=datetime.now(timezone.utc),
        ready_for_step_9_completion=ready,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        deferred_items=deferred_items,
        next_step=next_step,
    )


def write_step9_readiness_report(root: Path) -> Step9ReadinessReport:
    """Write the Step 9 report and deferred queue to the control plane."""

    resolved_root = root.resolve()
    report = build_step9_readiness_report(resolved_root)
    atomic_write_json(resolved_root / CONTROL_PLANE_DIR / STEP9_REPORT_NAME, report, resolved_root)
    atomic_write_json(
        resolved_root / CONTROL_PLANE_DIR / STEP9_QUEUE_NAME,
        {
            "generated_at": report.generated_at.isoformat(),
            "items": [item.model_dump(mode="json") for item in report.deferred_items],
        },
        resolved_root,
    )
    return report


def _check_step8_ready(root: Path) -> Step9Check:
    """Check that Step 8 passed before Step 9 is marked complete."""

    report_path = root / CONTROL_PLANE_DIR / "STEP8_READINESS_REPORT.json"
    if not report_path.exists():
        return Step9Check(
            name="Step 8 gate",
            ready=False,
            detail="Step 8 readiness report is missing.",
        )
    payload = load_json(report_path)
    ready = bool(payload.get("ready_for_step_8_completion")) if isinstance(payload, dict) else False
    return Step9Check(
        name="Step 8 gate",
        ready=ready,
        detail="Step 8 gate is clean." if ready else "Step 8 gate is not complete.",
    )


def _check_coverage_jsonl(root: Path) -> Step9Check:
    """Check that per-relationship coverage rows exist."""

    path = root / CONTROL_PLANE_DIR / "RELATIONSHIP_COVERAGE.jsonl"
    rows = _jsonl_rows(path)
    report = _report(root)
    total = int(report.get("total_relationships") or 0)
    ready = total > 0 and len(rows) == total
    return Step9Check(
        name="Relationship coverage rows",
        ready=ready,
        detail=(
            f"Relationship coverage contains {len(rows)} per-relationship rows."
            if ready
            else (
                "Relationship coverage rows are missing, incomplete, or still summary-shaped."
            )
        ),
    )


def _check_coverage_report(root: Path) -> Step9Check:
    """Check that the coverage report exists with relationship records."""

    report = _report(root)
    total = int(report.get("total_relationships") or 0)
    ready = total > 0 and int(report.get("crosswalk_files_checked") or 0) >= 6
    return Step9Check(
        name="Relationship coverage report",
        ready=ready,
        detail=(
            f"Relationship coverage report contains {total} relationships."
            if ready
            else "Relationship coverage report is missing or has no relationship records."
        ),
    )


def _check_structured_panel(root: Path) -> Step9Check:
    """Check that the structured relationship panel remains the product direction."""

    report = _report(root)
    ready = bool(report.get("structured_relationship_panel_ready"))
    return Step9Check(
        name="Structured relationship panel",
        ready=ready,
        detail=(
            "Structured relationship panel is supported by measured coverage."
            if ready
            else "Structured relationship panel is not yet supported by coverage."
        ),
    )


def _check_visual_graph_deferred(root: Path) -> Step9Check:
    """Check that visual graph work is not prematurely marked ready."""

    report = _report(root)
    ready = report.get("visual_graph_ready") is False and bool(
        report.get("visual_graph_deferred_reason")
    )
    return Step9Check(
        name="Visual graph boundary",
        ready=ready,
        detail=(
            "Visual graph is explicitly deferred until relationship coverage is stronger."
            if ready
            else "Visual graph boundary is unclear."
        ),
    )


def _check_relationship_api(root: Path) -> Step9Check:
    """Check product API access for relationship coverage."""

    route = root / "geode" / "web" / "src" / "app" / "api" / "product" / "relationships" / "route.ts"
    return _check_file_markers(
        "Relationships API",
        route,
        ("getRelationshipCoverageReport", "relationshipCoverage"),
    )


def _check_relationship_ui(root: Path) -> Step9Check:
    """Check product UI access for relationship coverage."""

    page = root / "geode" / "web" / "src" / "app" / "app" / "relationships" / "page.tsx"
    return _check_file_markers(
        "Relationships UI",
        page,
        ("Relationship Health", "visual graph", "getRelationshipCoverageReport"),
    )


def _check_file_markers(name: str, path: Path, markers: tuple[str, ...]) -> Step9Check:
    """Check that a file exists and contains required implementation markers."""

    ready = _file_has_markers(path, markers)
    return Step9Check(
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


def _warnings(root: Path) -> list[str]:
    """Return non-blocking Step 9 warnings."""

    report = _report(root)
    warnings: list[str] = []
    if int(report.get("total_missing_evidence") or 0) > 0:
        warnings.append("Some relationship records are missing evidence text.")
    if int(report.get("total_low_confidence") or 0) > 0:
        warnings.append("Some relationship records have low confidence.")
    if report.get("visual_graph_ready") is False:
        warnings.append("Visual graph remains queued after relationship coverage measurement.")
    return warnings


def _deferred_items(root: Path) -> list[Step9DeferredItem]:
    """Return queued work after relationship coverage exists."""

    report = _report(root)
    missing_evidence = int(report.get("total_missing_evidence") or 0)
    low_confidence = int(report.get("total_low_confidence") or 0)
    items = [
        Step9DeferredItem(
            id="STEP9-VISUAL-GRAPH",
            title="Defer visual graph",
            reason="The useful first product is a structured relationship panel, not a network view.",
            next_action="Build a visual graph only after relationship coverage and target resolution are stronger.",
        )
    ]
    empty_files = _empty_crosswalk_files(report)
    if empty_files:
        items.append(
            Step9DeferredItem(
                id="STEP9-EMPTY-CROSSWALKS",
                title="Populate empty relationship files",
                reason=f"These relationship files are empty: {', '.join(empty_files)}.",
                next_action="Prioritize agency-to-statute and amendment-history extraction.",
            )
        )
    if missing_evidence > 0:
        items.append(
            Step9DeferredItem(
                id="STEP9-EVIDENCE-BACKFILL",
                title="Backfill relationship evidence",
                reason=f"{missing_evidence} relationship records currently lack evidence text.",
                next_action="Prioritize source evidence backfill before relying on graph-style outputs.",
            )
        )
    if low_confidence > 0:
        items.append(
            Step9DeferredItem(
                id="STEP9-LOW-CONFIDENCE-REVIEW",
                title="Review low-confidence relationships",
                reason=f"{low_confidence} relationship records are below the confidence threshold.",
                next_action="Route low-confidence relationships into review or improve extraction rules.",
            )
        )
    return items


def _jsonl_rows(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows if present."""

    if not path.exists() or path.stat().st_size == 0:
        return []
    return list(iter_jsonl(path))


def _report(root: Path) -> dict[str, object]:
    """Load the relationship coverage report."""

    path = root / CONTROL_PLANE_DIR / "RELATIONSHIP_COVERAGE_REPORT.json"
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _empty_crosswalk_files(report: dict[str, object]) -> list[str]:
    """Return crosswalk files with no relationship rows."""

    records = report.get("coverage_records")
    if not isinstance(records, list):
        return []
    empty_files: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if int(record.get("relationship_count") or 0) == 0:
            file_name = record.get("crosswalk_file")
            if isinstance(file_name, str):
                empty_files.append(file_name)
    return empty_files


def main() -> None:
    """Run the Step 9 gate."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    report = write_step9_readiness_report(root) if args.write else build_step9_readiness_report(root)
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Ready for Step 9 completion: {report.ready_for_step_9_completion}")
    for check in report.checks:
        status = "ready" if check.ready else "blocked"
        print(f"- {check.name}: {status} - {check.detail}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
