"""Feedback capture for evaluation and correction review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field

from geode.orchestration.contracts.models import StrictOrchestrationModel


class CorrectionSuggestion(StrictOrchestrationModel):
    """One proposed rule or retrieval adjustment."""

    suggestion_type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class FeedbackRecord(StrictOrchestrationModel):
    """Captured evaluation failure for later human review."""

    question_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    errors: list[str] = Field(default_factory=list)
    suggestions: list[CorrectionSuggestion] = Field(default_factory=list)


class FeedbackLoop:
    """Capture eval failures and propose correction targets without auto-applying them."""

    def __init__(self, output_path: Path | None = None) -> None:
        """Create a feedback loop."""

        self.output_path = output_path
        self.records: list[FeedbackRecord] = []

    def capture_failure(
        self,
        *,
        question_id: str,
        query: str,
        errors: list[str],
    ) -> FeedbackRecord:
        """Record one failed evaluation and return proposed adjustment targets."""

        record = FeedbackRecord(
            question_id=question_id,
            query=query,
            errors=list(errors),
            suggestions=_suggest_adjustments(errors),
        )
        self.records.append(record)
        if self.output_path is not None:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            with self.output_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")
        return record

    def capture_eval_results(self, results: list[tuple[str, str, bool, list[str]]]) -> list[FeedbackRecord]:
        """Capture all failed eval rows."""

        return [
            self.capture_failure(question_id=question_id, query=query, errors=errors)
            for question_id, query, passed, errors in results
            if not passed
        ]


def _suggest_adjustments(errors: list[str]) -> list[CorrectionSuggestion]:
    """Map observed failures to reviewable correction targets."""

    suggestions: list[CorrectionSuggestion] = []
    for error in errors:
        lowered = error.casefold()
        if "question_type" in lowered:
            suggestions.append(
                CorrectionSuggestion(
                    suggestion_type="rule_adjustment",
                    target="config/rules.yaml",
                    reason=error,
                )
            )
        elif "coverage" in lowered or "citation" in lowered or "currency" in lowered:
            suggestions.append(
                CorrectionSuggestion(
                    suggestion_type="retrieval_adjustment",
                    target="retrieval backend or coverage template",
                    reason=error,
                )
            )
        else:
            suggestions.append(
                CorrectionSuggestion(
                    suggestion_type="review_adjustment",
                    target="evaluation harness",
                    reason=error,
                )
            )
    return list({item.model_dump_json(): item for item in suggestions}.values())
