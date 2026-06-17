"""Disabled LLM extraction API for deterministic Project Geode builds.

Project Geode no longer uses LLMs to build corpus records. The symbols in this
module remain only so older imports fail explicitly instead of silently running
provider-like behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

DISABLED_MESSAGE = "LLM extraction disabled — Geode uses deterministic extraction only"

GEODE_CONSTITUTION = """
PRINCIPLE 1 - SOURCE FIDELITY
Every claim in the extraction must be traceable to source text.

PRINCIPLE 2 - COMPLETENESS OVER BREVITY
Every obligation, prohibition, exception, deadline, and reporting requirement
must be captured by deterministic extraction.

PRINCIPLE 3 - EXCEPTION PRESERVATION
Exceptions and exemptions must be explicitly preserved.

PRINCIPLE 4 - CITATION COMPLETENESS
Statutory, regulatory, and federal citations must be captured in canonical form.

PRINCIPLE 5 - NO INTERPRETATION
Extraction must reflect source text rather than inferred meaning.

PRINCIPLE 6 - ATOMICITY
Rule units must be decomposed deterministically.

PRINCIPLE 7 - TEMPORAL PRECISION
Dates and deadlines must be captured exactly as stated.

PRINCIPLE 8 - ENTITY CLARITY
Regulated entities must be stated from source language.
""".strip()

TASK_INSTRUCTIONS: dict[str, str] = {
    "A": "Task A - Structure Verification disabled.",
    "B": "Task B - Deep Citation Extraction disabled.",
    "C": "Task C - Rule Unit Decomposition disabled.",
    "D": "Task D - Ontology Tagging disabled.",
    "E": "Task E - Summary Generation disabled.",
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
    """Minimal client protocol retained for backward-compatible imports."""

    provider: str
    model_name: str

    def complete(self, prompt: LLMTaskPrompt) -> Any:
        """Return a task-specific response without mutating source data."""

        raise NotImplementedError(DISABLED_MESSAGE)


@dataclass(frozen=True)
class ModelSpec:
    """Parsed model identifier for legacy provider adapter imports."""

    provider: str
    model_name: str


class LLMProviderUnavailable(RuntimeError):
    """Legacy exception retained for backward-compatible imports."""


def parse_model_spec(model: str) -> ModelSpec:
    """Parse a provider-qualified model string.

    Accepted forms are ``openai:gpt-4o`` and ``anthropic:claude-...``. Bare
    provider names are allowed and use ``default`` as the model name.
    """

    raise NotImplementedError(DISABLED_MESSAGE)


def build_task_prompt(
    task_id: str,
    markdown: str,
    context: object,
    model: LLMClient | str,
    output_contract: str,
) -> LLMTaskPrompt:
    """Build one B9 Layer 3 prompt with the Geode Constitution embedded."""

    raise NotImplementedError(DISABLED_MESSAGE)


def extract_structure(markdown: str, regex_structure: object, model: LLMClient | str) -> dict:
    """Run Task A: structure verification."""

    raise NotImplementedError(DISABLED_MESSAGE)


def extract_citations(markdown: str, regex_citations: object, model: LLMClient | str) -> list:
    """Run Task B: deep citation extraction."""

    raise NotImplementedError(DISABLED_MESSAGE)


def decompose_rule_units(markdown: str, ontology: object, model: LLMClient | str) -> list:
    """Run Task C: atomic rule unit decomposition."""

    raise NotImplementedError(DISABLED_MESSAGE)


def assign_tags(text: str, summary: str, ontology: object, model: LLMClient | str) -> dict:
    """Run Task D: controlled-vocabulary ontology tagging."""

    raise NotImplementedError(DISABLED_MESSAGE)


def generate_summary(markdown: str, model: LLMClient | str) -> str:
    """Run Task E: grounded 2-3 sentence summary generation."""

    raise NotImplementedError(DISABLED_MESSAGE)


def _invoke_task(
    task_id: str,
    markdown: str,
    context: object,
    model: LLMClient | str,
    output_contract: str,
) -> Any:
    """Build, log, and dispatch one prompt to an injected client."""

    raise NotImplementedError(DISABLED_MESSAGE)


def _model_identity(model: LLMClient | str) -> tuple[str, str]:
    """Return provider and model names for prompts and logs."""

    raise NotImplementedError(DISABLED_MESSAGE)


def _expect_dict(response: object, context: str) -> dict:
    """Require a dict response for dict-producing tasks."""

    raise NotImplementedError(DISABLED_MESSAGE)


def _expect_list(response: object, context: str) -> list:
    """Require a list response for list-producing tasks."""

    raise NotImplementedError(DISABLED_MESSAGE)


def _log_payload(event: str, payload: object) -> None:
    """Log prompt/response payloads with stable hashes and full debug payloads."""

    raise NotImplementedError(DISABLED_MESSAGE)
