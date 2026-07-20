"""Tests for the county semantic candidate pass."""

from pathlib import Path

from geode.pipeline.county_semantic_review import build_county_semantic_review
from geode.utils.file_io import atomic_write_jsonl, iter_jsonl


def test_county_semantic_candidates_remain_review_only(tmp_path: Path) -> None:
    """Candidates are source-grounded drafts and are never auto-promoted."""

    meta = tmp_path / "08_County_Authorities" / "_meta"
    meta.mkdir(parents=True)
    atomic_write_jsonl(
        meta / "local_rules.jsonl",
        [
            {
                "id": "LOCAL-RULE-TEST",
                "authority_id": "CO-COUNTY-TEST",
                "authority_name": "Test County",
                "source_category": "county_ordinances",
                "source_path": "_RAW_ARCHIVE/local/county/test.html",
                "source_url": "https://www.testcounty.gov/ordinance",
                "source_hash": "a" * 64,
                "full_text": "Applicants must submit the form within 30 days.",
            }
        ],
        tmp_path,
    )

    report = build_county_semantic_review(tmp_path)

    assert report["candidate_rule_units"] == 1
    assert report["promoted"] == 0
    row = next(iter_jsonl(tmp_path / "_CONTROL_PLANE" / "COUNTY_SEMANTIC_REVIEW_QUEUE.jsonl"))
    assert row["status"] == "pending"
    assert row["candidate_rule_unit"]["semantic_status"] == "needs_review"
