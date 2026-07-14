"""Default pytest entry point for evidence and policy generation tests."""

from geode.orchestration.tests.test_evidence_policy_generation import (
    test_assemble_evidence_adds_provenance_currency_and_jurisdiction,
    test_conflict_detection_marks_hierarchy_resolution_and_unresolved_conflicts,
    test_generate_draft_uses_evidence_not_raw_query_text,
    test_prompt_assembly_is_deterministic_snapshot,
)

__all__ = [
    "test_assemble_evidence_adds_provenance_currency_and_jurisdiction",
    "test_conflict_detection_marks_hierarchy_resolution_and_unresolved_conflicts",
    "test_generate_draft_uses_evidence_not_raw_query_text",
    "test_prompt_assembly_is_deterministic_snapshot",
]
