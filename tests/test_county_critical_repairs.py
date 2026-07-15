"""Regression tests for county coverage and local-source repairs."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.county_gap_audit import build_gap_audit
from geode.pipeline.local_rule_ingest import _extract_source, _quarantine_row


def _write_json(path: Path, payload: object) -> None:
    """Write a JSON fixture for a control-plane test."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_gap_audit_does_not_call_registered_source_missing(tmp_path: Path) -> None:
    """A registered but unattempted source is reported as pending, not absent."""

    control = tmp_path / "_CONTROL_PLANE"
    categories = {"county_codes": {"status": "not_started", "source_ids": [], "notes": ""}}
    _write_json(
        control / "COUNTY_SOURCE_COVERAGE.json",
        {
            "source_categories": ["county_codes"],
            "counties": [{
                "county_id": "CO-COUNTY-LARIMER",
                "county_name": "Larimer County",
                "source_categories": categories,
                "overall_status": "source_identified",
                "homepage": {"status": "downloaded", "raw_path": str(tmp_path / "homepage.html")},
            }],
        },
    )
    _write_json(
        control / "LOCAL_SOURCE_REGISTRY.json",
        {"pilot": {"counties": [{
            "authority_id": "CO-COUNTY-LARIMER",
            "source_id": "county_larimer_codes",
            "authority_level": "county",
            "name": "Larimer County",
            "url": "https://www.larimer.gov/",
        }], "county_sources": [{
            "authority_id": "CO-COUNTY-LARIMER",
            "source_id": "county_larimer_codes",
            "authority_level": "county",
            "category": "county_codes",
            "url": "https://www.larimer.gov/policies",
        }]}},
    )
    (control / "LOCAL_DOWNLOAD_MANIFEST.jsonl").write_text(
        json.dumps({
            "authority_id": "CO-COUNTY-LARIMER",
            "authority_level": "county",
            "source_id": "county_larimer_homepage",
            "source_url": "https://www.larimer.gov/",
            "requested_url": "https://www.larimer.gov/",
            "status": "downloaded",
            "raw_path": str(tmp_path / "homepage.html"),
            "sha256": "a" * 64,
        }) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "homepage.html").write_text("official discovery page", encoding="utf-8")

    records, matrix = build_gap_audit(tmp_path)

    assert records[0]["disposition"] == "source_identified_not_attempted"
    assert records[0]["candidate_source_ids"] == ["county_larimer_codes"]
    assert matrix["counties"][0]["source_categories"]["county_codes"]["status"] == "source_identified"


def test_html_source_extraction_removes_script_text(tmp_path: Path) -> None:
    """HTML normalization keeps visible source text and drops page scripts."""

    path = tmp_path / "source.html"
    path.write_text(
        "<html><script>ignore this</script><body>County ordinance text</body></html>",
        encoding="utf-8",
    )

    text, pages, source_format = _extract_source(path)

    assert "County ordinance text" in text
    assert "ignore this" not in text
    assert pages == 1
    assert source_format == "html"


def test_quarantine_record_preserves_source_identity(tmp_path: Path) -> None:
    """Failed extraction remains traceable to its registry and download row."""

    path = tmp_path / "source.html"
    path.write_text("unreadable source", encoding="utf-8")
    row = {
        "source_id": "county_larimer_codes",
        "requested_url": "https://www.larimer.gov/policies",
        "authority_id": "CO-COUNTY-LARIMER",
        "authority_level": "county",
        "category": "county_codes",
        "sha256": "a" * 64,
    }

    record = _quarantine_row(path, "needs review", row)

    assert record["source_id"] == "county_larimer_codes"
    assert record["authority_id"] == "CO-COUNTY-LARIMER"
    assert record["source_category"] == "county_codes"
    assert record["source_hash"] == "a" * 64
