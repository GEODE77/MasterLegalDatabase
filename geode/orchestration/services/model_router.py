"""Provider-agnostic model routing for orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from geode.orchestration.contracts import Answer, Citation, DraftRequest, ModelRouteDecision


class ModelAdapter(Protocol):
    """Provider adapter contract."""

    @property
    def provider(self) -> str:
        """Provider name."""

    @property
    def model(self) -> str:
        """Model name."""

    @property
    def estimated_cost(self) -> float:
        """Estimated call cost."""

    @property
    def estimated_latency_ms(self) -> int:
        """Estimated latency."""

    def generate(self, request: DraftRequest) -> Answer:
        """Generate a draft answer."""


@dataclass(frozen=True)
class DeterministicModelAdapter:
    """Local deterministic adapter used as the default writer."""

    provider: str = "local"
    model: str = "deterministic-writer"
    estimated_cost: float = 0.0
    estimated_latency_ms: int = 1

    def generate(self, request: DraftRequest) -> Answer:
        """Generate a deterministic draft from assembled evidence only."""

        citations: list[Citation] = []
        evidence_ids: list[str] = []
        lines: list[str] = []
        for item in request.evidence:
            evidence_ids.append(item.evidence_id)
            citations.append(item.citation)
            lines.append(f"{item.citation.citation_text}: {item.text}")
        if request.conflicts:
            lines.append(
                "Conflicts requiring disclosure: "
                + ", ".join(conflict.conflict_id for conflict in request.conflicts)
            )
        return Answer(
            answer_text="\n".join(lines),
            citations=citations,
            evidence_ids=evidence_ids,
            confidence=min((item.confidence for item in request.evidence), default=0.0),
        )


class ModelRouter:
    """Route model calls by cost/latency with fallback."""

    def __init__(self, adapters: list[ModelAdapter] | None = None) -> None:
        """Create a router with one or more provider adapters."""

        self.adapters = adapters or [DeterministicModelAdapter()]
        self.last_decision: ModelRouteDecision | None = None

    def generate_draft(self, request: DraftRequest) -> Answer:
        """Generate a draft through the selected provider adapter."""

        answer, _ = self.route_with_metadata(request)
        return answer

    def route_with_metadata(self, request: DraftRequest) -> tuple[Answer, ModelRouteDecision]:
        """Generate a draft and return the routing decision."""

        ordered = sorted(self.adapters, key=lambda item: (item.estimated_cost, item.estimated_latency_ms))
        failures: list[str] = []
        for index, adapter in enumerate(ordered):
            try:
                answer = adapter.generate(request)
            except Exception as exc:  # pragma: no cover - exercised by tests through fallback path
                failures.append(f"{adapter.provider}:{type(exc).__name__}")
                continue
            decision = ModelRouteDecision(
                provider=adapter.provider,
                model=adapter.model,
                estimated_cost=adapter.estimated_cost,
                estimated_latency_ms=adapter.estimated_latency_ms,
                fallback_used=index > 0 or bool(failures),
            )
            self.last_decision = decision
            return answer, decision
        raise RuntimeError(f"all model adapters failed: {', '.join(failures)}")

    def route(self, request: DraftRequest) -> Answer:
        """Backward-compatible alias for draft generation."""

        return self.generate_draft(request)
