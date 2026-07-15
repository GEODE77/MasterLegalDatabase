"""Audit whether Geode is usable by an AI as a verified knowledge layer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_FILES = (
    "AI_READ_ORDER.json",
    "AI_QUERY_CONTRACT.json",
    "AI_RETRIEVAL_CONTRACT.json",
    "AI_ANSWER_CONTRACT.json",
)


def build_ai_readiness_report(root: Path) -> dict[str, Any]:
    """Build a machine-readable AI-use readiness report from existing artifacts."""

    control = root / "_CONTROL_PLANE"
    checks: list[dict[str, Any]] = []

    for name in CONTRACT_FILES:
        path = control / name
        checks.append({"check": f"control_plane/{name}", "passed": path.exists()})

    manifest = _load_json(control / "MASTER_MANIFEST.json")
    checks.append({
        "check": "master_manifest",
        "passed": bool(manifest and manifest.get("data_layers")),
    })
    catalog = control / "RETRIEVAL_CATALOG.jsonl"
    checks.append({"check": "retrieval_catalog", "passed": catalog.exists() and catalog.stat().st_size > 0})

    review = _load_json(control / "LOCAL_REVIEW_SUMMARY.json")
    if review:
        checks.append({
            "check": "local_answer_safe_filter",
            "passed": review.get("answer_safe_local_rule_units", 0) == 0
            and review.get("semantic_review_items", 0) > 0,
            "detail": "Local preservation-only material is identified and excluded until reviewed.",
        })
        checks.append({
            "check": "local_review_queues",
            "passed": all(
                key in review
                for key in ("semantic_review_items", "ocr_items", "source_classification_items")
            ),
        })

    stress = _load_json(control / "LOCAL_STRESS_TEST_REPORT.json")
    if stress:
        checks.append({"check": "local_stress_tests", "passed": stress.get("passed", False)})

    local_golden = _load_json(control / "LOCAL_GOLDEN_EVALUATION.json")
    if local_golden:
        checks.append({
            "check": "local_golden_questions",
            "passed": local_golden.get("failed", 1) == 0
            and local_golden.get("passed", 0) == local_golden.get("total", -1),
        })

    promotion_report = _load_json(control / "LOCAL_PROMOTION_REPORT.json")
    if promotion_report:
        checks.append({
            "check": "local_promotion_boundary",
            "passed": promotion_report.get("blocked", 0) == 0,
            "detail": "Only validated reviewer decisions may promote local evidence.",
        })

    passed = sum(1 for check in checks if check["passed"])
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Determine whether an AI can read, retrieve, verify, and cite Geode safely.",
        "checks": checks,
        "passed_checks": passed,
        "total_checks": len(checks),
        "status": "ready" if checks and passed == len(checks) else "needs_review",
        "known_limits": [
            "Local source-preservation-only records remain available for audit but are not answer-safe.",
            "Unknown currency must be disclosed until the source is verified against a current official version.",
            "Coverage gaps are findings, not proof that no rule exists.",
        ],
    }


def write_ai_readiness_report(root: Path) -> dict[str, Any]:
    """Write the AI readiness report to the control plane."""

    report = build_ai_readiness_report(root)
    path = root / "_CONTROL_PLANE" / "AI_READINESS_REPORT.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load an optional JSON control-plane file."""

    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
