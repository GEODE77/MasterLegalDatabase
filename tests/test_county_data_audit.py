"""Tests for the county data quality audit."""

from geode.pipeline.county_data_audit import _contains_bad_text, _marker_counts


def test_county_audit_detects_replacement_and_mojibake() -> None:
    """Unreadable extraction markers are surfaced for review."""

    values = ["ordinary text", "broken \ufffd text", "cafÃ©"]

    assert _contains_bad_text(values)
    counts = _marker_counts(values)
    assert counts["\ufffd"] == 1
    assert counts["Ã"] == 1


def test_county_audit_accepts_normal_text() -> None:
    """Normal Unicode text is not marked as an encoding defect."""

    assert not _contains_bad_text(["Règlement § 1 — county notice"])
