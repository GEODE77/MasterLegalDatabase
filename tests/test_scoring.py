"""Confidence scoring tests."""

from __future__ import annotations

from geode.scoring.confidence import (
    calculate_field_confidence,
    clamp_confidence,
    compute_field_confidence,
    compute_record_confidence,
    route_confidence,
    route_record,
)


def test_clamp_confidence() -> None:
    """Confidence values are clamped to the valid range."""

    assert clamp_confidence(-0.5) == 0.0
    assert clamp_confidence(0.5) == 0.5
    assert clamp_confidence(1.5) == 1.0


def test_calculate_field_confidence_uses_design_weights() -> None:
    """Field confidence follows the weighted formula from the design."""

    score = compute_field_confidence(
        source_score=1.0,
        critique_score=0.8,
        validation_score=1.0,
        token_prob=0.5,
    )
    assert score == 0.85
    assert calculate_field_confidence(1.0, 0.8, 1.0, 0.5) == 0.85


def test_compute_record_confidence_weights_critical_fields() -> None:
    """Record confidence uses 2x weight on critical legal fields."""

    score = compute_record_confidence(
        {
            "ccr_number": 1.0,
            "rule_type": 1.0,
            "summary": 0.0,
        }
    )
    assert score == 0.8


def test_route_confidence_thresholds() -> None:
    """Confidence routing follows AUTO/FLAG/QUARANTINE/REJECT thresholds."""

    assert route_record(0.85) == "auto_accept"
    assert route_record(0.84) == "flag_accept"
    assert route_record(0.60) == "flag_accept"
    assert route_record(0.59) == "quarantine"
    assert route_record(0.99, has_hallucination=True) == "reject"
    assert route_confidence(0.90).route == "AUTO_ACCEPT"
    assert route_confidence(0.70).route == "FLAG_ACCEPT"
    assert route_confidence(0.40).route == "QUARANTINE"
    assert route_confidence(0.95, hallucination_reject=True).route == "REJECT"
