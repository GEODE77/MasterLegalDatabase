"""CLI tests for the bulk source-download entry point."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from geode.connectors import run as bulk_run
from geode.connectors.orchestrator import ConnectorRunResult, OrchestratorReport


def test_bulk_download_config_canonicalizes_source_selection(tmp_path: Path) -> None:
    """The CLI accepts operational source aliases and comma-separated values."""

    parser = bulk_run.build_parser()
    args = parser.parse_args(
        [
            "--root",
            str(tmp_path),
            "--connectors",
            "ccr,register",
            "exec-orders",
            "--delay",
            "0.5",
            "--delay-jitter",
            "0.2",
            "--discovery-delay-jitter",
            "0.1",
            "--max-downloads",
            "25",
            "--http-max-retries",
            "4",
            "--http-retry-jitter-ratio",
            "0",
            "--no-quality-report",
        ]
    )

    config = bulk_run.config_from_args(args)

    assert config["root"] == tmp_path
    assert config["connectors"] == ["ccr", "colorado_register", "executive_orders"]
    assert config["delay"] == 0.5
    assert config["delay_jitter"] == 0.2
    assert config["discovery_delay_jitter"] == 0.1
    assert config["max_downloads"] == 25
    assert config["http_max_retries"] == 4
    assert config["http_retry_jitter_ratio"] == 0.0
    assert config["write_quality_report"] is False


def test_bulk_download_config_rejects_mixed_all_selection() -> None:
    """The all source selector is kept unambiguous."""

    parser = bulk_run.build_parser()
    args = parser.parse_args(["--connectors", "all", "ccr"])

    try:
        bulk_run.config_from_args(args)
    except bulk_run.BulkDownloadCommandError as exc:
        assert "--connectors all" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected BulkDownloadCommandError")


def test_bulk_download_config_rejects_negative_download_cap() -> None:
    """Download caps must not silently disable connector work."""

    parser = bulk_run.build_parser()
    args = parser.parse_args(["--connectors", "ccr", "--max-downloads", "-1"])

    with pytest.raises(bulk_run.BulkDownloadCommandError):
        bulk_run.config_from_args(args)


def test_bulk_download_config_rejects_negative_jitter() -> None:
    """Throttle jitter options must be non-negative."""

    parser = bulk_run.build_parser()
    args = parser.parse_args(["--connectors", "ccr", "--delay-jitter", "-0.1"])

    with pytest.raises(bulk_run.BulkDownloadCommandError):
        bulk_run.config_from_args(args)


def test_bulk_download_warns_for_git_and_sync_managed_roots(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Large bulk runs should visibly warn on source or sync-managed roots."""

    repo_root = tmp_path / "OneDrive - Example" / "Geode"
    data_root = repo_root / "data_root"
    data_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    caplog.set_level(logging.WARNING)

    bulk_run._warn_if_storage_root_is_sensitive(data_root)

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "inside a Git worktree" in messages
    assert "sync-managed folder" in messages


def test_bulk_download_main_runs_orchestrator_and_prints_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command delegates to the orchestrator and reports outputs."""

    captured_config: dict[str, Any] = {}
    manifest_path = tmp_path / "_RAW_ARCHIVE" / "ccr" / "manifest.jsonl"

    def fake_run_full_download(config: dict[str, Any]) -> OrchestratorReport:
        captured_config.update(config)
        return OrchestratorReport(
            root=tmp_path.as_posix(),
            requested_connectors=config["connectors"],
            results=[
                ConnectorRunResult(
                    connector="ccr",
                    status="completed",
                    raw_dir=(tmp_path / "_RAW_ARCHIVE" / "ccr").as_posix(),
                    summary={
                        "discovered": 2,
                        "downloaded": 1,
                        "failed": 0,
                        "skipped": 1,
                        "manifest_path": manifest_path.as_posix(),
                    },
                )
            ],
            quality_report_path=(
                tmp_path / "_CONTROL_PLANE" / "BULK_DOWNLOAD_QUALITY_REPORT.json"
            ).as_posix(),
            quality_summary={"errors": 0, "warnings": 1},
        )

    monkeypatch.setattr(bulk_run, "run_full_download", fake_run_full_download)

    exit_code = bulk_run.main(
        [
            "--root",
            str(tmp_path),
            "--connectors",
            "ccr",
            "--http-timeout-seconds",
            "30",
            "--max-downloads",
            "10",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert captured_config["connectors"] == ["ccr"]
    assert captured_config["http_timeout_seconds"] == 30.0
    assert captured_config["max_downloads"] == 10
    assert "Bulk download run summary" in output
    assert "Attempted: 2  Succeeded: 1  Failed: 0  Skipped: 1" in output
    assert "Quality report:" in output
    assert manifest_path.as_posix() in output


def test_bulk_download_main_returns_nonzero_for_failed_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Item-level failures make the command visibly fail for automation."""

    def fake_run_full_download(config: dict[str, Any]) -> OrchestratorReport:
        return OrchestratorReport(
            root=tmp_path.as_posix(),
            requested_connectors=config["connectors"],
            results=[
                ConnectorRunResult(
                    connector="ccr",
                    status="completed_with_errors",
                    raw_dir=(tmp_path / "_RAW_ARCHIVE" / "ccr").as_posix(),
                    summary={"discovered": 1, "downloaded": 0, "failed": 1, "skipped": 0},
                )
            ],
        )

    monkeypatch.setattr(bulk_run, "run_full_download", fake_run_full_download)

    exit_code = bulk_run.main(["--root", str(tmp_path), "--connectors", "ccr"])

    assert exit_code == 2
    assert "Failed: 1" in capsys.readouterr().out
