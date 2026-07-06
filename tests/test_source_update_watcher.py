"""Source update watcher dashboard tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from geode.pipeline.source_update_watcher import (
    LIVE_PROBE_FAILED,
    MANUAL_REVIEW,
    NEW_DATA,
    NO_CHANGE,
    ObservedSourceState,
    build_source_update_watcher_dashboard,
    run_live_source_probes,
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
            {
                "source_id": "ccr",
                "source_name": "Code of Colorado Regulations",
                "url": "https://www.sos.state.co.us/CCR/Welcome.do",
                "access_method": "scrape",
                "update_frequency": "continuous",
            },
            {
                "source_id": "executive_orders",
                "source_name": "Colorado Governor Executive Orders",
                "url": "https://www.colorado.gov/governor/executive-orders",
                "access_method": "scrape",
                "update_frequency": "irregular",
            },
            {
                "source_id": "coprrr",
                "source_name": "COPRRR Sunrise and Sunset Reviews",
                "url": "https://coprrr.colorado.gov/",
                "access_method": "scrape",
                "update_frequency": "quarterly",
            },
            {
                "source_id": "ag_opinions",
                "source_name": "Colorado Attorney General Opinions",
                "url": "https://coag.gov/attorney-general-opinions/",
                "access_method": "scrape",
                "update_frequency": "irregular",
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
                {
                    "id": "02_Regulations_CCR",
                    "source": "ccr",
                    "last_checked": "2026-07-02",
                    "last_ingested": "2026-07-02",
                },
                {
                    "id": "05_Executive_Orders",
                    "source": "executive_orders",
                    "last_checked": "2026-07-02",
                    "last_ingested": "2026-07-02",
                },
                {
                    "id": "07_Supplementary",
                    "source": "coprrr, ag_opinions",
                    "last_checked": "2026-07-02",
                    "last_ingested": "2026-07-02",
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


def test_live_probes_extract_requested_source_markers() -> None:
    """Live probes extract latest visible markers from official source page shapes."""

    registry = [
        {"source_id": "ccr", "url": "https://www.sos.state.co.us/CCR/Welcome.do"},
        {"source_id": "colorado_register", "url": "https://www.sos.state.co.us/CCR/RegisterHome.do"},
        {"source_id": "executive_orders", "url": "https://www.colorado.gov/governor/executive-orders"},
        {"source_id": "coprrr", "url": "https://coprrr.colorado.gov/"},
        {"source_id": "ag_opinions", "url": "https://coag.gov/attorney-general-opinions/"},
    ]
    pages = {
        "https://www.sos.state.co.us/CCR/Welcome.do": (
            "The Code of Colorado Regulations is current with administrative rules "
            "effective on or before 07/20/2026."
        ),
        "https://www.sos.state.co.us/CCR/RegisterHome.do": "July 10, 2026 49 CR 13",
        "https://www.colorado.gov/governor/executive-orders": (
            '<a href="/governor/2026-executive-orders">2026 Executive Orders</a>'
        ),
        "https://www.colorado.gov/governor/2026-executive-orders": (
            '<a href="/files/d-2026-015.pdf">D 2026 015 July 4, 2026</a>'
        ),
        "https://coprrr.colorado.gov/": "Released October 15, 2026",
        "https://coag.gov/attorney-general-opinions/": (
            '<a href="/2026-formal-ag-opinions/">2026 Formal AG Opinions</a>'
        ),
        "https://coag.gov/2026-formal-ag-opinions/": "No. 26-001 (PDF) January 15, 2026",
    }

    states, errors = run_live_source_probes(registry, [], fetch_text=pages.__getitem__)

    assert errors == {}
    assert {state.source_id: state.marker for state in states} == {
        "ccr": "2026-07-20",
        "colorado_register": "2026-07-10",
        "executive_orders": "2026-07-04",
        "coprrr": "2026-10-15",
        "ag_opinions": "2026-01-15",
    }


def test_watcher_live_probes_queue_new_ccr_marker(tmp_path: Path) -> None:
    """Live probe evidence can move a source directly into the guarded queue."""

    seed_root(tmp_path)
    pages = {
        "https://www.sos.state.co.us/CCR/Welcome.do": (
            "The Code of Colorado Regulations is current with administrative rules "
            "effective on or before 07/20/2026."
        ),
        "https://www.sos.state.co.us/CCR/RegisterHome.do": "June 25, 2026 49 CR 12",
        "https://www.colorado.gov/governor/executive-orders": "2026 Executive Orders",
        "https://coprrr.colorado.gov/": "Released October 15, 2025",
        "https://coag.gov/attorney-general-opinions/": "",
    }

    dashboard = build_source_update_watcher_dashboard(
        tmp_path,
        live_probes=True,
        fetch_text=pages.__getitem__,
    )

    ccr = next(item for item in dashboard.items if item.source_id == "ccr")
    assert ccr.change_status == NEW_DATA
    assert ccr.latest_observed_marker == "2026-07-20"
    assert any(item.source_id == "ccr" for item in dashboard.download_queue)


def test_watcher_records_live_probe_failures(tmp_path: Path) -> None:
    """Live probe failures are visible but do not create download queue items."""

    seed_root(tmp_path)

    dashboard = build_source_update_watcher_dashboard(
        tmp_path,
        live_probes=True,
        fetch_text=lambda _url: (_ for _ in ()).throw(RuntimeError("network blocked")),
    )

    ccr = next(item for item in dashboard.items if item.source_id == "ccr")
    assert ccr.change_status == LIVE_PROBE_FAILED
    assert ccr.download_status == "probe_failed"
    assert all(item.source_id != "ccr" for item in dashboard.download_queue)
