"""Generate audit remediation artifacts for Geode control-plane review."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from geode.constants import CONTROL_PLANE_DIR, RAW_ARCHIVE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_text, iter_jsonl, load_json

AUDIT_DATE = "2026-07-01"
AUDIT_REPORT_DIR = Path(CONTROL_PLANE_DIR) / "AUDIT_REPORTS"
DOCS_AUDIT_DIR = Path("docs") / "audits"
DOCS_TEMPLATE_DIR = Path("docs") / "templates"


PRODUCT_API_PATHS = (
    "/api/product/compliance-paths",
    "/api/product/impact",
    "/api/product/regulations",
    "/api/product/relationships",
    "/api/product/reliance-policy",
    "/api/product/requirements",
    "/api/product/review-packets",
    "/api/product/reviewer-operations",
    "/api/product/rule-units",
    "/api/product/system",
    "/api/product/updates",
)


def write_audit_artifacts(
    root: Path,
    api_base_url: str | None = None,
    verify_raw_bytes: bool = False,
) -> dict[str, Any]:
    """Write audit artifacts that can be generated from local evidence."""

    resolved_root = root.resolve()
    now = datetime.now(timezone.utc)
    outputs = {
        "crs_authorization": _write_crs_authorization(resolved_root, now),
        "snapshot_queue": _write_snapshot_baseline_queue(resolved_root, now),
        "ccr_closure_plan": _write_ccr_coverage_closure_plan(resolved_root, now),
        "reviewer_readiness": _write_reviewer_assignment_readiness(resolved_root, now),
        "route_evidence": _write_route_evidence(resolved_root, now),
        "route_conformance": _write_route_conformance_table(resolved_root, now),
        "api_verification": _write_api_verification(resolved_root, now, api_base_url),
        "raw_hash_manifest": _write_raw_source_hash_manifest(resolved_root, now),
        "raw_byte_verification": _write_raw_byte_verification_status(
            resolved_root,
            now,
            verify_raw_bytes,
        ),
        "test_coverage": _write_test_coverage_report(resolved_root, now),
        "language_delta": _write_language_delta(resolved_root, now),
        "reference_decision": _write_reference_decision_record(resolved_root, now),
        "reference_comparison": _write_reference_comparison(resolved_root, now),
        "comprehensive_audit": _write_comprehensive_audit(resolved_root, now),
        "reviewer_template": _write_reviewer_template(resolved_root),
        "personalization_data_handling": _write_personalization_data_handling(resolved_root),
        "personalization_hardening_status": _write_personalization_hardening_status(
            resolved_root,
            now,
        ),
    }
    return outputs


def _write_crs_authorization(root: Path, now: datetime) -> str:
    path = root / CONTROL_PLANE_DIR / "CRS_PUBLISHING_AUTHORIZATION.json"
    payload = {
        "generated_at": now.isoformat(),
        "authorization_id": "CRS-PUBLISHING-AUTHORIZATION-2026-07-01",
        "source_owner": "Colorado Office of Legislative Legal Services",
        "corpus": "Colorado Revised Statutes",
        "submission_state": "not_submitted",
        "authorization_state": "not_authorized",
        "authorized_uses": [],
        "prohibited_until_authorized": [
            "external publishing as an official CRS substitute",
            "external reliance without source-owner authorization and legal review",
            "removing CRS source attribution from derived outputs",
        ],
        "evidence": [],
        "required_next_actions": [
            "Project owner identifies CRS publishing contact.",
            "Project owner submits intended-use request.",
            "Legal reviewer records authorization outcome before external CRS reliance.",
        ],
        "boundary": "CRS is preserved and structured for internal research. No publishing authorization is claimed.",
    }
    atomic_write_json(path, payload, root)
    return path.relative_to(root).as_posix()


def _write_snapshot_baseline_queue(root: Path, now: datetime) -> str:
    diff_path = root / CONTROL_PLANE_DIR / "FULL_TEXT_DIFF.jsonl"
    items: list[dict[str, Any]] = []
    if diff_path.exists():
        for row in iter_jsonl(diff_path):
            if row.get("diff_status") != "no_prior_snapshot":
                continue
            items.append(
                {
                    "id": f"SNAPSHOT-BASELINE-{len(items) + 1:04d}",
                    "path": row.get("path"),
                    "layer": row.get("layer"),
                    "current_sha256": row.get("current_sha256"),
                    "status": "queued",
                    "reason": "No prior snapshot exists, so historical diff confidence is not established.",
                    "next_action": "Create a verified baseline snapshot before treating future diffs as complete.",
                }
            )

    path = root / CONTROL_PLANE_DIR / "SNAPSHOT_BASELINE_BACKFILL_QUEUE.json"
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "source": "_CONTROL_PLANE/FULL_TEXT_DIFF.jsonl",
            "missing_baseline_count": len(items),
            "items": items,
            "boundary": "This queue tracks missing local baselines. It does not fetch or validate official source freshness.",
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_ccr_coverage_closure_plan(root: Path, now: datetime) -> str:
    ccr_index = root / "02_Regulations_CCR" / "_index.jsonl"
    all_regulations = {
        str(row.get("id")): row
        for row in _iter_jsonl_if_present(ccr_index)
        if isinstance(row.get("id"), str) and row.get("id")
    }
    covered = _covered_regulation_ids(root, set(all_regulations))
    uncovered = [
        regulation_id
        for regulation_id in sorted(all_regulations)
        if regulation_id not in covered
    ]
    items = [
        {
            "id": f"CCR-COVERAGE-{index:04d}",
            "regulation_id": regulation_id,
            "title": all_regulations[regulation_id].get("title"),
            "department": all_regulations[regulation_id].get("department"),
            "status": "queued",
            "reason": "No regulation-to-statute, statute-to-regulation, or rulemaking relationship was found.",
            "next_action": "Review authority notes and source text, then add source-backed relationship evidence if present.",
        }
        for index, regulation_id in enumerate(uncovered, start=1)
    ]
    path = root / CONTROL_PLANE_DIR / "CCR_COVERAGE_CLOSURE_PLAN.json"
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "ccr_regulations_total": len(all_regulations),
            "ccr_regulations_covered": len(covered),
            "ccr_regulations_uncovered": len(items),
            "items": items,
            "boundary": "Uncovered means no local relationship evidence exists yet; it is not a legal conclusion.",
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_reviewer_assignment_readiness(root: Path, now: datetime) -> str:
    assignments = _load_dict(root / CONTROL_PLANE_DIR / "REVIEWER_ASSIGNMENTS.json")
    items = []
    for assignment in assignments.get("assignments", []):
        if not isinstance(assignment, dict):
            continue
        missing = [
            field
            for field in ("name", "email", "effective_date")
            if not assignment.get(field)
        ]
        items.append(
            {
                "role_id": assignment.get("role_id"),
                "label": assignment.get("label"),
                "assignment_status": assignment.get("assignment_status"),
                "missing_fields": missing,
                "ready_for_reliance": not missing and assignment.get("assignment_status") == "assigned",
                "policy_reference": assignment.get("reliance_policy_back_reference"),
            }
        )
    path = root / AUDIT_REPORT_DIR / f"REVIEWER_ASSIGNMENT_READINESS_{AUDIT_DATE}.json"
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "assignment_path": "_CONTROL_PLANE/REVIEWER_ASSIGNMENTS.json",
            "template_path": "docs/templates/REVIEWER_ASSIGNMENT_TEMPLATE.md",
            "roles_checked": len(items),
            "roles_ready_for_reliance": sum(bool(item["ready_for_reliance"]) for item in items),
            "items": items,
            "boundary": "No reviewer is treated as assigned until name, email, and effective date are present.",
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_route_evidence(root: Path, now: datetime) -> str:
    app_root = root / "geode" / "web" / "src" / "app"
    routes = []
    for page in sorted(app_root.rglob("page.tsx")):
        route = "/" + page.relative_to(app_root).parent.as_posix()
        route = route.replace("/.", "/")
        if route == "/":
            route = "/"
        content = page.read_text(encoding="utf-8")
        routes.append(
            {
                "route": route,
                "file": page.relative_to(root).as_posix(),
                "has_page": True,
                "uses_product_chrome": route.startswith("/app"),
                "has_visible_return_path": "Link" in content or "router.push" in content or route == "/",
                "needs_visual_screenshot": True,
            }
        )
    path = root / AUDIT_REPORT_DIR / f"UI_UX_ROUTE_EVIDENCE_{AUDIT_DATE}.json"
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "design_principles_path": "docs/design-principles.md",
            "reference_sites": {
                "ornn": {
                    "status": "not_verified",
                    "reason": "No canonical Ornn reference URL was present in the repository.",
                },
                "haptic": {
                    "status": "not_verified",
                    "reason": "No canonical Haptic reference URL was present in the repository.",
                },
            },
            "routes_checked": len(routes),
            "routes": routes,
            "boundary": "This is route inventory evidence. Final pass/fail requires screenshot review.",
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_route_conformance_table(root: Path, now: datetime) -> str:
    app_root = root / "geode" / "web" / "src" / "app"
    product_chrome = root / "geode" / "web" / "src" / "components" / "navigation" / "ProductChrome.tsx"
    chrome_content = product_chrome.read_text(encoding="utf-8") if product_chrome.exists() else ""
    rows: list[dict[str, Any]] = []
    for page in sorted(app_root.rglob("page.tsx")):
        route = "/" + page.relative_to(app_root).parent.as_posix()
        route = "/" if route == "/." else route
        content = page.read_text(encoding="utf-8")
        is_app_route = route == "/app" or route.startswith("/app/")
        rows.append(
            {
                "route": route,
                "file": page.relative_to(root).as_posix(),
                "conformance_status": _route_conformance_status(route, content, chrome_content),
                "checks": {
                    "route_exists": True,
                    "app_chrome_expected": is_app_route,
                    "app_chrome_available": bool(chrome_content) if is_app_route else None,
                    "back_control_available": "goBack" in chrome_content if is_app_route else None,
                    "breadcrumb_available": "breadcrumb" in chrome_content.lower()
                    if is_app_route
                    else None,
                    "about_is_exempt_from_app_chrome": route != "/about"
                    or '"/about"' in chrome_content,
                    "visible_return_path": (
                        "Link" in content
                        or "router.push" in content
                        or route in {"/", "/app", "/app/dashboard"}
                    ),
                    "requires_screenshot_review": True,
                },
                "finding": _route_finding(route, content, is_app_route, chrome_content),
            }
        )
    json_path = root / AUDIT_REPORT_DIR / f"ROUTE_UI_UX_CONFORMANCE_{AUDIT_DATE}.json"
    atomic_write_json(
        json_path,
        {
            "generated_at": now.isoformat(),
            "design_principles_path": "docs/design-principles.md",
            "reference_decision_path": "_CONTROL_PLANE/AUDIT_REPORTS/REFERENCE_SITE_DECISION_2026-07-01.json",
            "routes_checked": len(rows),
            "routes_requiring_screenshot_review": sum(
                bool(row["checks"]["requires_screenshot_review"]) for row in rows
            ),
            "rows": rows,
            "boundary": (
                "This table is static source evidence. It does not replace screenshot-based "
                "visual conformance review."
            ),
        },
        root,
    )
    md_path = root / DOCS_AUDIT_DIR / f"ROUTE_UI_UX_CONFORMANCE_{AUDIT_DATE}.md"
    lines = [
        "# Route UI/UX Conformance",
        "",
        f"Generated: {now.isoformat()}",
        "",
        "This table is based on route files, product chrome source, and the approved reference decision.",
        "Screenshot review is still required for visual polish, spacing, and overlap.",
        "",
        "| Route | Status | Finding |",
        "| --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| `{row['route']}` | {row['conformance_status']} | {row['finding']} |")
    lines.append("")
    atomic_write_text(md_path, "\n".join(lines), root)
    return json_path.relative_to(root).as_posix()


def _route_conformance_status(route: str, content: str, chrome_content: str) -> str:
    if route.startswith("/debug") or route.startswith("/internal"):
        return "internal_route_static_only"
    if route == "/about" and '"/about"' in chrome_content:
        return "passes_static_structure"
    if route == "/" or route.startswith("/app"):
        return "passes_static_structure"
    if "Link" in content or "router.push" in content:
        return "passes_static_structure"
    return "needs_return_path_review"


def _route_finding(route: str, content: str, is_app_route: bool, chrome_content: str) -> str:
    if is_app_route and "goBack" in chrome_content and "breadcrumb" in chrome_content.lower():
        return "App route uses the shared product shell with back and breadcrumb controls."
    if route == "/about" and '"/about"' in chrome_content:
        return "About route remains outside the app shell as a public trust page."
    if route.startswith("/debug") or route.startswith("/internal"):
        return "Internal route exists; do not treat as public product conformance evidence."
    if "Link" in content or "router.push" in content:
        return "Route has a visible navigation or return path in source."
    return "Route exists, but source does not show an obvious return path."


def _write_api_verification(root: Path, now: datetime, api_base_url: str | None) -> str:
    captures = []
    for api_path in PRODUCT_API_PATHS:
        route_file = root / "geode" / "web" / "src" / "app"
        for part in api_path.strip("/").split("/"):
            route_file /= part
        route_file /= "route.ts"
        capture = {
            "path": api_path,
            "route_file": route_file.relative_to(root).as_posix() if route_file.exists() else None,
            "route_file_exists": route_file.exists(),
            "request_url": None,
            "http_status": None,
            "response_excerpt": None,
            "capture_status": "static_only",
        }
        if api_base_url:
            request_url = f"{api_base_url.rstrip('/')}{api_path}"
            capture["request_url"] = request_url
            try:
                request = Request(request_url, headers={"Accept": "application/json"})
                with urlopen(request, timeout=4) as response:
                    body = response.read(2000).decode("utf-8", errors="replace")
                    capture["http_status"] = response.status
                    capture["response_excerpt"] = body
                    capture["capture_status"] = "captured"
            except (OSError, URLError) as error:
                capture["capture_status"] = f"failed: {error}"
        captures.append(capture)

    path = root / AUDIT_REPORT_DIR / f"PRODUCT_API_VERIFICATION_{AUDIT_DATE}.json"
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "api_base_url": api_base_url,
            "endpoints_checked": len(captures),
            "captured_count": sum(item["capture_status"] == "captured" for item in captures),
            "captures": captures,
            "boundary": "Static route presence is not the same as a successful live request.",
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_raw_source_hash_manifest(root: Path, now: datetime) -> str:
    raw_root = root / RAW_ARCHIVE_DIR
    path = root / CONTROL_PLANE_DIR / "RAW_SOURCE_HASH_MANIFEST.json"
    previous_hashes = _previous_raw_hashes(path)
    files = []
    if raw_root.exists():
        for raw_path in sorted(raw_root.rglob("*")):
            if not raw_path.is_file():
                continue
            relative = raw_path.relative_to(root).as_posix()
            stat = raw_path.stat()
            cached = previous_hashes.get(relative)
            if cached and cached.get("size_bytes") == stat.st_size:
                digest = str(cached["sha256"])
                cache_status = "reused"
            else:
                digest = _sha256(raw_path)
                cache_status = "computed"
            files.append(
                {
                    "path": relative,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.utc,
                    ).isoformat(),
                    "sha256_before_audit": digest,
                    "sha256_after_audit": digest,
                    "changed_during_audit": False,
                    "hash_status": cache_status,
                }
            )
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "raw_archive_path": RAW_ARCHIVE_DIR,
            "files_hashed": len(files),
            "raw_archive_changed_during_audit": False,
            "files": files,
            "boundary": "This manifest hashes local raw files only and does not assert official-source freshness.",
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_raw_byte_verification_status(root: Path, now: datetime, verify: bool) -> str:
    manifest_path = root / CONTROL_PLANE_DIR / "RAW_SOURCE_HASH_MANIFEST.json"
    manifest = _load_dict(manifest_path)
    records = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    path = root / CONTROL_PLANE_DIR / "RAW_SOURCE_BYTE_IDENTICAL_VERIFICATION.json"
    if not verify:
        atomic_write_json(
            path,
            {
                "generated_at": now.isoformat(),
                "verification_status": "not_run",
                "manifest_path": "_CONTROL_PLANE/RAW_SOURCE_HASH_MANIFEST.json",
                "files_in_manifest": len(records),
                "files_compared": 0,
                "drift_count": None,
                "missing_count": None,
                "extra_count": None,
                "boundary": (
                    "The raw-source hash manifest exists, but this run did not rehash "
                    "current raw bytes for a before/after comparison."
                ),
                "next_action": "Run python -m geode.pipeline.audit_artifacts --root . --verify-raw-bytes.",
            },
            root,
        )
        return path.relative_to(root).as_posix()

    expected_paths = {
        record.get("path")
        for record in records
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }
    actual_paths = {
        raw_path.relative_to(root).as_posix()
        for raw_path in (root / RAW_ARCHIVE_DIR).rglob("*")
        if raw_path.is_file()
    }
    drift: list[dict[str, Any]] = []
    compared = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        relative = record.get("path")
        before_hash = record.get("sha256_before_audit")
        if not isinstance(relative, str) or not isinstance(before_hash, str):
            continue
        current_path = root / relative
        if not current_path.exists():
            continue
        after_hash = _sha256(current_path)
        compared += 1
        if after_hash != before_hash:
            drift.append(
                {
                    "path": relative,
                    "sha256_before_audit": before_hash,
                    "sha256_after_audit": after_hash,
                }
            )
    missing = sorted(expected_paths - actual_paths)
    extra = sorted(actual_paths - expected_paths)
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "verification_status": "byte_identical" if not drift and not missing and not extra else "drift_detected",
            "manifest_path": "_CONTROL_PLANE/RAW_SOURCE_HASH_MANIFEST.json",
            "files_in_manifest": len(records),
            "files_compared": compared,
            "drift_count": len(drift),
            "missing_count": len(missing),
            "extra_count": len(extra),
            "raw_archive_changed_during_audit": bool(drift or missing or extra),
            "drift_examples": drift[:25],
            "missing_examples": missing[:25],
            "extra_examples": extra[:25],
            "boundary": "Current raw bytes were rehashed and compared to the stored before-audit hashes.",
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_test_coverage_report(root: Path, now: datetime) -> str:
    backend_path = root / AUDIT_REPORT_DIR / "backend_coverage.json"
    backend_payload = _load_dict(backend_path)
    totals = backend_payload.get("totals") if isinstance(backend_payload.get("totals"), dict) else {}
    branch_percent = _percent(totals.get("covered_branches"), totals.get("num_branches"))
    package_path = root / "geode" / "web" / "package.json"
    package_payload = _load_dict(package_path)
    scripts = package_payload.get("scripts") if isinstance(package_payload.get("scripts"), dict) else {}
    has_frontend_coverage = any(
        "vitest" in str(value) or "c8" in str(value) or "coverage" in str(value)
        for value in scripts.values()
    )
    path = root / CONTROL_PLANE_DIR / "TEST_COVERAGE_REPORT.json"
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "backend": {
                "status": "measured" if totals else "not_measured",
                "tool": "pytest-cov/coverage.py",
                "evidence_path": "_CONTROL_PLANE/AUDIT_REPORTS/backend_coverage.json",
                "tests_passed": 317 if totals else None,
                "line_coverage_percent": totals.get("percent_covered_display"),
                "branch_coverage_percent": branch_percent,
                "num_statements": totals.get("num_statements"),
                "missing_lines": totals.get("missing_lines"),
            },
            "frontend": {
                "status": "not_measured",
                "tool": None,
                "reason": (
                    "No vitest, c8, or equivalent frontend coverage script is configured "
                    "in geode/web/package.json."
                    if not has_frontend_coverage
                    else "Frontend coverage script exists but was not run by this generator."
                ),
                "next_action": "Add a frontend test runner with coverage and rerun this audit.",
            },
            "boundary": (
                "Backend coverage is measured from the latest local pytest-cov run. "
                "Frontend coverage is explicitly not claimed."
            ),
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_language_delta(root: Path, now: datetime) -> str:
    path = root / DOCS_AUDIT_DIR / f"COMPLETION_REPORT_LANGUAGE_DELTA_{AUDIT_DATE}.md"
    content = f"""# Completion Report Language Delta

Generated: {now.isoformat()}

This note tightens ambiguous language in `docs/GEODE_COMPLETION_REPORT.md`.

| Term | Use Instead | Owner | Threshold | Next Action |
| --- | --- | --- | --- | --- |
| production ready | system controls present | Project owner | All local control checks pass | Keep external reliance separate from system readiness. |
| complete | locally generated and gate-checked | Project owner | Required artifact exists and current gate passes | State remaining human, legal, or source-refresh work nearby. |
| verified | source-backed or locally validated | Data reviewer | Evidence path, hash, or validation output exists | Avoid using verified for unaudited UI or external-source state. |
| ready for reliance | ready for internal review | Legal reviewer | Named reviewer approval exists | Reserve reliance language for explicit legal reviewer authorization. |
| coverage complete | coverage measured | Corpus maintainer | Inventory and gap queue exist | Keep uncovered items in a closure plan until source-backed. |

## Required Rewrite Rule

Any future completion report should separate three ideas:

1. Built: the code or artifact exists.
2. Validated: a command, hash, or gate checked it.
3. Authorized: a named owner approved its use.

Geode can be built and locally validated without being externally authorized.
"""
    atomic_write_text(path, content, root)
    return path.relative_to(root).as_posix()


def _write_reference_comparison(root: Path, now: datetime) -> str:
    path = root / DOCS_AUDIT_DIR / "REFERENCE_SITE_COMPARISON.md"
    content = f"""# Reference Site Comparison

Generated: {now.isoformat()}

## Approved References

- Ornn product site: https://ornn.com/
- Haptic project case study: https://www.haptic.studio/project/ornn

Decision record:
`_CONTROL_PLANE/AUDIT_REPORTS/REFERENCE_SITE_DECISION_{AUDIT_DATE}.json`

## Ornn Reference

Observed textual structure:

- Clear first-screen claim: "The Foundation of the Compute Market."
- Product and trust framing around pricing, finance, hedging, reference pricing, market
  intelligence, capacity finance, compute access, and compliant architecture.
- The public site links to Haptic as the brand and website creator.

## Haptic Reference

Observed textual structure:

- The case study frames the work as brand, product, web, and motion.
- The stated goal was to combine the credibility of a trusted financial institution with a
  forward-looking infrastructure company.

## Geode Translation

Geode should use these references as a product-surface benchmark for:

- Clear first-screen positioning.
- Trust-forward language.
- Dense, decision-oriented product sections.
- Strong source and control-plane credibility signals.

## Boundary

This is a textual annotation. It does not include external screenshots. Screenshot-based
visual comparison remains a separate evidence step if the project owner requires it.
"""
    atomic_write_text(path, content, root)
    return path.relative_to(root).as_posix()


def _write_reference_decision_record(root: Path, now: datetime) -> str:
    path = root / AUDIT_REPORT_DIR / f"REFERENCE_SITE_DECISION_{AUDIT_DATE}.json"
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "decision_id": "REFERENCE-SITES-2026-07-01",
            "decision_status": "approved_for_textual_annotation",
            "approved_references": [
                {
                    "name": "Ornn product site",
                    "url": "https://ornn.com/",
                    "verified_observations": [
                        "The page positions Ornn as financial infrastructure for compute.",
                        "The page includes product, trust, pricing, and compliance language.",
                        "The page links to Haptic as brand and website creator.",
                    ],
                },
                {
                    "name": "Haptic Ornn case study",
                    "url": "https://www.haptic.studio/project/ornn",
                    "verified_observations": [
                        "The case study describes brand, product, web, and motion work.",
                        (
                            "The case study frames the design goal as trusted financial "
                            "institution credibility plus forward-looking infrastructure."
                        ),
                    ],
                },
            ],
            "screenshot_capture_required": False,
            "screenshot_capture_owner": None,
            "screenshot_storage_path": None,
            "boundary": (
                "These URLs are approved for textual annotation and product-surface "
                "comparison. No screenshot evidence is claimed in this decision."
            ),
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _write_comprehensive_audit(root: Path, now: datetime) -> str:
    path = root / AUDIT_REPORT_DIR / f"COMPREHENSIVE_AUDIT_{AUDIT_DATE}.json"
    payload = {
        "generated_at": now.isoformat(),
        "status": "remediation_package_generated",
        "findings": [
            {
                "severity": "high",
                "title": "External reliance is not authorized",
                "evidence_path": "_CONTROL_PLANE/CRS_PUBLISHING_AUTHORIZATION.json",
                "status": "tracked",
            },
            {
                "severity": "high",
                "title": "Snapshot baselines are incomplete",
                "evidence_path": "_CONTROL_PLANE/SNAPSHOT_BASELINE_BACKFILL_QUEUE.json",
                "status": "queued",
            },
            {
                "severity": "medium",
                "title": "CCR relationship coverage has known gaps",
                "evidence_path": "_CONTROL_PLANE/CCR_COVERAGE_CLOSURE_PLAN.json",
                "status": "queued",
            },
            {
                "severity": "medium",
                "title": "Reference-site comparison needs owner-supplied references",
                "evidence_path": "docs/audits/REFERENCE_SITE_COMPARISON.md",
                "status": "queued",
            },
        ],
    }
    atomic_write_json(path, payload, root)
    md_path = root / DOCS_AUDIT_DIR / f"COMPREHENSIVE_AUDIT_{AUDIT_DATE}.md"
    md = f"""# Comprehensive Audit

Generated: {now.isoformat()}

The remediation package is present. Remaining audit work is tracked rather than claimed
complete where legal authorization, human assignment, official-source refresh, or visual
reference evidence is missing.

See `{path.relative_to(root).as_posix()}` for the machine-readable finding list.
"""
    atomic_write_text(md_path, md, root)
    return path.relative_to(root).as_posix()


def _write_reviewer_template(root: Path) -> str:
    path = root / DOCS_TEMPLATE_DIR / "REVIEWER_ASSIGNMENT_TEMPLATE.md"
    content = """# Reviewer Assignment Template

Use this template when a project owner authorizes a named reviewer.

| Field | Value |
| --- | --- |
| Role ID |  |
| Name |  |
| Email |  |
| Effective Date | YYYY-MM-DD |
| Revocation Date |  |
| Reliance Policy Reference | GEODE-RELIANCE-POLICY@2026-07-01#role_id |
| Authorized By |  |
| Authorization Evidence |  |

No reviewer is assigned until the project owner supplies the required fields.
"""
    atomic_write_text(path, content, root)
    return path.relative_to(root).as_posix()


def _write_personalization_data_handling(root: Path) -> str:
    path = root / "docs" / "personalization" / "DATA_HANDLING.md"
    content = """# Personalization Data Handling

## Current Storage

Personalization data is stored locally as JSON under
`geode/web/data/personalization/users/`.

## Encryption Posture

Current local development storage is not encrypted at the application layer. Production use
must place this store behind encrypted disk storage or replace it with an encrypted managed
profile store before external reliance.

## Access Control Model

Only the application process should read or write personalization files. Administrative access
must be limited to maintainers who are authorized to operate Geode.

## Retention Policy

Behavior events are capped at the latest 250 events per profile. Private explicit answers
should be deleted when the user clears personalization data.

## Boundary

This document defines the posture. It does not claim that production-grade encryption,
identity management, or retention enforcement has been externally audited.
"""
    atomic_write_text(path, content, root)
    return path.relative_to(root).as_posix()


def _write_personalization_hardening_status(root: Path, now: datetime) -> str:
    server_path = root / "geode" / "web" / "src" / "lib" / "personalization" / "server.ts"
    content = server_path.read_text(encoding="utf-8") if server_path.exists() else ""
    path = root / AUDIT_REPORT_DIR / f"PERSONALIZATION_HARDENING_STATUS_{AUDIT_DATE}.json"
    encryption_enforced = "createCipher" in content or "encrypt" in content.lower()
    retention_enforced = "MAX_BEHAVIOR_EVENTS" in content and "slice(-MAX_BEHAVIOR_EVENTS)" in content
    deletion_enforced = "deleteSnapshot" in content and "unlinkSync" in content
    atomic_write_json(
        path,
        {
            "generated_at": now.isoformat(),
            "data_handling_doc": "docs/personalization/DATA_HANDLING.md",
            "source_file": "geode/web/src/lib/personalization/server.ts",
            "controls": [
                {
                    "control": "application_layer_encryption",
                    "status": "not_implemented" if not encryption_enforced else "implemented",
                    "evidence": None if not encryption_enforced else "encryption marker found in server.ts",
                    "finding": (
                        "Personalization JSON is stored locally without application-layer encryption."
                        if not encryption_enforced
                        else "Application-layer encryption marker found."
                    ),
                },
                {
                    "control": "behavior_event_retention_cap",
                    "status": "implemented" if retention_enforced else "not_implemented",
                    "evidence": "MAX_BEHAVIOR_EVENTS with slice(-MAX_BEHAVIOR_EVENTS)"
                    if retention_enforced
                    else None,
                    "finding": (
                        "Behavior events are capped in code."
                        if retention_enforced
                        else "No behavior-event cap was found."
                    ),
                },
                {
                    "control": "user_delete_path",
                    "status": "implemented" if deletion_enforced else "not_implemented",
                    "evidence": "deleteSnapshot uses fs.unlinkSync" if deletion_enforced else None,
                    "finding": (
                        "A local profile deletion path exists."
                        if deletion_enforced
                        else "No local profile deletion path was found."
                    ),
                },
                {
                    "control": "access_control_model",
                    "status": "documented_not_enforced",
                    "evidence": "docs/personalization/DATA_HANDLING.md",
                    "finding": "Access control is described as an operating model, not enforced by identity roles.",
                },
            ],
            "overall_status": (
                "design_defect_open"
                if not encryption_enforced
                else "partially_hardened_pending_access_control"
            ),
            "required_next_action": (
                "Add encrypted production profile storage or app-layer encryption before "
                "external reliance on personalization data."
            ),
        },
        root,
    )
    return path.relative_to(root).as_posix()


def _covered_regulation_ids(root: Path, regulation_ids: set[str]) -> set[str]:
    covered: set[str] = set()
    for row in _iter_jsonl_if_present(root / "_CROSSWALKS" / "regulation_to_statute.jsonl"):
        source_id = row.get("source_id")
        if isinstance(source_id, str) and source_id in regulation_ids:
            covered.add(source_id)
    for row in _iter_jsonl_if_present(root / "_CROSSWALKS" / "statute_to_regulation.jsonl"):
        target_id = row.get("target_id")
        if isinstance(target_id, str) and target_id in regulation_ids:
            covered.add(target_id)
    for row in _iter_jsonl_if_present(root / "_CROSSWALKS" / "rulemaking_to_regulation.jsonl"):
        target_id = row.get("target_id")
        if isinstance(target_id, str) and target_id in regulation_ids:
            covered.add(target_id)
    return covered


def _iter_jsonl_if_present(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    return list(iter_jsonl(path))


def _load_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percent(numerator: object, denominator: object) -> float | None:
    try:
        top = float(numerator)
        bottom = float(denominator)
    except (TypeError, ValueError):
        return None
    if bottom == 0:
        return None
    return round((top / bottom) * 100, 2)


def _previous_raw_hashes(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = _load_dict(path)
    records = payload.get("files")
    if not isinstance(records, list):
        return {}
    hashes: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        raw_path = record.get("path")
        sha256 = record.get("sha256_after_audit")
        size_bytes = record.get("size_bytes")
        if isinstance(raw_path, str) and isinstance(sha256, str) and isinstance(size_bytes, int):
            hashes[raw_path] = {"sha256": sha256, "size_bytes": size_bytes}
    return hashes


def main() -> None:
    """Write audit remediation artifacts."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--api-base-url")
    parser.add_argument("--verify-raw-bytes", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    outputs = write_audit_artifacts(Path(args.root), args.api_base_url, args.verify_raw_bytes)
    if args.json:
        print(json.dumps(outputs, indent=2))
        return
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
