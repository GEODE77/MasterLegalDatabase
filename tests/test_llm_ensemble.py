"""Layer 3 prompt and Layer 4 ensemble tests."""

from __future__ import annotations

import pytest

from geode.extractors.ensemble import (
    compare_exact_fields,
    compare_list_fields,
    compare_semantic_fields,
    compare_text_fields,
    run_ensemble_extraction,
)
from geode.extractors.llm_extractor import (
    GEODE_CONSTITUTION,
    TASK_INSTRUCTIONS,
    LLMProviderUnavailable,
    LLMTaskPrompt,
    build_task_prompt,
    extract_citations,
    extract_structure,
    generate_summary,
)


class FakeClient:
    """Deterministic fake LLM client for offline tests."""

    def __init__(self, provider: str, model_name: str, responses: dict[str, object]) -> None:
        """Create a fake client with task-keyed responses."""

        self.provider = provider
        self.model_name = model_name
        self.responses = responses
        self.prompts: list[LLMTaskPrompt] = []

    def complete(self, prompt: LLMTaskPrompt) -> object:
        """Capture prompt payloads and return the configured fake response."""

        self.prompts.append(prompt)
        return self.responses[prompt.task_id]


def test_all_task_prompts_embed_constitution() -> None:
    """Every Layer 3 prompt includes the Geode Constitution and task text."""

    client = FakeClient("openai", "fake-openai", {})
    for task_id, task_text in TASK_INSTRUCTIONS.items():
        prompt = build_task_prompt(task_id, "source", {}, client, "contract")
        assert GEODE_CONSTITUTION in prompt.system_prompt
        assert "PRINCIPLE 1 - SOURCE FIDELITY" in prompt.system_prompt
        assert "PRINCIPLE 8 - ENTITY CLARITY" in prompt.system_prompt
        assert task_text in prompt.system_prompt


def test_llm_task_functions_use_injected_client_only() -> None:
    """Task wrappers dispatch to fake clients and return typed task outputs."""

    client = FakeClient(
        "anthropic",
        "fake-claude",
        {
            "A": {"corrected_structure": [], "correction_notes": []},
            "B": [{"canonical_form": "CRS-25-7-109"}],
            "E": "The commission must issue permits.",
        },
    )
    assert extract_structure("text", {}, client)["corrected_structure"] == []
    assert extract_citations("text", [], client)[0]["canonical_form"] == "CRS-25-7-109"
    assert generate_summary("text", client) == "The commission must issue permits."
    assert [prompt.task_id for prompt in client.prompts] == ["A", "B", "E"]


def test_provider_string_requires_adapter() -> None:
    """Provider strings are parsed, but no live SDK call is attempted."""

    with pytest.raises(LLMProviderUnavailable):
        generate_summary("source text", "openai:gpt-4o")


def test_exact_field_voting_boundaries() -> None:
    """Exact voting accepts agreement/regex matches and quarantines all-different."""

    assert compare_exact_fields("x", "x", "y").confidence == 0.99
    regex_match = compare_exact_fields("x", "z", "x")
    assert regex_match.status == "ACCEPT"
    assert regex_match.confidence == 0.90
    assert compare_exact_fields("x", "y", "z").status == "QUARANTINE"


def test_semantic_field_voting_boundaries() -> None:
    """Semantic voting returns accept, flag, and quarantine ranges."""

    assert compare_semantic_fields("permit required", "permit required").status == "ACCEPT"
    assert compare_semantic_fields("permit required", "permit required soon").status == "FLAG"
    assert compare_semantic_fields("permit required", "zoning appeal").status == "QUARANTINE"


def test_list_field_voting_uses_verified_union() -> None:
    """List voting accepts exact matches and verifies partial differences."""

    assert compare_list_fields(["a"], ["a"]).status == "ACCEPT"
    partial = compare_list_fields(["a", "b"], ["b", "c"])
    assert partial.status == "VERIFY"
    assert partial.accepted_value == ["a", "b", "c"]


def test_text_field_grounding_rejects_unsupported_claims() -> None:
    """Text voting accepts grounded summaries and rejects ungrounded claims."""

    source = "The commission must issue permits. Owners must submit reports."
    grounded = compare_text_fields(
        "The commission must issue permits.",
        "Owners must submit reports.",
        source,
    )
    assert grounded.status == "ACCEPT"
    rejected = compare_text_fields(
        "The agency funds school buses.",
        "The rule creates criminal immunity.",
        source,
    )
    assert rejected.status == "REJECT"


def test_run_ensemble_extraction_with_fake_models() -> None:
    """Full ensemble run executes all five tasks twice without API keys."""

    responses = {
        "A": {"corrected_structure": [{"section": "1"}], "correction_notes": []},
        "B": [{"canonical_form": "CRS-25-7-109", "found_by": "llm"}],
        "C": [{"rule_id": "r1", "rule_type": "obligation"}],
        "D": {
            "subject_tags": ["air_quality"],
            "industry_tags": ["manufacturing"],
            "compliance_keywords": ["permit_required"],
        },
        "E": "The commission must issue permits. Owners must submit reports.",
    }
    models = [
        FakeClient("openai", "fake-openai", responses),
        FakeClient("anthropic", "fake-claude", responses),
    ]
    result = run_ensemble_extraction(
        "The commission must issue permits. Owners must submit reports.",
        {"structure": {}, "citations": [], "ontology": {}},
        models=models,
    )
    assert result.route_hint == "AUTO_ACCEPT"
    assert result.merged_output["summary"].startswith("The commission")
    assert all(len(model.prompts) == 5 for model in models)
