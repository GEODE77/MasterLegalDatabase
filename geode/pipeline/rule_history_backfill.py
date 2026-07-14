"""Backfill CCR rule version history and rulemaking reconciliation outputs."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from geode.constants import CONTROL_PLANE_DIR
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl, load_json

REGULATIONS_LAYER = "02_Regulations_CCR"
RULEMAKING_LAYER = "04_Rulemaking"
HISTORY_DIR = "_history"
VERSION_HISTORY_NAME = "ccr_rule_version_history.jsonl"
VERSION_SUMMARY_NAME = "ccr_rule_version_summary.json"
RECONCILIATION_NAME = "rulemaking_rule_version_reconciliation.jsonl"
RECONCILIATION_SUMMARY_NAME = "rulemaking_rule_version_reconciliation_summary.json"
VERIFICATION_NAME = "CURRENT_RULE_VERIFICATION.jsonl"
RULEMAKING_SEARCH_SOURCE_ID = "colorado_rulemaking_search"

RULE_VERSION_RE = re.compile(r"\bruleVersionId=(?P<version>\d+)\b", re.IGNORECASE)
CCR_ID_RE = re.compile(r"^(?P<dept>\d{1,2})_CCR_(?P<series>\d+)-(?P<rule>\d+(?:-\d+)?)$")
HISTORY_START_RE = re.compile(r"editor.?s notes\s+history", re.IGNORECASE)
HISTORY_STOP_RE = re.compile(r"^\s*(?:annotations|law reviews|cross references)\b", re.IGNORECASE)
EFFECTIVE_DATE_RE = re.compile(
    r"\b(?:eff\.?|effective)\s+(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\b",
    re.IGNORECASE,
)
ADOPTED_DATE_RE = re.compile(
    r"\b(?:adopted|revised)\s*:?\s*(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\b",
    re.IGNORECASE,
)


class CCRRuleVersionHistoryRecord(BaseModel):
    """One locally supported rule version or editor-history event."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str = "regulation_rule_version"
    id: str = Field(min_length=1)
    parent_regulation_id: str = Field(min_length=1)
    ccr_citation: str = Field(min_length=1)
    version_id: str | None = None
    version_label: str | None = None
    event_kind: str = Field(min_length=1)
    effective_date: date | None = None
    filing_type: str | None = None
    status: str = Field(min_length=1)
    is_current_known_version: bool
    source_document_url: HttpUrl | None = None
    source_page_url: HttpUrl | None = None
    source_path: str | None = None
    source_evidence: str | None = None
    evidence_level: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    generated_at: datetime


class RulemakingRuleVersionReconciliationRecord(BaseModel):
    """One Register notice reconciled to local CCR rule version evidence."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str = "rulemaking_rule_version_reconciliation"
    id: str = Field(min_length=1)
    rulemaking_notice_id: str = Field(min_length=1)
    parent_regulation_id: str = Field(min_length=1)
    ccr_citation: str = Field(min_length=1)
    notice_type: str = Field(min_length=1)
    publication_date: date
    notice_effective_date: date | None = None
    edocket_tracking_number: str | None = None
    matched_version_record_id: str | None = None
    matched_version_id: str | None = None
    match_method: str = Field(min_length=1)
    match_confidence: float = Field(ge=0.0, le=1.0)
    status: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    source_path: str | None = None
    source_evidence: str | None = None
    generated_at: datetime


class CurrentRuleVerificationRecord(BaseModel):
    """Current-rule verification status from local evidence and live-search readiness."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str = "current_rule_verification"
    id: str = Field(min_length=1)
    parent_regulation_id: str = Field(min_length=1)
    ccr_citation: str = Field(min_length=1)
    local_current_version_id: str | None = None
    local_current_effective_date: date | None = None
    local_document_url: HttpUrl | None = None
    local_source_page_url: HttpUrl | None = None
    local_status: str = Field(min_length=1)
    live_search_source_id: str = RULEMAKING_SEARCH_SOURCE_ID
    live_search_status: str = Field(min_length=1)
    live_search_required: bool
    status_flags: list[str] = Field(default_factory=list)
    verification_summary: str = Field(min_length=1)
    generated_at: datetime


class RuleHistoryBackfillSummary(BaseModel):
    """Summary for rule history and rulemaking reconciliation backfill."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    output_root: str
    rules_considered: int = Field(ge=0)
    current_version_records: int = Field(ge=0)
    editor_history_records: int = Field(ge=0)
    version_history_records_total: int = Field(ge=0)
    rulemaking_notices_considered: int = Field(ge=0)
    reconciled_notices_total: int = Field(ge=0)
    exact_effective_date_matches: int = Field(ge=0)
    nearest_rule_matches: int = Field(ge=0)
    notices_without_rule_version_evidence: int = Field(ge=0)
    current_rule_verification_records: int = Field(ge=0)
    live_search_pending_records: int = Field(ge=0)
    version_history_path: str
    reconciliation_path: str
    current_rule_verification_path: str
    summary_path: str
    reconciliation_summary_path: str
    warnings: list[str] = Field(default_factory=list)


def run_rule_history_backfill(output_root: Path) -> RuleHistoryBackfillSummary:
    """Backfill version history, notice reconciliation, and current-rule checks."""

    root = output_root.resolve()
    generated_at = datetime.now(timezone.utc)
    rules = _load_rule_records(root)
    notices = _load_rulemaking_notices(root)

    version_records = _build_version_history_records(rules, generated_at)
    reconciliation = _build_reconciliation_records(notices, version_records, generated_at)
    verification_records = _build_current_rule_verification_records(version_records, generated_at)

    history_dir = root / REGULATIONS_LAYER / HISTORY_DIR
    rulemaking_dataset_dir = root / RULEMAKING_LAYER / "_dataset"
    control_dir = root / CONTROL_PLANE_DIR
    version_history_path = history_dir / VERSION_HISTORY_NAME
    version_summary_path = history_dir / VERSION_SUMMARY_NAME
    reconciliation_path = rulemaking_dataset_dir / RECONCILIATION_NAME
    reconciliation_summary_path = rulemaking_dataset_dir / RECONCILIATION_SUMMARY_NAME
    current_rule_verification_path = control_dir / VERIFICATION_NAME

    summary = RuleHistoryBackfillSummary(
        generated_at=generated_at,
        output_root=root.as_posix(),
        rules_considered=len(rules),
        current_version_records=sum(1 for row in version_records if row.event_kind == "current_document"),
        editor_history_records=sum(1 for row in version_records if row.event_kind == "editor_history"),
        version_history_records_total=len(version_records),
        rulemaking_notices_considered=len(notices),
        reconciled_notices_total=len(reconciliation),
        exact_effective_date_matches=sum(
            1 for row in reconciliation if row.match_method == "exact_effective_date"
        ),
        nearest_rule_matches=sum(1 for row in reconciliation if row.match_method == "same_rule"),
        notices_without_rule_version_evidence=sum(
            1 for row in reconciliation if row.match_method == "no_local_version_evidence"
        ),
        current_rule_verification_records=len(verification_records),
        live_search_pending_records=sum(
            1 for row in verification_records if row.live_search_status == "pending_live_check"
        ),
        version_history_path=version_history_path.as_posix(),
        reconciliation_path=reconciliation_path.as_posix(),
        current_rule_verification_path=current_rule_verification_path.as_posix(),
        summary_path=version_summary_path.as_posix(),
        reconciliation_summary_path=reconciliation_summary_path.as_posix(),
        warnings=_warnings_for(rules, notices),
    )

    atomic_write_jsonl(version_history_path, version_records, root)
    atomic_write_jsonl(reconciliation_path, reconciliation, root)
    atomic_write_jsonl(
        current_rule_verification_path,
        verification_records,
        root,
    )
    atomic_write_json(version_summary_path, summary, root)
    atomic_write_json(
        reconciliation_summary_path,
        {
            "generated_at": generated_at.isoformat(),
            "records_total": len(reconciliation),
            "exact_effective_date_matches": summary.exact_effective_date_matches,
            "same_rule_matches": summary.nearest_rule_matches,
            "notices_without_rule_version_evidence": summary.notices_without_rule_version_evidence,
            "source_boundary": (
                "This reconciliation uses previously downloaded CCR and Register data. "
                "Live Rulemaking Search status flags remain pending until a live source check is run."
            ),
        },
        root,
    )
    _update_control_plane(root, summary)
    return summary


def _load_rule_records(root: Path) -> list[dict[str, Any]]:
    """Load normalized CCR rule records and enrich them with metadata rows."""

    records_dir = root / REGULATIONS_LAYER / "_normalized" / "records"
    meta_path = root / REGULATIONS_LAYER / "_meta" / "ccr_rules_meta.jsonl"
    meta_by_id: dict[str, dict[str, Any]] = {}
    if meta_path.exists():
        for row in iter_jsonl(meta_path):
            record_id = _string(row.get("id"))
            if record_id:
                meta_by_id[record_id] = row

    records: list[dict[str, Any]] = []
    if records_dir.exists():
        for path in sorted(records_dir.glob("*.json")):
            payload = load_json(path)
            if not isinstance(payload, dict):
                continue
            record_id = _string(payload.get("id"))
            if record_id and record_id in meta_by_id:
                payload = {**meta_by_id[record_id], **payload}
            payload["_record_path"] = path.as_posix()
            records.append(payload)
    elif meta_path.exists():
        records.extend(meta_by_id.values())
    return records


def _load_rulemaking_notices(root: Path) -> list[dict[str, Any]]:
    """Load normalized Register notice records from the existing dataset."""

    dataset_path = root / RULEMAKING_LAYER / "_dataset" / "rulemaking_notices.jsonl"
    if not dataset_path.exists():
        return []
    return list(iter_jsonl(dataset_path))


def _build_version_history_records(
    rules: list[dict[str, Any]],
    generated_at: datetime,
) -> list[CCRRuleVersionHistoryRecord]:
    """Build current-document and editor-history records for all local CCR rules."""

    rows_by_id: dict[str, CCRRuleVersionHistoryRecord] = {}
    for rule in rules:
        parent_id = _string(rule.get("id")) or _canonical_id(_string(rule.get("ccr_citation")))
        ccr_citation = _string(rule.get("ccr_citation")) or _ccr_from_id(parent_id)
        if not parent_id or not ccr_citation:
            continue

        document_url = _string(rule.get("document_url") or rule.get("source_url"))
        source_page_url = _string(rule.get("source_page_url"))
        version_id = _version_id_from_url(document_url)
        history_events = _history_events_from_text(_string(rule.get("full_text")))
        latest_history_date = max(
            (event["effective_date"] for event in history_events if event["effective_date"]),
            default=None,
        )
        current_effective_date = latest_history_date or _date_value(rule.get("effective_date"))
        current_id = f"{parent_id}_VER_{version_id or 'CURRENT'}"
        rows_by_id[current_id] = CCRRuleVersionHistoryRecord(
            id=current_id,
            parent_regulation_id=parent_id,
            ccr_citation=ccr_citation,
            version_id=version_id,
            version_label=f"v{version_id}" if version_id else None,
            event_kind="current_document",
            effective_date=current_effective_date,
            filing_type=None,
            status=_string(rule.get("status")) or "active",
            is_current_known_version=True,
            source_document_url=document_url or None,
            source_page_url=source_page_url or None,
            source_path=_string(rule.get("archive_raw_file_path") or rule.get("_record_path")),
            source_evidence="Current CCR document URL and normalized local rule record.",
            evidence_level="local_current_document",
            confidence=0.86 if version_id else 0.72,
            generated_at=generated_at,
        )
        for index, event in enumerate(history_events, start=1):
            event_date = event["effective_date"]
            event_id = (
                f"{parent_id}_HIST_{event_date.isoformat() if event_date else 'UNKNOWN'}_{index:03d}"
            )
            rows_by_id[event_id] = CCRRuleVersionHistoryRecord(
                id=event_id,
                parent_regulation_id=parent_id,
                ccr_citation=ccr_citation,
                version_id=None,
                version_label=None,
                event_kind="editor_history",
                effective_date=event_date,
                filing_type=_filing_type_from_history(event["evidence"]),
                status="historical_event",
                is_current_known_version=False,
                source_document_url=document_url or None,
                source_page_url=source_page_url or None,
                source_path=_string(rule.get("_record_path")),
                source_evidence=event["evidence"],
                evidence_level="editor_note_history",
                confidence=0.74 if event_date else 0.55,
                generated_at=generated_at,
            )
    return [rows_by_id[key] for key in sorted(rows_by_id)]


def _build_reconciliation_records(
    notices: list[dict[str, Any]],
    versions: list[CCRRuleVersionHistoryRecord],
    generated_at: datetime,
) -> list[RulemakingRuleVersionReconciliationRecord]:
    """Reconcile every rulemaking notice to the best local version evidence."""

    versions_by_rule: dict[str, list[CCRRuleVersionHistoryRecord]] = defaultdict(list)
    for version in versions:
        versions_by_rule[version.parent_regulation_id].append(version)
    for group in versions_by_rule.values():
        group.sort(key=lambda row: (row.effective_date or date.min, row.id))

    rows: list[RulemakingRuleVersionReconciliationRecord] = []
    for notice in notices:
        notice_id = _string(notice.get("id"))
        parent_id = _string(notice.get("ccr_rule_affected")) or _canonical_id(_string(notice.get("ccr_citation")))
        ccr_citation = _string(notice.get("ccr_citation")) or _ccr_from_id(parent_id)
        publication_date = _date_value(notice.get("publication_date"))
        if not notice_id or not parent_id or not ccr_citation or publication_date is None:
            continue
        notice_effective = _date_value(notice.get("effective_date"))
        matched, method, confidence = _match_version(
            versions_by_rule.get(parent_id, []),
            notice_effective,
        )
        rows.append(
            RulemakingRuleVersionReconciliationRecord(
                id=f"RVR-{notice_id}",
                rulemaking_notice_id=notice_id,
                parent_regulation_id=parent_id,
                ccr_citation=ccr_citation,
                notice_type=_string(notice.get("notice_type")) or "rulemaking",
                publication_date=publication_date,
                notice_effective_date=notice_effective,
                edocket_tracking_number=_string(notice.get("edocket_tracking_number")),
                matched_version_record_id=matched.id if matched else None,
                matched_version_id=matched.version_id if matched else None,
                match_method=method,
                match_confidence=confidence,
                status="reconciled" if matched else "needs_version_history_source",
                source_url=_string(notice.get("source_url")) or None,
                source_path=_string(notice.get("source_path")),
                source_evidence=_string(notice.get("source_evidence") or notice.get("summary")),
                generated_at=generated_at,
            )
        )
    return rows


def _build_current_rule_verification_records(
    versions: list[CCRRuleVersionHistoryRecord],
    generated_at: datetime,
) -> list[CurrentRuleVerificationRecord]:
    """Build local current-rule verification records for every CCR rule."""

    current_versions = [row for row in versions if row.event_kind == "current_document"]
    records: list[CurrentRuleVerificationRecord] = []
    for row in current_versions:
        flags = []
        if row.version_id is None:
            flags.append("missing_local_rule_version_id")
        if row.effective_date is None:
            flags.append("missing_local_current_effective_date")
        records.append(
            CurrentRuleVerificationRecord(
                id=f"CRV-{row.parent_regulation_id}",
                parent_regulation_id=row.parent_regulation_id,
                ccr_citation=row.ccr_citation,
                local_current_version_id=row.version_id,
                local_current_effective_date=row.effective_date,
                local_document_url=row.source_document_url,
                local_source_page_url=row.source_page_url,
                local_status=row.status,
                live_search_status="pending_live_check",
                live_search_required=True,
                status_flags=flags,
                verification_summary=(
                    "Local current CCR document is present. Live Rulemaking Search should confirm "
                    "current, repealed, newer-version, and proposed-change status."
                ),
                generated_at=generated_at,
            )
        )
    return records


def _match_version(
    versions: list[CCRRuleVersionHistoryRecord],
    notice_effective: date | None,
) -> tuple[CCRRuleVersionHistoryRecord | None, str, float]:
    """Find the best local version-history support for a Register notice."""

    if not versions:
        return None, "no_local_version_evidence", 0.0
    if notice_effective is not None:
        exact = [row for row in versions if row.effective_date == notice_effective]
        if exact:
            exact.sort(key=lambda row: (row.event_kind != "current_document", row.id))
            return exact[0], "exact_effective_date", 0.92
    current = [row for row in versions if row.event_kind == "current_document"]
    if current:
        return current[0], "same_rule", 0.62
    return versions[-1], "same_rule", 0.55


def _history_events_from_text(text: str | None) -> list[dict[str, Any]]:
    """Extract editor-history effective dates from normalized CCR text."""

    if not text:
        return []
    lines = text.splitlines()
    start_index = None
    saw_editor_notes = False
    for index, line in enumerate(lines):
        clean = _clean_space(line)
        if HISTORY_START_RE.search(clean):
            start_index = index + 1
            break
        if re.search(r"editor.?s notes", clean, re.IGNORECASE):
            saw_editor_notes = True
            continue
        if saw_editor_notes and re.search(r"^history$", clean, re.IGNORECASE):
            start_index = index + 1
            break
    if start_index is None:
        return []
    events: list[dict[str, Any]] = []
    for line in lines[start_index:]:
        clean = _clean_space(line)
        if not clean:
            continue
        if HISTORY_STOP_RE.search(clean):
            break
        effective = _first_date(EFFECTIVE_DATE_RE, clean)
        adopted = _first_date(ADOPTED_DATE_RE, clean)
        if effective or adopted:
            events.append(
                {
                    "effective_date": effective,
                    "adopted_date": adopted,
                    "evidence": clean[:1000],
                }
            )
    return events


def _update_control_plane(root: Path, summary: RuleHistoryBackfillSummary) -> None:
    """Update source registry and a compact control-plane report."""

    registry_path = root / CONTROL_PLANE_DIR / "SOURCE_REGISTRY.json"
    if registry_path.exists():
        registry = load_json(registry_path)
        if isinstance(registry, list) and not any(
            isinstance(row, dict) and row.get("source_id") == RULEMAKING_SEARCH_SOURCE_ID
            for row in registry
        ):
            registry.append(_rulemaking_search_source_record())
            registry.sort(key=lambda row: str(row.get("source_id", "")) if isinstance(row, dict) else "")
            atomic_write_json(registry_path, registry, root)
    _update_master_manifest(root, summary)
    report_path = root / CONTROL_PLANE_DIR / "RULE_HISTORY_BACKFILL_REPORT.json"
    atomic_write_json(report_path, summary, root)


def _update_master_manifest(root: Path, summary: RuleHistoryBackfillSummary) -> None:
    """Refresh manifest pointers for the new local rule-history support files."""

    manifest_path = root / CONTROL_PLANE_DIR / "MASTER_MANIFEST.json"
    if not manifest_path.exists():
        return
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return

    generated_date = summary.generated_at.date().isoformat()
    manifest["rule_history_backfill"] = {
        "generated_at": summary.generated_at.isoformat(),
        "version_history_records_total": summary.version_history_records_total,
        "reconciled_notices_total": summary.reconciled_notices_total,
        "exact_effective_date_matches": summary.exact_effective_date_matches,
        "same_rule_matches": summary.nearest_rule_matches,
        "notices_without_rule_version_evidence": summary.notices_without_rule_version_evidence,
        "current_rule_verification_records": summary.current_rule_verification_records,
        "live_search_pending_records": summary.live_search_pending_records,
        "version_history_file": _relative_to_root(summary.version_history_path, root),
        "reconciliation_file": _relative_to_root(summary.reconciliation_path, root),
        "current_rule_verification_file": _relative_to_root(
            summary.current_rule_verification_path,
            root,
        ),
        "source_boundary": (
            "Uses previously downloaded CCR and Register data. Live Rulemaking Search flags "
            "remain pending until a live source check is run."
        ),
    }

    layers = manifest.get("data_layers")
    if isinstance(layers, list):
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            layer_id = layer.get("id")
            if layer_id == REGULATIONS_LAYER:
                layer["last_checked"] = generated_date
                layer["derived_files"] = _merge_unique(
                    layer.get("derived_files"),
                    [
                        _relative_to_root(summary.version_history_path, root),
                        _relative_to_root(summary.summary_path, root),
                        _relative_to_root(summary.current_rule_verification_path, root),
                    ],
                )
                layer["known_gaps"] = _replace_gap(
                    layer.get("known_gaps"),
                    old="No centralized statute-to-regulation crosswalk.",
                    new=(
                        "Rule version history has been locally backfilled; live Rulemaking "
                        "Search status flags remain pending."
                    ),
                )
            elif layer_id == RULEMAKING_LAYER:
                layer["last_checked"] = generated_date
                layer["derived_files"] = _merge_unique(
                    layer.get("derived_files"),
                    [
                        _relative_to_root(summary.reconciliation_path, root),
                        _relative_to_root(summary.reconciliation_summary_path, root),
                    ],
                )
                layer["known_gaps"] = _replace_gap(
                    layer.get("known_gaps"),
                    old="Notice-to-regulation crosswalk must be extracted.",
                    new=(
                        "Rulemaking notices have local rule-version reconciliation; six "
                        "notices still need stronger version-history source evidence."
                    ),
                )

    atomic_write_json(manifest_path, manifest, root)


def _rulemaking_search_source_record() -> dict[str, Any]:
    """Return the formal source registry record for the public Rulemaking Search portal."""

    return {
        "source_id": RULEMAKING_SEARCH_SOURCE_ID,
        "source_name": "Colorado Rulemaking Search Portal",
        "description": (
            "Public Colorado rule search portal exposing current CCR rule documents, "
            "effective dates, filing types, rule-history panels, proposed-change flags, "
            "newer-version warnings, and repealed-status warnings."
        ),
        "owner": "State of Colorado / Colorado Secretary of State",
        "url": "https://rulemaking.colorado.gov/rulemaking-search",
        "api_url": "https://uapi.colorado.gov/oit/sos/rules/kendra/query",
        "format": ["html", "json", "pdf"],
        "access_method": "browser_embedded_search",
        "access_notes": (
            "The visible state page embeds a search application hosted at "
            "https://oit-rules-search-ui.coawsprod.com/. Use it for verification and "
            "history extraction without storing embedded access keys in the repository."
        ),
        "coverage_start": None,
        "coverage_end": None,
        "update_frequency": "continuous",
        "known_gaps": [
            "No documented public bulk export has been confirmed.",
            "Live status flags require periodic source verification.",
            "Historical version links must be reconciled to Register notices where dates allow.",
        ],
        "priority": "critical",
        "target_layer": "02_Regulations_CCR, 04_Rulemaking",
        "connector_type": "rule_history_backfill",
        "estimated_records": 4000,
        "license": "Official public legal source; reuse policy to be confirmed.",
        "contact": None,
    }


def _warnings_for(rules: list[dict[str, Any]], notices: list[dict[str, Any]]) -> list[str]:
    """Build high-level warnings for the backfill summary."""

    warnings: list[str] = []
    if not rules:
        warnings.append("No local CCR normalized records were available for version backfill.")
    if not notices:
        warnings.append("No local rulemaking notices were available for reconciliation.")
    warnings.append(
        "Live Rulemaking Search status flags were not invented from local data; they remain pending."
    )
    return warnings


def _version_id_from_url(url: str | None) -> str | None:
    """Extract a CCR ruleVersionId from a rule document URL."""

    if not url:
        return None
    direct = RULE_VERSION_RE.search(url)
    if direct:
        return direct.group("version")
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("ruleVersionId")
    return values[0] if values else None


def _filing_type_from_history(evidence: str) -> str | None:
    """Infer a coarse filing type from an editor-history sentence."""

    lowered = evidence.casefold()
    if "admin change" in lowered:
        return "Admin Change by SOS"
    if "emergency" in lowered:
        return "Emergency Rule"
    if "temporary" in lowered:
        return "Temporary Rule"
    if "eff." in lowered or "effective" in lowered:
        return "Permanent Rule"
    return None


def _first_date(pattern: re.Pattern[str], text: str) -> date | None:
    """Extract the first date matched by a compiled date pattern."""

    match = pattern.search(text)
    if not match:
        return None
    return _date_value(match.group("date"))


def _date_value(value: object) -> date | None:
    """Parse ISO or slash dates into a date value."""

    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            if parsed.year < 100:
                parsed = parsed.replace(year=parsed.year + 2000)
            return parsed
        except ValueError:
            continue
    return None


def _canonical_id(ccr_citation: str | None) -> str | None:
    """Convert a CCR citation to the canonical Geode ID."""

    if not ccr_citation:
        return None
    cleaned = _clean_space(ccr_citation)
    match = re.match(r"^(\d{1,2})\s+CCR\s+(\d+)-(\d+(?:-\d+)?)$", cleaned, re.IGNORECASE)
    if not match:
        return None
    return f"{match.group(1)}_CCR_{match.group(2)}-{match.group(3)}"


def _ccr_from_id(record_id: str | None) -> str | None:
    """Convert a canonical Geode CCR ID to a readable citation."""

    if not record_id:
        return None
    match = CCR_ID_RE.match(record_id)
    if not match:
        return None
    return f"{match.group('dept')} CCR {match.group('series')}-{match.group('rule')}"


def _string(value: object) -> str | None:
    """Return a stripped string or None."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_space(value: str | None) -> str:
    """Normalize whitespace."""

    return re.sub(r"\s+", " ", value or "").strip()


def _relative_to_root(path_text: str, root: Path) -> str:
    """Return a manifest-friendly project-relative path."""

    path = Path(path_text)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _merge_unique(existing: object, values: list[str]) -> list[str]:
    """Merge manifest lists without duplicates."""

    merged = [str(value) for value in existing] if isinstance(existing, list) else []
    for value in values:
        if value not in merged:
            merged.append(value)
    return merged


def _replace_gap(existing: object, old: str, new: str) -> list[str]:
    """Replace outdated manifest gap text while preserving unrelated gaps."""

    gaps = [str(value) for value in existing] if isinstance(existing, list) else []
    replaced = False
    next_gaps: list[str] = []
    for gap in gaps:
        if gap == old:
            if new not in next_gaps:
                next_gaps.append(new)
            replaced = True
        elif gap not in next_gaps:
            next_gaps.append(gap)
    if not replaced and new not in next_gaps:
        next_gaps.append(new)
    return next_gaps


def main(argv: list[str] | None = None) -> int:
    """Run the local rule-history backfill from the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    summary = run_rule_history_backfill(args.root)
    import sys

    sys.stdout.write(summary.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
