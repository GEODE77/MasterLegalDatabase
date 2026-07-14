"""Context budgeting for model requests."""

from __future__ import annotations

from geode.orchestration.contracts import (
    AuthorityLevel,
    ContextBudgetReport,
    DraftRequest,
    Evidence,
)

AUTHORITY_PRIORITY = {
    AuthorityLevel.FEDERAL: 4,
    AuthorityLevel.STATE: 3,
    AuthorityLevel.COUNTY: 2,
    AuthorityLevel.MUNICIPAL: 1,
}


class ContextBudgetManager:
    """Fit evidence and policies into a deterministic token budget."""

    def __init__(self, token_limit: int = 4000) -> None:
        """Create a budget manager."""

        self.token_limit = token_limit

    def fit(self, request: DraftRequest) -> tuple[DraftRequest, ContextBudgetReport]:
        """Return a budgeted request while preserving high-authority evidence."""

        policy_tokens = _estimate_tokens(request.prompt)
        budget = max(self.token_limit - policy_tokens, 0)
        ordered = sorted(
            request.evidence,
            key=lambda item: (
                -AUTHORITY_PRIORITY.get(item.authority_level or item.citation.authority_level, 0),
                -item.confidence,
                item.evidence_id,
            ),
        )
        kept: list[Evidence] = []
        dropped: list[Evidence] = []
        used = 0
        for item in ordered:
            item_tokens = _estimate_tokens(item.text)
            is_high_authority = (item.authority_level or item.citation.authority_level) in {
                AuthorityLevel.FEDERAL,
                AuthorityLevel.STATE,
            }
            if used + item_tokens <= budget or is_high_authority:
                kept.append(item)
                used += item_tokens
            else:
                dropped.append(item)
        kept_ids = [item.evidence_id for item in kept]
        report = ContextBudgetReport(
            token_limit=self.token_limit,
            estimated_tokens=policy_tokens + used,
            kept_evidence_ids=kept_ids,
            dropped_evidence_ids=[item.evidence_id for item in dropped],
            preserved_high_authority_ids=[
                item.evidence_id
                for item in kept
                if (item.authority_level or item.citation.authority_level)
                in {AuthorityLevel.FEDERAL, AuthorityLevel.STATE}
            ],
        )
        return request.model_copy(update={"evidence": kept}), report


def _estimate_tokens(text: str) -> int:
    """Estimate tokens cheaply and deterministically."""

    return max(1, len(text.split()))
