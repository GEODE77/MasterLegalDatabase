"""Tests for deterministic generated sample bill data."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_sample_data import SAMPLE_BILLS, generate_all_samples, seed_pipeline


def test_generate_all_samples_creates_five_files(tmp_path: Path) -> None:
    """The sample generator writes one extracted JSON file per hardcoded bill."""

    summary = generate_all_samples(str(tmp_path))
    files = sorted(tmp_path.glob("*_extracted.json"))
    expected_numbers = [str(bill["bill_number"]) for bill in SAMPLE_BILLS]

    assert summary["generated"] == 5
    assert summary["bills"] == expected_numbers
    assert len(files) == 5
    assert [path.stem.removesuffix("_extracted") for path in files] == sorted(
        expected_numbers
    )


def test_seed_pipeline_copies_files_idempotently(tmp_path: Path) -> None:
    """Seeding copies generated samples once and skips existing files later."""

    sample_dir = tmp_path / "sample"
    target_dir = tmp_path / "extracted_text"
    generate_all_samples(str(sample_dir))

    first = seed_pipeline(str(sample_dir), str(target_dir))
    second = seed_pipeline(str(sample_dir), str(target_dir))

    assert first == {"copied": 5, "skipped": 0}
    assert second == {"copied": 0, "skipped": 5}
    assert len(list(target_dir.glob("*_extracted.json"))) == 5


def test_sample_json_structure_matches_extractor_schema(tmp_path: Path) -> None:
    """Generated sample JSON matches the extractor payload consumed by parser."""

    generate_all_samples(str(tmp_path))

    for path in sorted(tmp_path.glob("*_extracted.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))

        assert set(payload) == {
            "source_file",
            "extractor",
            "page_count",
            "pages",
            "full_text",
            "total_chars",
        }
        assert payload["source_file"].endswith(".pdf")
        assert payload["extractor"] == "sample_generator"
        assert payload["page_count"] == len(payload["pages"])
        assert payload["total_chars"] == len(payload["full_text"])
        assert "BE IT ENACTED BY THE GENERAL ASSEMBLY OF THE STATE OF COLORADO:" in payload[
            "full_text"
        ]
        assert any("\u00a7 " in page["text"] for page in payload["pages"])

        for index, page in enumerate(payload["pages"], start=1):
            assert set(page) == {"page_number", "text", "char_count"}
            assert page["page_number"] == index
            assert page["char_count"] == len(page["text"])
            assert page["text"].strip()
