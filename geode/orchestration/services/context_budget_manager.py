"""Safe, content-aware context budgeting for model requests."""

from __future__ import annotations

from geode.orchestration.contracts import (
    AuthorityLevel,
    ContextBudgetReport,
    DraftRequest,
    Evidence,
    EvidenceContentType,
    EvidenceRetrievalReference,
)
from geode.orchestration.services.evidence_store import EvidenceStore
from geode.orchestration.services.token_count import TokenCounter


AUTHORITY_PRIORITY = {
    AuthorityLevel.FEDERAL: 4,
    AuthorityLevel.STATE: 3,
    AuthorityLevel.COUNTY: 2,
    AuthorityLevel.MUNICIPAL: 1,
    AuthorityLevel.DISTRICT: 1,
}


class ContextBudgetManager:
    """Fit evidence into a token budget without losing mandatory legal content."""

    def __init__(
        self,
        token_limit: int = 4000,
        *,
        token_counter: TokenCounter | None = None,
        evidence_store: EvidenceStore | None = None,
        corpus_version: str = "unknown",
        retention_seconds: int = 3600,
    ) -> None:
        """Create a budget manager with optional reversible evidence storage."""

        if token_limit < 1:
            raise ValueError("token_limit must be positive")
        self.token_limit = token_limit
        self.token_counter = token_counter or TokenCounter()
        self.evidence_store = evidence_store
        self.corpus_version = corpus_version
        self.retention_seconds = retention_seconds

    def fit(self, request: DraftRequest) -> tuple[DraftRequest, ContextBudgetReport]:
        """Return a budgeted request and preserve omitted evidence by reference."""

        policy_tokens = self.token_counter.count(request.prompt)
        evidence_tokens_before = sum(
            self.token_counter.count(item.text) for item in request.evidence
        )
        budget = max(self.token_limit - policy_tokens, 0)
        ordered = sorted(request.evidence, key=self._sort_key)
        kept: list[Evidence] = []
        excluded: list[Evidence] = []
        used = 0
        mandatory_ids: list[str] = []
        metadata_ids: list[str] = []

        for item in ordered:
            content_type = classify_evidence(item)
            item_tokens = self.token_counter.count(item.text)
            if content_type == EvidenceContentType.METADATA:
                metadata_ids.append(item.evidence_id)
            is_mandatory = item.mandatory and content_type == EvidenceContentType.LEGAL
            if is_mandatory:
                mandatory_ids.append(item.evidence_id)
            if is_mandatory or used + item_tokens <= budget:
                kept.append(item)
                used += item_tokens
            else:
                excluded.append(item)

        references: list[EvidenceRetrievalReference] = [
            reference
            for item in excluded
            if (reference := self._store_excluded(item)) is not None
        ]
        prompt, references = self._fit_complete_request(
            request.prompt,
            kept,
            excluded,
            references,
            mandatory_ids,
        )
        budgeted_request = request.model_copy(
            update={
                "prompt": prompt,
                "evidence": kept,
                "retrieval_references": [*request.retrieval_references, *references],
            }
        )
        evidence_tokens_after = sum(
            self.token_counter.count(item.text) for item in kept
        )
        estimated_tokens = self.token_counter.count(prompt) + evidence_tokens_after
        initial_tokens = policy_tokens + evidence_tokens_before
        savings = max(initial_tokens - estimated_tokens, 0)
        savings_percent = (
            round((savings / initial_tokens) * 100, 2)
            if initial_tokens
            else 0.0
        )
        report = ContextBudgetReport(
            token_limit=self.token_limit,
            estimated_tokens=estimated_tokens,
            kept_evidence_ids=[item.evidence_id for item in kept],
            dropped_evidence_ids=[item.evidence_id for item in excluded],
            preserved_high_authority_ids=[
                item.evidence_id
                for item in kept
                if (item.authority_level or item.citation.authority_level)
                in {AuthorityLevel.FEDERAL, AuthorityLevel.STATE}
            ],
            policy_tokens=policy_tokens,
            evidence_tokens_before=evidence_tokens_before,
            evidence_tokens_after=evidence_tokens_after,
            excluded_evidence_ids=[item.evidence_id for item in excluded],
            mandatory_evidence_ids=mandatory_ids,
            metadata_evidence_ids=metadata_ids,
            retrieval_references=references,
            estimated_savings_tokens=savings,
            estimated_savings_percent=savings_percent,
            tokenizer=self.token_counter.name,
            budget_overflow_tokens=max(estimated_tokens - self.token_limit, 0),
        )
        return budgeted_request, report

    def _fit_complete_request(
        self,
        base_prompt: str,
        kept: list[Evidence],
        excluded: list[Evidence],
        references: list[EvidenceRetrievalReference],
        mandatory_ids: list[str],
    ) -> tuple[str, list[EvidenceRetrievalReference]]:
        """Account for the final prompt and exclusion instructions together."""

        while True:
            prompt = _append_retrieval_instructions(base_prompt, references, excluded)
            total_tokens = self.token_counter.count(prompt) + sum(
                self.token_counter.count(item.text) for item in kept
            )
            if total_tokens <= self.token_limit:
                return prompt, references

            removable = next(
                (
                    item
                    for item in reversed(kept)
                    if not (item.mandatory and classify_evidence(item) == EvidenceContentType.LEGAL)
                ),
                None,
            )
            if removable is None:
                return prompt, references
            kept.remove(removable)
            excluded.append(removable)
            if removable.evidence_id in mandatory_ids:
                mandatory_ids.remove(removable.evidence_id)
            stored = self._store_excluded(removable)
            if stored is not None:
                references.append(stored)

    def _sort_key(self, item: Evidence) -> tuple[int, int, float, str]:
        """Order mandatory legal evidence before compressible metadata."""

        content_type = classify_evidence(item)
        mandatory = int(item.mandatory and content_type == EvidenceContentType.LEGAL)
        authority = AUTHORITY_PRIORITY.get(
            item.authority_level or item.citation.authority_level,
            0,
        )
        return (-mandatory, -authority, -item.confidence, item.evidence_id)

    def _store_excluded(self, item: Evidence) -> EvidenceRetrievalReference | None:
        """Store one excluded item when reversible retrieval is configured."""

        if self.evidence_store is None:
            return None
        return self.evidence_store.put(
            item,
            self.corpus_version,
            retention_seconds=self.retention_seconds,
            token_counter=self.token_counter,
        )


def classify_evidence(evidence: Evidence) -> EvidenceContentType:
    """Classify evidence without allowing learned ranking to change legal status."""

    if evidence.answer_mode == "conditional":
        return EvidenceContentType.CONDITIONAL
    if evidence.content_type != EvidenceContentType.LEGAL:
        return evidence.content_type
    if evidence.semantic_status in {"source_preservation_only", "needs_review"}:
        return EvidenceContentType.METADATA
    if evidence.is_candidate and not evidence.assembled:
        return EvidenceContentType.METADATA
    return EvidenceContentType.LEGAL


def _append_retrieval_instructions(
    prompt: str,
    references: list[EvidenceRetrievalReference],
    excluded: list[Evidence],
) -> str:
    """Tell the model what was omitted without exposing unsupported content."""

    if not excluded:
        return prompt
    lines = [
        "## Evidence available by controlled retrieval",
        "Some non-mandatory evidence was excluded from immediate context. "
        "Do not infer its contents; request it by reference if needed.",
    ]
    if references:
        lines.extend(
            f"- {reference.reference_id}: {reference.evidence_id} "
            f"({reference.original_tokens} tokens)"
            for reference in references
        )
    else:
        lines.extend(f"- excluded evidence ID: {item.evidence_id}" for item in excluded)
    return f"{prompt.rstrip()}\n\n" + "\n".join(lines)
