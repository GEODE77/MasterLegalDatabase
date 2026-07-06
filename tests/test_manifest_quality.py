"""Tests for safe connector manifest quality utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from geode.connectors.manifest_quality import (
    DEDUPLICATION_STRATEGY,
    build_ccr_manifest_quality_report,
    build_manifest_quality_report,
    render_manifest_quality_summary,
    write_deduplicated_manifest_report,
)


def test_manifest_quality_detects_duplicate_archive_paths_without_mutation(
    tmp_path: Path,
) -> None:
    """Duplicate archive paths are reported while the source manifest is untouched."""

    raw_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    manifest = raw_dir / "download_manifest.jsonl"
    duplicate_path = raw_dir / "5_CCR_1001-9.pdf"
    unique_path = raw_dir / "5_CCR_1007-2.docx"
    _write_manifest(
        manifest,
        [
            _manifest_row(duplicate_path, "5_CCR_1001-9", sha256="a"),
            _manifest_row(duplicate_path, "5_CCR_1001-9", sha256="b"),
            _manifest_row(unique_path, "5_CCR_1007-2", sha256="c"),
        ],
    )
    original_manifest = manifest.read_text(encoding="utf-8")

    report = build_ccr_manifest_quality_report(raw_dir)
    summary = render_manifest_quality_summary(report)

    assert report.total_rows == 3
    assert report.unique_archive_paths == 2
    assert report.duplicate_archive_paths == 1
    assert report.duplicate_rows == 2
    assert report.duplicate_excess_rows == 1
    assert report.duplicates[0].archive_path == duplicate_path.as_posix()
    assert report.duplicates[0].row_numbers == [1, 2]
    assert report.duplicates[0].kept_row_number == 2
    assert duplicate_path.as_posix() in summary
    assert "rows 1, 2; keep row 2" in summary
    assert manifest.read_text(encoding="utf-8") == original_manifest
    assert not (tmp_path / "_CONTROL_PLANE").exists()


def test_deduplicated_manifest_report_is_separate_and_latest_row_wins(
    tmp_path: Path,
) -> None:
    """A requested artifact contains deduplicated rows without rewriting the manifest."""

    raw_dir = tmp_path / "_RAW_ARCHIVE" / "ccr"
    manifest = raw_dir / "download_manifest.jsonl"
    duplicate_path = raw_dir / "5_CCR_1001-9.pdf"
    unique_path = raw_dir / "5_CCR_1007-2.docx"
    _write_manifest(
        manifest,
        [
            _manifest_row(duplicate_path, "5_CCR_1001-9", sha256="old"),
            _manifest_row(duplicate_path, "5_CCR_1001-9", sha256="new"),
            _manifest_row(unique_path, "5_CCR_1007-2", sha256="solo"),
        ],
    )
    original_manifest = manifest.read_text(encoding="utf-8")
    report = build_manifest_quality_report(manifest)
    output_path = tmp_path / "_CONTROL_PLANE" / "CCR_MANIFEST_DEDUP_REPORT.json"

    written = write_deduplicated_manifest_report(report, output_path, tmp_path)
    artifact = json.loads(written.read_text(encoding="utf-8"))

    assert written == output_path
    assert manifest.read_text(encoding="utf-8") == original_manifest
    assert artifact["source_manifest_path"] == manifest.as_posix()
    assert artifact["strategy"] == DEDUPLICATION_STRATEGY
    assert artifact["original_rows"] == 3
    assert artifact["deduplicated_row_count"] == 2
    assert artifact["duplicate_archive_paths"] == 1
    assert artifact["duplicate_excess_rows"] == 1
    kept_duplicate_rows = [
        row for row in artifact["deduplicated_rows"] if row["archive_path"] == duplicate_path.as_posix()
    ]
    assert len(kept_duplicate_rows) == 1
    assert kept_duplicate_rows[0]["sha256"] == "new"

    with pytest.raises(ValueError, match="must not overwrite"):
        write_deduplicated_manifest_report(report, manifest, tmp_path)


def test_manifest_quality_handles_clean_manifest(tmp_path: Path) -> None:
    """Clean manifests render an operator summary without duplicate details."""

    manifest = tmp_path / "_RAW_ARCHIVE" / "ccr" / "download_manifest.jsonl"
    _write_manifest(
        manifest,
        [
            _manifest_row(manifest.parent / "5_CCR_1001-9.pdf", "5_CCR_1001-9"),
            _manifest_row(manifest.parent / "5_CCR_1007-2.docx", "5_CCR_1007-2"),
        ],
    )

    report = build_manifest_quality_report(manifest)
    summary = render_manifest_quality_summary(report)

    assert report.has_duplicates is False
    assert report.duplicate_archive_paths == 0
    assert report.duplicate_excess_rows == 0
    assert report.errors == []
    assert "Duplicate archive paths: none" in summary


def _write_manifest(manifest: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows to a test manifest."""

    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _manifest_row(
    archive_path: Path,
    document_id: str,
    *,
    sha256: str = "digest",
) -> dict[str, object]:
    """Return a minimal manifest row for duplicate-path tests."""

    return {
        "archive_path": archive_path.as_posix(),
        "document_id": document_id,
        "downloaded_at": "2026-06-19T00:00:00Z",
        "sha256": sha256,
        "status": "downloaded",
    }
