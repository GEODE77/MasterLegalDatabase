"""Compare Geode CCR/rulemaking data with a Colorado Rulemaking Search snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, atomic_write_text, iter_jsonl, load_json

REGULATIONS_LAYER = "02_Regulations_CCR"
RULEMAKING_LAYER = "04_Rulemaking"
CROSSWALK_DIR = "_CROSSWALKS"
VERIFICATION_DIR = "_verification"
OFFICIAL_NORMALIZED_NAME = "colorado_rulemaking_search_snapshot_normalized.jsonl"
COMPARISON_NAME = "rulemaking_search_comparison.jsonl"
SUMMARY_NAME = "rulemaking_search_verification_summary.json"
CONTROL_SUMMARY_NAME = "COLORADO_RULEMAKING_SEARCH_VERIFICATION.json"
TEMPLATE_NAME = "rulemaking_search_snapshot_template.csv"

CCR_RE = re.compile(r"\b(?P<dept>\d{1,2})\s+CCR\s+(?P<series>\d+)-(?P<rule>\d+(?:-\d+)?)\b")
CCR_ID_RE = re.compile(r"^(?P<dept>\d{1,2})_CCR_(?P<series>\d+)-(?P<rule>\d+(?:-\d+)?)$")

CSV_HEADERS = [
    "ccr_citation",
    "rule_title",
    "agency",
    "rulemaking_status",
    "filing_type",
    "publication_date",
    "effective_date",
    "edocket_tracking_number",
    "source_url",
]

FIELD_ALIASES = {
    "agency": ("agency", "agency_name", "department", "division"),
    "ccr_citation": ("ccr_citation", "ccr", "rule", "rule_number", "rule_num", "series_num"),
    "edocket_tracking_number": (
        "edocket_tracking_number",
        "edocket",
        "tracking_number",
        "trackingnum",
        "docket",
    ),
    "effective_date": ("effective_date", "eff_date", "rule_effective_date"),
    "filing_type": ("filing_type", "filing", "notice_type", "type"),
    "publication_date": ("publication_date", "published", "publish_date", "notice_date"),
    "rule_title": ("rule_title", "title", "name", "rule_name"),
    "rulemaking_status": ("rulemaking_status", "status", "current_status"),
    "source_url": ("source_url", "url", "link", "official_url"),
}


class OfficialRulemakingSearchRecord(BaseModel):
    """One normalized record from an official Rulemaking Search snapshot."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str = "official_rulemaking_search_record"
    id: str = Field(min_length=1)
    parent_regulation_id: str = Field(min_length=1)
    ccr_citation: str = Field(min_length=1)
    rule_title: str | None = None
    agency: str | None = None
    rulemaking_status: str | None = None
    filing_type: str | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    edocket_tracking_number: str | None = None
    source_url: str | None = None
    raw_fields: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime


class RulemakingSearchComparisonRecord(BaseModel):
    """One comparison result between Geode and the official snapshot."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str = "rulemaking_search_comparison"
    id: str = Field(min_length=1)
    parent_regulation_id: str = Field(min_length=1)
    ccr_citation: str = Field(min_length=1)
    geode_rule_present: bool
    geode_rulemaking_notice_count: int = Field(ge=0)
    official_match_count: int = Field(ge=0)
    strongest_match_method: str = Field(min_length=1)
    strongest_match_confidence: float = Field(ge=0.0, le=1.0)
    status: str = Field(min_length=1)
    status_flags: list[str] = Field(default_factory=list)
    geode_notice_ids: list[str] = Field(default_factory=list)
    official_record_ids: list[str] = Field(default_factory=list)
    official_statuses: list[str] = Field(default_factory=list)
    official_effective_dates: list[date] = Field(default_factory=list)
    verification_summary: str = Field(min_length=1)
    generated_at: datetime


class RulemakingSearchVerificationSummary(BaseModel):
    """Top-level comparison summary."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    official_snapshot_path: str | None = None
    official_snapshot_loaded: bool
    geode_rules_total: int = Field(ge=0)
    geode_rulemaking_notices_total: int = Field(ge=0)
    official_records_total: int = Field(ge=0)
    comparison_records_total: int = Field(ge=0)
    official_match_found: int = Field(ge=0)
    possible_official_match: int = Field(ge=0)
    no_official_match: int = Field(ge=0)
    geode_only_history: int = Field(ge=0)
    missing_geode_rule: int = Field(ge=0)
    awaiting_official_snapshot: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    normalized_snapshot_path: str
    comparison_path: str
    summary_path: str
    control_summary_path: str
    template_path: str
    boundary: str
    next_steps: list[str] = Field(default_factory=list)


def run_rulemaking_search_verification(
    output_root: Path,
    official_snapshot_path: Path | None = None,
) -> RulemakingSearchVerificationSummary:
    """Build a testing-ready comparison between Geode and official rulemaking data."""

    root = output_root.resolve()
    generated_at = datetime.now(timezone.utc)
    rules = _load_geode_rules(root)
    notices = _load_geode_notices(root)
    official_records = (
        _load_official_snapshot(official_snapshot_path, generated_at)
        if official_snapshot_path
        else []
    )
    comparisons = _build_comparisons(rules, notices, official_records, generated_at)

    verification_dir = root / RULEMAKING_LAYER / VERIFICATION_DIR
    normalized_path = verification_dir / OFFICIAL_NORMALIZED_NAME
    comparison_path = verification_dir / COMPARISON_NAME
    summary_path = verification_dir / SUMMARY_NAME
    control_path = root / CONTROL_PLANE_DIR / CONTROL_SUMMARY_NAME
    template_path = verification_dir / TEMPLATE_NAME

    summary = _build_summary(
        root=root,
        official_snapshot_path=official_snapshot_path,
        rules=rules,
        notices=notices,
        official_records=official_records,
        comparisons=comparisons,
        generated_at=generated_at,
        normalized_path=normalized_path,
        comparison_path=comparison_path,
        summary_path=summary_path,
        control_path=control_path,
        template_path=template_path,
    )

    atomic_write_jsonl(normalized_path, official_records, root)
    atomic_write_jsonl(comparison_path, comparisons, root)
    atomic_write_json(summary_path, summary, root)
    atomic_write_json(control_path, summary, root)
    atomic_write_text(template_path, ",".join(CSV_HEADERS) + "\n", root)
    _write_markdown_report(root, summary)
    _update_manifest(root, summary)
    return summary


def _load_geode_rules(root: Path) -> dict[str, dict[str, Any]]:
    """Load local CCR rule index records keyed by canonical regulation ID."""

    index_path = root / REGULATIONS_LAYER / "_index.jsonl"
    if not index_path.exists():
        return {}

    rules: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(index_path):
        rule_id = _canonical_id(_string(row.get("citation"))) or _canonical_id(_string(row.get("id")))
        if not rule_id:
            continue
        rules[rule_id] = row
    return rules


def _load_geode_notices(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Load local rulemaking notice rows keyed by affected CCR rule."""

    notices_by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dataset_path = root / RULEMAKING_LAYER / "_dataset" / "rulemaking_notices.jsonl"
    index_path = root / RULEMAKING_LAYER / "_index.jsonl"
    source_path = dataset_path if dataset_path.exists() else index_path
    if not source_path.exists():
        return {}

    for row in iter_jsonl(source_path):
        rule_id = (
            _canonical_id(_string(row.get("ccr_rule_affected")))
            or _canonical_id(_string(row.get("ccr_citation")))
            or _canonical_id(_string(row.get("citation")))
        )
        if rule_id:
            notices_by_rule[rule_id].append(row)
    return dict(notices_by_rule)


def _load_official_snapshot(
    snapshot_path: Path,
    generated_at: datetime,
) -> list[OfficialRulemakingSearchRecord]:
    """Load a JSON, JSONL, or CSV official snapshot into normalized records."""

    path = snapshot_path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"official snapshot does not exist: {snapshot_path}")

    raw_rows = _read_snapshot_rows(path)
    records: list[OfficialRulemakingSearchRecord] = []
    seen_ids: set[str] = set()
    for row in raw_rows:
        record = _official_record_from_row(row, generated_at)
        if not record or record.id in seen_ids:
            continue
        seen_ids.add(record.id)
        records.append(record)
    return records


def _read_snapshot_rows(path: Path) -> list[dict[str, Any]]:
    """Read supported official snapshot formats."""

    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return list(iter_jsonl(path))
    if suffix == ".json":
        payload = load_json(path)
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("records", "results", "items", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
            return [payload]
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported official snapshot format: {path.suffix}")


def _official_record_from_row(
    row: dict[str, Any],
    generated_at: datetime,
) -> OfficialRulemakingSearchRecord | None:
    """Normalize one flexible official snapshot row."""

    raw_fields = {str(key): _clean_space(_string(value)) for key, value in row.items()}
    ccr_citation = _first_value(row, "ccr_citation")
    parent_id = _canonical_id(ccr_citation)
    if not parent_id:
        return None

    readable_citation = _ccr_from_id(parent_id)
    tracking = _first_value(row, "edocket_tracking_number")
    effective_date = _date_value(_first_value(row, "effective_date"))
    publication_date = _date_value(_first_value(row, "publication_date"))
    source_url = _first_value(row, "source_url")
    status = _first_value(row, "rulemaking_status")
    title = _first_value(row, "rule_title")
    agency = _first_value(row, "agency")
    filing_type = _first_value(row, "filing_type")
    record_id = _official_record_id(parent_id, tracking, effective_date, publication_date, status)

    return OfficialRulemakingSearchRecord(
        id=record_id,
        parent_regulation_id=parent_id,
        ccr_citation=readable_citation or ccr_citation or parent_id,
        rule_title=title,
        agency=agency,
        rulemaking_status=status,
        filing_type=filing_type,
        publication_date=publication_date,
        effective_date=effective_date,
        edocket_tracking_number=tracking,
        source_url=source_url,
        raw_fields=raw_fields,
        generated_at=generated_at,
    )


def _build_comparisons(
    rules: dict[str, dict[str, Any]],
    notices: dict[str, list[dict[str, Any]]],
    official_records: list[OfficialRulemakingSearchRecord],
    generated_at: datetime,
) -> list[RulemakingSearchComparisonRecord]:
    """Compare local Geode evidence to official snapshot evidence."""

    official_by_rule: dict[str, list[OfficialRulemakingSearchRecord]] = defaultdict(list)
    for record in official_records:
        official_by_rule[record.parent_regulation_id].append(record)

    parent_ids = set(rules) | set(notices) | set(official_by_rule)
    if not official_records:
        parent_ids = set(rules) | set(notices)

    rows = [
        _comparison_for_rule(
            parent_id=parent_id,
            rule=rules.get(parent_id),
            notices=notices.get(parent_id, []),
            official_records=official_by_rule.get(parent_id, []),
            official_snapshot_loaded=bool(official_records),
            generated_at=generated_at,
        )
        for parent_id in sorted(parent_ids)
    ]
    return rows


def _comparison_for_rule(
    parent_id: str,
    rule: dict[str, Any] | None,
    notices: list[dict[str, Any]],
    official_records: list[OfficialRulemakingSearchRecord],
    official_snapshot_loaded: bool,
    generated_at: datetime,
) -> RulemakingSearchComparisonRecord:
    """Build one comparison record."""

    method, confidence = _strongest_match(notices, official_records)
    status, flags = _status_for(rule, notices, official_records, official_snapshot_loaded, method)
    citation = _ccr_from_id(parent_id) or _string(rule.get("citation") if rule else None) or parent_id
    geode_notice_ids = sorted(
        _string(row.get("id")) or _string(row.get("source_id")) or ""
        for row in notices
        if _string(row.get("id")) or _string(row.get("source_id"))
    )
    official_statuses = sorted(
        {record.rulemaking_status for record in official_records if record.rulemaking_status}
    )
    official_dates = sorted(
        {record.effective_date for record in official_records if record.effective_date}
    )

    return RulemakingSearchComparisonRecord(
        id=f"RMSEARCH-{parent_id}",
        parent_regulation_id=parent_id,
        ccr_citation=citation,
        geode_rule_present=rule is not None,
        geode_rulemaking_notice_count=len(notices),
        official_match_count=len(official_records),
        strongest_match_method=method,
        strongest_match_confidence=confidence,
        status=status,
        status_flags=flags,
        geode_notice_ids=geode_notice_ids[:25],
        official_record_ids=[record.id for record in official_records[:25]],
        official_statuses=official_statuses,
        official_effective_dates=official_dates,
        verification_summary=_verification_summary(status, citation, len(notices), len(official_records)),
        generated_at=generated_at,
    )


def _strongest_match(
    notices: list[dict[str, Any]],
    official_records: list[OfficialRulemakingSearchRecord],
) -> tuple[str, float]:
    """Return the strongest deterministic match between local notices and official rows."""

    if not official_records:
        return ("no_official_record", 0.0)
    if not notices:
        return ("official_rule_only", 0.7)

    notice_tracking = {
        _clean_space(_string(row.get("edocket_tracking_number"))).casefold()
        for row in notices
        if _string(row.get("edocket_tracking_number"))
    }
    official_tracking = {
        _clean_space(record.edocket_tracking_number).casefold()
        for record in official_records
        if record.edocket_tracking_number
    }
    if notice_tracking and official_tracking and notice_tracking & official_tracking:
        return ("exact_tracking_number", 0.98)

    notice_effective_dates = {_date_value(row.get("effective_date")) for row in notices}
    official_effective_dates = {record.effective_date for record in official_records}
    if None in notice_effective_dates:
        notice_effective_dates.remove(None)
    if None in official_effective_dates:
        official_effective_dates.remove(None)
    if notice_effective_dates and official_effective_dates and notice_effective_dates & official_effective_dates:
        return ("exact_effective_date", 0.93)

    return ("same_ccr_rule", 0.84)


def _status_for(
    rule: dict[str, Any] | None,
    notices: list[dict[str, Any]],
    official_records: list[OfficialRulemakingSearchRecord],
    official_snapshot_loaded: bool,
    method: str,
) -> tuple[str, list[str]]:
    """Return a plain status and review flags."""

    flags: list[str] = []
    if not official_snapshot_loaded:
        return ("awaiting_official_snapshot", ["official_snapshot_needed"])
    if official_records and not rule:
        return ("missing_geode_rule", ["official_rule_not_in_geode", "manual_review"])
    if official_records and method in {"exact_tracking_number", "exact_effective_date", "same_ccr_rule"}:
        if not notices:
            flags.append("official_match_without_local_notice")
            return ("possible_official_match", flags)
        return ("official_match_found", flags)
    if official_records:
        flags.append("official_match_needs_review")
        return ("needs_review", flags)
    if notices:
        return ("geode_only_history", ["geode_history_not_in_official_snapshot"])
    return ("no_official_match", [])


def _build_summary(
    root: Path,
    official_snapshot_path: Path | None,
    rules: dict[str, dict[str, Any]],
    notices: dict[str, list[dict[str, Any]]],
    official_records: list[OfficialRulemakingSearchRecord],
    comparisons: list[RulemakingSearchComparisonRecord],
    generated_at: datetime,
    normalized_path: Path,
    comparison_path: Path,
    summary_path: Path,
    control_path: Path,
    template_path: Path,
) -> RulemakingSearchVerificationSummary:
    """Build the summary object."""

    counts = defaultdict(int)
    for row in comparisons:
        counts[row.status] += 1

    loaded = bool(official_snapshot_path)
    return RulemakingSearchVerificationSummary(
        generated_at=generated_at,
        output_root=root.as_posix(),
        official_snapshot_path=official_snapshot_path.as_posix() if official_snapshot_path else None,
        official_snapshot_loaded=loaded,
        geode_rules_total=len(rules),
        geode_rulemaking_notices_total=sum(len(values) for values in notices.values()),
        official_records_total=len(official_records),
        comparison_records_total=len(comparisons),
        official_match_found=counts["official_match_found"],
        possible_official_match=counts["possible_official_match"],
        no_official_match=counts["no_official_match"],
        geode_only_history=counts["geode_only_history"],
        missing_geode_rule=counts["missing_geode_rule"],
        awaiting_official_snapshot=counts["awaiting_official_snapshot"],
        needs_review=counts["needs_review"],
        normalized_snapshot_path=_relative_to_root(normalized_path, root),
        comparison_path=_relative_to_root(comparison_path, root),
        summary_path=_relative_to_root(summary_path, root),
        control_summary_path=_relative_to_root(control_path, root),
        template_path=_relative_to_root(template_path, root),
        boundary=(
            "This workflow compares Geode CCR and rulemaking records against a saved "
            "Colorado Rulemaking Search snapshot. It does not call the live website during "
            "search and does not treat uncertain matches as confirmed."
        ),
        next_steps=_next_steps(loaded),
    )


def _next_steps(official_snapshot_loaded: bool) -> list[str]:
    """Return practical next steps for the testing workflow."""

    if official_snapshot_loaded:
        return [
            "Review missing_geode_rule and needs_review records first.",
            "Spot-check official_match_found records against the state portal.",
            "Use the comparison file to decide which CCR search results need status warnings.",
        ]
    return [
        "Export or capture a Rulemaking Search snapshot using the template columns.",
        "Run this command again with --official-snapshot pointing to the CSV, JSON, or JSONL file.",
        "Review the comparison output before using the status labels in release testing.",
    ]


def _write_markdown_report(root: Path, summary: RulemakingSearchVerificationSummary) -> None:
    """Write a human-readable readiness report."""

    report_path = root / "docs" / "audits" / "RULEMAKING_SEARCH_VERIFICATION_READY_2026-07-08.md"
    lines = [
        "# Rulemaking Search Verification Readiness",
        "",
        "Date: 2026-07-08",
        "",
        "## Summary",
        "",
        (
            "Geode now has a testing workflow for comparing local CCR and rulemaking "
            "records against an official Colorado Rulemaking Search snapshot."
        ),
        "",
        "## Current Run",
        "",
        f"- Official snapshot loaded: {summary.official_snapshot_loaded}",
        f"- Geode CCR rules considered: {summary.geode_rules_total}",
        f"- Geode rulemaking notices considered: {summary.geode_rulemaking_notices_total}",
        f"- Official records loaded: {summary.official_records_total}",
        f"- Comparison records written: {summary.comparison_records_total}",
        f"- Awaiting official snapshot: {summary.awaiting_official_snapshot}",
        f"- Official matches found: {summary.official_match_found}",
        f"- Missing Geode rules: {summary.missing_geode_rule}",
        f"- Needs review: {summary.needs_review}",
        "",
        "## Files",
        "",
        f"- Template: `{summary.template_path}`",
        f"- Normalized official snapshot: `{summary.normalized_snapshot_path}`",
        f"- Comparison output: `{summary.comparison_path}`",
        f"- Summary: `{summary.summary_path}`",
        f"- Control-plane summary: `{summary.control_summary_path}`",
        "",
        "## Boundary",
        "",
        summary.boundary,
        "",
        "## Next Steps",
        "",
        *[f"- {step}" for step in summary.next_steps],
        "",
    ]
    atomic_write_text(report_path, "\n".join(lines), root)


def _update_manifest(root: Path, summary: RulemakingSearchVerificationSummary) -> None:
    """Record derived verification outputs in the master manifest when available."""

    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    if not manifest_path.exists():
        return
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return

    manifest["rulemaking_search_verification"] = summary.model_dump(mode="json")
    layers = manifest.get("data_layers")
    if isinstance(layers, list):
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            if layer.get("id") not in {REGULATIONS_LAYER, RULEMAKING_LAYER}:
                continue
            layer["derived_files"] = _merge_unique(
                layer.get("derived_files"),
                [
                    summary.comparison_path,
                    summary.summary_path,
                    summary.control_summary_path,
                ],
            )
            layer["known_gaps"] = _merge_unique(
                layer.get("known_gaps"),
                [
                    (
                        "Rulemaking Search comparison workflow is ready; official "
                        "snapshot comparison must be refreshed during release testing."
                    )
                ],
            )
    atomic_write_json(manifest_path, manifest, root)


def _first_value(row: dict[str, Any], canonical_name: str) -> str | None:
    """Return the first non-empty value for a canonical field."""

    aliases = FIELD_ALIASES[canonical_name]
    normalized = {_normalize_key(key): value for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(_normalize_key(alias))
        text = _string(value)
        if text:
            return _clean_space(text)
    return None


def _official_record_id(
    parent_id: str,
    tracking: str | None,
    effective_date: date | None,
    publication_date: date | None,
    status: str | None,
) -> str:
    """Build a stable ID for an official snapshot row."""

    source = "|".join(
        [
            parent_id,
            tracking or "",
            effective_date.isoformat() if effective_date else "",
            publication_date.isoformat() if publication_date else "",
            status or "",
        ]
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    return f"CO-RMSEARCH-{parent_id}-{digest}"


def _canonical_id(value: str | None) -> str | None:
    """Convert a CCR citation or Geode ID to a canonical regulation ID."""

    if not value:
        return None
    cleaned = _clean_space(value).replace("-", "-", 1)
    id_match = CCR_ID_RE.match(cleaned)
    if id_match:
        return f"{id_match.group('dept')}_CCR_{id_match.group('series')}-{id_match.group('rule')}"
    match = CCR_RE.search(cleaned)
    if not match:
        return None
    return f"{match.group('dept')}_CCR_{match.group('series')}-{match.group('rule')}"


def _ccr_from_id(record_id: str | None) -> str | None:
    """Convert a canonical regulation ID to readable CCR citation text."""

    if not record_id:
        return None
    match = CCR_ID_RE.match(record_id)
    if not match:
        return None
    return f"{match.group('dept')} CCR {match.group('series')}-{match.group('rule')}"


def _verification_summary(status: str, citation: str, geode_count: int, official_count: int) -> str:
    """Return a clear human-readable status sentence."""

    if status == "awaiting_official_snapshot":
        return f"{citation} is ready for comparison after an official snapshot is loaded."
    if status == "official_match_found":
        return f"{citation} has Geode rulemaking history and an official snapshot match."
    if status == "possible_official_match":
        return f"{citation} appears in the official snapshot but needs local notice review."
    if status == "missing_geode_rule":
        return f"{citation} appears in the official snapshot but not in the Geode CCR index."
    if status == "geode_only_history":
        return f"{citation} has {geode_count} Geode notice(s) but no official snapshot match."
    if status == "no_official_match":
        return f"{citation} has no official snapshot match in this comparison run."
    return f"{citation} needs review. Geode notices: {geode_count}; official rows: {official_count}."


def _date_value(value: object) -> date | None:
    """Parse common official date formats."""

    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = _string(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _clean_space(value: str | None) -> str:
    """Normalize whitespace."""

    return re.sub(r"\s+", " ", value or "").strip()


def _string(value: object) -> str | None:
    """Return a stripped string or None."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_key(value: object) -> str:
    """Normalize a field name for alias matching."""

    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _relative_to_root(path: Path, root: Path) -> str:
    """Return a project-relative path where possible."""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _merge_unique(existing: object, values: Iterable[str]) -> list[str]:
    """Merge list values without duplicates."""

    merged = [str(value) for value in existing] if isinstance(existing, list) else []
    for value in values:
        if value not in merged:
            merged.append(value)
    return merged


def main(argv: list[str] | None = None) -> int:
    """Run the Rulemaking Search verification workflow."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--official-snapshot", type=Path, default=None)
    args = parser.parse_args(argv)
    summary = run_rulemaking_search_verification(args.root, args.official_snapshot)
    import sys

    sys.stdout.write(summary.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
