"""Run orchestration integration/evaluation tests from the top-level suite."""

from geode.orchestration.tests.test_integration_eval import (
    test_co2_manufacturing_runs_end_to_end_with_local_limitations,
    test_default_pipeline_stage_order_matches_architecture,
    test_feedback_loop_captures_eval_failures,
    test_golden_evaluation_reports_all_questions_green,
    test_coverage_templates_are_split_by_question_type,
    test_local_location_parsing_keeps_county_only_city_conditional,
    test_local_location_parsing_makes_known_city_required,
    test_manual_review_workflow_promotes_complete_queued_row,
    test_manual_review_workflow_rejects_non_queued_rows,
    test_manual_review_workflow_requires_answer_and_citations,
    test_reviewed_real_corpus_questions_are_loaded_only_after_review,
)

__all__ = [
    "test_co2_manufacturing_runs_end_to_end_with_local_limitations",
    "test_coverage_templates_are_split_by_question_type",
    "test_default_pipeline_stage_order_matches_architecture",
    "test_feedback_loop_captures_eval_failures",
    "test_golden_evaluation_reports_all_questions_green",
    "test_local_location_parsing_keeps_county_only_city_conditional",
    "test_local_location_parsing_makes_known_city_required",
    "test_manual_review_workflow_promotes_complete_queued_row",
    "test_manual_review_workflow_rejects_non_queued_rows",
    "test_manual_review_workflow_requires_answer_and_citations",
    "test_reviewed_real_corpus_questions_are_loaded_only_after_review",
]
