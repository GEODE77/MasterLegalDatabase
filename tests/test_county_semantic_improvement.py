"""Tests for conservative county semantic candidate improvements."""

from geode.pipeline.county_semantic_improvement import _improve_row


def test_improvement_captures_conditions_and_exceptions() -> None:
    """Visible limiting language is copied into structured review fields."""

    row = {
        "source_path": "_RAW_ARCHIVE/example.html",
        "candidate_rule_unit": {
            "entity_type": "rule_unit",
            "id": "LOCAL-RULE-TEST_RU_0001",
            "parent_regulation_id": "LOCAL-RULE-TEST",
            "source_section": "Section 1",
            "rule_type": "obligation",
            "regulated_entity": "Applicants",
            "action_required": "Applicants must file within 30 days unless extended by the county.",
            "conditions": [],
            "exceptions": [],
            "enabling_statute": [],
            "temporal": None,
            "penalties": [],
            "plain_english_summary": "placeholder",
            "subject_tags": ["compliance"],
            "confidence": {"overall": 0.6, "fields": {}, "route": "test"},
            "semantic_status": "needs_review",
        },
    }

    improved, changes = _improve_row(row)

    assert improved["candidate_rule_unit"]["exceptions"]
    assert any("exception" in change for change in changes)
    assert improved["candidate_rule_unit"]["semantic_status"] == "needs_review"
