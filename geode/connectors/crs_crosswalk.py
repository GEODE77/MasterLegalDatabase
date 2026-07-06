"""CRS crosswalk builders for statute-to-regulation relationships."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from geode.schemas import CrosswalkEntry
from geode.utils.file_io import atomic_write_jsonl, iter_jsonl

REGULATION_TO_STATUTE = "regulation_to_statute.jsonl"
STATUTE_TO_REGULATION = "statute_to_regulation.jsonl"
CRS_ID_RE = re.compile(
    r"^CRS-(?P<title>\d{1,2}(?:\.\d+)?)-(?P<article>\d+(?:\.\d+)?)-"
    r"(?P<section>\d+(?:\.\d+)?)$"
)


class CRSCrosswalkSummary(BaseModel):
    """Summary for CRS inverse crosswalk generation."""

    model_config = ConfigDict(extra="forbid")

    regulation_to_statute_path: str
    statute_to_regulation_path: str
    input_rows: int = Field(ge=0)
    output_rows: int = Field(ge=0)
    skipped_rows: int = Field(ge=0)


def rebuild_statute_to_regulation_crosswalk(root: Path) -> CRSCrosswalkSummary:
    """Build ``statute_to_regulation.jsonl`` from regulation-to-statute rows."""

    project_root = root.resolve()
    crosswalk_dir = project_root / "_CROSSWALKS"
    source_path = crosswalk_dir / REGULATION_TO_STATUTE
    target_path = crosswalk_dir / STATUTE_TO_REGULATION
    input_rows = 0
    skipped_rows = 0
    rows_by_key: dict[tuple[str, str], CrosswalkEntry] = {}
    if source_path.exists():
        for payload in iter_jsonl(source_path):
            input_rows += 1
            try:
                source = CrosswalkEntry.model_validate(payload)
            except Exception:
                skipped_rows += 1
                continue
            if (
                not source.target_id
                or not _is_plausible_crs_id(source.target_id)
                or not _has_statutory_evidence_for_id(source.target_id, source.source_evidence)
            ):
                skipped_rows += 1
                continue
            inverse = CrosswalkEntry(
                source_id=source.target_id,
                source_type="statute_section",
                target_id=source.source_id,
                target_type="regulation_rule",
                relationship="implements",
                confidence=source.confidence,
                source_evidence=source.source_evidence,
                data_retrieved=source.data_retrieved or date.today(),
            )
            rows_by_key[(inverse.source_id, inverse.target_id or "")] = inverse
    rows = [rows_by_key[key] for key in sorted(rows_by_key)]
    atomic_write_jsonl(target_path, rows, project_root)
    return CRSCrosswalkSummary(
        regulation_to_statute_path=source_path.as_posix(),
        statute_to_regulation_path=target_path.as_posix(),
        input_rows=input_rows,
        output_rows=len(rows),
        skipped_rows=skipped_rows,
    )


def _is_plausible_crs_id(value: str) -> bool:
    """Return whether a string looks like a real Colorado Revised Statutes ID."""

    match = CRS_ID_RE.match(value)
    if not match:
        return False
    title = float(match.group("title"))
    article = float(match.group("article"))
    section = float(match.group("section"))
    return 1 <= title <= 44 and article > 0 and section > 0


def _has_statutory_evidence_for_id(crs_id: str, value: str | None) -> bool:
    """Return whether evidence ties the specific CRS ID to statutory text."""

    evidence = (value or "").casefold()
    match = CRS_ID_RE.match(crs_id)
    if not match:
        return False
    citation = r"\s*-\s*".join(
        re.escape(match.group(part).lstrip("0") or "0")
        for part in ("title", "article", "section")
    )
    c_r_s = r"(?:c\.?\s*r\.?\s*s\.?|colorado revised statutes)"
    after_citation = re.search(citation + rf".{{0,80}}{c_r_s}", evidence)
    before_citation = re.search(rf"{c_r_s}.{{0,80}}" + citation, evidence)
    section_citation = re.search(r"(?:§|section)\s*" + citation, evidence)
    return bool(after_citation or before_citation or section_citation)
