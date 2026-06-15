"""Layer 4 ensemble voting for offline extraction results."""

from __future__ import annotations

import asyncio
import json
import re
from difflib import SequenceMatcher
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from geode.extractors.llm_extractor import (
    LLMClient,
    LLMTaskPrompt,
    assign_tags,
    decompose_rule_units,
    extract_citations,
    extract_structure,
    generate_summary,
)

FieldStatus = Literal["ACCEPT", "FLAG", "VERIFY", "QUARANTINE", "REJECT"]
RouteHint = Literal["AUTO_ACCEPT", "FLAG_ACCEPT", "QUARANTINE", "REJECT"]


class FieldResult(BaseModel):
    """Field-level ensemble decision."""

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(default="field", min_length=1)
    status: FieldStatus
    accepted_value: Any = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    candidates: list[Any] = Field(default_factory=list)


class EnsembleModelOutput(BaseModel):
    """All five Layer 3 task outputs from one model."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    structure: dict
    citations: list
    rule_units: list
    tags: dict
    summary: str


class EnsembleResult(BaseModel):
    """Combined two-model ensemble result."""

    model_config = ConfigDict(extra="forbid")

    model_outputs: list[EnsembleModelOutput]
    field_results: list[FieldResult]
    merged_output: dict[str, Any]
    route_hint: RouteHint
    confidence: float = Field(ge=0.0, le=1.0)


class DeterministicLLMClient:
    """Offline deterministic client used when no provider adapter is supplied."""

    def __init__(self, provider: str, model_name: str) -> None:
        """Create a deterministic model identity."""

        self.provider = provider
        self.model_name = model_name

    def complete(self, prompt: LLMTaskPrompt) -> Any:
        """Return stable task output from prompt context without network calls."""

        context = _prompt_context(prompt.user_prompt)
        if prompt.task_id == "A":
            return {
                "corrected_structure": context.get("regex_structure", []),
                "correction_notes": [],
            }
        if prompt.task_id == "B":
            return context.get("regex_citations", [])
        if prompt.task_id == "C":
            return []
        if prompt.task_id == "D":
            return {
                "subject_tags": [],
                "industry_tags": [],
                "compliance_keywords": [],
            }
        return _summarize_prompt_source(prompt.user_prompt)


def compare_exact_fields(
    field_a: Any,
    field_b: Any,
    field_regex: Any,
    field_name: str = "field",
) -> FieldResult:
    """Compare exact fields using B9 Layer 4 thresholds."""

    candidates = [field_a, field_b, field_regex]
    if field_a == field_b and field_a is not None:
        return FieldResult(
            field_name=field_name,
            status="ACCEPT",
            accepted_value=field_a,
            confidence=0.99,
            reason="both models agree",
            candidates=candidates,
        )
    if field_a == field_regex and field_a is not None:
        return FieldResult(
            field_name=field_name,
            status="ACCEPT",
            accepted_value=field_a,
            confidence=0.90,
            reason="model A matches regex",
            candidates=candidates,
        )
    if field_b == field_regex and field_b is not None:
        return FieldResult(
            field_name=field_name,
            status="ACCEPT",
            accepted_value=field_b,
            confidence=0.90,
            reason="model B matches regex",
            candidates=candidates,
        )
    return FieldResult(
        field_name=field_name,
        status="QUARANTINE",
        confidence=0.0,
        reason="all exact-field candidates differ",
        candidates=candidates,
    )


def compare_semantic_fields(
    field_a: Any,
    field_b: Any,
    field_name: str = "field",
) -> FieldResult:
    """Compare semantic fields with deterministic string similarity."""

    similarity = _similarity(field_a, field_b)
    accepted = _prefer_informative(field_a, field_b)
    if similarity > 0.90:
        return FieldResult(
            field_name=field_name,
            status="ACCEPT",
            accepted_value=accepted,
            confidence=similarity,
            reason="semantic similarity > 0.90",
            candidates=[field_a, field_b],
        )
    if similarity >= 0.70:
        return FieldResult(
            field_name=field_name,
            status="FLAG",
            accepted_value=accepted,
            confidence=similarity,
            reason="semantic similarity from 0.70 to 0.90",
            candidates=[field_a, field_b],
        )
    return FieldResult(
        field_name=field_name,
        status="QUARANTINE",
        confidence=similarity,
        reason="semantic similarity < 0.70",
        candidates=[field_a, field_b],
    )


def compare_list_fields(
    list_a: Sequence[Any],
    list_b: Sequence[Any],
    field_name: str = "field",
) -> FieldResult:
    """Compare list fields with intersection and verified-union routing."""

    map_a = {_stable_key(item): item for item in list_a}
    map_b = {_stable_key(item): item for item in list_b}
    keys_a = set(map_a)
    keys_b = set(map_b)
    union_keys = keys_a | keys_b
    if not union_keys:
        return FieldResult(
            field_name=field_name,
            status="ACCEPT",
            accepted_value=[],
            confidence=1.0,
            reason="both models returned an empty list",
            candidates=[list(list_a), list(list_b)],
        )
    intersection = keys_a & keys_b
    confidence = len(intersection) / len(union_keys)
    if keys_a == keys_b:
        return FieldResult(
            field_name=field_name,
            status="ACCEPT",
            accepted_value=[map_a[key] for key in sorted(keys_a)],
            confidence=0.99,
            reason="list fields agree exactly",
            candidates=[list(list_a), list(list_b)],
        )
    union_map = {**map_a, **map_b}
    return FieldResult(
        field_name=field_name,
        status="VERIFY",
        accepted_value=[union_map[key] for key in sorted(union_keys)],
        confidence=confidence,
        reason="list differences require verification; accepted value is union",
        candidates=[list(list_a), list(list_b)],
    )


def compare_text_fields(text_a: str, text_b: str, source: str) -> FieldResult:
    """Compare summaries and reject ungrounded claims."""

    grounded_a = _is_grounded(text_a, source)
    grounded_b = _is_grounded(text_b, source)
    if grounded_a and grounded_b:
        accepted = _choose_better_text(text_a, text_b, source)
        return FieldResult(
            field_name="summary",
            status="ACCEPT",
            accepted_value=accepted,
            confidence=0.90,
            reason="both text fields are grounded in source",
            candidates=[text_a, text_b],
        )
    if grounded_a:
        return FieldResult(
            field_name="summary",
            status="ACCEPT",
            accepted_value=text_a,
            confidence=0.80,
            reason="only model A text is grounded in source",
            candidates=[text_a, text_b],
        )
    if grounded_b:
        return FieldResult(
            field_name="summary",
            status="ACCEPT",
            accepted_value=text_b,
            confidence=0.80,
            reason="only model B text is grounded in source",
            candidates=[text_a, text_b],
        )
    return FieldResult(
        field_name="summary",
        status="REJECT",
        confidence=0.0,
        reason="neither text field is grounded in source",
        candidates=[text_a, text_b],
    )


async def run_ensemble_extraction_async(
    markdown: str,
    regex_output: dict[str, Any],
    models: Sequence[LLMClient] | None = None,
) -> EnsembleResult:
    """Run Layer 3 tasks for two models and combine them with Layer 4 voting."""

    chosen_models = list(models or _default_models())
    if len(chosen_models) != 2:
        raise ValueError("ensemble extraction requires exactly two models")
    outputs = await asyncio.gather(
        *(_run_model_tasks(markdown, regex_output, model) for model in chosen_models)
    )
    field_results = _compare_outputs(outputs[0], outputs[1], markdown, regex_output)
    merged_output = {result.field_name: result.accepted_value for result in field_results}
    confidence = _overall_confidence(field_results)
    return EnsembleResult(
        model_outputs=list(outputs),
        field_results=field_results,
        merged_output=merged_output,
        route_hint=_route_from_results(field_results),
        confidence=confidence,
    )


def run_ensemble_extraction(
    markdown: str,
    regex_output: dict[str, Any],
    models: Sequence[LLMClient] | None = None,
) -> EnsembleResult:
    """Synchronous wrapper for the async-capable ensemble pipeline."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_ensemble_extraction_async(markdown, regex_output, models))
    raise RuntimeError("use run_ensemble_extraction_async inside an active event loop")


async def _run_model_tasks(
    markdown: str,
    regex_output: dict[str, Any],
    model: LLMClient,
) -> EnsembleModelOutput:
    """Execute all five Layer 3 tasks for one injected model."""

    structure, citations, rule_units, summary = await asyncio.gather(
        asyncio.to_thread(
            extract_structure,
            markdown,
            regex_output.get("structure", {}),
            model,
        ),
        asyncio.to_thread(
            extract_citations,
            markdown,
            regex_output.get("citations", []),
            model,
        ),
        asyncio.to_thread(
            decompose_rule_units,
            markdown,
            regex_output.get("ontology", {}),
            model,
        ),
        asyncio.to_thread(generate_summary, markdown, model),
    )
    tags = await asyncio.to_thread(
        assign_tags,
        markdown,
        summary,
        regex_output.get("ontology", {}),
        model,
    )
    return EnsembleModelOutput(
        provider=model.provider,
        model_name=model.model_name,
        structure=structure,
        citations=citations,
        rule_units=rule_units,
        tags=tags,
        summary=summary,
    )


def _compare_outputs(
    output_a: EnsembleModelOutput,
    output_b: EnsembleModelOutput,
    markdown: str,
    regex_output: dict[str, Any],
) -> list[FieldResult]:
    """Compare all required ensemble fields."""

    results = [
        compare_semantic_fields(output_a.structure, output_b.structure, "structure"),
        compare_list_fields(output_a.citations, output_b.citations, "citations"),
        compare_list_fields(output_a.rule_units, output_b.rule_units, "rule_units"),
        compare_list_fields(
            output_a.tags.get("subject_tags", []),
            output_b.tags.get("subject_tags", []),
            "subject_tags",
        ),
        compare_list_fields(
            output_a.tags.get("industry_tags", []),
            output_b.tags.get("industry_tags", []),
            "industry_tags",
        ),
        compare_list_fields(
            output_a.tags.get("compliance_keywords", []),
            output_b.tags.get("compliance_keywords", []),
            "compliance_keywords",
        ),
        compare_text_fields(output_a.summary, output_b.summary, markdown),
    ]
    exact_fields = regex_output.get("exact_fields", {})
    for field_name, regex_value in exact_fields.items():
        results.append(
            compare_exact_fields(
                _lookup_output_field(output_a, field_name),
                _lookup_output_field(output_b, field_name),
                regex_value,
                field_name,
            )
        )
    return results


def _default_models() -> tuple[DeterministicLLMClient, DeterministicLLMClient]:
    """Return two offline model identities for no-key test execution."""

    return (
        DeterministicLLMClient("openai", "gpt-4o-offline"),
        DeterministicLLMClient("anthropic", "claude-offline"),
    )


def _route_from_results(results: Sequence[FieldResult]) -> RouteHint:
    """Map field-level decisions to pipeline route hints."""

    statuses = {result.status for result in results}
    if "REJECT" in statuses:
        return "REJECT"
    if "QUARANTINE" in statuses:
        return "QUARANTINE"
    if statuses & {"FLAG", "VERIFY"}:
        return "FLAG_ACCEPT"
    return "AUTO_ACCEPT"


def _overall_confidence(results: Sequence[FieldResult]) -> float:
    """Average field confidences for a simple ensemble-level score."""

    if not results:
        return 0.0
    return sum(result.confidence for result in results) / len(results)


def _lookup_output_field(output: EnsembleModelOutput, field_name: str) -> Any:
    """Look up a field from the common output locations."""

    if field_name in output.structure:
        return output.structure[field_name]
    if field_name in output.tags:
        return output.tags[field_name]
    return getattr(output, field_name, None)


def _similarity(field_a: Any, field_b: Any) -> float:
    """Compute deterministic semantic similarity from normalized JSON strings."""

    normalized_a = _normalize_for_compare(field_a)
    normalized_b = _normalize_for_compare(field_b)
    if not normalized_a and not normalized_b:
        return 1.0
    return SequenceMatcher(None, normalized_a, normalized_b).ratio()


def _normalize_for_compare(value: Any) -> str:
    """Normalize an arbitrary value for deterministic comparison."""

    if isinstance(value, str):
        raw = value
    else:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return re.sub(r"\s+", " ", raw.casefold()).strip()


def _stable_key(value: Any) -> str:
    """Return a stable key for list voting."""

    return _normalize_for_compare(value)


def _prefer_informative(field_a: Any, field_b: Any) -> Any:
    """Prefer the non-empty candidate with more normalized content."""

    if len(_normalize_for_compare(field_b)) > len(_normalize_for_compare(field_a)):
        return field_b
    return field_a


def _is_grounded(text: str, source: str) -> bool:
    """Return whether a text field is sufficiently supported by source text."""

    normalized_text = _normalize_plain_text(text)
    normalized_source = _normalize_plain_text(source)
    if not normalized_text or not normalized_source:
        return False
    if normalized_text in normalized_source:
        return True
    text_tokens = set(_meaningful_tokens(normalized_text))
    source_tokens = set(_meaningful_tokens(normalized_source))
    if not text_tokens:
        return False
    return len(text_tokens & source_tokens) / len(text_tokens) >= 0.70


def _choose_better_text(text_a: str, text_b: str, source: str) -> str:
    """Choose the grounded text with better source-token coverage."""

    coverage_a = _grounding_coverage(text_a, source)
    coverage_b = _grounding_coverage(text_b, source)
    if coverage_b > coverage_a:
        return text_b
    return text_a


def _grounding_coverage(text: str, source: str) -> float:
    """Compute a simple source-token coverage score."""

    text_tokens = set(_meaningful_tokens(_normalize_plain_text(text)))
    source_tokens = set(_meaningful_tokens(_normalize_plain_text(source)))
    if not text_tokens:
        return 0.0
    return len(text_tokens & source_tokens) / len(text_tokens)


def _meaningful_tokens(text: str) -> list[str]:
    """Extract comparable tokens, dropping very small function words."""

    return [token for token in re.findall(r"[a-z0-9]+", text) if len(token) > 3]


def _normalize_plain_text(text: str) -> str:
    """Normalize natural-language text for grounding checks."""

    return re.sub(r"\s+", " ", text.casefold()).strip()


def _prompt_context(user_prompt: str) -> dict[str, Any]:
    """Extract deterministic context JSON from a generated prompt."""

    marker = "Deterministic context:\n"
    if marker not in user_prompt:
        return {}
    after = user_prompt.split(marker, 1)[1]
    context_json = after.split("\n\nReturn only", 1)[0]
    try:
        decoded = json.loads(context_json)
    except json.JSONDecodeError:
        return {}
    if isinstance(decoded, dict):
        return decoded
    return {}


def _summarize_prompt_source(user_prompt: str) -> str:
    """Create a small deterministic summary from the source markdown."""

    marker = "Source Markdown:\n"
    if marker not in user_prompt:
        return ""
    source = user_prompt.split(marker, 1)[1].split("\n\nDeterministic context:", 1)[0]
    sentences = re.split(r"(?<=[.!?])\s+", source.strip())
    selected = " ".join(sentence for sentence in sentences[:3] if sentence)
    return selected[:1000]
