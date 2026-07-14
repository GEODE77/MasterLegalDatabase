"""End-to-end orchestration integration and evaluation tests."""

from pathlib import Path

from geode.orchestration.contracts import (
    CoverageRequirement,
    CoverageStatus,
    EmittedAnswer,
    QuestionType,
)
from geode.orchestration.entrypoint import (
    DEFAULT_STAGE_ORDER,
    build_default_stages,
    run_orchestration,
)
from geode.orchestration.evaluation import (
    GoldenQuestion,
    build_mock_knowledge_backend,
    load_golden_questions,
    run_golden_evaluation,
)
from geode.orchestration.feedback import FeedbackLoop


def test_default_pipeline_stage_order_matches_architecture() -> None:
    """The public entrypoint wires the requested full stage order."""

    stages = build_default_stages(retrieval_backend=build_mock_knowledge_backend())

    assert [stage.name for stage in stages] == DEFAULT_STAGE_ORDER


def test_co2_manufacturing_runs_end_to_end_with_local_limitations() -> None:
    """The sample query emits a valid cited answer and local coverage limits."""

    state = run_orchestration(
        "What are the regulations that pertain to CO2 emissions for manufacturing?",
        retrieval_backend=build_mock_knowledge_backend(),
        corpus_version="mock-golden",
    )

    assert state.emitted_answer is not None
    EmittedAnswer.model_validate_json(state.emitted_answer.model_dump_json())
    assert state.intent.question_type == QuestionType.COMPLIANCE_SURVEY
    assert state.final_answer is not None
    assert state.final_answer.citations
    assert 0.0 <= state.final_answer.confidence.score <= 1.0
    limitation_text = " ".join(state.final_answer.uncertainties).casefold()
    assert "county" in limitation_text
    assert "municipal" in limitation_text
    assert state.coverage_contract is not None
    assert all(
        category.status == CoverageStatus.FOUND
        for category in state.coverage_contract.expected_categories
        if category.requirement == CoverageRequirement.REQUIRED
    )


def test_golden_evaluation_reports_all_questions_green() -> None:
    """The golden-question harness reports pass/fail rows and summary counts."""

    questions = load_golden_questions()
    summary = run_golden_evaluation(questions=questions)

    assert summary.total >= 11
    assert summary.failed == 0
    assert summary.passed == summary.total
    assert all(result.passed for result in summary.results)


def test_feedback_loop_captures_eval_failures(tmp_path: Path) -> None:
    """Failed evaluation rows create reviewable correction suggestions."""

    feedback_path = tmp_path / "feedback.jsonl"
    feedback_loop = FeedbackLoop(feedback_path)
    questions = [
        GoldenQuestion(
            question_id="intent-mismatch",
            query="What does CRS 25-7-109 say about air pollution control?",
            expected_question_type=QuestionType.COMPLIANCE_SURVEY,
        )
    ]

    summary = run_golden_evaluation(
        questions=questions,
        feedback_loop=feedback_loop,
    )

    assert summary.failed == 1
    assert summary.feedback_records
    assert summary.feedback_records[0].suggestions
    assert feedback_path.read_text(encoding="utf-8").strip()
