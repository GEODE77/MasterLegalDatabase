"""Run orchestration integration/evaluation tests from the top-level suite."""

from geode.orchestration.tests.test_integration_eval import (
    test_co2_manufacturing_runs_end_to_end_with_local_limitations,
    test_default_pipeline_stage_order_matches_architecture,
    test_feedback_loop_captures_eval_failures,
    test_golden_evaluation_reports_all_questions_green,
)

__all__ = [
    "test_co2_manufacturing_runs_end_to_end_with_local_limitations",
    "test_default_pipeline_stage_order_matches_architecture",
    "test_feedback_loop_captures_eval_failures",
    "test_golden_evaluation_reports_all_questions_green",
]
