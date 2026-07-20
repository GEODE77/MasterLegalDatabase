"""Safety tests for context budgeting, retrieval, and prompt caching metadata."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from geode.orchestration.contracts import (
    Answer,
    AuthorityLevel,
    Citation,
    DraftRequest,
    Evidence,
    EvidenceContentType,
    PromptPacket,
    Provenance,
    QueryState,
    Intent,
)
from geode.orchestration.services import (
    ContextBudgetManager,
    ControlledEvidenceRetriever,
    DeterministicModelAdapter,
    EvidenceStore,
    ModelRouter,
    PromptPrefixBuilder,
    ProviderCacheTracker,
    TokenCounter,
)
from geode.orchestration.entrypoint import build_default_pipeline, run_orchestration
from geode.orchestration.evaluation import build_mock_knowledge_backend
from geode.orchestration.stages import GenerateDraftStage


def _evidence(
    evidence_id: str,
    text: str,
    *,
    content_type: EvidenceContentType = EvidenceContentType.LEGAL,
    assembled: bool = True,
    mandatory: bool = True,
) -> Evidence:
    """Build a small source-backed evidence item for safety tests."""

    provenance = Provenance(source_id=f"source-{evidence_id}", source_path=f"{evidence_id}.md")
    citation = Citation(
        citation_text=f"Source {evidence_id}",
        canonical_id=evidence_id,
        authority_level=AuthorityLevel.STATE,
        provenance=provenance,
    )
    return Evidence(
        evidence_id=evidence_id,
        text=text,
        citation=citation,
        provenance=provenance,
        confidence=1.0,
        authority_level=AuthorityLevel.STATE,
        assembled=assembled,
        is_candidate=not assembled,
        content_type=content_type,
        mandatory=mandatory,
        compression_allowed=content_type != EvidenceContentType.LEGAL,
    )


def test_legal_text_is_preserved_and_metadata_is_retrievable(tmp_path) -> None:
    """Budgeting must retain legal wording and store omitted support durably."""

    legal_text = "The permit is required, except when the statutory exemption applies."
    metadata_text = " ".join(["metadata"] * 100)
    legal = _evidence("legal-1", legal_text)
    metadata = _evidence(
        "meta-1",
        metadata_text,
        content_type=EvidenceContentType.METADATA,
        assembled=False,
        mandatory=False,
    )
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    request = DraftRequest(prompt="Answer from the evidence.", evidence=[legal, metadata])

    fitted, report = ContextBudgetManager(
        token_limit=30,
        evidence_store=store,
        corpus_version="corpus-1",
    ).fit(request)

    assert fitted.evidence[0].text == legal_text
    assert legal_text in fitted.evidence[0].text
    assert report.excluded_evidence_ids == ["meta-1"]
    assert len(fitted.retrieval_references) == 1
    reference = fitted.retrieval_references[0]
    recovered = ControlledEvidenceRetriever(store, "corpus-1").retrieve(reference)
    assert recovered.text == metadata_text
    assert len(store.history(reference.reference_id)) == 1


def test_golden_legal_answer_is_unchanged_when_metadata_is_excluded(tmp_path) -> None:
    """Removing support metadata must not change the generated legal answer."""

    legal = _evidence(
        "golden-legal",
        "The permit is required, except when the statutory exemption applies.",
    )
    metadata = _evidence(
        "golden-metadata",
        "supporting metadata " * 80,
        content_type=EvidenceContentType.METADATA,
        assembled=False,
        mandatory=False,
    )
    request = DraftRequest(prompt="Answer the legal question.", evidence=[legal, metadata])
    fitted, _ = ContextBudgetManager(
        token_limit=25,
        evidence_store=EvidenceStore(tmp_path / "golden.sqlite"),
        corpus_version="golden-1",
    ).fit(request)
    router = ModelRouter([DeterministicModelAdapter()])

    baseline = router.generate_draft(
        DraftRequest(prompt=request.prompt, evidence=[legal])
    )
    compressed = router.generate_draft(fitted)

    assert compressed.answer_text == baseline.answer_text
    assert "except when the statutory exemption applies" in compressed.answer_text


def test_controlled_retrieval_rejects_a_different_corpus(tmp_path) -> None:
    """References from an older corpus must not cross into the active corpus."""

    evidence = _evidence("legal-2", "A source-backed legal requirement.")
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    reference = store.put(evidence, "corpus-1")

    with pytest.raises(ValueError, match="active corpus"):
        ControlledEvidenceRetriever(store, "corpus-2").retrieve(reference)


def test_expired_evidence_reference_is_rejected(tmp_path) -> None:
    """Expiration must prevent recovery after the retention window."""

    evidence = _evidence("expired", "A retained legal passage.")
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    reference = store.put(evidence, "corpus-1", retention_seconds=1)
    expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE evidence_store SET expires_at = ? WHERE reference_id = ?",
            (expired_at, reference.reference_id),
        )

    with pytest.raises(ValueError, match="expired"):
        ControlledEvidenceRetriever(store, "corpus-1").retrieve(reference)


def test_evidence_and_append_only_history_survive_restart(tmp_path) -> None:
    """A new store instance must recover evidence and every retrieval event."""

    evidence = _evidence("restart", "A passage that survives a process restart.")
    path = tmp_path / "evidence.sqlite"
    reference = EvidenceStore(path).put(evidence, "corpus-1")
    first_store = EvidenceStore(path)
    first_store.retrieve(reference.reference_id, "corpus-1", query="passage")
    first_store.retrieve(reference.reference_id, "corpus-1", query="restart")

    restarted_store = EvidenceStore(path)
    recovered = restarted_store.retrieve(reference.reference_id, "corpus-1")
    history = restarted_store.history(reference.reference_id)

    assert recovered.text == evidence.text
    assert len(history) == 3
    assert history[0]["query"] == "passage"
    assert history[1]["query"] == "restart"
    assert history[2]["query"] is None


def test_stable_prompt_prefix_is_measured_without_rewriting_prompt() -> None:
    """Stable policy text should hash consistently while request text remains dynamic."""

    builder = PromptPrefixBuilder()
    first = builder.split_rendered(
        "# Packet\n\n## Policies\nUse citations.\n\n## User Intent\nQuestion one."
    )
    second = builder.split_rendered(
        "# Packet\n\n## Policies\nUse citations.\n\n## User Intent\nQuestion two."
    )

    assert first.prefix_hash == second.prefix_hash
    assert first.stable_prefix == second.stable_prefix
    assert first.dynamic_suffix != second.dynamic_suffix


def test_provider_cache_metrics_only_report_measured_events() -> None:
    """Cache savings must be based on recorded provider results, not guesses."""

    tracker = ProviderCacheTracker()
    events = [
        tracker.record(
            provider="generic",
            model="test-model",
            stable_prefix_hash="hash",
            stable_prefix_tokens=100,
            cache_hit=True,
        ),
        tracker.record(
            provider="generic",
            model="test-model",
            stable_prefix_hash="hash",
            stable_prefix_tokens=100,
            cache_hit=False,
        ),
    ]

    metrics = tracker.metrics(events)
    assert metrics.eligible_requests == 2
    assert metrics.hits == 1
    assert metrics.hit_rate_percent == 50.0

    state = QueryState(intent=Intent(raw_query="test"))
    tracker.attach(state, events[0])
    assert state.provider_cache_metrics.hits == 1


def test_routed_cache_measurement_is_attached_to_query_state() -> None:
    """A provider-reported hit must flow into the orchestration audit state."""

    class MeasuredAdapter:
        """Minimal adapter that reports a real cache hit for this test."""

        provider = "measured-provider"
        model = "measured-model"
        estimated_cost = 0.0
        estimated_latency_ms = 1
        last_cache_hit = True
        received_context = None

        def generate(self, request: DraftRequest) -> Answer:
            """Return the same deterministic answer shape as a provider."""

            self.received_context = request.prompt_context
            return Answer(
                answer_text=request.evidence[0].text,
                citations=[request.evidence[0].citation],
                evidence_ids=[request.evidence[0].evidence_id],
                confidence=1.0,
            )

    evidence = _evidence("cache-legal", "A verified legal requirement.")
    state = QueryState(
        intent=Intent(raw_query="What is required?"),
        draft_request=DraftRequest(prompt="## User Intent\nWhat is required?", evidence=[evidence]),
        prompt_packet=PromptPacket(
            rendered_prompt="## User Intent\nWhat is required?",
            evidence_ids=[evidence.evidence_id],
        ),
    )

    adapter = MeasuredAdapter()
    output = GenerateDraftStage(router=ModelRouter([adapter]))(state)

    assert output.provider_cache_metrics.hits == 1
    assert output.provider_cache_metrics.eligible_requests == 1
    assert output.prompt_packet.provider_cache_settings["provider"] == "measured-provider"
    assert adapter.received_context is not None
    assert adapter.received_context.stable_prefix_hash


def test_final_budget_includes_retrieval_instructions(tmp_path) -> None:
    """The reported budget must equal the complete prompt plus kept evidence."""

    evidence = _evidence(
        "budget-metadata",
        "metadata " * 100,
        content_type=EvidenceContentType.METADATA,
        assembled=False,
        mandatory=False,
    )
    request = DraftRequest(prompt="Answer from verified sources.", evidence=[evidence])
    fitted, report = ContextBudgetManager(
        token_limit=100,
        evidence_store=EvidenceStore(tmp_path / "budget.sqlite"),
        corpus_version="budget-1",
    ).fit(request)

    measured_total = TokenCounter().count(fitted.prompt) + sum(
        TokenCounter().count(item.text) for item in fitted.evidence
    )
    assert measured_total == report.estimated_tokens
    assert measured_total <= report.token_limit


def test_production_pipeline_configures_durable_evidence_store(tmp_path) -> None:
    """The public pipeline must construct its budget manager with the configured store."""

    store_path = tmp_path / "production-evidence.sqlite"
    pipeline = build_default_pipeline(
        retrieval_backend=build_mock_knowledge_backend(),
        corpus_version="production-test",
        evidence_store_path=store_path,
    )
    generate_stage = next(stage for stage in pipeline.stages if stage.name == "generate_draft")

    assert generate_stage.budget_manager.evidence_store is not None
    assert generate_stage.budget_manager.evidence_store.path == store_path

    state = run_orchestration(
        "What reporting requirements apply to a facility in Boulder County?",
        retrieval_backend=build_mock_knowledge_backend(),
        corpus_version="production-test",
        evidence_store_path=store_path,
    )
    assert state.context_budget is not None
    assert store_path.exists()


def test_token_counter_reports_a_deterministic_strategy() -> None:
    """Token accounting must identify the tokenizer used for its estimate."""

    counter = TokenCounter()
    assert counter.count("shall, except") > 0
    assert counter.name
