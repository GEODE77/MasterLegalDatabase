"""Post-download helpers for CCR raw archive outputs."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SUPPORTED_CCR_SORT_EXTENSIONS = {".docx", ".pdf"}
CCR_FILENAME_RE = re.compile(
    r"^(?P<department>\d{1,2})_CCR_(?P<series>\d+)-(?P<rule>\d+(?:-\d+)?)$",
    re.IGNORECASE,
)


class CCRSortedFile(BaseModel):
    """One copied CCR source artifact in the sorted output tree."""

    model_config = ConfigDict(extra="forbid")

    source_path: str
    sorted_path: str
    series: str
    source_format: str


class CCRSortReport(BaseModel):
    """Summary from copying CCR raw archive files into series folders."""

    model_config = ConfigDict(extra="forbid")

    raw_dir: str
    sorted_dir: str
    discovered: int = Field(ge=0)
    copied: int = Field(ge=0)
    skipped_unsupported: int = Field(ge=0)
    skipped_unrecognized: int = Field(ge=0)
    files: list[CCRSortedFile] = Field(default_factory=list)


class CCRSeriesFolderSummary(BaseModel):
    """Inventory counts for one CCR series folder."""

    model_config = ConfigDict(extra="forbid")

    series: str
    folder_path: str
    file_count: int = Field(ge=0)
    pdf_count: int = Field(ge=0)
    docx_count: int = Field(ge=0)


class CCRInventorySummary(BaseModel):
    """Concise inventory summary for CCR operational output directories."""

    model_config = ConfigDict(extra="forbid")

    raw_dir: str
    sorted_dir: str
    curated_dir: str
    raw_file_count: int = Field(ge=0)
    raw_pdf_count: int = Field(ge=0)
    raw_docx_count: int = Field(ge=0)
    sorted_series_count: int = Field(ge=0)
    sorted_file_count: int = Field(ge=0)
    sorted_series: list[CCRSeriesFolderSummary] = Field(default_factory=list)
    curated_series_count: int = Field(ge=0)
    curated_file_count: int = Field(ge=0)
    curated_series: list[CCRSeriesFolderSummary] = Field(default_factory=list)


def sort_ccr_raw_archive(root: Path) -> CCRSortReport:
    """Copy CCR raw archive files into the standard sorted CCR tree.

    Args:
        root: Project root containing ``_RAW_ARCHIVE``.

    Returns:
        Sort report for copied and skipped CCR raw files.
    """

    return copy_ccr_files_to_sorted(root / "_RAW_ARCHIVE" / "ccr", root / "_SORTED" / "ccr")


def summarize_ccr_inventory(root: Path) -> CCRInventorySummary:
    """Summarize CCR raw, sorted, and curated output directories.

    Args:
        root: Project root containing CCR operational output directories.

    Returns:
        Structured inventory summary for operator review.
    """

    raw_dir = root / "_RAW_ARCHIVE" / "ccr"
    sorted_dir = root / "_SORTED" / "ccr"
    curated_dir = root / "_CURATED" / "coorstek_core"
    raw_counts = count_ccr_raw_files(raw_dir)
    sorted_series = summarize_ccr_series_folders(sorted_dir)
    curated_series = summarize_ccr_series_folders(curated_dir)

    return CCRInventorySummary(
        raw_dir=raw_dir.as_posix(),
        sorted_dir=sorted_dir.as_posix(),
        curated_dir=curated_dir.as_posix(),
        raw_file_count=raw_counts["total"],
        raw_pdf_count=raw_counts["pdf"],
        raw_docx_count=raw_counts["docx"],
        sorted_series_count=len(sorted_series),
        sorted_file_count=sum(series.file_count for series in sorted_series),
        sorted_series=sorted_series,
        curated_series_count=len(curated_series),
        curated_file_count=sum(series.file_count for series in curated_series),
        curated_series=curated_series,
    )


def render_ccr_inventory_summary(summary: CCRInventorySummary) -> str:
    """Render a compact terminal-friendly CCR inventory summary."""

    lines = [
        "CCR inventory summary",
        (
            "Raw: {total} files ({pdf} PDF, {docx} DOCX)"
        ).format(
            total=summary.raw_file_count,
            pdf=summary.raw_pdf_count,
            docx=summary.raw_docx_count,
        ),
        (
            "Sorted: {series} series, {files} files"
        ).format(
            series=summary.sorted_series_count,
            files=summary.sorted_file_count,
        ),
    ]
    lines.extend(_series_summary_lines(summary.sorted_series))
    lines.append(
        (
            "Curated core: {series} series, {files} files"
        ).format(
            series=summary.curated_series_count,
            files=summary.curated_file_count,
        )
    )
    lines.extend(_series_summary_lines(summary.curated_series))
    return "\n".join(lines)


def count_ccr_raw_files(raw_dir: Path) -> dict[str, int]:
    """Count supported CCR raw archive files by format."""

    counts = {"total": 0, "pdf": 0, "docx": 0}
    if not raw_dir.exists():
        return counts
    for path in sorted(raw_dir.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.casefold()
        if suffix not in SUPPORTED_CCR_SORT_EXTENSIONS:
            continue
        counts["total"] += 1
        counts[suffix.lstrip(".")] += 1
    return counts


def summarize_ccr_series_folders(parent_dir: Path) -> list[CCRSeriesFolderSummary]:
    """Return counts for ``CCR_<series>`` folders under one output directory."""

    if not parent_dir.exists():
        return []

    summaries: list[CCRSeriesFolderSummary] = []
    for folder in sorted(parent_dir.iterdir()):
        if not folder.is_dir() or not folder.name.startswith("CCR_"):
            continue
        counts = count_ccr_raw_files(folder)
        series = folder.name.removeprefix("CCR_")
        summaries.append(
            CCRSeriesFolderSummary(
                series=series,
                folder_path=folder.as_posix(),
                file_count=counts["total"],
                pdf_count=counts["pdf"],
                docx_count=counts["docx"],
            )
        )
    return summaries


def copy_ccr_files_to_sorted(raw_dir: Path, sorted_dir: Path) -> CCRSortReport:
    """Copy supported CCR raw files into series folders under ``sorted_dir``.

    Args:
        raw_dir: CCR raw archive directory containing files such as
            ``2_CCR_402-1.pdf``.
        sorted_dir: Destination directory for series folders such as
            ``CCR_402``.

    Returns:
        Report summarizing copied and skipped files.

    Raises:
        ValueError: If the destination is inside the raw source directory.
    """

    _ensure_copy_destination_is_not_raw(raw_dir, sorted_dir)
    files: list[CCRSortedFile] = []
    discovered = 0
    skipped_unsupported = 0
    skipped_unrecognized = 0

    source_paths = sorted(raw_dir.iterdir()) if raw_dir.exists() else []
    for source_path in source_paths:
        if not source_path.is_file():
            continue
        discovered += 1
        suffix = source_path.suffix.casefold()
        if suffix not in SUPPORTED_CCR_SORT_EXTENSIONS:
            skipped_unsupported += 1
            continue
        series = ccr_series_from_filename(source_path.name)
        if series is None:
            skipped_unrecognized += 1
            continue

        target = sorted_ccr_path(sorted_dir, series, source_path.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        files.append(
            CCRSortedFile(
                source_path=source_path.as_posix(),
                sorted_path=target.as_posix(),
                series=series,
                source_format=suffix.lstrip("."),
            )
        )

    return CCRSortReport(
        raw_dir=raw_dir.as_posix(),
        sorted_dir=sorted_dir.as_posix(),
        discovered=discovered,
        copied=len(files),
        skipped_unsupported=skipped_unsupported,
        skipped_unrecognized=skipped_unrecognized,
        files=files,
    )


def sorted_ccr_path(sorted_dir: Path, series: str, filename: str) -> Path:
    """Return the sorted destination path for one CCR source filename."""

    return sorted_dir / f"CCR_{series}" / filename


def ccr_series_from_filename(filename: str) -> str | None:
    """Return the CCR series from a canonical raw archive filename.

    Examples:
        ``1_CCR_301-75.pdf`` returns ``301``.
        ``2_CCR_402-1.docx`` returns ``402``.
    """

    path = Path(filename)
    if path.suffix.casefold() not in SUPPORTED_CCR_SORT_EXTENSIONS:
        return None
    match = CCR_FILENAME_RE.match(path.stem)
    if match is None:
        return None
    return match.group("series")


def _ensure_copy_destination_is_not_raw(raw_dir: Path, sorted_dir: Path) -> None:
    """Ensure sorted output does not write inside the raw archive directory."""

    resolved_raw = raw_dir.resolve()
    resolved_sorted = sorted_dir.resolve()
    if resolved_sorted == resolved_raw or resolved_sorted.is_relative_to(resolved_raw):
        raise ValueError("sorted CCR output must not be inside the raw archive directory")


def _series_summary_lines(series_summaries: list[CCRSeriesFolderSummary]) -> list[str]:
    """Render compact per-series count lines."""

    return [
        (
            "  - CCR_{series}: {total} files ({pdf} PDF, {docx} DOCX)"
        ).format(
            series=summary.series,
            total=summary.file_count,
            pdf=summary.pdf_count,
            docx=summary.docx_count,
        )
        for summary in series_summaries
    ]
