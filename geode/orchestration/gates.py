"""Hard accuracy validators for orchestration answers."""

from __future__ import annotations

import re
import hashlib

from geode.orchestration.contracts import (
    Answer,
    AtomicClaim,
    CoverageRequirement,
    CoverageStatus,
    CurrencyStatus,
    Evidence,
    GateAction,
    GateResult,
    QueryState,
    VerificationReport,
    VerificationStatus,
)

MIN_TOKEN_OVERLAP = 2
CITATION_PATTERN = re.compile(r"\b(?:CRS|CCR|CFR|USC|[A-Z]+[-_])[\w_. -]*\d[\w_. -]*\b")


def enforce_grounding(state: QueryState) -> tuple[QueryState, GateResult]:
    """Strip answer claims with no supporting evidence."""

    claims = extract_atomic_claims(state.answer)
    evidence_ids = {item.evidence_id for item in state.evidence}
    supported: list[AtomicClaim] = []
    stripped: list[str] = []
    for claim in claims:
        claim_evidence = [
            item
            for item in state.evidence
            if item.evidence_id in set(claim.evidence_ids) and _evidence_is_answer_safe(item)
        ]
        claim_supported = bool(claim_evidence) and _claim_supported_by_text(
            claim.text,
            claim_evidence,
        )
        updated = claim.model_copy(update={"supported": claim_supported})
        if claim_supported:
            supported.append(updated)
        else:
            stripped.append(claim.claim_id)
    state.extracted_claims = supported
    if state.answer is not None and stripped:
        state.answer = _answer_with_claims(state.answer, supported)
    result = GateResult(
        gate_name="enforce_grounding",
        action=GateAction.STRIP if stripped else GateAction.PASS,
        passed=not stripped,
        checked_claim_ids=[claim.claim_id for claim in claims],
        stripped_claim_ids=stripped,
        messages=["Stripped ungrounded claims."] if stripped else ["All claims had evidence support."],
    )
    return state, result


def verify_citations(state: QueryState) -> tuple[QueryState, GateResult]:
    """Verify that answer citations exist and are supported by evidence text."""

    if state.answer is None:
        return state, _pass_result("verify_citations", "No answer to verify.")
    evidence_by_citation = _evidence_by_citation(state.evidence)
    valid_citations = []
    stripped_citations: list[str] = []
    for citation in state.answer.citations:
        citation_id = citation.canonical_id or citation.citation_text
        evidence = evidence_by_citation.get(citation_id)
        if evidence is None or not _citation_text_supported(evidence) or not _evidence_is_answer_safe(evidence):
            stripped_citations.append(citation_id)
            continue
        valid_citations.append(citation)
    if stripped_citations:
        state.answer = state.answer.model_copy(
            update={
                "citations": valid_citations,
                "answer_text": _remove_sentences_with_terms(
                    state.answer.answer_text,
                    stripped_citations,
                ),
            }
        )
    result = GateResult(
        gate_name="verify_citations",
        action=GateAction.STRIP if stripped_citations else GateAction.PASS,
        passed=not stripped_citations,
        stripped_citations=stripped_citations,
        messages=(
            ["Stripped citations that were absent from assembled evidence or unsupported."]
            if stripped_citations
            else ["All citations matched assembled evidence."]
        ),
    )
    return state, result


def verify_currency(state: QueryState) -> tuple[QueryState, GateResult]:
    """Flag repealed or superseded cited evidence."""

    cited_evidence = _cited_evidence(state)
    flagged = [
        item.evidence_id
        for item in cited_evidence
        if item.currency.status in {CurrencyStatus.REPEALED, CurrencyStatus.AMENDED}
        and not _historical_query(state)
    ]
    unknown = [
        item.evidence_id
        for item in cited_evidence
        if item.currency.status == CurrencyStatus.UNKNOWN and not _historical_query(state)
    ]
    flagged = list(dict.fromkeys([*flagged, *unknown]))
    if flagged and state.answer is not None:
        state.answer = state.answer.model_copy(update={"confidence": min(state.answer.confidence, 0.5)})
    result = GateResult(
        gate_name="verify_currency",
        action=GateAction.DOWNGRADE if flagged else GateAction.PASS,
        passed=not flagged,
        flagged_evidence_ids=flagged,
        messages=(
            [
                "Flagged cited provisions whose current status is repealed, amended, superseded, "
                "or unverified for a current-law query."
            ]
            if flagged
            else ["Cited provisions passed currency checks."]
        ),
    )
    return state, result


def check_completeness(state: QueryState) -> tuple[QueryState, GateResult]:
    """Flag missing non-conditional coverage categories."""

    if state.coverage_contract is None:
        return state, _pass_result("check_completeness", "No coverage contract to verify.")
    missing = [
        category.category_id
        for category in state.coverage_contract.expected_categories
        if category.requirement == CoverageRequirement.REQUIRED
        and category.status in {CoverageStatus.EMPTY, CoverageStatus.PENDING}
    ]
    state.empty_expected_categories = list(dict.fromkeys([*state.empty_expected_categories, *missing]))
    if missing and state.answer is not None:
        disclosure = "Retrieval gaps: " + ", ".join(missing) + "."
        if disclosure not in state.answer.answer_text:
            state.answer = state.answer.model_copy(
                update={"answer_text": "\n".join([state.answer.answer_text, disclosure]).strip()}
            )
    result = GateResult(
        gate_name="check_completeness",
        action=GateAction.DOWNGRADE if missing else GateAction.PASS,
        passed=not missing,
        missing_categories=missing,
        messages=(
            ["Required coverage categories were missing and must be disclosed."]
            if missing
            else ["Coverage contract categories were accounted for."]
        ),
    )
    return state, result


def check_faithfulness(state: QueryState) -> tuple[QueryState, GateResult]:
    """Remove answer sentences that are not entailed by evidence text."""

    if state.answer is None:
        return state, _pass_result("check_faithfulness", "No answer to verify.")
    sentences = _split_sentences(state.answer.answer_text)
    kept: list[str] = []
    stripped_ids: list[str] = []
    for index, sentence in enumerate(sentences, start=1):
        if sentence.startswith("Retrieval gaps:") or _claim_supported_by_text(sentence, state.evidence):
            kept.append(sentence)
        else:
            stripped_ids.append(f"sentence-{index}")
    if stripped_ids:
        state.answer = state.answer.model_copy(update={"answer_text": " ".join(kept)})
    result = GateResult(
        gate_name="check_faithfulness",
        action=GateAction.STRIP if stripped_ids else GateAction.PASS,
        passed=not stripped_ids,
        stripped_claim_ids=stripped_ids,
        messages=(
            ["Removed unsupported answer sentences."]
            if stripped_ids
            else ["Every answer sentence was supported by evidence."]
        ),
    )
    return state, result


def absence_verification(state: QueryState) -> tuple[QueryState, GateResult]:
    """Prevent retrieval limitations from being stated as verified absence."""

    if state.answer is None:
        return state, _pass_result("absence_verification", "No answer to verify.")
    lowered = state.answer.answer_text.casefold()
    absence_claim = "no such requirement exists" in lowered or "no requirement exists" in lowered
    has_verified_absence = any(item.category_id == "verified_absence" for item in state.evidence)
    if absence_claim and not has_verified_absence:
        state.answer = state.answer.model_copy(
            update={
                "answer_text": re.sub(
                    r"no such requirement exists|no requirement exists",
                    "no candidate source was found",
                    state.answer.answer_text,
                    flags=re.IGNORECASE,
                )
            }
        )
        result = GateResult(
            gate_name="absence_verification",
            action=GateAction.STRIP,
            passed=False,
            messages=[
                "Replaced verified-absence language with retrieval-limitation language."
            ],
        )
        return state, result
    return state, _pass_result("absence_verification", "Absence language passed verification.")


def append_gate_result(state: QueryState, result: GateResult) -> QueryState:
    """Write one gate result to the query state's verification report."""

    report = state.verification_report or VerificationReport()
    report.checks_run.append(result.gate_name)
    report.gate_results.append(result)
    if result.passed:
        if report.status == VerificationStatus.NOT_RUN:
            report.status = VerificationStatus.PASSED
    else:
        report.status = VerificationStatus.NEEDS_REVIEW
        report.failures.extend(result.messages)
        if result.action == GateAction.REGENERATE:
            state.regeneration_requested = True
            state.regeneration_reason = "; ".join(result.messages)
    state.verification_report = report
    return state


def request_regeneration(state: QueryState, reason: str) -> QueryState:
    """Mark the state for a later regeneration step."""

    state.regeneration_requested = True
    state.regeneration_reason = reason
    return state


def extract_atomic_claims(answer: Answer | None) -> list[AtomicClaim]:
    """Extract simple sentence-level claims from an answer."""

    if answer is None:
        return []
    claims: list[AtomicClaim] = []
    for index, sentence in enumerate(_split_sentences(answer.answer_text), start=1):
        citations = _extract_citation_ids(sentence)
        claims.append(
            AtomicClaim(
                claim_id=f"claim-{index}",
                text=sentence,
                citation_ids=citations,
                evidence_ids=list(answer.evidence_ids),
                supported=False,
            )
        )
    return claims


def _pass_result(gate_name: str, message: str) -> GateResult:
    """Return a passing gate result."""

    return GateResult(
        gate_name=gate_name,
        action=GateAction.PASS,
        passed=True,
        messages=[message],
    )


def _answer_with_claims(answer: Answer, claims: list[AtomicClaim]) -> Answer:
    """Return an answer containing only surviving claims."""

    surviving_text = " ".join(claim.text for claim in claims)
    surviving_citation_ids = {citation for claim in claims for citation in claim.citation_ids}
    citations = [
        citation
        for citation in answer.citations
        if (citation.canonical_id or citation.citation_text) in surviving_citation_ids
        or not surviving_citation_ids
    ]
    return answer.model_copy(update={"answer_text": surviving_text, "citations": citations})


def _evidence_by_citation(evidence: list[Evidence]) -> dict[str, Evidence]:
    """Return evidence keyed by canonical and written citations."""

    keyed: dict[str, Evidence] = {}
    for item in evidence:
        keyed[item.citation.citation_text] = item
        if item.citation.canonical_id:
            keyed[item.citation.canonical_id] = item
    return keyed


def _citation_text_supported(evidence: Evidence) -> bool:
    """Confirm the citation has evidence text and a specific source path."""

    passage = evidence.provenance.passage
    if not evidence.text.strip() or not evidence.provenance.source_path.strip() or passage is None:
        return False
    if not passage.text_hash:
        return False
    normalized = " ".join(evidence.text.split()).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest() == passage.text_hash


def _evidence_is_answer_safe(evidence: Evidence) -> bool:
    """Reject evidence that is explicitly not ready for model answers."""

    return evidence.answer_safe and evidence.semantic_status != "source_preservation_only"


def _remove_sentences_with_terms(text: str, terms: list[str]) -> str:
    """Remove sentences containing any listed term."""

    lowered_terms = [term.casefold() for term in terms]
    kept = [
        sentence
        for sentence in _split_sentences(text)
        if not any(term in sentence.casefold() for term in lowered_terms)
    ]
    return " ".join(kept)


def _cited_evidence(state: QueryState) -> list[Evidence]:
    """Return evidence cited by the current answer."""

    if state.answer is None:
        return []
    cited_ids = set(state.answer.evidence_ids)
    citation_ids = {citation.canonical_id or citation.citation_text for citation in state.answer.citations}
    return [
        item
        for item in state.evidence
        if item.evidence_id in cited_ids
        or item.citation.citation_text in citation_ids
        or (item.citation.canonical_id is not None and item.citation.canonical_id in citation_ids)
    ]


def _historical_query(state: QueryState) -> bool:
    """Return whether the query asks for historical law."""

    return state.temporal is not None and state.temporal.mode in {"historical", "as_of"}


def _claim_supported_by_text(text: str, evidence: list[Evidence]) -> bool:
    """Use deterministic token overlap to check evidence support."""

    claim_tokens = _tokens(text)
    if not claim_tokens:
        return False
    for item in evidence:
        if not _evidence_is_answer_safe(item):
            continue
        evidence_tokens = _tokens(item.text)
        if len(claim_tokens & evidence_tokens) >= MIN_TOKEN_OVERLAP:
            return True
    return False


def _extract_citation_ids(sentence: str) -> list[str]:
    """Extract citation-like strings from one sentence."""

    return [match.group(0).strip(" .,:;") for match in CITATION_PATTERN.finditer(sentence)]


def _split_sentences(text: str) -> list[str]:
    """Split text into simple answer sentences."""

    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", text.strip()) if item.strip()]


def _tokens(text: str) -> set[str]:
    """Return normalized tokens for support checks."""

    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "for",
        "from",
        "in",
        "is",
        "of",
        "or",
        "the",
        "to",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.casefold())
        if len(token) > 2 and token not in stopwords
    }
