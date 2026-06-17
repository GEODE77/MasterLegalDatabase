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
    DISABLED_MESSAGE,
    GEODE_CONSTITUTION,
    TASK_INSTRUCTIONS,
    LLMTaskPrompt,
    assign_tags,
    build_task_prompt,
    decompose_rule_units,
    extract_citations,
    extract_structure,
    generate_summary,
    parse_model_spec,
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


def test_llm_constants_remain_importable() -> None:
    """Legacy LLM constants remain importable for archived design references."""

    assert "PRINCIPLE 1 - SOURCE FIDELITY" in GEODE_CONSTITUTION
    assert set(TASK_INSTRUCTIONS) == {"A", "B", "C", "D", "E"}


def test_llm_extractor_functions_are_disabled() -> None:
    """Every LLM extractor entry point raises the deterministic-only error."""

    client = FakeClient("openai", "fake-openai", {})
    disabled_calls = [
        lambda: parse_model_spec("openai:gpt-4o"),
        lambda: build_task_prompt("A", "source", {}, client, "contract"),
        lambda: extract_structure("text", {}, client),
        lambda: extract_citations("text", [], client),
        lambda: decompose_rule_units("text", {}, client),
        lambda: assign_tags("text", "summary", {}, client),
        lambda: generate_summary("text", client),
        lambda: generate_summary("text", "openai:gpt-4o"),
    ]

    for call in disabled_calls:
        with pytest.raises(NotImplementedError, match=DISABLED_MESSAGE):
            call()


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


def test_run_ensemble_extraction_is_disabled() -> None:
    """Full LLM ensemble extraction is disabled in deterministic-only Geode."""

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
    with pytest.raises(NotImplementedError, match=DISABLED_MESSAGE):
        run_ensemble_extraction(
            "The commission must issue permits. Owners must submit reports.",
            {"structure": {}, "citations": [], "ontology": {}},
            models=models,
        )
    assert all(len(model.prompts) == 0 for model in models)
