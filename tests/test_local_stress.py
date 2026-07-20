"""Stress and adversarial tests for the improved local-authority controls."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from geode.pipeline.local_freshness import build_local_source_freshness
from geode.pipeline.local_metadata_control import archive_unreferenced_metadata
from geode.pipeline.local_ocr import run_local_ocr
from geode.pipeline.local_rule_ingest import _extract_source
from geode.pipeline.local_review import build_local_review_queues
from geode.utils.file_io import atomic_write_jsonl


def test_mislabeled_html_and_media_are_classified_by_signature(tmp_path: Path) -> None:
    """A filename cannot make a non-PDF source look like a PDF."""

    html_path = tmp_path / "rule.pdf"
    html_path.write_text("<!doctype html><html><body>visible rule text</body></html>", encoding="utf-8")
    text, pages, source_format = _extract_source(html_path)
    assert "visible rule text" in text
    assert pages == 1
    assert source_format == "html"

    media_path = tmp_path / "video.html"
    media_path.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00")
    try:
        _extract_source(media_path)
    except ValueError as exc:
        assert "media" in str(exc)
    else:
        raise AssertionError("media source was accepted as legal text")


def test_extract_source_respects_legacy_html_charset(tmp_path: Path) -> None:
    """Legacy county pages decode without replacement characters or mojibake."""

    html_path = tmp_path / "legacy.html"
    html_path.write_bytes(
        b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">'
        + "Règlement § 1".encode("cp1252")
    )

    text, _, _ = _extract_source(html_path)

    assert "Règlement § 1" in text
    assert "\ufffd" not in text


def test_extract_source_repairs_common_html_mojibake(tmp_path: Path) -> None:
    """Derived HTML text repairs a legacy-decoding error without touching raw bytes."""

    path = tmp_path / "broken.html"
    path.write_bytes("<html><body>Garfield Ã³rdinance</body></html>".encode("utf-8"))

    text, _, _ = _extract_source(path)

    assert "Garfield órdinance" in text


def test_local_freshness_uses_latest_download_and_reports_missing_raw(tmp_path: Path) -> None:
    """Freshness is source-specific and exposes missing preserved files."""

    manifest = tmp_path / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"
    atomic_write_jsonl(
        manifest,
        [
            {
                "source_id": "county_test",
                "authority_id": "CO-COUNTY-TEST",
                "authority_level": "county",
                "status": "downloaded",
                "retrieved_at": "2026-01-01T00:00:00Z",
                "raw_path": str(tmp_path / "missing.pdf"),
                "sha256": "a" * 64,
            },
            {
                "source_id": "county_test",
                "authority_id": "CO-COUNTY-TEST",
                "authority_level": "county",
                "status": "downloaded",
                "retrieved_at": "2026-07-01T00:00:00Z",
                "raw_path": str(tmp_path / "missing.pdf"),
                "sha256": "a" * 64,
            },
        ],
        tmp_path,
    )
    report = build_local_source_freshness(tmp_path, today=date(2026, 7, 15))
    assert report["sources_checked"] == 1
    assert report["records"][0]["status"] == "fresh"
    assert report["records"][0]["raw_exists"] is False


def test_ocr_control_reports_dependency_without_touching_raw(tmp_path: Path, monkeypatch) -> None:
    """OCR readiness never edits a source when the OCR engine is unavailable."""

    queue = tmp_path / "_CONTROL_PLANE" / "LOCAL_OCR_QUEUE.jsonl"
    atomic_write_jsonl(
        queue,
        [{
            "source_id": "county_scan",
            "authority_id": "CO-COUNTY-TEST",
            "source_category": "county_codes",
            "source_path": str(tmp_path / "scan.pdf"),
            "source_hash": "b" * 64,
        }],
        tmp_path,
    )
    monkeypatch.setattr("geode.pipeline.local_ocr.shutil.which", lambda _: None)
    report = run_local_ocr(tmp_path)
    assert report["pending_items"] == 1
    assert report["completed_items"] == 0


def test_review_summary_keeps_unreviewed_units_out_of_answer_safe_count(tmp_path: Path) -> None:
    """The review control plane does not promote preservation units automatically."""

    for layer in ("08_County_Authorities", "09_District_Authorities"):
        (tmp_path / layer).mkdir(parents=True, exist_ok=True)
        (tmp_path / layer / "_index.jsonl").write_text(
            json.dumps({
                "id": "UNIT-1",
                "entity_type": "rule_unit",
                "semantic_status": "source_preservation_only",
                "source_path": "raw.pdf",
                "authority_id": "CO-COUNTY-TEST",
                "authority_level": "county",
                "source_category": "county_codes",
                "source_section": "Section 1",
                "source_page": 1,
                "source_page_end": 1,
                "source_hash": "a" * 64,
            })
            + "\n",
            encoding="utf-8",
        )
    (tmp_path / "_CONTROL_PLANE").mkdir(exist_ok=True)
    (tmp_path / "_CONTROL_PLANE" / "COUNTY_SOURCE_COVERAGE.json").write_text(
        json.dumps({"counties": []}), encoding="utf-8"
    )
    summary = build_local_review_queues(tmp_path)
    assert summary.semantic_review_items == 2
    assert summary.answer_safe_local_rule_units == 0


def test_metadata_archive_moves_only_unreferenced_generated_versions(tmp_path: Path) -> None:
    """Metadata cleanup is reversible and leaves the active index untouched."""

    layer = tmp_path / "08_County_Authorities"
    meta = layer / "_meta"
    meta.mkdir(parents=True)
    (layer / "_index.jsonl").write_text(
        json.dumps({"id": "RULE-1", "meta_path": "08_County_Authorities/_meta/active.jsonl"}) + "\n",
        encoding="utf-8",
    )
    inactive = meta / "local_rules_20260715T000000Z.jsonl"
    inactive.write_text("{}\n", encoding="utf-8")
    report = archive_unreferenced_metadata(tmp_path, execute=True)
    assert report["items"][0]["status"] == "archived"
    assert not inactive.exists()
    assert (tmp_path / report["items"][0]["target"]).exists()
