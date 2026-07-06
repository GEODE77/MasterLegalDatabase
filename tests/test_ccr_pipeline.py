"""Tests for CCR live ingestion orchestration."""

from __future__ import annotations

import sys
from pathlib import Path

from geode.pipeline import ccr
from geode.pipeline.run import build_parser, main


EXPECTED_RULE_URL = (
    "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=3154"
)


class FakeSession:
    """Minimal closeable session for pipeline tests."""

    def __init__(self) -> None:
        """Create a fake session."""

        self.closed = False

    def close(self) -> None:
        """Mark the session closed."""

        self.closed = True


class FakeConversion:
    """Minimal conversion object consumed by the CCR pipeline writer."""

    markdown_text = "# Minimum Wage Order\n\nAuthority: section 8-6-101, C.R.S."

    def model_dump(self, **_kwargs) -> dict[str, object]:
        """Return stable conversion metadata."""

        return {
            "conversion_path": "path_1_docx",
            "tool_used": "test",
            "warnings": [],
        }


def test_resolve_ccr_url_format() -> None:
    """CCR rule IDs resolve to the expected SOS rule-info URL."""

    assert ccr._resolve_ccr_url("3154") == EXPECTED_RULE_URL


def test_output_paths_structure(tmp_path: Path) -> None:
    """CCR output paths use the raw, normalized, and tagged layout."""

    paths = ccr._output_paths(tmp_path, "3154", "out")

    assert set(paths) == {"raw", "normalized", "tagged"}
    assert paths["raw"] == tmp_path / "out" / "raw" / "Colorado" / "CCR"
    assert paths["normalized"] == tmp_path / "out" / "normalized" / "Colorado" / "CCR"
    assert paths["tagged"] == tmp_path / "out" / "tagged"


def test_run_ccr_pipeline_dry_run(monkeypatch, tmp_path: Path) -> None:
    """Dry-run mode plans work without touching disk or network."""

    def fail_build_session() -> None:
        raise AssertionError("network session should not be created during dry run")

    monkeypatch.setattr(ccr, "build_session", fail_build_session)

    exit_code = ccr.run_ccr_pipeline(
        tmp_path,
        "3154",
        output_dir="out",
        dry_run=True,
    )

    assert exit_code == 0
    assert not (tmp_path / "out").exists()


def test_run_ccr_pipeline_happy_path(monkeypatch, tmp_path: Path) -> None:
    """CCR pipeline writes raw, normalized, and tagged outputs on success."""

    session = FakeSession()
    entry = ccr.CCRRuleEntry(
        ccr_number="7 CCR 1103-1",
        department="Department of Labor and Employment",
        agency="Division of Labor Standards and Statistics",
        source_page_url=EXPECTED_RULE_URL,
        docx_url="https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=1&type=word",
    )

    def fake_download_rule(_entry, archive_dir: Path, client=None) -> Path:
        raw_path = archive_dir / "ccr_rule_3154.docx"
        raw_path.write_bytes(b"fake docx")
        return raw_path

    monkeypatch.setattr(ccr, "build_session", lambda: session)
    monkeypatch.setattr(ccr, "resolve_rule_info_page", lambda *_args, **_kwargs: entry)
    monkeypatch.setattr(ccr, "download_rule", fake_download_rule)
    monkeypatch.setattr(ccr, "convert_to_markdown", lambda *_args, **_kwargs: FakeConversion())
    monkeypatch.setattr(ccr, "load_taxonomies", lambda _path: {})
    monkeypatch.setattr(ccr, "tag_bill", lambda *_args, **_kwargs: {"ok": True})

    exit_code = ccr.run_ccr_pipeline(tmp_path, "3154", output_dir="out")

    assert exit_code == 0
    assert session.closed is True
    assert (tmp_path / "out" / "raw" / "Colorado" / "CCR" / "ccr_rule_3154.docx").exists()
    assert (
        tmp_path / "out" / "normalized" / "Colorado" / "CCR" / "ccr_rule_7_CCR_1103-1.md"
    ).exists()
    assert (tmp_path / "out" / "tagged" / "ccr_rule_7_CCR_1103-1_tags.json").exists()


def test_run_ccr_pipeline_scraper_failure(monkeypatch, tmp_path: Path) -> None:
    """Scraper failures return non-zero and leave no output files."""

    def fail_resolve(*_args, **_kwargs):
        raise RuntimeError("scraper failed")

    monkeypatch.setattr(ccr, "build_session", FakeSession)
    monkeypatch.setattr(ccr, "resolve_rule_info_page", fail_resolve)

    exit_code = ccr.run_ccr_pipeline(tmp_path, "3154", output_dir="out")

    assert exit_code != 0
    output_dir = tmp_path / "out"
    assert not output_dir.exists() or not any(path.is_file() for path in output_dir.rglob("*"))


def test_pipeline_cli_routes_ccr_layer() -> None:
    """The shared pipeline parser accepts the CCR layer and rule ID."""

    args = build_parser().parse_args(["--layer", "ccr", "--rule-id", "3154", "--dry-run"])

    assert args.layer == "ccr"
    assert args.rule_id == "3154"
    assert args.dry_run is True


def test_pipeline_cli_rejects_ccr_without_rule_id(monkeypatch) -> None:
    """The CCR CLI branch rejects missing rule IDs with exit code 2."""

    monkeypatch.setattr(sys, "argv", ["geode-pipeline-run", "--layer", "ccr"])

    assert main() == 2
