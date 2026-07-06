"""Safe file I/O tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from geode.constants import CRS_LAYER
from geode.schemas import SourceDocument
from geode.utils import file_io
from geode.utils.file_io import (
    RawArchiveWriteError,
    atomic_write_jsonl,
    atomic_write_text,
    iter_jsonl,
)


def test_atomic_write_snapshots_existing_file(project_root: Path) -> None:
    """Overwrites snapshot the previous version first."""

    target = project_root / "01_Statutes_CRS" / "example.md"
    atomic_write_text(target, "first\n", project_root)
    atomic_write_text(target, "second\n", project_root)
    snapshots = list((project_root / "_SNAPSHOTS").glob("snapshot_*/01_Statutes_CRS/example.md"))
    assert snapshots
    assert target.read_text(encoding="utf-8") == "second\n"


def test_raw_archive_writes_are_refused(project_root: Path) -> None:
    """Generated writes cannot target `_RAW_ARCHIVE`."""

    with pytest.raises(RawArchiveWriteError):
        atomic_write_text(project_root / "_RAW_ARCHIVE" / "crs" / "bad.txt", "bad\n", project_root)


def test_jsonl_writer_has_no_blank_lines(project_root: Path) -> None:
    """JSONL writer writes one object per line without blanks."""

    target = project_root / "01_Statutes_CRS" / "_meta" / "sources.jsonl"
    record = SourceDocument(
        source_id="source",
        layer=CRS_LAYER,
        source_owner="Office of Legislative Legal Services",
        source_url=(
            "https://content.leg.colorado.gov/agencies/office-legislative-legal-services/"
            "2025-crs-titles-download"
        ),
        source_format="fixture",
        retrieved_at=datetime.now(timezone.utc),
        raw_path="_RAW_ARCHIVE/crs/source.txt",
        sha256="a" * 64,
        confidence=1.0,
    )
    atomic_write_jsonl(target, [record], project_root)
    assert "\n\n" not in target.read_text(encoding="utf-8")
    assert len(list(iter_jsonl(target))) == 1


def test_atomic_write_retries_transient_permission_error(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient Windows file lock during replace is retried."""

    target = project_root / "01_Statutes_CRS" / "retry.md"
    real_replace = file_io.os.replace
    attempts = 0

    def flaky_replace(source: Path, destination: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("locked")
        real_replace(source, destination)

    monkeypatch.setattr(file_io.os, "replace", flaky_replace)
    monkeypatch.setattr(file_io.time, "sleep", lambda _seconds: None)

    atomic_write_text(target, "ok\n", project_root)

    assert attempts == 2
    assert target.read_text(encoding="utf-8") == "ok\n"
