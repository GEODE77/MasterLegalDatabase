"""Utility tests for file I/O and hashing helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from geode.utils.file_io import append_jsonl, read_json, read_jsonl, write_json, write_jsonl
from geode.utils.hashing import compute_preservation_score, compute_sha256


def test_json_helpers_round_trip(tmp_path: Path) -> None:
    """JSON helpers write and read UTF-8 objects atomically."""

    target = tmp_path / "example.json"
    write_json(target, {"name": "Geode"}, tmp_path)
    assert read_json(target) == {"name": "Geode"}


def test_jsonl_helpers_stream_records(tmp_path: Path) -> None:
    """JSONL helpers stream one object per line."""

    target = tmp_path / "records.jsonl"
    write_jsonl(target, [{"id": "one"}], tmp_path)
    append_jsonl(target, {"id": "two"}, tmp_path)
    assert list(read_jsonl(target)) == [{"id": "one"}, {"id": "two"}]


def test_compute_sha256(tmp_path: Path) -> None:
    """SHA-256 helper returns a stable digest."""

    target = tmp_path / "source.txt"
    target.write_text("geode", encoding="utf-8")
    expected = "3e20eb0bd0cae2e403b462f9be7f335e88368f6d39043b229a789bed59cbc3cf"
    assert compute_sha256(target) == expected


def test_compute_preservation_score() -> None:
    """Preservation score measures shared source tokens."""

    report = compute_preservation_score("alpha beta beta", "alpha beta")
    assert report["source_tokens"] == 3
    assert report["shared_tokens"] == 2
    assert report["preservation_score"] == pytest.approx(2 / 3)
