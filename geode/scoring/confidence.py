"""Confidence-score helpers."""

from __future__ import annotations

from geode.pipeline.contracts import PipelineRoutingDecision

HIGH_VALUE_FIELDS = {"ccr_number", "enabling_statutes", "effective_date", "rule_type"}


def clamp_confidence(value: float) -> float:
    """Clamp a confidence score to the inclusive 0.0-1.0 range."""

    return max(0.0, min(1.0, value))


def compute_field_confidence(
    source_score: float,
    critique_score: float,
    validation_score: float,
    token_prob: float = 0.5,
) -> float:
    """Calculate the design's weighted field confidence score."""

    return clamp_confidence(
        0.30 * source_score
        + 0.25 * critique_score
        + 0.25 * validation_score
        + 0.20 * token_prob
    )


def calculate_field_confidence(
    source_score: float,
    critique_score: float,
    validation_score: float,
    token_probability: float = 0.5,
) -> float:
    """Compatibility alias for the field confidence formula."""

    return compute_field_confidence(
        source_score=source_score,
        critique_score=critique_score,
        validation_score=validation_score,
        token_prob=token_probability,
    )


def compute_record_confidence(field_scores: dict[str, float]) -> float:
    """Compute weighted record confidence, doubling high-value legal fields."""

    if not field_scores:
        return 0.0
    weighted_total = 0.0
    weight_total = 0.0
    for field_name, score in field_scores.items():
        weight = 2.0 if field_name in HIGH_VALUE_FIELDS else 1.0
        weighted_total += clamp_confidence(score) * weight
        weight_total += weight
    return clamp_confidence(weighted_total / weight_total)


def route_record(confidence: float, has_hallucination: bool = False) -> str:
    """Route a record using the B9 Layer 7 lowercase route labels."""

    normalized = clamp_confidence(confidence)
    if has_hallucination:
        return "reject"
    if normalized >= 0.85:
        return "auto_accept"
    if normalized >= 0.60:
        return "flag_accept"
    return "quarantine"


def route_confidence(
    composite_confidence: float,
    hallucination_reject: bool = False,
) -> PipelineRoutingDecision:
    """Route a record according to the design confidence thresholds."""

    confidence = clamp_confidence(composite_confidence)
    route = route_record(confidence, hallucination_reject)
    if route == "reject":
        return PipelineRoutingDecision(
            route="REJECT",
            composite_confidence=confidence,
            reasons=["R9 hallucination critique did not pass"],
        )
    if route == "auto_accept":
        return PipelineRoutingDecision(
            route="AUTO_ACCEPT",
            composite_confidence=confidence,
            reasons=["composite confidence >= 0.85"],
        )
    if route == "flag_accept":
        return PipelineRoutingDecision(
            route="FLAG_ACCEPT",
            composite_confidence=confidence,
            reasons=["composite confidence from 0.60 to 0.84"],
        )
    return PipelineRoutingDecision(
        route="QUARANTINE",
        composite_confidence=confidence,
        reasons=["composite confidence < 0.60"],
    )
