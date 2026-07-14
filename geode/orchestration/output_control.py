"""Output shaping and control helpers."""

from __future__ import annotations

import re

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import (
    Answer,
    AuthorityLevel,
    ConfidenceLevel,
    ConfidenceReport,
    CoverageRequirement,
    CoverageStatus,
    CurrencyStatus,
    EmittedAnswer,
    FinalAnswer,
    GateAction,
    QueryState,
    RequirementItem,
)

AUTHORITY_WEIGHTS = {
    AuthorityLevel.FEDERAL: 1.0,
    AuthorityLevel.STATE: 0.9,
    AuthorityLevel.COUNTY: 0.7,
    AuthorityLevel.MUNICIPAL: 0.65,
}


def compute_confidence(state: QueryState) -> ConfidenceReport:
    """Compute answer confidence from deterministic evidence factors."""

    authority = _authority_factor(state)
    corroboration = min(len(state.evidence) / 3.0, 1.0)
    currency = _currency_factor(state)
    coverage = _coverage_factor(state)
    conflict = 0.75 if state.conflicts else 1.0
    citation = _citation_pass_rate(state)
    factors = {
        "authority": round(authority, 4),
        "corroboration": round(corroboration, 4),
        "currency": round(currency, 4),
        "coverage": round(coverage, 4),
        "conflict": round(conflict, 4),
        "citation": round(citation, 4),
    }
    score = round(
        authority * 0.20
        + corroboration * 0.15
        + currency * 0.20
        + coverage * 0.20
        + conflict * 0.10
        + citation * 0.15,
        4,
    )
    return ConfidenceReport(
        score=score,
        level=_confidence_level(score),
        factors=factors,
        explanation=[
            f"{name}={value:.4f}" for name, value in factors.items()
        ],
    )


def repair_final_answer(state: QueryState) -> FinalAnswer:
    """Repair draft output into the strict final answer schema."""

    confidence = state.confidence_report or compute_confidence(state)
    answer = state.answer or Answer(answer_text="No draft answer was produced.")
    requirements = _requirements_from_answer(answer)
    citations = answer.citations
    jurisdictions = _jurisdictions(state)
    uncertainties = [
        conflict.description for conflict in state.conflicts if conflict.disclosure_required
    ]
    uncertainties.extend(_conditional_coverage_limitations(state))
    coverage_gaps = list(state.empty_expected_categories)
    summary = _summary(answer.answer_text, coverage_gaps)
    return FinalAnswer(
        summary=summary,
        requirements=requirements,
        citations=citations,
        jurisdictions=jurisdictions,
        confidence=confidence,
        uncertainties=uncertainties,
        coverage_gaps=coverage_gaps,
    )


def apply_guardrails(state: QueryState) -> QueryState:
    """Attach config-driven disclaimers to the final answer."""

    if state.final_answer is None:
        state.final_answer = repair_final_answer(state)
    config = load_orchestration_config()["guardrails"]["guardrails"]
    disclaimers = [str(item) for item in config.get("disclaimers", [])]
    upl = config.get("unauthorized_practice_of_law", {})
    answer_text = _final_answer_text(state.final_answer).casefold()
    trigger_terms = [str(item).casefold() for item in upl.get("trigger_terms", [])]
    if any(term in answer_text for term in trigger_terms):
        disclaimers.append(str(upl["disclaimer"]))
    state.final_answer = state.final_answer.model_copy(
        update={"disclaimers": list(dict.fromkeys(disclaimers))}
    )
    return state


def apply_escalation(state: QueryState) -> QueryState:
    """Flag final answers requiring human review."""

    if state.final_answer is None:
        state.final_answer = repair_final_answer(state)
    config = load_orchestration_config()["guardrails"]["escalation"]
    threshold = float(config["low_confidence_threshold"])
    text = _final_answer_text(state.final_answer).casefold()
    high_stakes = any(str(term).casefold() in text for term in config.get("high_stakes_terms", []))
    low_confidence = state.final_answer.confidence.score < threshold
    if low_confidence or high_stakes:
        reason = str(config["reason_template"])
        state.escalation_required = True
        state.escalation_reason = reason
        state.final_answer = state.final_answer.model_copy(
            update={
                "escalation_required": True,
                "escalation_reason": reason,
            }
        )
    return state


def emit_final_answer(state: QueryState) -> QueryState:
    """Create emitted output with final answer and full trace."""

    if state.final_answer is None:
        state.final_answer = repair_final_answer(state)
    state.emitted_answer = EmittedAnswer(
        answer=state.final_answer,
        trace=state.trace,
        verification_report=state.verification_report,
    )
    return state


def _authority_factor(state: QueryState) -> float:
    """Compute average authority strength."""

    if not state.evidence:
        return 0.0
    values = [
        AUTHORITY_WEIGHTS.get(item.authority_level or item.citation.authority_level, 0.5)
        for item in state.evidence
    ]
    return sum(values) / len(values)


def _currency_factor(state: QueryState) -> float:
    """Compute currency strength."""

    if not state.evidence:
        return 0.0
    values = []
    for item in state.evidence:
        if item.currency.status == CurrencyStatus.CURRENT:
            values.append(1.0)
        elif item.currency.status == CurrencyStatus.AMENDED:
            values.append(0.6)
        elif item.currency.status == CurrencyStatus.REPEALED:
            values.append(0.0)
        else:
            values.append(0.5)
    return sum(values) / len(values)


def _coverage_factor(state: QueryState) -> float:
    """Compute coverage completeness."""

    if state.coverage_contract is None:
        return 1.0
    required = [
        item
        for item in state.coverage_contract.expected_categories
        if item.requirement == CoverageRequirement.REQUIRED
    ]
    if not required:
        return 1.0
    found = [item for item in required if item.status == CoverageStatus.FOUND]
    return len(found) / len(required)


def _citation_pass_rate(state: QueryState) -> float:
    """Compute citation gate pass rate."""

    if state.verification_report is None:
        return 1.0
    citation_results = [
        result
        for result in state.verification_report.gate_results
        if result.gate_name == "verify_citations"
    ]
    if not citation_results:
        return 1.0
    result = citation_results[-1]
    if result.action == GateAction.PASS:
        return 1.0
    stripped = len(result.stripped_citations)
    remaining = len(state.answer.citations) if state.answer is not None else 0
    total = stripped + remaining
    return remaining / total if total else 0.0


def _confidence_level(score: float) -> ConfidenceLevel:
    """Convert numeric confidence to label."""

    if score >= 0.8:
        return ConfidenceLevel.HIGH
    if score >= 0.6:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _requirements_from_answer(answer: Answer) -> list[RequirementItem]:
    """Create structured requirements from draft answer sentences."""

    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", answer.answer_text) if item.strip()]
    if not sentences and answer.answer_text.strip():
        sentences = [answer.answer_text.strip()]
    citation_ids = [citation.canonical_id or citation.citation_text for citation in answer.citations]
    return [
        RequirementItem(
            requirement_id=f"REQ-{index:03d}",
            text=sentence,
            evidence_ids=list(answer.evidence_ids),
            citation_ids=citation_ids,
        )
        for index, sentence in enumerate(sentences, start=1)
    ]


def _jurisdictions(state: QueryState) -> list[str]:
    """Return final jurisdiction labels."""

    if state.jurisdiction_coverage:
        return [item.label for item in state.jurisdiction_coverage]
    if state.jurisdiction is not None:
        return [state.jurisdiction.state]
    return []


def _conditional_coverage_limitations(state: QueryState) -> list[str]:
    """Return local-coverage limitations that must be disclosed."""

    if state.coverage_contract is None:
        return []
    limitations = [
        f"{category.label} are conditional: {category.reason}"
        for category in state.coverage_contract.expected_categories
        if category.requirement == CoverageRequirement.CONDITIONAL
        and category.status == CoverageStatus.CONDITIONAL
    ]
    return list(dict.fromkeys(limitations))


def _summary(answer_text: str, coverage_gaps: list[str]) -> str:
    """Build final summary."""

    first_sentence = next(
        (item.strip() for item in re.split(r"(?<=[.!?])\s+", answer_text) if item.strip()),
        "",
    )
    if first_sentence:
        return first_sentence
    if coverage_gaps:
        return "No supported requirement summary was produced; coverage gaps were disclosed."
    return "No supported requirement summary was produced."


def _final_answer_text(answer: FinalAnswer) -> str:
    """Flatten final answer text for guardrail checks."""

    return " ".join(
        [
            answer.summary,
            *[item.text for item in answer.requirements],
            *answer.uncertainties,
            *answer.coverage_gaps,
        ]
    )
