"""Provider-neutral LLM extraction prompt contracts.

This module builds the five Layer 3 prompts from the system design and invokes
only injected clients. It intentionally contains no live OpenAI or Anthropic SDK
calls; provider adapters can implement the ``LLMClient`` protocol later.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

GEODE_CONSTITUTION = """
PRINCIPLE 1 - SOURCE FIDELITY
Every claim in the extraction must be traceable to a specific passage in the
source document. If it cannot be traced, it must be removed. No inference,
assumption, or general knowledge.

PRINCIPLE 2 - COMPLETENESS OVER BREVITY
It is better to include a requirement that seems minor than to omit one that
could matter. Every obligation, prohibition, exception, deadline, and reporting
requirement must be captured.

PRINCIPLE 3 - EXCEPTION PRESERVATION
Exceptions and exemptions are as important as obligations. If a rule says
"except as provided in (2)(c)", that exception must be explicitly captured and
linked.

PRINCIPLE 4 - CITATION COMPLETENESS
Every statutory citation (C.R.S.), regulatory reference (CCR), and federal
reference (CFR/USC) must be captured in canonical form, even if only mentioned
in passing. Implicit references count and must be resolved.

PRINCIPLE 5 - NO INTERPRETATION
The extraction must reflect what the law says, not what it might mean. Do not
add implications, inferences, or interpretive commentary. If the statute is
ambiguous, preserve the ambiguity.

PRINCIPLE 6 - ATOMICITY
Each rule unit must contain exactly one obligation, prohibition, or permission.
If a section contains three requirements, it must produce three rule units.

PRINCIPLE 7 - TEMPORAL PRECISION
All dates, deadlines, and effective dates must be captured exactly as stated.
Do not convert relative dates to absolute dates.

PRINCIPLE 8 - ENTITY CLARITY
The regulated entity must be stated specifically enough that a reader can
determine whether they are covered. Use the source document's actual language.
""".strip()

TASK_INSTRUCTIONS: dict[str, str] = {
    "A": (
        "Task A - Structure Verification: Verify part/section/subsection "
        "hierarchy from regex parse. Return corrected structure JSON with "
        "correction notes."
    ),
    "B": (
        "Task B - Deep Citation Extraction: Find all citations regex missed: "
        "implicit refs, shorthand, federal refs. Return canonical_form, "
        "as_written, location, found_by."
    ),
    "C": (
        "Task C - Rule Unit Decomposition: Decompose into atomic rule units. "
        "Each = ONE obligation/prohibition/etc. Return rule_id, rule_type, "
        "regulated_entity, action_required, conditions, exceptions, "
        "enabling_statute, temporal, penalties, plain_english_summary. "
        "Follow Geode Constitution P1-P8."
    ),
    "D": (
        "Task D - Ontology Tagging: Assign 2-5 subject_tags, 1-3 industry_tags, "
        "0-5 compliance_keywords from ONTOLOGY.json ONLY. No invented tags."
    ),
    "E": (
        "Task E - Summary Generation: 2-3 sentences: what it requires, who it "
        "applies to, key obligations. Business owner must understand. 50-200 "
        "tokens. No info beyond source."
    ),
}


class LLMTaskPrompt(BaseModel):
    """Complete prompt payload sent to an injected LLM client."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^[A-E]$")
    task_name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    output_contract: str = Field(min_length=1)


@runtime_checkable
class LLMClient(Protocol):
    """Minimal client protocol for offline tests and future provider adapters."""

    provider: str
    model_name: str

    def complete(self, prompt: LLMTaskPrompt) -> Any:
        """Return a task-specific response without mutating source data."""


@dataclass(frozen=True)
class ModelSpec:
    """Parsed model identifier for future provider adapters."""

    provider: str
    model_name: str


class LLMProviderUnavailable(RuntimeError):
    """Raised when a live provider string is supplied without an adapter."""


def parse_model_spec(model: str) -> ModelSpec:
    """Parse a provider-qualified model string.

    Accepted forms are ``openai:gpt-4o`` and ``anthropic:claude-...``. Bare
    provider names are allowed and use ``default`` as the model name.
    """

    if ":" in model:
        provider, model_name = model.split(":", 1)
    else:
        provider, model_name = model, "default"
    provider = provider.strip().lower()
    model_name = model_name.strip()
    if provider not in {"openai", "anthropic"}:
        raise ValueError("model provider must be 'openai' or 'anthropic'")
    if not model_name:
        raise ValueError("model name is required")
    return ModelSpec(provider=provider, model_name=model_name)


def build_task_prompt(
    task_id: str,
    markdown: str,
    context: object,
    model: LLMClient | str,
    output_contract: str,
) -> LLMTaskPrompt:
    """Build one B9 Layer 3 prompt with the Geode Constitution embedded."""

    instruction = TASK_INSTRUCTIONS[task_id]
    provider, model_name = _model_identity(model)
    system_prompt = (
        "You are a Project Geode legal extraction agent. Follow the Geode "
        "Constitution exactly.\n\n"
        f"{GEODE_CONSTITUTION}\n\n"
        f"{instruction}"
    )
    context_json = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    user_prompt = (
        f"{instruction}\n\n"
        "Source Markdown:\n"
        f"{markdown}\n\n"
        "Deterministic context:\n"
        f"{context_json}\n\n"
        "Return only data matching the requested output contract."
    )
    return LLMTaskPrompt(
        task_id=task_id,
        task_name=instruction.split(":", 1)[0],
        provider=provider,
        model_name=model_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_contract=output_contract,
    )


def extract_structure(markdown: str, regex_structure: object, model: LLMClient | str) -> dict:
    """Run Task A: structure verification."""

    response = _invoke_task(
        task_id="A",
        markdown=markdown,
        context={"regex_structure": regex_structure},
        model=model,
        output_contract="dict with corrected_structure and correction_notes",
    )
    return _expect_dict(response, "structure extraction")


def extract_citations(markdown: str, regex_citations: object, model: LLMClient | str) -> list:
    """Run Task B: deep citation extraction."""

    response = _invoke_task(
        task_id="B",
        markdown=markdown,
        context={"regex_citations": regex_citations},
        model=model,
        output_contract="list of citation objects",
    )
    return _expect_list(response, "citation extraction")


def decompose_rule_units(markdown: str, ontology: object, model: LLMClient | str) -> list:
    """Run Task C: atomic rule unit decomposition."""

    response = _invoke_task(
        task_id="C",
        markdown=markdown,
        context={"ontology": ontology},
        model=model,
        output_contract="list of atomic rule unit objects",
    )
    return _expect_list(response, "rule unit decomposition")


def assign_tags(text: str, summary: str, ontology: object, model: LLMClient | str) -> dict:
    """Run Task D: controlled-vocabulary ontology tagging."""

    response = _invoke_task(
        task_id="D",
        markdown=text,
        context={"summary": summary, "ontology": ontology},
        model=model,
        output_contract="dict with subject_tags, industry_tags, compliance_keywords",
    )
    return _expect_dict(response, "ontology tagging")


def generate_summary(markdown: str, model: LLMClient | str) -> str:
    """Run Task E: grounded 2-3 sentence summary generation."""

    response = _invoke_task(
        task_id="E",
        markdown=markdown,
        context={},
        model=model,
        output_contract="string summary, 50-200 tokens, no unsupported claims",
    )
    if not isinstance(response, str):
        raise TypeError("summary generation response must be a string")
    return response


def _invoke_task(
    task_id: str,
    markdown: str,
    context: object,
    model: LLMClient | str,
    output_contract: str,
) -> Any:
    """Build, log, and dispatch one prompt to an injected client."""

    prompt = build_task_prompt(task_id, markdown, context, model, output_contract)
    _log_payload("llm_prompt_sent", prompt.model_dump())
    if isinstance(model, str):
        spec = parse_model_spec(model)
        raise LLMProviderUnavailable(
            f"{spec.provider}:{spec.model_name} requires an injected provider adapter"
        )
    response = model.complete(prompt)
    _log_payload("llm_response_received", response)
    return response


def _model_identity(model: LLMClient | str) -> tuple[str, str]:
    """Return provider and model names for prompts and logs."""

    if isinstance(model, str):
        spec = parse_model_spec(model)
        return spec.provider, spec.model_name
    return model.provider, model.model_name


def _expect_dict(response: object, context: str) -> dict:
    """Require a dict response for dict-producing tasks."""

    if not isinstance(response, dict):
        raise TypeError(f"{context} response must be a dict")
    return response


def _expect_list(response: object, context: str) -> list:
    """Require a list response for list-producing tasks."""

    if not isinstance(response, list):
        raise TypeError(f"{context} response must be a list")
    return response


def _log_payload(event: str, payload: object) -> None:
    """Log prompt/response payloads with stable hashes and full debug payloads."""

    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    logger.info("%s sha256=%s", event, digest)
    logger.debug("%s payload=%s", event, payload_json)
