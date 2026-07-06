"""Tests for CCR post-download sorting helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from geode.connectors.ccr_postprocess import (
    ccr_series_from_filename,
    copy_ccr_files_to_sorted,
    count_ccr_raw_files,
    render_ccr_inventory_summary,
    summarize_ccr_inventory,
    summarize_ccr_series_folders,
    sort_ccr_raw_archive,
    sorted_ccr_path,
)


def test_sort_ccr_raw_archive_copies_pdf_by_series(tmp_path: Path) -> None:
    """PDF files are copied into the matching CCR series folder."""

    raw_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    raw_dir.mkdir(parents=True)
    raw_file = raw_dir / "2_CCR_402-1.pdf"
    raw_file.write_bytes(b"%PDF-1.7\nfixture")

    report = sort_ccr_raw_archive(tmp_path)

    sorted_file = tmp_path / "_SORTED" / "ccr" / "CCR_402" / raw_file.name
    assert report.discovered == 1
    assert report.copied == 1
    assert report.files[0].series == "402"
    assert report.files[0].source_format == "pdf"
    assert sorted_file.read_bytes() == raw_file.read_bytes()
    assert raw_file.exists()


def test_copy_ccr_files_to_sorted_copies_docx_and_preserves_raw(
    tmp_path: Path,
) -> None:
    """DOCX files are copied without moving or deleting the raw source file."""

    raw_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    sorted_dir = tmp_path / "_SORTED" / "ccr"
    raw_dir.mkdir(parents=True)
    raw_file = raw_dir / "1_CCR_301-75.docx"
    raw_file.write_bytes(b"PK\x03\x04docx fixture")

    report = copy_ccr_files_to_sorted(raw_dir, sorted_dir)

    sorted_file = sorted_dir / "CCR_301" / raw_file.name
    assert report.discovered == 1
    assert report.copied == 1
    assert report.skipped_unsupported == 0
    assert report.skipped_unrecognized == 0
    assert sorted_file.exists()
    assert sorted_file.read_bytes() == b"PK\x03\x04docx fixture"
    assert raw_file.exists()
    assert raw_file.read_bytes() == b"PK\x03\x04docx fixture"


def test_ccr_sorting_skips_unsupported_and_unrecognized_files(tmp_path: Path) -> None:
    """Only canonical CCR PDF/DOCX filenames are copied."""

    raw_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    sorted_dir = tmp_path / "_SORTED" / "ccr"
    raw_dir.mkdir(parents=True)
    (raw_dir / "download_manifest.jsonl").write_text("{}", encoding="utf-8")
    (raw_dir / "not_a_ccr_rule.pdf").write_bytes(b"pdf")

    report = copy_ccr_files_to_sorted(raw_dir, sorted_dir)

    assert report.discovered == 2
    assert report.copied == 0
    assert report.skipped_unsupported == 1
    assert report.skipped_unrecognized == 1
    assert not sorted_dir.exists()


def test_ccr_series_and_sorted_path_helpers() -> None:
    """Filename helpers derive stable series folders from CCR raw names."""

    assert ccr_series_from_filename("1_CCR_301-75.pdf") == "301"
    assert ccr_series_from_filename("2_CCR_402-1.docx") == "402"
    assert ccr_series_from_filename("bad.pdf") is None
    assert sorted_ccr_path(Path("_SORTED/ccr"), "402", "2_CCR_402-1.pdf") == Path(
        "_SORTED/ccr/CCR_402/2_CCR_402-1.pdf"
    )


def test_ccr_sorting_refuses_destination_inside_raw_archive(tmp_path: Path) -> None:
    """Sorted output cannot be placed inside the raw archive tree."""

    raw_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    raw_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="must not be inside"):
        copy_ccr_files_to_sorted(raw_dir, raw_dir / "_SORTED")


def test_ccr_inventory_summary_handles_empty_directories(tmp_path: Path) -> None:
    """Inventory reports zero counts when CCR output folders are absent."""

    summary = summarize_ccr_inventory(tmp_path)
    rendered = render_ccr_inventory_summary(summary)

    assert summary.raw_file_count == 0
    assert summary.sorted_series_count == 0
    assert summary.curated_series_count == 0
    assert "Raw: 0 files (0 PDF, 0 DOCX)" in rendered
    assert "Sorted: 0 series, 0 files" in rendered
    assert "Curated core: 0 series, 0 files" in rendered


def test_ccr_inventory_summary_counts_raw_sorted_and_curated_outputs(
    tmp_path: Path,
) -> None:
    """Inventory reports mixed PDF/DOCX counts for operational output folders."""

    raw_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    sorted_402 = tmp_path / "_SORTED" / "ccr" / "CCR_402"
    sorted_1007 = tmp_path / "_SORTED" / "ccr" / "CCR_1007"
    curated_402 = tmp_path / "_CURATED" / "coorstek_core" / "CCR_402"
    for directory in (raw_dir, sorted_402, sorted_1007, curated_402):
        directory.mkdir(parents=True)

    (raw_dir / "2_CCR_402-1.pdf").write_bytes(b"pdf")
    (raw_dir / "2_CCR_402-2.docx").write_bytes(b"docx")
    (raw_dir / "download_manifest.jsonl").write_text("{}", encoding="utf-8")
    (sorted_402 / "2_CCR_402-1.pdf").write_bytes(b"pdf")
    (sorted_402 / "2_CCR_402-2.docx").write_bytes(b"docx")
    (sorted_1007 / "6_CCR_1007-2.docx").write_bytes(b"docx")
    (curated_402 / "2_CCR_402-1.pdf").write_bytes(b"pdf")

    summary = summarize_ccr_inventory(tmp_path)
    rendered = render_ccr_inventory_summary(summary)

    assert summary.raw_file_count == 2
    assert summary.raw_pdf_count == 1
    assert summary.raw_docx_count == 1
    assert summary.sorted_series_count == 2
    assert summary.sorted_file_count == 3
    assert [(item.series, item.file_count) for item in summary.sorted_series] == [
        ("1007", 1),
        ("402", 2),
    ]
    assert summary.curated_series_count == 1
    assert summary.curated_file_count == 1
    assert summary.curated_series[0].series == "402"
    assert "Raw: 2 files (1 PDF, 1 DOCX)" in rendered
    assert "Sorted: 2 series, 3 files" in rendered
    assert "  - CCR_402: 2 files (1 PDF, 1 DOCX)" in rendered
    assert "Curated core: 1 series, 1 files" in rendered


def test_ccr_inventory_helpers_count_supported_files_only(tmp_path: Path) -> None:
    """Low-level inventory helpers count supported CCR document formats."""

    raw_dir = tmp_path / "raw"
    series_dir = tmp_path / "series" / "CCR_301"
    raw_dir.mkdir()
    series_dir.mkdir(parents=True)
    (raw_dir / "1_CCR_301-1.pdf").write_bytes(b"pdf")
    (raw_dir / "1_CCR_301-2.docx").write_bytes(b"docx")
    (raw_dir / "notes.txt").write_text("skip", encoding="utf-8")
    (series_dir / "1_CCR_301-1.pdf").write_bytes(b"pdf")

    assert count_ccr_raw_files(raw_dir) == {"total": 2, "pdf": 1, "docx": 1}
    series = summarize_ccr_series_folders(tmp_path / "series")
    assert len(series) == 1
    assert series[0].series == "301"
    assert series[0].file_count == 1
