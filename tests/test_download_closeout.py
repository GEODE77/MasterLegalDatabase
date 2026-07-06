"""Download closeout checklist tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from geode.pipeline.download_closeout import (
    FAIL,
    PASS,
    WARN,
    check_dashboard_updated,
    check_no_pending_downloads,
    overall_status,
)


def write_json(path: Path, payload: dict[str, object]) -> None:
    """Write a JSON test fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pending_downloads_pass_with_no_active_retry_work(tmp_path: Path) -> None:
    """Known future blocked items warn, but active retry work fails."""

    write_json(
        tmp_path / "03_Legislation" / "_documents" / "bill_document_summary.json",
        {"pending": 0, "pending_retry": 0, "run_failed": 0},
    )

    result = check_no_pending_downloads(tmp_path)

    assert result.status == PASS


def test_pending_downloads_warn_for_known_blocked_queue(tmp_path: Path) -> None:
    """Known blocked future downloads are visible as warnings."""

    write_json(
        tmp_path / "03_Legislation" / "_documents" / "bill_document_summary.json",
        {"pending": 0, "pending_retry": 0, "run_failed": 0},
    )
    write_json(tmp_path / "_CONTROL_PLANE" / "BLOCKED_DOWNLOAD_QUEUE.json", {"open_items": 1})

    result = check_no_pending_downloads(tmp_path)

    assert result.status == WARN


def test_pending_downloads_fail_for_active_pending_work(tmp_path: Path) -> None:
    """Active pending downloads fail the checklist."""

    write_json(
        tmp_path / "03_Legislation" / "_documents" / "bill_document_summary.json",
        {"pending": 2, "pending_retry": 0, "run_failed": 0},
    )

    result = check_no_pending_downloads(tmp_path)

    assert result.status == FAIL


def test_dashboard_updated_requires_today(tmp_path: Path) -> None:
    """The dashboard must be dated for the closeout date."""

    write_json(
        tmp_path / "_CONTROL_PLANE" / "NEXT_DOWNLOAD_DASHBOARD.json",
        {
            "generated_at": "2026-07-06T16:26:07Z",
            "overall_recommendation": {"next_download_area": "05_Executive_Orders"},
            "next_actions": [{"id": "EO-2019-007"}],
        },
    )

    result = check_dashboard_updated(tmp_path, date(2026, 7, 6))

    assert result.status == PASS


def test_dashboard_updated_fails_when_stale(tmp_path: Path) -> None:
    """A stale dashboard fails closeout."""

    write_json(
        tmp_path / "_CONTROL_PLANE" / "NEXT_DOWNLOAD_DASHBOARD.json",
        {
            "generated_at": "2026-07-05T16:26:07Z",
            "overall_recommendation": {"next_download_area": "05_Executive_Orders"},
            "next_actions": [{"id": "EO-2019-007"}],
        },
    )

    result = check_dashboard_updated(tmp_path, date(2026, 7, 6))

    assert result.status == FAIL


def test_overall_status_warns_without_failures() -> None:
    """Warnings produce a warning overall status."""

    assert overall_status([]) == PASS
