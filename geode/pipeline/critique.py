"""Layer 5 constitutional critique and repair loop."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


class ConstitutionPrinciple(BaseModel):
    """One Geode Constitution extraction principle."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^P[1-8]$")
    name: str = Field(min_length=1)
    text: str = Field(min_length=1)


class JudgeDimension(BaseModel):
    """One constitutional judge dimension."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[MDR]\d+$")
    name: str = Field(min_length=1)
    category: Literal["metadata", "decomposition", "rule_unit"]


class DimensionScore(BaseModel):
    """Score for one constitutional judge dimension."""

    model_config = ConfigDict(extra="forbid")

    dimension_id: str = Field(pattern=r"^[MDR]\d+$")
    name: str = Field(min_length=1)
    score: int = Field(ge=1, le=5)
    notes: str = ""


class ScoreCard(BaseModel):
    """Full 19-dimension constitutional critique scorecard."""

    model_config = ConfigDict(extra="forbid")

    scores: list[DimensionScore]

    @model_validator(mode="after")
    def validate_all_dimensions(self) -> "ScoreCard":
        """Require exactly one score for every judge dimension."""

        ids = [score.dimension_id for score in self.scores]
        duplicates = sorted({dimension_id for dimension_id in ids if ids.count(dimension_id) > 1})
        missing = [dimension.id for dimension in JUDGE_DIMENSIONS if dimension.id not in ids]
        extra = sorted(set(ids) - set(JUDGE_DIMENSION_MAP))
        if duplicates:
            raise ValueError(f"duplicate critique dimensions: {duplicates}")
        if missing:
            raise ValueError(f"missing critique dimensions: {missing}")
        if extra:
            raise ValueError(f"unknown critique dimensions: {extra}")
        return self

    @property
    def failed_dimensions(self) -> list[str]:
        """Return dimensions that failed the pass threshold."""

        failed = []
        for score in self.scores:
            threshold = 5 if score.dimension_id == "R9" else 4
            if score.score < threshold:
                failed.append(score.dimension_id)
        return failed

    @property
    def passes(self) -> bool:
        """Return whether every dimension meets the pass threshold."""

        return not self.failed_dimensions and not self.has_hallucination

    @property
    def has_hallucination(self) -> bool:
        """Return whether R9 requires mandatory rejection."""

        return self.score_for("R9") < 5

    def score_for(self, dimension_id: str) -> int:
        """Return the numeric score for one dimension."""

        for score in self.scores:
            if score.dimension_id == dimension_id:
                return score.score
        raise KeyError(dimension_id)

    def limited_to(self, dimension_ids: list[str]) -> "ScoreCard":
        """Return a scorecard with only selected failed dimensions changed."""

        selected = set(dimension_ids)
        scores = []
        for score in self.scores:
            if score.dimension_id in selected:
                scores.append(score)
            else:
                scores.append(
                    DimensionScore(
                        dimension_id=score.dimension_id,
                        name=score.name,
                        score=5,
                        notes="Not targeted in this repair cycle.",
                    )
                )
        return ScoreCard(scores=scores)


class CritiquePrompt(BaseModel):
    """Prompt payload sent to a critique or repair model."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["critique", "repair"]
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    extraction: dict[str, Any]
    source_markdown: str
    target_dimensions: list[str] = Field(default_factory=list)
    score_card: dict[str, Any] | None = None


class CritiqueResult(BaseModel):
    """Result from the capped constitutional critique loop."""

    model_config = ConfigDict(extra="forbid")

    final_extraction: dict[str, Any]
    score_card: ScoreCard
    iterations: int = Field(ge=0, le=3)
    route: Literal["ACCEPT", "REJECT", "QUARANTINE"]
    repair_history: list[dict[str, Any]] = Field(default_factory=list)


@runtime_checkable
class CritiqueClient(Protocol):
    """Minimal offline critique model protocol."""

    provider: str
    model_name: str

    def complete(self, prompt: CritiquePrompt) -> Any:
        """Return critique scores or repaired extraction data."""


class DeterministicCritiqueClient:
    """Offline no-network critique client for deterministic execution."""

    provider = "offline"
    model_name = "deterministic-critique"

    def complete(self, prompt: CritiquePrompt) -> Any:
        """Score all dimensions as passing unless forced by extraction data."""

        if prompt.kind == "repair":
            repaired = copy.deepcopy(prompt.extraction)
            repaired_dimensions = set(repaired.get("_repaired_dimensions", []))
            repaired_dimensions.update(prompt.target_dimensions)
            repaired["_repaired_dimensions"] = sorted(repaired_dimensions)
            forced_scores = dict(repaired.get("_force_scores", {}))
            for dimension_id in prompt.target_dimensions:
                forced_scores.pop(dimension_id, None)
            if forced_scores:
                repaired["_force_scores"] = forced_scores
            else:
                repaired.pop("_force_scores", None)
            return repaired
        forced = prompt.extraction.get("_force_scores", {})
        scores = {
            dimension.id: int(forced.get(dimension.id, 5))
            for dimension in JUDGE_DIMENSIONS
        }
        return {"scores": scores}


GEODE_CONSTITUTION: tuple[ConstitutionPrinciple, ...] = (
    ConstitutionPrinciple(
        id="P1",
        name="SOURCE FIDELITY",
        text=(
            "Every claim in the extraction must be traceable to a specific passage "
            "in the source document. If it cannot be traced, it must be removed. "
            "No inference, assumption, or general knowledge."
        ),
    ),
    ConstitutionPrinciple(
        id="P2",
        name="COMPLETENESS OVER BREVITY",
        text=(
            "It is better to include a requirement that seems minor than to omit "
            "one that could matter. Every obligation, prohibition, exception, "
            "deadline, and reporting requirement must be captured."
        ),
    ),
    ConstitutionPrinciple(
        id="P3",
        name="EXCEPTION PRESERVATION",
        text=(
            "Exceptions and exemptions are as important as obligations. If a rule "
            "says \"except as provided in (2)(c)\", that exception must be "
            "explicitly captured and linked."
        ),
    ),
    ConstitutionPrinciple(
        id="P4",
        name="CITATION COMPLETENESS",
        text=(
            "Every statutory citation (C.R.S.), regulatory reference (CCR), and "
            "federal reference (CFR/USC) must be captured in canonical form, even "
            "if only mentioned in passing. Implicit references count and must be "
            "resolved."
        ),
    ),
    ConstitutionPrinciple(
        id="P5",
        name="NO INTERPRETATION",
        text=(
            "The extraction must reflect what the law says, not what it might "
            "mean. Do not add implications, inferences, or interpretive "
            "commentary. If the statute is ambiguous, preserve the ambiguity."
        ),
    ),
    ConstitutionPrinciple(
        id="P6",
        name="ATOMICITY",
        text=(
            "Each rule unit must contain exactly one obligation, prohibition, or "
            "permission. If a section contains three requirements, it must produce "
            "three rule units."
        ),
    ),
    ConstitutionPrinciple(
        id="P7",
        name="TEMPORAL PRECISION",
        text=(
            "All dates, deadlines, and effective dates must be captured exactly as "
            "stated. Do not convert relative dates to absolute dates."
        ),
    ),
    ConstitutionPrinciple(
        id="P8",
        name="ENTITY CLARITY",
        text=(
            "The regulated entity must be stated specifically enough that a reader "
            "can determine whether they are covered. Use the source document's "
            "actual language."
        ),
    ),
)

JUDGE_DIMENSIONS: tuple[JudgeDimension, ...] = (
    JudgeDimension(id="M1", name="Source fidelity", category="metadata"),
    JudgeDimension(id="M2", name="Citation accuracy", category="metadata"),
    JudgeDimension(id="M3", name="Agency attribution", category="metadata"),
    JudgeDimension(id="M4", name="Temporal accuracy", category="metadata"),
    JudgeDimension(id="M5", name="Cross-ref completeness", category="metadata"),
    JudgeDimension(id="D1", name="Term completeness", category="decomposition"),
    JudgeDimension(id="D2", name="Definition accuracy", category="decomposition"),
    JudgeDimension(id="D3", name="Scope correctness", category="decomposition"),
    JudgeDimension(id="D4", name="Exception coverage", category="decomposition"),
    JudgeDimension(id="D5", name="Dependency tracking", category="decomposition"),
    JudgeDimension(id="R1", name="Rule type", category="rule_unit"),
    JudgeDimension(id="R2", name="Entity ID", category="rule_unit"),
    JudgeDimension(id="R3", name="Action completeness", category="rule_unit"),
    JudgeDimension(id="R4", name="Condition fidelity", category="rule_unit"),
    JudgeDimension(id="R5", name="Logical structure", category="rule_unit"),
    JudgeDimension(id="R6", name="Granularity", category="rule_unit"),
    JudgeDimension(id="R7", name="Penalty linkage", category="rule_unit"),
    JudgeDimension(id="R8", name="Summary accuracy", category="rule_unit"),
    JudgeDimension(id="R9", name="No hallucination", category="rule_unit"),
)

JUDGE_DIMENSION_MAP = {dimension.id: dimension for dimension in JUDGE_DIMENSIONS}
REPAIR_CYCLES: dict[int, tuple[str, ...]] = {
    1: ("M1", "M2", "M4", "M5"),
    2: ("D1", "D2", "D3", "D4", "D5", "R6"),
    3: ("R1", "R2", "R3", "R4", "R5", "R7", "R8", "R9"),
}


def critique(
    extraction: dict[str, Any],
    source_markdown: str,
    model: CritiqueClient | None = None,
) -> ScoreCard:
    """Evaluate an extraction across all 19 constitutional judge dimensions."""

    client = model or DeterministicCritiqueClient()
    prompt = _build_prompt("critique", extraction, source_markdown)
    _log_payload("critique_prompt_sent", prompt.model_dump())
    response = client.complete(prompt)
    _log_payload("critique_response_received", response)
    return _coerce_score_card(response)


def repair(
    extraction: dict[str, Any],
    source_markdown: str,
    score_card: ScoreCard,
    model: CritiqueClient | None = None,
) -> dict[str, Any]:
    """Repair failed dimensions using source-grounded critique feedback."""

    client = model or DeterministicCritiqueClient()
    prompt = _build_prompt(
        "repair",
        extraction,
        source_markdown,
        target_dimensions=score_card.failed_dimensions,
        score_card=score_card,
    )
    _log_payload("repair_prompt_sent", prompt.model_dump())
    response = client.complete(prompt)
    _log_payload("repair_response_received", response)
    if not isinstance(response, dict):
        raise TypeError("repair response must be a dict extraction")
    return response


def run_critique_loop(
    extraction: dict[str, Any],
    source_markdown: str,
    max_iterations: int = 3,
    model: CritiqueClient | None = None,
) -> CritiqueResult:
    """Run the upstream-first critique/repair loop with a hard three-cycle cap."""

    if max_iterations < 1 or max_iterations > 3:
        raise ValueError("max_iterations must be between 1 and 3")
    current = copy.deepcopy(extraction)
    repair_history: list[dict[str, Any]] = []
    client = model or DeterministicCritiqueClient()
    last_score_card = critique(current, source_markdown, client)
    if last_score_card.passes:
        return CritiqueResult(
            final_extraction=current,
            score_card=last_score_card,
            iterations=0,
            route="ACCEPT",
            repair_history=repair_history,
        )
    for cycle in range(1, max_iterations + 1):
        target_dimensions = _cycle_failures(last_score_card, cycle)
        if target_dimensions:
            cycle_card = last_score_card.limited_to(target_dimensions)
            current = repair(current, source_markdown, cycle_card, client)
        repair_history.append(
            {
                "cycle": cycle,
                "target_dimensions": target_dimensions,
                "failed_dimensions": last_score_card.failed_dimensions,
            }
        )
        last_score_card = critique(current, source_markdown, client)
        if last_score_card.passes:
            return CritiqueResult(
                final_extraction=current,
                score_card=last_score_card,
                iterations=cycle,
                route="ACCEPT",
                repair_history=repair_history,
            )
    route: Literal["REJECT", "QUARANTINE"] = (
        "REJECT" if last_score_card.has_hallucination else "QUARANTINE"
    )
    return CritiqueResult(
        final_extraction=current,
        score_card=last_score_card,
        iterations=max_iterations,
        route=route,
        repair_history=repair_history,
    )


def _build_prompt(
    kind: Literal["critique", "repair"],
    extraction: dict[str, Any],
    source_markdown: str,
    target_dimensions: list[str] | None = None,
    score_card: ScoreCard | None = None,
) -> CritiquePrompt:
    """Build a critique or repair prompt containing the Constitution verbatim."""

    constitution = _constitution_prompt_text()
    dimensions = "\n".join(
        f"{dimension.id} - {dimension.name}" for dimension in JUDGE_DIMENSIONS
    )
    system_prompt = (
        "You are the Project Geode constitutional judge. Apply every principle "
        "and judge dimension strictly.\n\n"
        f"{constitution}\n\nJudge dimensions:\n{dimensions}"
    )
    target_dimensions = target_dimensions or []
    user_prompt = (
        f"Mode: {kind}\n"
        f"Target dimensions: {', '.join(target_dimensions) or 'all'}\n\n"
        f"Source Markdown:\n{source_markdown}\n\n"
        "Extraction JSON:\n"
        f"{json.dumps(extraction, ensure_ascii=False, sort_keys=True, default=str)}"
    )
    if score_card is not None:
        user_prompt += (
            "\n\nScoreCard JSON:\n"
            f"{score_card.model_dump_json(by_alias=True)}"
        )
    return CritiquePrompt(
        kind=kind,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        extraction=extraction,
        source_markdown=source_markdown,
        target_dimensions=target_dimensions,
        score_card=score_card.model_dump() if score_card else None,
    )


def _constitution_prompt_text() -> str:
    """Render the structured Constitution as prompt text."""

    return "\n\n".join(
        f"{principle.id} - {principle.name}\n{principle.text}"
        for principle in GEODE_CONSTITUTION
    )


def _cycle_failures(score_card: ScoreCard, cycle: int) -> list[str]:
    """Return failed dimensions targeted by one upstream-first repair cycle."""

    allowed = set(REPAIR_CYCLES[cycle])
    return [
        dimension_id
        for dimension_id in score_card.failed_dimensions
        if dimension_id in allowed
    ]


def _coerce_score_card(raw: Any) -> ScoreCard:
    """Coerce a fake/model response into a full ScoreCard."""

    if isinstance(raw, ScoreCard):
        return raw
    if isinstance(raw, dict):
        raw_scores = raw.get("scores", raw)
    else:
        raw_scores = raw
    if isinstance(raw_scores, dict):
        scores = [
            _score_from_value(dimension.id, raw_scores.get(dimension.id, 5))
            for dimension in JUDGE_DIMENSIONS
        ]
        return ScoreCard(scores=scores)
    if isinstance(raw_scores, list):
        scores = [_score_from_entry(entry) for entry in raw_scores]
        return ScoreCard(scores=scores)
    raise TypeError("critique response must be a ScoreCard, dict, or list")


def _score_from_value(dimension_id: str, value: Any) -> DimensionScore:
    """Build a score from a scalar or mapping value."""

    dimension = JUDGE_DIMENSION_MAP[dimension_id]
    if isinstance(value, dict):
        score = int(value.get("score", 5))
        notes = str(value.get("notes", ""))
    else:
        score = int(value)
        notes = ""
    return DimensionScore(
        dimension_id=dimension.id,
        name=dimension.name,
        score=score,
        notes=notes,
    )


def _score_from_entry(entry: Any) -> DimensionScore:
    """Build a score from a list entry returned by a fake/model."""

    if not isinstance(entry, dict):
        raise TypeError("score entries must be dicts")
    dimension_id = str(entry.get("dimension_id", entry.get("dimension", "")))
    if dimension_id not in JUDGE_DIMENSION_MAP:
        raise ValueError(f"unknown critique dimension: {dimension_id}")
    dimension = JUDGE_DIMENSION_MAP[dimension_id]
    return DimensionScore(
        dimension_id=dimension.id,
        name=str(entry.get("name", dimension.name)),
        score=int(entry.get("score", 5)),
        notes=str(entry.get("notes", "")),
    )


def _log_payload(event: str, payload: object) -> None:
    """Log critique prompts/responses with hashes and full debug payloads."""

    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    logger.info("%s sha256=%s", event, digest)
    logger.debug("%s payload=%s", event, payload_json)
