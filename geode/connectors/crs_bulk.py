"""Bulk CRS ingestion orchestration for archived title source files."""

from __future__ import annotations

import re
import shutil
import zipfile
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.crs_crosswalk import (
    CRSCrosswalkSummary,
    rebuild_statute_to_regulation_crosswalk,
)
from geode.connectors.crs_parser import CRSParseError, detect_crs_source_metadata, parse_crs_source
from geode.constants import CRS_LAYER, RAW_ARCHIVE_DIR
from geode.pipeline.writer import ensure_project_structure, write_crs_title
from geode.schemas.validators import canonical_crs_id
from geode.utils.file_io import atomic_write_json, atomic_write_jsonl

CRS_SOURCE_PATTERNS = ("*.sgml", "*.xml", "*.txt", "*.md")
CRS_BULK_SUMMARY_NAME = "crs_bulk_summary.json"
CRS_SUBJECT_INDEX_NAME = "crs_subject_index.jsonl"
CRS_INDEX_LINE_RE = re.compile(r"^\s*<L(?P<level>[1-4])>(?P<text>.*)$")
CRS_INDEX_CITATION_RE = re.compile(
    r"\b(?P<citation>\d{1,2}(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?)\b"
)


class CRSBulkItem(BaseModel):
    """One CRS source file processed or skipped during a bulk run."""

    model_config = ConfigDict(extra="forbid")

    source_path: str
    title_number: str | None = None
    publication_year: int | None = None
    status: str
    sections_written: int = Field(default=0, ge=0)
    error: str | None = None


class CRSBulkSummary(BaseModel):
    """Summary for bulk CRS ingestion."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    input_dir: str
    dry_run: bool
    discovered_files: int = Field(ge=0)
    parsed_titles: int = Field(ge=0)
    sections_written: int = Field(ge=0)
    failed_files: int = Field(ge=0)
    skipped_files: int = Field(ge=0)
    summary_path: str
    items: list[CRSBulkItem] = Field(default_factory=list)
    crosswalk_summary: CRSCrosswalkSummary | None = None


class CRSArchiveStageSummary(BaseModel):
    """Summary for staging an official CRS zip under the raw archive."""

    model_config = ConfigDict(extra="forbid")

    zip_path: str
    staged_zip_path: str
    extract_dir: str
    extracted_files: int = Field(ge=0)
    extracted_bytes: int = Field(ge=0)


class CRSSubjectIndexRecord(BaseModel):
    """One official CRS subject index row for AI lookup."""

    model_config = ConfigDict(extra="forbid")

    id: str
    heading_path: list[str]
    display_text: str
    cited_sections: list[str] = Field(default_factory=list)
    see_also: str | None = None
    source_path: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class CRSSubjectIndexSummary(BaseModel):
    """Summary for parsing the official CRS subject index sidecar."""

    model_config = ConfigDict(extra="forbid")

    source_path: str
    output_path: str
    records_written: int = Field(ge=0)


def run_crs_bulk_pipeline(
    root: Path,
    *,
    input_dir: Path | None = None,
    publication_year: int | None = None,
    dry_run: bool = False,
    rebuild_crosswalks: bool = True,
) -> CRSBulkSummary:
    """Parse all archived CRS title files in a directory and write normalized outputs."""

    project_root = root.resolve()
    ensure_project_structure(project_root)
    raw_root = (project_root / RAW_ARCHIVE_DIR / "crs").resolve()
    source_dir = (input_dir or raw_root).resolve()
    if not source_dir.is_relative_to(raw_root):
        raise ValueError("CRS bulk input directory must live under _RAW_ARCHIVE/crs")

    items: list[CRSBulkItem] = []
    parsed_titles = 0
    sections_written = 0
    files = _source_files(source_dir)
    seen_titles: set[tuple[str, int]] = set()
    for source_file in files:
        relative_source = _relative_or_absolute(source_file, project_root)
        try:
            metadata = detect_crs_source_metadata(source_file)
            year = publication_year or metadata.publication_year
            if not metadata.title_number:
                raise CRSParseError("could not determine CRS title number")
            if year is None:
                raise CRSParseError("could not determine CRS publication year")
            title_key = (metadata.title_number, year)
            if title_key in seen_titles:
                items.append(
                    CRSBulkItem(
                        source_path=relative_source,
                        title_number=metadata.title_number,
                        publication_year=year,
                        status="skipped_duplicate_title",
                    )
                )
                continue
            seen_titles.add(title_key)
            document = parse_crs_source(source_file, metadata.title_number, year)
            if not dry_run:
                write_crs_title(project_root, document)
            parsed_titles += 1
            sections_written += len(document.sections)
            items.append(
                CRSBulkItem(
                    source_path=relative_source,
                    title_number=document.title_number,
                    publication_year=document.publication_year,
                    status="parsed" if dry_run else "written",
                    sections_written=len(document.sections),
                )
            )
        except Exception as exc:
            items.append(
                CRSBulkItem(
                    source_path=relative_source,
                    status="failed",
                    error=str(exc),
                )
            )

    crosswalk_summary = None
    if rebuild_crosswalks and not dry_run:
        crosswalk_summary = rebuild_statute_to_regulation_crosswalk(project_root)
    summary_path = project_root / CRS_LAYER / "_meta" / CRS_BULK_SUMMARY_NAME
    summary = CRSBulkSummary(
        generated_at=datetime.now(timezone.utc),
        input_dir=source_dir.as_posix(),
        dry_run=dry_run,
        discovered_files=len(files),
        parsed_titles=parsed_titles,
        sections_written=sections_written,
        failed_files=sum(1 for item in items if item.status == "failed"),
        skipped_files=sum(1 for item in items if item.status.startswith("skipped")),
        summary_path=summary_path.as_posix(),
        items=items,
        crosswalk_summary=crosswalk_summary,
    )
    if not dry_run:
        atomic_write_json(summary_path, summary, project_root)
    return summary


def stage_crs_archive(root: Path, zip_path: Path, archive_date: str = "2025-10-01") -> CRSArchiveStageSummary:
    """Copy and safely extract an official CRS zip into the raw archive."""

    project_root = root.resolve()
    ensure_project_structure(project_root)
    source_zip = zip_path.resolve()
    if not source_zip.exists():
        raise FileNotFoundError(source_zip)
    raw_root = (project_root / RAW_ARCHIVE_DIR / "crs").resolve()
    destination_dir = (raw_root / archive_date).resolve()
    staged_zip = destination_dir / "CRSDATA20251001.zip"
    extract_dir = destination_dir / "extracted"
    if destination_dir.exists():
        raise FileExistsError(f"CRS archive destination already exists: {destination_dir}")
    destination_dir.mkdir(parents=True)
    shutil.copy2(source_zip, staged_zip)

    extracted_files = 0
    extracted_bytes = 0
    with zipfile.ZipFile(staged_zip) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            target = _safe_zip_target(extract_dir, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("xb") as destination:
                shutil.copyfileobj(source, destination)
            extracted_files += 1
            extracted_bytes += member.file_size
    return CRSArchiveStageSummary(
        zip_path=source_zip.as_posix(),
        staged_zip_path=staged_zip.as_posix(),
        extract_dir=extract_dir.as_posix(),
        extracted_files=extracted_files,
        extracted_bytes=extracted_bytes,
    )


def parse_crs_subject_index(root: Path, index_path: Path) -> CRSSubjectIndexSummary:
    """Parse the official CRS subject index into a metadata sidecar."""

    project_root = root.resolve()
    source = index_path.resolve()
    raw_root = (project_root / RAW_ARCHIVE_DIR / "crs").resolve()
    if not source.is_relative_to(raw_root):
        raise ValueError("CRS subject index input must live under _RAW_ARCHIVE/crs")
    output_path = project_root / CRS_LAYER / "_meta" / CRS_SUBJECT_INDEX_NAME
    records = _subject_index_records(source, project_root)
    atomic_write_jsonl(output_path, records, project_root)
    return CRSSubjectIndexSummary(
        source_path=_relative_or_absolute(source, project_root),
        output_path=_relative_or_absolute(output_path, project_root),
        records_written=len(records),
    )


def _safe_zip_target(extract_dir: Path, member_name: str) -> Path:
    """Return a safe extraction target for one zip member."""

    normalized = member_name.replace("\\", "/")
    member_path = PurePosixPath(normalized)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError(f"unsafe CRS zip member path: {member_name}")
    target = (extract_dir / Path(*member_path.parts)).resolve()
    if not target.is_relative_to(extract_dir.resolve()):
        raise ValueError(f"unsafe CRS zip member path: {member_name}")
    return target


def _subject_index_records(source: Path, project_root: Path) -> list[CRSSubjectIndexRecord]:
    """Return structured rows from the official CRS subject index."""

    records: list[CRSSubjectIndexRecord] = []
    heading_stack: dict[int, str] = {}
    for line_number, line in enumerate(_read_crs_index_text(source).splitlines(), start=1):
        match = CRS_INDEX_LINE_RE.match(line)
        if not match:
            continue
        level = int(match.group("level"))
        display_text = _clean_index_text(match.group("text"))
        if not display_text:
            continue
        heading_stack = {
            existing_level: heading
            for existing_level, heading in heading_stack.items()
            if existing_level < level
        }
        heading_stack[level] = _index_heading(display_text)
        heading_path = [heading_stack[key] for key in sorted(heading_stack)]
        cited_sections = _index_citations(display_text)
        see_also = _index_see_also(display_text)
        records.append(
            CRSSubjectIndexRecord(
                id=f"CRS-SUBJECT-{line_number:06d}",
                heading_path=heading_path,
                display_text=display_text,
                cited_sections=cited_sections,
                see_also=see_also,
                source_path=_relative_or_absolute(source, project_root),
                confidence=1.0,
            )
        )
    return records


def _clean_index_text(value: str) -> str:
    """Clean one official CRS index line."""

    text = re.sub(r"</?[A-Z0-9_]+\b[^>]*>", "", value)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _read_crs_index_text(source: Path) -> str:
    """Read the official CRS index with a conservative encoding fallback."""

    try:
        return source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return source.read_text(encoding="cp1252")


def _index_heading(display_text: str) -> str:
    """Return the heading text before citations."""

    heading = re.split(r",\s*(?:§|&sect;)", display_text, maxsplit=1)[0]
    heading = re.sub(r"\s*\.$", "", heading)
    return heading.strip()


def _index_citations(display_text: str) -> list[str]:
    """Return canonical CRS IDs cited in one index row."""

    citations: set[str] = set()
    for match in CRS_INDEX_CITATION_RE.finditer(display_text):
        raw = match.group("citation")
        parts = raw.split("-")
        if len(parts) != 3:
            continue
        citations.add(canonical_crs_id(parts[0], parts[1], parts[2]))
    return sorted(citations)


def _index_see_also(display_text: str) -> str | None:
    """Return a See/See also reference from one index row when present."""

    match = re.search(r"\bSee(?: also)?\s+(.+)$", display_text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip().rstrip(".") or None


def _source_files(source_dir: Path) -> list[Path]:
    """Return deterministic CRS source files from a directory."""

    files: list[Path] = []
    for pattern in CRS_SOURCE_PATTERNS:
        files.extend(path for path in source_dir.rglob(pattern) if path.is_file())
    return sorted(set(files))


def _relative_or_absolute(path: Path, root: Path) -> str:
    """Return a project-relative path when possible."""

    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
