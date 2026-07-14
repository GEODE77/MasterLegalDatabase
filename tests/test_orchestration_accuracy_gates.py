"""Default pytest entry point for hard accuracy gate tests."""

from geode.orchestration.tests.test_accuracy_gates import (
    test_absence_verification_rewrites_retrieval_limit_as_not_verified_absence,
    test_fabricated_citation_is_stripped_and_claim_does_not_survive,
    test_gate_outcomes_are_recorded_in_report_and_trace,
    test_missing_category_is_flagged_by_completeness_gate,
    test_repealed_provision_is_flagged_by_currency_gate,
    test_unsupported_sentence_is_removed_by_faithfulness_gate,
)

__all__ = [
    "test_absence_verification_rewrites_retrieval_limit_as_not_verified_absence",
    "test_fabricated_citation_is_stripped_and_claim_does_not_survive",
    "test_gate_outcomes_are_recorded_in_report_and_trace",
    "test_missing_category_is_flagged_by_completeness_gate",
    "test_repealed_provision_is_flagged_by_currency_gate",
    "test_unsupported_sentence_is_removed_by_faithfulness_gate",
]
