"""Assemble model-safe evidence from retrieved candidates."""

from __future__ import annotations

from datetime import datetime, timezone

from geode.orchestration.contracts import (
    CurrencyMetadata,
    CurrencyStatus,
    Evidence,
    QueryState,
    StageLog,
    StageStatus,
)
from geode.orchestration.stages._stub import PassThroughStage

MAX_EVIDENCE_EXCERPT_CHARS = 800


class AssembleEvidenceStage(PassThroughStage):
    """Convert candidate sources into structured evidence."""

    def __call__(self, state: QueryState) -> QueryState:
        """Attach provenance, currency, jurisdiction, and authority metadata."""

        assembled = [_assemble_candidate(state, candidate) for candidate in state.evidence]
        state.evidence = assembled
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Candidate sources assembled into model-safe evidence.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "evidence_count": len(assembled),
                    "evidence_ids": [item.evidence_id for item in assembled],
                },
            )
        )
        return state


def _assemble_candidate(state: QueryState, candidate: Evidence) -> Evidence:
    """Return one assembled evidence item without raw document dumping."""

    authority_level = candidate.authority_level or candidate.citation.authority_level
    source_id = candidate.citation.canonical_id or candidate.provenance.source_id
    chain = ["claim:pending", state.query_id, candidate.category_id or "uncategorized", source_id]
    if candidate.relationship_path:
        chain.extend(candidate.relationship_path)
    provenance = candidate.provenance.model_copy(
        update={"chain": list(dict.fromkeys(chain))}
    )
    currency = candidate.currency
    if currency.status == CurrencyStatus.UNKNOWN:
        currency = CurrencyMetadata(
            effective_date=currency.effective_date,
            status=CurrencyStatus.CURRENT,
            amendment_status=currency.amendment_status or "not_reported",
            repeal_status=currency.repeal_status or "not_reported",
            as_of_date=state.temporal.as_of_date if state.temporal else None,
        )
    return candidate.model_copy(
        update={
            "text": _trim_excerpt(candidate.text),
            "provenance": provenance,
            "currency": currency,
            "jurisdiction": state.jurisdiction,
            "authority_level": authority_level,
            "assembled": True,
            "is_candidate": False,
            "enabling_statute": candidate.enabling_statute or _infer_enabling_statute(candidate),
        }
    )


def _trim_excerpt(text: str) -> str:
    """Limit evidence to a compact excerpt."""

    normalized = " ".join(text.split())
    if len(normalized) <= MAX_EVIDENCE_EXCERPT_CHARS:
        return normalized
    return normalized[: MAX_EVIDENCE_EXCERPT_CHARS - 3].rstrip() + "..."


def _infer_enabling_statute(candidate: Evidence) -> str | None:
    """Infer enabling statute from relationship path when present."""

    for item in candidate.relationship_path:
        if item.startswith("CRS-"):
            return item
    if candidate.citation.canonical_id and candidate.citation.canonical_id.startswith("CRS-"):
        return candidate.citation.canonical_id
    return None
