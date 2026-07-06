"""Source update watcher dashboard tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from geode.pipeline.source_update_watcher import (
    MANUAL_REVIEW,
    NEW_DATA,
    NO_CHANGE,
    ObservedSourceState,
    build_source_update_watcher_dashboard,
    write_source_update_watcher_dashboard,
)


def write_json(path: Path, payload: object) -> None:
    """Write a JSON fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_root(tmp_path: Path) -> None:
    """Seed the minimum control-plane files for watcher tests."""

    write_json(
        tmp_path / "_CONTROL_PLANE" / "SOURCE_REGISTRY.json",
        [
            {
                "source_id": "legiscan",
                "source_name": "LegiScan Colorado",
                "url": "https://legiscan.com/CO",
                "access_method": "api",
                "update_frequency": "weekly during session",
            },
            {
                "source_id": "colorado_register",
                "source_name": "Colorado Register",
                "url": "https://www.sos.state.co.us/CCR/RegisterHome.do",
                "access_method": "scrape",
                "update_frequency": "twice monthly",
            },
            {
                "source_id": "crs",
                "source_name": "Colorado Revised Statutes",
                "url": "https://leg.colorado.gov/colorado-revised-statutes",
                "access_method": "email_request",
                "update_frequency": "annually",
            },
        ],
    )
    write_json(
        tmp_path / "_CONTROL_PLANE" / "MASTER_MANIFEST.json",
        {
            "data_layers": [
                {
                    "id": "03_Legislation",
                    "source": "legiscan",
                    "last_checked": "2026-07-06",
                    "last_ingested": "2026-07-06",
                },
                {
                    "id": "04_Rulemaking",
                    "source": "colorado_register",
                    "last_checked": "2026-06-25",
                    "last_ingested": "2026-06-25",
                },
                {
                    "id": "01_Statutes_CRS",
                    "source": "crs",
                    "last_checked": "2026-07-02",
                    "last_ingested": "2026-07-02",
                    "currency": "2025",
                },
            ]
        },
    )
    write_json(
        tmp_path / "_CONTROL_PLANE" / "FRESHNESS_VERIFICATION_QUEUE.json",
        {"items": []},
    )


def observed(source_id: str, marker: str) -> ObservedSourceState:
    """Build an observed source state fixture."""

    return ObservedSourceState(
        source_id=source_id,
        marker=marker,
        observed_at=datetime(2026, 7, 6, tzinfo=UTC),
        evidence_url="https://example.test/source",
        evidence_note="fixture marker",
    )


def test_watcher_queues_new_register_marker(tmp_path: Path) -> None:
    """A source marker newer than the local marker creates a guarded queue item."""

    seed_root(tmp_path)

    dashboard = build_source_update_watcher_dashboard(
        tmp_path,
        [observed("colorado_register", "2026-07-10")],
    )

    register = next(item for item in dashboard.items if item.source_id == "colorado_register")
    assert register.change_status == NEW_DATA
    assert register.download_status == "guarded_download_ready"
    assert dashboard.download_queue[0].source_id == "colorado_register"


def test_watcher_marks_equal_or_older_marker_as_no_change(tmp_path: Path) -> None:
    """A source marker not newer than the local marker does not queue a download."""

    seed_root(tmp_path)

    dashboard = build_source_update_watcher_dashboard(
        tmp_path,
        [observed("legiscan", "2026-07-06")],
    )

    legiscan = next(item for item in dashboard.items if item.source_id == "legiscan")
    assert legiscan.change_status == NO_CHANGE
    assert all(item.source_id != "legiscan" for item in dashboard.download_queue)


def test_watcher_keeps_email_request_sources_manual(tmp_path: Path) -> None:
    """Email-request sources stay in manual review rather than automatic download."""

    seed_root(tmp_path)

    dashboard = build_source_update_watcher_dashboard(tmp_path)

    crs = next(item for item in dashboard.items if item.source_id == "crs")
    assert crs.change_status == MANUAL_REVIEW
    assert crs.download_status == "manual_or_guarded_intake_required"


def test_watcher_writes_dashboard_and_queue(tmp_path: Path) -> None:
    """Writing the watcher creates both machine and human-facing artifacts."""

    seed_root(tmp_path)

    dashboard = write_source_update_watcher_dashboard(
        tmp_path,
        [observed("colorado_register", "2026-07-10")],
    )

    assert dashboard.new_data_items == 1
    assert (tmp_path / "_CONTROL_PLANE" / "SOURCE_UPDATE_WATCHER_DASHBOARD.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "SOURCE_UPDATE_DOWNLOAD_QUEUE.json").exists()
    assert (tmp_path / "docs" / "audits" / "SOURCE_UPDATE_WATCHER_DASHBOARD_2026-07-06.md").exists()
