"""Manual review workflow for real-corpus golden questions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field

from geode.orchestration.contracts import QuestionType
from geode.orchestration.contracts.models import StrictOrchestrationModel
from geode.orchestration.evaluation import (
    REAL_CORPUS_GOLDEN_QUESTIONS_PATH,
    GoldenQuestion,
)


class GoldenQuestionReview(StrictOrchestrationModel):
    """Human-supplied review package needed to certify one corpus golden row."""

    question_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    expected_citations: list[str] = Field(min_length=1)
    review_note: str | None = None


class GoldenQuestionReviewLog(StrictOrchestrationModel):
    """Audit record for one successful corpus golden review."""

    question_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    reviewed_at: datetime
    previous_status: str = Field(min_length=1)
    new_status: str = "human_reviewed"
    expected_citations: list[str] = Field(min_length=1)


class GoldenQuestionReviewWorkflow:
    """Promote queued corpus golden rows only after complete human review."""

    def __init__(
        self,
        corpus_golden_path: Path = REAL_CORPUS_GOLDEN_QUESTIONS_PATH,
        *,
        review_log_path: Path | None = None,
    ) -> None:
        """Create a review workflow for a corpus golden-question file."""

        self.corpus_golden_path = corpus_golden_path
        self.review_log_path = review_log_path

    def queued_questions(self) -> list[GoldenQuestion]:
        """Return corpus golden rows still awaiting review."""

        return [
            GoldenQuestion.model_validate(_row_with_question_type(row))
            for row in self._read_rows()
            if str(row.get("review_status") or "").casefold() == "queued"
        ]

    def promote_to_human_reviewed(self, review: GoldenQuestionReview) -> GoldenQuestion:
        """Promote one queued row after required human-reviewed fields are supplied."""

        rows = self._read_rows()
        row_index = _find_row_index(rows, review.question_id)
        row = rows[row_index]
        previous_status = str(row.get("review_status") or "")
        if previous_status.casefold() != "queued":
            raise ValueError(
                f"golden question {review.question_id} is not queued; "
                f"current status is {previous_status!r}"
            )

        reviewed_at = datetime.now(timezone.utc)
        expected_citations = list(dict.fromkeys(review.expected_citations))
        updated = {
            **row,
            "expected_answer": review.expected_answer,
            "expected_citations": expected_citations,
            "review_status": "human_reviewed",
            "reviewer": review.reviewer,
            "reviewed_at": reviewed_at.isoformat(),
            "review_note": review.review_note,
        }
        GoldenQuestion.model_validate(_row_with_question_type(updated))
        rows[row_index] = updated
        self._write_rows(rows)
        self._append_review_log(
            GoldenQuestionReviewLog(
                question_id=review.question_id,
                reviewer=review.reviewer,
                reviewed_at=reviewed_at,
                previous_status=previous_status,
                expected_citations=expected_citations,
            )
        )
        return GoldenQuestion.model_validate(_row_with_question_type(updated))

    def _read_rows(self) -> list[dict[str, object]]:
        """Read the real-corpus golden-question file."""

        payload = json.loads(self.corpus_golden_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("corpus golden-question file must contain a JSON array")
        return [_validate_raw_row(row) for row in payload]

    def _write_rows(self, rows: list[dict[str, object]]) -> None:
        """Atomically write the updated corpus golden-question file."""

        self.corpus_golden_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.corpus_golden_path.with_suffix(
            f"{self.corpus_golden_path.suffix}.tmp"
        )
        temp_path.write_text(
            json.dumps(rows, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.corpus_golden_path)

    def _append_review_log(self, record: GoldenQuestionReviewLog) -> None:
        """Append one review audit record when a log path is configured."""

        if self.review_log_path is None:
            return
        self.review_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.review_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")


def _find_row_index(rows: list[dict[str, object]], question_id: str) -> int:
    """Find a golden-question row by ID."""

    for index, row in enumerate(rows):
        if row.get("question_id") == question_id:
            return index
    raise ValueError(f"golden question not found: {question_id}")


def _validate_raw_row(row: object) -> dict[str, object]:
    """Validate one raw JSON row is an object."""

    if not isinstance(row, dict):
        raise ValueError("each corpus golden-question row must be an object")
    return row


def _row_with_question_type(row: dict[str, object]) -> dict[str, object]:
    """Return a row with the strict question type enum applied."""

    return {
        **row,
        "expected_question_type": QuestionType(str(row["expected_question_type"])),
    }
