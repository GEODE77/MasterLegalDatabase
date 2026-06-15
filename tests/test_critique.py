"""Constitutional critique loop tests."""

from __future__ import annotations

from typing import Any

from geode.pipeline.critique import (
    GEODE_CONSTITUTION,
    JUDGE_DIMENSIONS,
    CritiquePrompt,
    critique,
    repair,
    run_critique_loop,
)


class FakeCritiqueClient:
    """Fake critique model with deterministic queued scorecards."""

    provider = "fake"
    model_name = "fake-judge"

    def __init__(self, scorecards: list[dict[str, Any]]) -> None:
        """Create a fake critique client."""

        self.scorecards = scorecards
        self.prompts: list[CritiquePrompt] = []

    def complete(self, prompt: CritiquePrompt) -> Any:
        """Return queued critique scorecards and source-preserving repairs."""

        self.prompts.append(prompt)
        if prompt.kind == "repair":
            repaired = dict(prompt.extraction)
            history = list(repaired.get("repaired_dimensions", []))
            history.extend(prompt.target_dimensions)
            repaired["repaired_dimensions"] = history
            return repaired
        return self.scorecards.pop(0)


def _scores(**overrides: int) -> dict[str, Any]:
    """Build a complete 19-dimension score response."""

    scores = {dimension.id: 5 for dimension in JUDGE_DIMENSIONS}
    scores.update(overrides)
    return {"scores": scores}


def test_critique_constants_cover_constitution_and_dimensions() -> None:
    """The phase-required constants include all principles and dimensions."""

    assert len(GEODE_CONSTITUTION) == 8
    assert len(JUDGE_DIMENSIONS) == 19
    assert [dimension.id for dimension in JUDGE_DIMENSIONS[:5]] == [
        "M1",
        "M2",
        "M3",
        "M4",
        "M5",
    ]
    assert [dimension.id for dimension in JUDGE_DIMENSIONS[-2:]] == ["R8", "R9"]


def test_critique_evaluates_all_dimensions_and_embeds_constitution() -> None:
    """Critique prompts include Constitution text and return 19 scores."""

    client = FakeCritiqueClient([_scores()])
    score_card = critique({"id": "x"}, "source text", client)
    assert len(score_card.scores) == 19
    assert score_card.passes
    prompt = client.prompts[0]
    assert "P1 - SOURCE FIDELITY" in prompt.system_prompt
    assert "P8 - ENTITY CLARITY" in prompt.system_prompt


def test_repair_uses_target_dimensions_from_scorecard() -> None:
    """Repair prompts target only failed dimensions supplied by the scorecard."""

    client = FakeCritiqueClient([])
    score_card = critique({"_force_scores": {"M1": 2}}, "source", None)
    repaired = repair({"id": "x"}, "source", score_card, client)
    assert "M1" in repaired["repaired_dimensions"]
    assert client.prompts[0].target_dimensions == ["M1"]


def test_run_critique_loop_repairs_upstream_first() -> None:
    """The loop repairs M, then D/R6, then downstream R dimensions."""

    client = FakeCritiqueClient(
        [
            _scores(M1=2, D1=2, R1=2),
            _scores(D1=2, R1=2),
            _scores(R1=2),
            _scores(),
        ]
    )
    result = run_critique_loop({"id": "x"}, "source text", model=client)
    assert result.route == "ACCEPT"
    assert result.iterations == 3
    assert result.repair_history[0]["target_dimensions"] == ["M1"]
    assert result.repair_history[1]["target_dimensions"] == ["D1"]
    assert result.repair_history[2]["target_dimensions"] == ["R1"]


def test_run_critique_loop_rejects_r9_after_cap() -> None:
    """R9 below 5 after the capped loop forces rejection."""

    client = FakeCritiqueClient(
        [
            _scores(R9=4),
            _scores(R9=4),
            _scores(R9=4),
            _scores(R9=4),
        ]
    )
    result = run_critique_loop({"id": "x"}, "source text", model=client)
    assert result.route == "REJECT"
    assert result.iterations == 3
    assert result.score_card.has_hallucination
