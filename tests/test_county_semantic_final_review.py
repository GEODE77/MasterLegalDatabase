"""Tests for the final county semantic review pass."""

from geode.pipeline.county_semantic_final_review import _split_proposals


def test_split_proposals_preserve_multiple_source_actions() -> None:
    """Multiple modal actions become review proposals, not automatic edits."""

    proposals = _split_proposals("Applicants shall file the form; applicants must retain a copy.")

    assert len(proposals) == 2
    assert all("applicant" in proposal.casefold() for proposal in proposals)
