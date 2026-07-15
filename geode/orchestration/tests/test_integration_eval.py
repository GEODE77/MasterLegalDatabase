"""End-to-end orchestration integration and evaluation tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from geode.orchestration.contracts import (
    AuthorityLevel,
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
    load_real_corpus_golden_questions,
    run_golden_evaluation,
)
from geode.orchestration.feedback import FeedbackLoop, ReviewedCorrectionQueue
from geode.orchestration.golden_review import (
    GoldenQuestionReview,
    GoldenQuestionReviewWorkflow,
)


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
    feedback_loop = FeedbackLoop(correction_queue=ReviewedCorrectionQueue(feedback_path))
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
    records = ReviewedCorrectionQueue(feedback_path).read_all()
    assert records
    assert records[0].review_status == "pending_review"


def test_reviewed_real_corpus_questions_are_loaded_only_after_review(tmp_path: Path) -> None:
    """Real-corpus golden rows must be explicitly reviewed before joining eval."""

    fixture_path = tmp_path / "real_corpus_golden_questions.json"
    fixture_path.write_text(
        """[
  {
    "question_id": "queued-row",
    "query": "What does CRS-1-1-101 say?",
    "expected_question_type": "exact_citation",
    "expected_answer": null,
    "expected_citations": ["CRS-1-1-101"],
    "source_sample_id": "GS-0001",
    "source_record_id": "CRS-1-1-101",
    "source_path": "_RAW_ARCHIVE/crs/title01.txt",
    "review_status": "queued"
  },
  {
    "question_id": "reviewed-row",
    "query": "What laws govern greenhouse gas emissions in Colorado?",
    "expected_question_type": "broad_discovery",
    "expected_answer": "Federal greenhouse gas reporting rules require covered facilities to report carbon dioxide.",
    "expected_citations": ["40_CFR_98"],
    "source_sample_id": "manual-001",
    "source_record_id": "40_CFR_98",
    "source_path": "mock://40_CFR_98",
    "review_status": "human_reviewed",
    "reviewer": "test-reviewer"
  }
]""",
        encoding="utf-8",
    )

    reviewed_questions = load_real_corpus_golden_questions(fixture_path)
    all_questions = load_real_corpus_golden_questions(fixture_path, reviewed_only=False)
    summary = run_golden_evaluation(questions=reviewed_questions)

    assert [question.question_id for question in reviewed_questions] == ["reviewed-row"]
    assert len(all_questions) == 2
    assert summary.failed == 0


def test_local_location_parsing_makes_known_city_required() -> None:
    """A known city makes county and municipal coverage required."""

    state = run_orchestration(
        "Does a manufacturing facility in Denver need a permit for air emissions?",
        retrieval_backend=build_mock_knowledge_backend(),
        corpus_version="mock-golden",
    )

    coverage = {
        item.authority_level: item.requirement for item in state.jurisdiction_coverage
    }
    assert state.jurisdiction is not None
    assert state.jurisdiction.county == "Denver County"
    assert state.jurisdiction.municipality == "Denver"
    assert coverage[AuthorityLevel.COUNTY] == CoverageRequirement.REQUIRED
    assert coverage[AuthorityLevel.MUNICIPAL] == CoverageRequirement.REQUIRED


def test_local_location_parsing_keeps_county_only_city_conditional() -> None:
    """A county-only location makes county required but city still conditional."""

    state = run_orchestration(
        "What reporting requirements apply to a facility in Boulder County?",
        retrieval_backend=build_mock_knowledge_backend(),
        corpus_version="mock-golden",
    )

    coverage = {
        item.authority_level: item.requirement for item in state.jurisdiction_coverage
    }
    assert state.jurisdiction is not None
    assert state.jurisdiction.county == "Boulder County"
    assert state.jurisdiction.municipality is None
    assert coverage[AuthorityLevel.COUNTY] == CoverageRequirement.REQUIRED
    assert coverage[AuthorityLevel.MUNICIPAL] == CoverageRequirement.CONDITIONAL


def test_coverage_templates_are_split_by_question_type() -> None:
    """Exact citation coverage no longer falls back to broad compliance survey."""

    state = run_orchestration(
        "What does CRS 25-7-109 say about air pollution control?",
        retrieval_backend=build_mock_knowledge_backend(),
        corpus_version="mock-golden",
    )

    assert state.coverage_contract is not None
    category_ids = {
        category.category_id for category in state.coverage_contract.expected_categories
    }
    assert category_ids == {"colorado_statutes", "colorado_regulations"}


def test_manual_review_workflow_promotes_complete_queued_row(tmp_path: Path) -> None:
    """A queued real-corpus row can be promoted only with complete review content."""

    corpus_path = tmp_path / "real_corpus_golden_questions.json"
    log_path = tmp_path / "review_log.jsonl"
    corpus_path.write_text(
        """[
  {
    "question_id": "corpus-GS-0001",
    "query": "What does CRS-1-1-101 say?",
    "expected_question_type": "exact_citation",
    "expected_answer": null,
    "expected_citations": [],
    "source_sample_id": "GS-0001",
    "source_record_id": "CRS-1-1-101",
    "source_path": "_RAW_ARCHIVE/crs/title01.txt",
    "review_status": "queued",
    "reviewer": null,
    "review_note": null
  }
]""",
        encoding="utf-8",
    )
    workflow = GoldenQuestionReviewWorkflow(
        corpus_path,
        review_log_path=log_path,
    )

    promoted = workflow.promote_to_human_reviewed(
        GoldenQuestionReview(
            question_id="corpus-GS-0001",
            reviewer="reviewer@example.test",
            expected_answer="CRS 1-1-101 provides the short title for the Colorado Revised Statutes.",
            expected_citations=["CRS-1-1-101"],
            review_note="Reviewed against source text.",
        )
    )

    reviewed = load_real_corpus_golden_questions(corpus_path)
    assert promoted.review_status == "human_reviewed"
    assert promoted.reviewer == "reviewer@example.test"
    assert promoted.expected_answer is not None
    assert promoted.expected_citations == ["CRS-1-1-101"]
    assert [question.question_id for question in reviewed] == ["corpus-GS-0001"]
    assert "corpus-GS-0001" in log_path.read_text(encoding="utf-8")


def test_manual_review_workflow_requires_answer_and_citations() -> None:
    """Incomplete review packages cannot be promoted."""

    with pytest.raises(ValidationError):
        GoldenQuestionReview(
            question_id="corpus-GS-0001",
            reviewer="reviewer@example.test",
            expected_answer="",
            expected_citations=["CRS-1-1-101"],
        )

    with pytest.raises(ValidationError):
        GoldenQuestionReview(
            question_id="corpus-GS-0001",
            reviewer="reviewer@example.test",
            expected_answer="Reviewed expected answer.",
            expected_citations=[],
        )


def test_manual_review_workflow_rejects_non_queued_rows(tmp_path: Path) -> None:
    """Already reviewed rows cannot be promoted again through the queued workflow."""

    corpus_path = tmp_path / "real_corpus_golden_questions.json"
    corpus_path.write_text(
        """[
  {
    "question_id": "corpus-GS-0001",
    "query": "What does CRS-1-1-101 say?",
    "expected_question_type": "exact_citation",
    "expected_answer": "Already reviewed answer.",
    "expected_citations": ["CRS-1-1-101"],
    "source_sample_id": "GS-0001",
    "source_record_id": "CRS-1-1-101",
    "source_path": "_RAW_ARCHIVE/crs/title01.txt",
    "review_status": "human_reviewed",
    "reviewer": "reviewer@example.test",
    "review_note": null
  }
]""",
        encoding="utf-8",
    )
    workflow = GoldenQuestionReviewWorkflow(corpus_path)

    with pytest.raises(ValueError, match="not queued"):
        workflow.promote_to_human_reviewed(
            GoldenQuestionReview(
                question_id="corpus-GS-0001",
                reviewer="second-reviewer@example.test",
                expected_answer="Replacement answer.",
                expected_citations=["CRS-1-1-101"],
            )
        )
