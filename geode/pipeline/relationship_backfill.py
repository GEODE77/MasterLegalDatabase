"""Backfill relationship crosswalks from existing source-backed Geode records."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, iter_jsonl

SUMMARY_PATH = Path("_CONTROL_PLANE/RELATIONSHIP_BACKFILL_SUMMARY.json")
AGENCY_TO_STATUTE_PATH = Path("_CROSSWALKS/agency_to_statute.jsonl")
AMENDMENT_HISTORY_PATH = Path("_CROSSWALKS/amendment_history.jsonl")


class AgencyToStatuteEntry(BaseModel):
    """Derived agency-to-statute relationship backed by a CCR rule citation."""

    entity_type: str = "crosswalk_entry"
    source_id: str
    source_type: str = "agency"
    target_id: str
    target_ids: list[str] = Field(default_factory=list)
    target_type: str = "statute_section"
    relationship: str = "has_rule_citing_statute"
    confidence: float = Field(ge=0.0, le=1.0)
    source_evidence: str
    data_retrieved: str
    agency_name: str
    department_name: str | None = None
    supporting_regulation_id: str


class AmendmentHistoryEntry(BaseModel):
    """Derived amendment history entry backed by bill-to-statute data."""

    entity_type: str = "amendment_history_entry"
    statute_id: str
    event_id: str
    event_type: str
    event_date: str | None = None
    bill_id: str
    bill_title: str | None = None
    bill_status: str | None = None
    source_url: str | None = None
    source_evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
    data_retrieved: str


class RelationshipBackfillSummary(BaseModel):
    """Summary of relationship backfill outputs."""

    generated_at: datetime
    agency_to_statute_path: str
    agency_to_statute_rows: int = Field(ge=0)
    amendment_history_path: str
    amendment_history_rows: int = Field(ge=0)
    source_boundaries: list[str]


def build_relationship_backfill(root: Path) -> tuple[list[AgencyToStatuteEntry], list[AmendmentHistoryEntry]]:
    """Build agency and amendment relationship rows from existing corpus evidence."""

    resolved_root = root.resolve()
    agency_rows = _build_agency_to_statute(resolved_root)
    amendment_rows = _build_amendment_history(resolved_root)
    return agency_rows, amendment_rows


def write_relationship_backfill(root: Path) -> RelationshipBackfillSummary:
    """Write agency-to-statute and amendment-history crosswalks."""

    resolved_root = root.resolve()
    agency_rows, amendment_rows = build_relationship_backfill(resolved_root)
    summary = RelationshipBackfillSummary(
        generated_at=datetime.now(timezone.utc),
        agency_to_statute_path=AGENCY_TO_STATUTE_PATH.as_posix(),
        agency_to_statute_rows=len(agency_rows),
        amendment_history_path=AMENDMENT_HISTORY_PATH.as_posix(),
        amendment_history_rows=len(amendment_rows),
        source_boundaries=[
            "Agency-to-statute rows are derived through regulation-to-statute relationships.",
            "Amendment-history rows are derived from existing bill-to-statute relationships.",
            "No direct legal conclusion is added beyond the source-backed relationship chain.",
        ],
    )
    atomic_write_jsonl(resolved_root / AGENCY_TO_STATUTE_PATH, agency_rows, resolved_root)
    atomic_write_jsonl(resolved_root / AMENDMENT_HISTORY_PATH, amendment_rows, resolved_root)
    atomic_write_json(resolved_root / SUMMARY_PATH, summary, resolved_root)
    return summary


def _build_agency_to_statute(root: Path) -> list[AgencyToStatuteEntry]:
    """Build agency-to-statute rows through CCR regulation authority links."""

    metadata = _ccr_metadata_by_id(root)
    rows: list[AgencyToStatuteEntry] = []
    seen: set[tuple[str, str, str]] = set()
    today = datetime.now(timezone.utc).date().isoformat()
    for relation in _read_jsonl(root / "_CROSSWALKS" / "regulation_to_statute.jsonl"):
        regulation_id = _optional_str(relation.get("source_id"))
        statute_id = _optional_str(relation.get("target_id"))
        if not regulation_id or not statute_id:
            continue
        meta = metadata.get(regulation_id)
        if not meta:
            continue
        agency_name = _optional_str(meta.get("agency_normalized")) or _optional_str(meta.get("agency"))
        department_name = _optional_str(meta.get("department_normalized")) or _optional_str(
            meta.get("department")
        )
        if not agency_name:
            continue
        agency_id = _agency_id(agency_name, department_name)
        key = (agency_id, statute_id, regulation_id)
        if key in seen:
            continue
        seen.add(key)
        evidence = _optional_str(relation.get("source_evidence")) or (
            f"{regulation_id} cites {statute_id}."
        )
        rows.append(
            AgencyToStatuteEntry(
                source_id=agency_id,
                target_id=statute_id,
                confidence=min(_confidence(relation.get("confidence")), 0.68),
                source_evidence=f"{agency_name} is tied to {regulation_id}; {evidence}",
                data_retrieved=today,
                agency_name=agency_name,
                department_name=department_name,
                supporting_regulation_id=regulation_id,
            )
        )
    return sorted(rows, key=lambda row: (row.source_id, row.target_id, row.supporting_regulation_id))


def _build_amendment_history(root: Path) -> list[AmendmentHistoryEntry]:
    """Build amendment history rows from bill-to-statute crosswalks."""

    bill_meta = _bill_metadata_by_id(root)
    rows: list[AmendmentHistoryEntry] = []
    seen: set[tuple[str, str, str]] = set()
    today = datetime.now(timezone.utc).date().isoformat()
    for relation in _read_jsonl(root / "_CROSSWALKS" / "bill_to_statute.jsonl"):
        bill_id = _optional_str(relation.get("source_id"))
        statute_id = _optional_str(relation.get("target_id"))
        relationship = _optional_str(relation.get("relationship")) or "amends"
        if not bill_id or not statute_id:
            continue
        key = (statute_id, bill_id, relationship)
        if key in seen:
            continue
        seen.add(key)
        bill = bill_meta.get(bill_id, {})
        event_date = _optional_str(bill.get("status_date")) or _optional_str(bill.get("introduced_date"))
        evidence = _optional_str(relation.get("source_evidence")) or f"{bill_id} {relationship} {statute_id}."
        rows.append(
            AmendmentHistoryEntry(
                statute_id=statute_id,
                event_id=f"AH-{_slug(statute_id)}-{_slug(bill_id)}",
                event_type=relationship,
                event_date=event_date,
                bill_id=bill_id,
                bill_title=_optional_str(bill.get("title")),
                bill_status=_optional_str(bill.get("status")),
                source_url=_optional_str(bill.get("source_url")),
                source_evidence=evidence,
                confidence=_confidence(relation.get("confidence")),
                data_retrieved=today,
            )
        )
    return sorted(rows, key=lambda row: (row.statute_id, row.event_date or "", row.bill_id))


def _ccr_metadata_by_id(root: Path) -> dict[str, dict[str, Any]]:
    """Return normalized CCR metadata keyed by regulation id."""

    return {
        _id: row
        for row in _read_jsonl(root / "02_Regulations_CCR" / "_meta" / "ccr_normalized_meta.jsonl")
        if (_id := _optional_str(row.get("id")))
    }


def _bill_metadata_by_id(root: Path) -> dict[str, dict[str, Any]]:
    """Return bill metadata keyed by bill id."""

    records: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "03_Legislation").glob("*/bills_*.jsonl")):
        for row in _read_jsonl(path):
            bill_id = _optional_str(row.get("id"))
            if bill_id:
                records[bill_id] = row
    return records


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows if the path exists."""

    if not path.exists() or path.stat().st_size == 0:
        return []
    return list(iter_jsonl(path))


def _agency_id(agency_name: str, department_name: str | None) -> str:
    """Build a stable derived agency id."""

    base = f"{department_name or 'agency'} {agency_name}"
    return f"AGENCY-{_slug(base)}"


def _slug(value: str) -> str:
    """Return a compact uppercase slug."""

    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return normalized.upper() or "UNKNOWN"


def _optional_str(value: object) -> str | None:
    """Convert a value to a non-empty optional string."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _confidence(value: object) -> float:
    """Normalize confidence to a 0-1 float."""

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(confidence, 0.0), 1.0)


def main() -> None:
    """Build or write relationship backfill artifacts."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    if args.write:
        summary = write_relationship_backfill(root)
    else:
        agency_rows, amendment_rows = build_relationship_backfill(root)
        summary = RelationshipBackfillSummary(
            generated_at=datetime.now(timezone.utc),
            agency_to_statute_path=AGENCY_TO_STATUTE_PATH.as_posix(),
            agency_to_statute_rows=len(agency_rows),
            amendment_history_path=AMENDMENT_HISTORY_PATH.as_posix(),
            amendment_history_rows=len(amendment_rows),
            source_boundaries=[
                "Agency-to-statute rows are derived through regulation-to-statute relationships.",
                "Amendment-history rows are derived from existing bill-to-statute relationships.",
                "No direct legal conclusion is added beyond the source-backed relationship chain.",
            ],
        )
    if args.json:
        print(summary.model_dump_json(indent=2))
        return
    print(f"Agency-to-statute rows: {summary.agency_to_statute_rows}")
    print(f"Amendment-history rows: {summary.amendment_history_rows}")


if __name__ == "__main__":
    main()
