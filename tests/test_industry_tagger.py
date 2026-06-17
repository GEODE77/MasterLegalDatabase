"""Tests for deterministic NAICS industry tagging."""

from __future__ import annotations

from geode.scoring.industry_tagger import (
    build_theme_index,
    classify_scope,
    load_taxonomies,
    parse_crs_ref,
    rank_industries,
    tag_bill,
    tag_by_crs,
)


def test_parse_crs_ref_standard_references() -> None:
    """CRS references are parsed into title and article numbers."""

    assert parse_crs_ref("\u00a7 25-7-114.7, C.R.S.") == ("25", "7")
    assert parse_crs_ref("\u00a7 8-4-101, C.R.S.") == ("8", "4")
    assert parse_crs_ref("\u00a7 39-22-104 (3)(a), C.R.S.") == ("39", "22")


def test_parse_crs_ref_bad_inputs() -> None:
    """Malformed or empty references return null title/article values."""

    assert parse_crs_ref("not a CRS reference") == (None, None)
    assert parse_crs_ref("") == (None, None)


def test_tag_by_crs_uses_real_taxonomies() -> None:
    """CRS tagging finds article-level manufacturing codes and universal scope."""

    taxonomies = load_taxonomies("taxonomies")
    bill = {
        "bill_number": "HB25-1001",
        "crs_references": [
            "\u00a7 25-7-114.7, C.R.S.",
            "\u00a7 8-6-101, C.R.S.",
        ],
    }

    result = tag_by_crs(bill, taxonomies["crs_map"])

    assert result["confidence"] == "high"
    assert result["universal_detected"] is True
    assert result["naics_hits"]["3271"] == 3
    assert result["naics_hits"]["3272"] == 3
    assert "emissions" in result["themes"]
    assert "wages" in result["themes"]
    assert result["article_match_count"] == 2


def test_classify_scope() -> None:
    """Scope classification follows sector-count and universal rules."""

    hierarchy = load_taxonomies("taxonomies")["naics_hierarchy"]

    five_sector_hits = {
        "1111": 1,
        "2111": 1,
        "2211": 1,
        "3271": 1,
        "5241": 1,
    }
    two_sector_hits = {"3271": 1, "2211": 1}

    assert classify_scope(five_sector_hits, hierarchy, False) == "universal"
    assert classify_scope(two_sector_hits, hierarchy, False) == "narrow"
    assert classify_scope({}, hierarchy, True) == "universal"


def test_rank_industries_sorts_labels_and_caps() -> None:
    """Industry ranking sorts by score, labels relevance, and caps at 20."""

    hierarchy = load_taxonomies("taxonomies")["naics_hierarchy"]
    hits = {str(1000 + index): float(25 - index) for index in range(25)}
    hits.update({"3271": 100.0, "2211": 90.0, "5241": 80.0, "6211": 70.0})

    ranked = rank_industries(hits, hierarchy)

    assert len(ranked) == 20
    assert [item["naics"] for item in ranked[:4]] == ["3271", "2211", "5241", "6211"]
    assert [item["relevance"] for item in ranked[:4]] == ["high", "high", "high", "high"]
    assert ranked[4]["relevance"] == "medium"
    assert ranked[-1]["relevance"] == "low"
    assert ranked[0]["name"] == "Clay Product and Refractory Manufacturing"


def test_tag_bill_end_to_end_output_shape() -> None:
    """End-to-end bill tagging returns the complete public tag record shape."""

    taxonomies = load_taxonomies("taxonomies")
    bill = {
        "bill_number": "HB25-1001",
        "title": "Concerning Emissions From Industrial Facilities",
        "crs_references": ["\u00a7 25-7-114.7, C.R.S.", "\u00a7 8-6-101, C.R.S."],
        "entities": {
            "committees": [{"committee": "Energy & Environment", "chamber": "house"}]
        },
    }

    record = tag_bill(bill, taxonomies)

    assert set(record) == {
        "bill_number",
        "applicability_scope",
        "industries",
        "regulatory_themes",
        "crs_titles",
        "universal_applicability",
        "tagging_metadata",
    }
    assert record["bill_number"] == "HB25-1001"
    assert record["applicability_scope"] == "universal"
    assert record["industries"]
    assert record["regulatory_themes"]
    assert record["tagging_metadata"]["confidence"] == "high"
    assert record["tagging_metadata"]["crs_matches"]["article_level"] == 2


def test_build_theme_index() -> None:
    """Theme index reverses bill tag records into theme-to-bill lookups."""

    tags = {
        "HB25-1001": {"regulatory_themes": ["emissions", "permitting"]},
        "SB25-0055": {"regulatory_themes": ["labor", "permitting"]},
    }

    assert build_theme_index(tags) == {
        "emissions": ["HB25-1001"],
        "labor": ["SB25-0055"],
        "permitting": ["HB25-1001", "SB25-0055"],
    }
