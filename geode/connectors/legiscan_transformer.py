"""Transform LegiScan bill JSON into Geode bill records."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from geode.extractors.citation_extractor import extract_crs_citations
from geode.schemas.models import Bill

SUBJECT_TAG_HINTS = {
    "air": "air_quality",
    "environment": "environment",
    "water": "water_quality",
    "health": "public_health",
    "labor": "employment_standards",
    "employment": "employment_standards",
    "housing": "housing",
    "energy": "energy",
    "transportation": "transportation",
    "education": "education",
    "tax": "taxation",
}


def transform_bill(raw_bill: dict[str, Any], ontology: dict[str, Any]) -> dict[str, Any]:
    """Map LegiScan bill JSON into the Geode bill schema."""

    bill = raw_bill.get("bill", raw_bill)
    if not isinstance(bill, dict):
        raise ValueError("raw_bill must contain a bill object")
    session_year = _session_year(bill)
    prefix, bill_number = _bill_prefix_and_number(str(bill.get("number", "")), session_year)
    bill_id = f"{prefix}{str(session_year)[-2:]}-{bill_number}"
    text = _bill_text(bill)
    citations = sorted({citation.canonical_form for citation in extract_crs_citations(text)})
    source_url = bill.get("url") or f"https://legiscan.com/CO/bill/{bill_id}/{session_year}"
    record = {
        "entity_type": "bill",
        "id": bill_id,
        "session": str(session_year),
        "chamber": "Senate" if prefix.startswith("S") else "House",
        "bill_number": bill_number,
        "title": str(bill.get("title") or bill.get("description") or bill_id),
        "sponsors": _sponsors(bill, prefix),
        "status": _status(bill),
        "status_date": _status_date(bill),
        "introduced_date": _introduced_date(bill),
        "statutes_amended": citations,
        "statutes_created": [],
        "statutes_repealed": [],
        "subject_tags": _subject_tags(bill, ontology),
        "source_url": source_url,
        "confidence": {"overall": 0.9},
    }
    Bill.model_validate(record)
    return record


def _session_year(bill: dict[str, Any]) -> int:
    """Extract the four-digit session year from a LegiScan bill."""

    session = bill.get("session")
    if isinstance(session, dict):
        for key in ("year_start", "year", "year_end"):
            if session.get(key):
                return int(session[key])
    if bill.get("session_year"):
        return int(bill["session_year"])
    for key in ("status_date", "introduced_date", "date"):
        value = bill.get(key)
        if value:
            return int(str(value)[:4])
    raise ValueError("bill session year is required")


def _bill_prefix_and_number(number: str, session_year: int) -> tuple[str, str]:
    """Normalize LegiScan bill numbers to Geode ID parts."""

    compact = re.sub(r"\s+", "", number.upper())
    match = re.match(r"^(SB|HB|SCR|HCR|SJR|HJR)(?:\d{2}-?)?(\d+)$", compact)
    if not match:
        raise ValueError(f"unsupported Colorado bill number: {number}")
    prefix = match.group(1)
    numeric = int(match.group(2))
    return prefix, f"{numeric:03d}"


def _bill_text(bill: dict[str, Any]) -> str:
    """Collect bill text fields for citation extraction."""

    parts = [
        str(bill.get("title", "")),
        str(bill.get("description", "")),
        str(bill.get("body", "")),
    ]
    for text_entry in bill.get("texts", []) or []:
        if isinstance(text_entry, dict):
            parts.append(str(text_entry.get("text", "")))
            parts.append(str(text_entry.get("doc", "")))
    return "\n".join(part for part in parts if part)


def _sponsors(bill: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    """Map LegiScan sponsor records to Geode sponsor objects."""

    sponsors = []
    default_chamber = "Senate" if prefix.startswith("S") else "House"
    for sponsor in bill.get("sponsors", []) or []:
        if not isinstance(sponsor, dict):
            continue
        chamber = str(sponsor.get("chamber", sponsor.get("type", default_chamber)))
        sponsors.append(
            {
                "name": str(sponsor.get("name", "Unknown sponsor")),
                "party": sponsor.get("party"),
                "chamber": "Senate" if chamber.lower().startswith("s") else "House",
                "role": str(sponsor.get("role", "primary")),
            }
        )
    if not sponsors:
        sponsors.append(
            {
                "name": "Unknown sponsor",
                "party": None,
                "chamber": default_chamber,
                "role": "unknown",
            }
        )
    return sponsors


def _status(bill: dict[str, Any]) -> str:
    """Map LegiScan status values to Geode status vocabulary."""

    status_text = str(bill.get("status_desc", bill.get("status", ""))).casefold()
    if "veto" in status_text:
        return "vetoed"
    if any(token in status_text for token in ("signed", "enacted", "chapter")):
        return "signed"
    return "in_committee"


def _status_date(bill: dict[str, Any]) -> str:
    """Return status date, falling back to introduced date."""

    return str(bill.get("status_date") or _introduced_date(bill))


def _introduced_date(bill: dict[str, Any]) -> str:
    """Return introduced date from explicit field or earliest history date."""

    if bill.get("introduced_date"):
        return str(bill["introduced_date"])
    history_dates = []
    for event in bill.get("history", []) or []:
        if isinstance(event, dict) and event.get("date"):
            try:
                history_dates.append(date.fromisoformat(str(event["date"])[:10]))
            except ValueError:
                continue
    if history_dates:
        return min(history_dates).isoformat()
    if bill.get("status_date"):
        return str(bill["status_date"])
    raise ValueError("introduced_date is required")


def _subject_tags(bill: dict[str, Any], ontology: dict[str, Any]) -> list[str]:
    """Map LegiScan subjects to Geode ontology tags."""

    allowed = _allowed_subject_tags(ontology)
    raw_subjects = bill.get("subjects", []) or []
    haystack = " ".join(str(subject) for subject in raw_subjects).casefold()
    haystack += f" {bill.get('title', '')} {bill.get('description', '')}".casefold()
    tags = []
    for needle, tag in SUBJECT_TAG_HINTS.items():
        if needle in haystack and tag in allowed:
            tags.append(tag)
    return sorted(set(tags))


def _allowed_subject_tags(ontology: dict[str, Any]) -> set[str]:
    """Flatten ontology subject tags from hierarchical or legacy shapes."""

    subject_tags = ontology.get("subject_tags", {})
    if isinstance(subject_tags, list):
        return {str(tag) for tag in subject_tags}
    allowed: set[str] = set()
    if isinstance(subject_tags, dict):
        for parent, payload in subject_tags.items():
            allowed.add(str(parent))
            if isinstance(payload, dict):
                children = payload.get("children", [])
                if isinstance(children, list):
                    allowed.update(str(child) for child in children)
    return allowed
