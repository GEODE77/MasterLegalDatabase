"""Step 2 readiness gate for Project Geode retrieval."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json
from geode.search.detail_index import detail_index
from geode.search.query_index import query_index

STEP2_REPORT_NAME = "STEP2_READINESS_REPORT.json"
STEP2_QUEUE_NAME = "STEP2_DEFERRED_QUEUE.json"
DEFAULT_DATABASE = Path("data/structured_output/indices/commons.sqlite3")


class Step2Check(BaseModel):
    """One Step 2 readiness check."""

    name: str
    ready: bool
    detail: str


class Step2DeferredItem(BaseModel):
    """A Step 2 item that should remain queued after the core gate passes."""

    id: str
    title: str
    reason: str
    next_action: str


class Step2ReadinessReport(BaseModel):
    """Overall Step 2 foundation readiness report."""

    generated_at: datetime
    ready_for_step_2_completion: bool
    checks: list[Step2Check]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    deferred_items: list[Step2DeferredItem] = Field(default_factory=list)
    next_step: str


def build_step2_readiness_report(root: Path, database_path: Path) -> Step2ReadinessReport:
    """Build the Step 2 gate report from the read index and requirement evidence."""

    resolved_root = root.resolve()
    resolved_database = _resolve_database_path(resolved_root, database_path)
    checks = [
        _check_step1_ready(resolved_root),
        _check_database_exists(resolved_database),
    ]
    if resolved_database.exists():
        checks.extend(
            [
                _check_index_run(resolved_database),
                _check_exact_citation(resolved_database),
                _check_operational_search(resolved_database),
                _check_detail_record(resolved_database),
            ]
        )
    checks.append(_check_rule_units(resolved_root))

    blockers = [check.detail for check in checks if not check.ready]
    warnings = _warnings(resolved_root)
    deferred_items = _default_deferred_items(resolved_root)
    ready = not blockers
    next_step = (
        "Step 2 foundation is complete; continue queued review and precision work."
        if ready
        else "Finish the blocking Step 2 checks, then rerun this gate."
    )
    return Step2ReadinessReport(
        generated_at=datetime.now(timezone.utc),
        ready_for_step_2_completion=ready,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        deferred_items=deferred_items,
        next_step=next_step,
    )


def write_step2_readiness_report(root: Path, database_path: Path) -> Step2ReadinessReport:
    """Write the Step 2 report and deferred queue to the control plane."""

    resolved_root = root.resolve()
    report = build_step2_readiness_report(resolved_root, database_path)
    atomic_write_json(resolved_root / CONTROL_PLANE_DIR / STEP2_REPORT_NAME, report, resolved_root)
    atomic_write_json(
        resolved_root / CONTROL_PLANE_DIR / STEP2_QUEUE_NAME,
        {
            "generated_at": report.generated_at.isoformat(),
            "items": [item.model_dump(mode="json") for item in report.deferred_items],
        },
        resolved_root,
    )
    return report


def _check_step1_ready(root: Path) -> Step2Check:
    """Check that Step 1 passed before Step 2 is marked complete."""

    report_path = root / CONTROL_PLANE_DIR / "STEP1_READINESS_REPORT.json"
    if not report_path.exists():
        return Step2Check(
            name="Step 1 gate",
            ready=False,
            detail="Step 1 readiness report is missing.",
        )
    payload = load_json(report_path)
    ready = bool(payload.get("ready_for_step_2")) if isinstance(payload, dict) else False
    return Step2Check(
        name="Step 1 gate",
        ready=ready,
        detail="Step 1 gate is clean." if ready else "Step 1 gate is not ready for Step 2.",
    )


def _check_database_exists(database_path: Path) -> Step2Check:
    """Check that the read index database exists."""

    return Step2Check(
        name="Read index database",
        ready=database_path.exists(),
        detail=(
            f"Read index database exists at {database_path}."
            if database_path.exists()
            else f"Read index database is missing at {database_path}."
        ),
    )


def _check_index_run(database_path: Path) -> Step2Check:
    """Check that the read index has meaningful corpus counts."""

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT entity_count, chunk_count, relation_count, timeline_count
            FROM index_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return Step2Check(name="Index run", ready=False, detail="No index run was recorded.")
    entity_count, chunk_count, relation_count, timeline_count = row
    ready = entity_count > 0 and chunk_count > 0 and relation_count > 0
    detail = (
        "Read index contains "
        f"{entity_count} entities, {chunk_count} chunks, {relation_count} relationships, "
        f"and {timeline_count} timeline events."
    )
    return Step2Check(name="Index run", ready=ready, detail=detail)


def _check_exact_citation(database_path: Path) -> Step2Check:
    """Check exact citation lookup."""

    results = query_index(database_path, "CRS 25-7-109", limit=3)
    ready = bool(results) and results[0].id == "CRS-25-7-109"
    detail = (
        "Exact CRS citation lookup returns CRS-25-7-109 first."
        if ready
        else "Exact CRS citation lookup did not return CRS-25-7-109 first."
    )
    return Step2Check(name="Exact citation lookup", ready=ready, detail=detail)


def _check_operational_search(database_path: Path) -> Step2Check:
    """Check operational search quality against a known bad false positive."""

    results = query_index(database_path, "air permitting obligations for manufacturing", limit=8)
    result_ids = [result.id for result in results]
    has_results = bool(result_ids)
    avoids_known_false_positive = "CRS-42-2-107" not in result_ids
    ready = has_results and avoids_known_false_positive
    detail = (
        "Operational search returns results and avoids the driver-license false positive."
        if ready
        else (
            "Operational search is missing results or still includes the driver-license "
            "false positive."
        )
    )
    return Step2Check(name="Operational search", ready=ready, detail=detail)


def _check_detail_record(database_path: Path) -> Step2Check:
    """Check that detail pages can retrieve full record evidence."""

    detail = detail_index(database_path, "CRS-25-7-109")
    ready = bool(detail and detail.get("chunks") and detail.get("source_versions"))
    return Step2Check(
        name="Authority detail",
        ready=ready,
        detail=(
            "Authority detail returns source chunks and source-version evidence."
            if ready
            else "Authority detail is missing chunks or source-version evidence."
        ),
    )


def _check_rule_units(root: Path) -> Step2Check:
    """Check that CCR rule units exist for requirement-level Step 2 work."""

    rule_units_path = root / "02_Regulations_CCR" / "_meta" / "rule_units.jsonl"
    count = _count_jsonl_rows(rule_units_path)
    ready = count > 0
    return Step2Check(
        name="Requirement foundation",
        ready=ready,
        detail=(
            f"Requirement foundation contains {count} rule units."
            if ready
            else "Requirement foundation has no rule units."
        ),
    )


def _warnings(root: Path) -> list[str]:
    """Return non-blocking Step 2 warnings."""

    warnings: list[str] = []
    review_summary_path = (
        root / "02_Regulations_CCR" / "_meta" / "rule_units_review_summary.json"
    )
    if review_summary_path.exists():
        payload = load_json(review_summary_path)
        if isinstance(payload, dict):
            pending = int(payload.get("pending_items") or payload.get("pendingItems") or 0)
            if pending > 0:
                warnings.append(f"{pending} rule units remain in the review queue.")
    return warnings


def _default_deferred_items(root: Path) -> list[Step2DeferredItem]:
    """Return the known queue for later Step 2 hardening."""

    pending_review = _pending_review_count(root)
    return [
        Step2DeferredItem(
            id="STEP2-RU-REVIEW",
            title="Finish rule-unit review queue",
            reason=f"{pending_review} rule units still need review before production use.",
            next_action="Review, approve, revise, split, or quarantine each queued rule unit.",
        ),
        Step2DeferredItem(
            id="STEP2-SEMANTIC-IMPACT",
            title="Add higher-precision impact scoring",
            reason="Current impact scoring is deterministic and source-backed but not deeply semantic.",
            next_action="Add reviewed semantic scoring after enough validated outcomes exist.",
        ),
        Step2DeferredItem(
            id="STEP2-VERSION-DIFFS",
            title="Add source version comparison",
            reason="The detail layer stores source versions but does not yet show full legal text diffs.",
            next_action="Build a source-version diff view for changed statutes and regulations.",
        ),
        Step2DeferredItem(
            id="STEP2-HUMAN-LEGAL-REVIEW",
            title="Add formal legal review before external reliance",
            reason="The app provides research and operating signals, not legal advice.",
            next_action="Define the human review workflow for externally relied-on guidance.",
        ),
    ]


def _pending_review_count(root: Path) -> int:
    """Return the current pending review count when available."""

    review_summary_path = (
        root / "02_Regulations_CCR" / "_meta" / "rule_units_review_summary.json"
    )
    if not review_summary_path.exists():
        return 0
    payload = load_json(review_summary_path)
    if not isinstance(payload, dict):
        return 0
    return int(payload.get("pending_items") or payload.get("pendingItems") or 0)


def _count_jsonl_rows(path: Path) -> int:
    """Count valid JSONL rows."""

    if not path.exists():
        return 0
    return sum(1 for _ in iter_jsonl(path))


def _resolve_database_path(root: Path, database_path: Path) -> Path:
    """Resolve a database path relative to the project root."""

    if database_path.is_absolute():
        return database_path
    return root / database_path


def main() -> None:
    """Run the Step 2 gate."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    database_path = Path(args.database)
    report = (
        write_step2_readiness_report(root, database_path)
        if args.write
        else build_step2_readiness_report(root, database_path)
    )
    if args.json:
        print(report.model_dump_json(indent=2))
        return
    print(f"Ready for Step 2 completion: {report.ready_for_step_2_completion}")
    for check in report.checks:
        status = "ready" if check.ready else "blocked"
        print(f"- {check.name}: {status} - {check.detail}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
