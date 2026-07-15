"""Run deterministic end-to-end stress checks for local authority controls."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json


REPORT_PATH = Path("_CONTROL_PLANE") / "LOCAL_STRESS_TEST_REPORT.json"


def run_local_stress(root: Path) -> dict[str, Any]:
    """Run invariant checks across local data, controls, and retrieval artifacts."""

    resolved = root.resolve()
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: Callable[[], bool]) -> None:
        try:
            passed = bool(condition())
            checks.append({"name": name, "passed": passed})
        except Exception as exc:  # pragma: no cover - defensive stress-report boundary
            checks.append({"name": name, "passed": False, "error": str(exc)})

    county_index = [row for row in iter_jsonl(resolved / "08_County_Authorities" / "_index.jsonl")]
    master = load_json(resolved / "_CONTROL_PLANE" / "MASTER_MANIFEST.json")
    retrieval = load_json(resolved / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG_SUMMARY.json")
    summary = load_json(resolved / "_CONTROL_PLANE" / "LOCAL_REVIEW_SUMMARY.json")
    coverage = load_json(resolved / "_CONTROL_PLANE" / "COUNTY_SOURCE_COVERAGE.json")
    schema = load_json(resolved / "_CONTROL_PLANE" / "MASTER_SCHEMA.json")
    registry = load_json(resolved / "_CONTROL_PLANE" / "LOCAL_SOURCE_REGISTRY.json")
    manifest_ids = {
        str(row.get("source_id"))
        for row in iter_jsonl(resolved / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl")
    }

    check("county index matches master manifest", lambda: len(county_index) == next(
        row["record_count"] for row in master["data_layers"] if row["id"] == "08_County_Authorities"
    ))
    check("county index matches retrieval catalog", lambda: len(county_index) == retrieval["layer_counts"]["08_County_Authorities"])
    check("local line provenance is complete", lambda: all(
        row.get("source_line_end")
        for row in county_index
        if row.get("entity_type") in {"local_rule", "rule_unit"}
    ))
    check("local categories are explicit", lambda: all(
        row.get("source_category")
        for row in county_index
        if row.get("entity_type") == "local_rule"
    ))
    check("unreviewed units are marked unsafe", lambda: all(
        row.get("semantic_status") == "source_preservation_only"
        for row in county_index
        if row.get("entity_type") == "rule_unit"
    ))
    check("review queue matches summary", lambda: sum(
        1 for _ in iter_jsonl(resolved / "_CONTROL_PLANE" / "LOCAL_REVIEW_QUEUE.jsonl")
    ) == summary["total_review_items"])
    check("OCR report matches queue", lambda: (
        load_json(resolved / "_CONTROL_PLANE" / "LOCAL_OCR_REPORT.json")["pending_items"]
        + load_json(resolved / "_CONTROL_PLANE" / "LOCAL_OCR_REPORT.json")["completed_items"]
        == summary["ocr_items"]
    ))
    check("all registered county sources have manifest rows", lambda: all(
        str(row["source_id"]) in manifest_ids
        for row in registry["pilot"]["county_sources"]
    ))
    check("coverage has 832 cells", lambda: len(coverage["counties"]) == 64 and sum(
        len(county["source_categories"]) for county in coverage["counties"]
    ) == 832)
    check("master schema puts semantic status on rule units", lambda: (
        "semantic_status" in schema["$defs"]["rule_unit"]["properties"]
        and "semantic_status" not in schema["$defs"]["local_authority"]["properties"]
    ))
    check("metadata version audit is clear", lambda: not load_json(
        resolved / "_CONTROL_PLANE" / "LOCAL_METADATA_VERSION_AUDIT.json"
    )["unreferenced_versioned_files"])

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "boundary": "This stress report checks deterministic local control-plane invariants; it does not approve legal meaning or prove live official freshness.",
    }
    atomic_write_json(resolved / REPORT_PATH, report, resolved)
    return report


def main() -> int:
    """Run and persist the local stress report."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = run_local_stress(args.root.resolve())
    print(json.dumps({"passed": report["passed"], "checks": len(report["checks"])}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
