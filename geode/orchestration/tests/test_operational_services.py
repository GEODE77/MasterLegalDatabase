"""Tests for cross-cutting orchestration services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from geode.orchestration.contracts import (
    Answer,
    AuthorityLevel,
    CacheStatus,
    Citation,
    DraftRequest,
    Evidence,
    Intent,
    Provenance,
    QueryState,
)
from geode.orchestration.pipeline import Pipeline
from geode.orchestration.services import (
    AccessControlService,
    ContextBudgetManager,
    FreshnessMonitor,
    ModelRouter,
    OrchestrationCache,
    OrchestrationLogger,
)
from geode.orchestration.stages import GenerateDraftStage, QueryNormalizationStage


def test_all_model_calls_route_through_model_router() -> None:
    """Draft generation uses the router adapter and no direct SDK calls exist."""

    adapter = CountingAdapter()
    router = ModelRouter([FailingAdapter(), adapter])
    evidence = _evidence("ev-fed", AuthorityLevel.FEDERAL, "Federal evidence supports reporting.")
    state = QueryState(
        intent=Intent(raw_query="What applies?"),
        draft_request=DraftRequest(prompt="prompt", evidence=[evidence]),
    )

    output = GenerateDraftStage("generate_draft", router=router)(state)

    assert adapter.calls == 1
    assert output.model_route is not None
    assert output.model_route.fallback_used is True
    assert output.answer is not None
    assert output.answer.evidence_ids == ["ev-fed"]
    _assert_no_direct_model_sdk_calls()


def test_context_budget_never_drops_high_authority_source() -> None:
    """Budgeting preserves federal and state evidence before local evidence."""

    federal = _evidence("ev-fed", AuthorityLevel.FEDERAL, "federal " * 100)
    state = _evidence("ev-state", AuthorityLevel.STATE, "state " * 100)
    municipal = _evidence("ev-muni", AuthorityLevel.MUNICIPAL, "municipal " * 100)
    request = DraftRequest(prompt="policy " * 20, evidence=[municipal, federal, state])

    _, report = ContextBudgetManager(token_limit=30).fit(request)

    assert "ev-fed" in report.kept_evidence_ids
    assert "ev-state" in report.kept_evidence_ids
    assert "ev-fed" in report.preserved_high_authority_ids
    assert "ev-state" in report.preserved_high_authority_ids


def test_pipeline_emits_replayable_json_audit_trace(tmp_path: Path) -> None:
    """Pipeline logging persists enough JSON to replay stage decisions."""

    audit_path = tmp_path / "audit.jsonl"
    logger = OrchestrationLogger(audit_path)
    state = QueryState(intent=Intent(raw_query="CO2 rules"))

    result = Pipeline(
        [QueryNormalizationStage("query_normalization")],
        logger=logger,
        corpus_version="v1",
    ).run(state)

    assert result.audit_log_path == audit_path.as_posix()
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert rows
    assert all(row["query_id"] == result.query_id for row in rows)
    assert {row["stage_name"] for row in rows} == {"query_normalization"}
    assert all("payload" in row for row in rows)


def test_cache_hit_miss_and_freshness_invalidation(tmp_path: Path) -> None:
    """Cache reports miss, hit, and stale when corpus version changes."""

    cache = OrchestrationCache(tmp_path / "cache")
    state = QueryState(intent=Intent(raw_query="CO2 rules", normalized_query="co2 rules"))
    key = cache.make_key("co2 rules", "v1", "query_normalization")

    cached, miss = cache.get(key, "v1")
    assert cached is None
    assert miss.status == CacheStatus.MISS

    cache.set(key, state, "v1")
    cached, hit = cache.get(key, "v1")
    assert cached is not None
    assert hit.status == CacheStatus.HIT

    stale_cached, stale = cache.get(key, "v2")
    assert stale_cached is None
    assert stale.status == CacheStatus.STALE
    freshness = FreshnessMonitor("v2").check("v1")
    assert freshness.stale is True


def test_access_control_rejects_missing_provenance() -> None:
    """Access control enforces provenance integrity."""

    state = QueryState(
        intent=Intent(raw_query="What applies?"),
        evidence=[
            Evidence(
                evidence_id="ev-bad",
                text="Bad evidence",
                citation=Citation(
                    citation_text="CRS-1-1-1",
                    canonical_id="CRS-1-1-1",
                    authority_level=AuthorityLevel.STATE,
                ),
                    provenance=Provenance(
                        source_id="CRS-1-1-1",
                        source_path="_RAW_ARCHIVE/crs/source.pdf",
                    ),
                    confidence=0.5,
                    assembled=True,
                )
        ],
    )

    with pytest.raises(ValueError):
        AccessControlService().validate_state(state)


@dataclass
class CountingAdapter:
    """Test adapter that records calls."""

    provider: str = "test"
    model: str = "counting"
    estimated_cost: float = 0.1
    estimated_latency_ms: int = 10
    calls: int = 0

    def generate(self, request: DraftRequest) -> Answer:
        """Generate from evidence."""

        self.calls += 1
        return Answer(
            answer_text=request.evidence[0].text,
            citations=[request.evidence[0].citation],
            evidence_ids=[request.evidence[0].evidence_id],
            confidence=0.8,
        )


@dataclass(frozen=True)
class FailingAdapter:
    """Adapter that always fails to force fallback."""

    provider: str = "fail"
    model: str = "failing"
    estimated_cost: float = 0.0
    estimated_latency_ms: int = 1

    def generate(self, request: DraftRequest) -> Answer:
        """Raise to force fallback."""

        del request
        raise RuntimeError("adapter unavailable")


def _evidence(evidence_id: str, authority_level: AuthorityLevel, text: str) -> Evidence:
    """Create evidence for service tests."""

    return Evidence(
        evidence_id=evidence_id,
        text=text,
        citation=Citation(
            citation_text=evidence_id,
            canonical_id=evidence_id,
            authority_level=authority_level,
        ),
        provenance=Provenance(source_id=evidence_id, source_path=f"_fixture/{evidence_id}.json"),
        confidence=0.9,
        authority_level=authority_level,
        assembled=True,
        is_candidate=False,
    )


def _assert_no_direct_model_sdk_calls() -> None:
    """Confirm orchestration code has no direct model SDK calls outside the router."""

    root = Path(__file__).parents[1]
    forbidden = ("openai", "anthropic", "responses.create", "chat.completions", "messages.create")
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "model_router.py" or "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8").casefold()
        if any(term in text for term in forbidden):
            offenders.append(path.as_posix())
    assert offenders == []
