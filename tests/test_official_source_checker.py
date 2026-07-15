"""Official source checker tests."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from geode.pipeline.official_source_checker import (
    BLOCKED,
    CONFIG_REQUIRED,
    NEWER_MARKER,
    NO_NEWER_MARKER,
    REACHABLE,
    LiveFetchResult,
    build_official_source_check_report,
    _fetch_registered_source,
    _source_marker,
    _status_from_fetch,
    write_official_source_check_report,
)


def write_json(path: Path, payload: object) -> None:
    """Write a compact JSON fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_root(tmp_path: Path) -> None:
    """Seed minimal source registry and manifest fixtures."""

    write_json(
        tmp_path / "_CONTROL_PLANE" / "SOURCE_REGISTRY.json",
        [
            {
                "source_id": "crs",
                "source_name": "Colorado Revised Statutes",
                "owner": "Office of Legislative Legal Services",
                "url": "https://leg.colorado.gov/colorado-revised-statutes",
                "api_url": None,
                "access_method": "email_request",
                "target_layer": "01_Statutes_CRS",
            },
            {
                "source_id": "ccr",
                "source_name": "Code of Colorado Regulations",
                "owner": "Colorado Secretary of State",
                "url": "https://www.sos.state.co.us/CCR/Welcome.do",
                "api_url": None,
                "access_method": "scrape",
                "target_layer": "02_Regulations_CCR",
            },
            {
                "source_id": "legiscan",
                "source_name": "LegiScan Colorado",
                "owner": "LegiScan",
                "url": "https://legiscan.com/CO",
                "api_url": "https://api.legiscan.com/",
                "access_method": "api",
                "target_layer": "03_Legislation",
            },
            {
                "source_id": "federal_osha",
                "source_name": "Federal OSHA Standards",
                "owner": "Occupational Safety and Health Administration",
                "url": "https://www.ecfr.gov/current/title-29/part-1910",
                "api_url": None,
                "access_method": "official_web_reference",
                "target_layer": "07_Supplementary",
            },
        ],
    )
    write_json(
        tmp_path / "_CONTROL_PLANE" / "MASTER_MANIFEST.json",
        {
            "data_layers": [
                {
                    "id": "01_Statutes_CRS",
                    "source": "crs",
                    "currency": "2025",
                    "last_checked": "2026-07-02",
                },
                {
                    "id": "02_Regulations_CCR",
                    "source": "ccr",
                    "last_checked": "2026-07-08",
                },
                {
                    "id": "03_Legislation",
                    "source": "legiscan",
                    "last_checked": "2026-07-06",
                },
                {
                    "id": "07_Supplementary",
                    "source": "federal_osha",
                    "last_checked": "2026-07-08",
                },
            ]
        },
    )


def fetch_fixture(source: dict[str, object]) -> LiveFetchResult:
    """Return source-specific fake live pages."""

    source_id = str(source["source_id"])
    pages = {
        "crs": "Colorado Revised Statutes hosted by LexisNexis",
        "ccr": (
            "The Code of Colorado Regulations is current with administrative rules "
            "effective on or before 07/10/2026."
        ),
        "legiscan": "Colorado Legislature | 2026 | Regular Session | Adjourned Sine Die",
        "federal_osha": "Federal OSHA eCFR page updated 2026-07-01",
    }
    return LiveFetchResult(
        requested_url=str(source["url"]),
        final_url=str(source["url"]),
        status_code=200,
        text=pages[source_id],
        fetched_at=datetime(2026, 7, 14, tzinfo=UTC),
    )


def test_checker_covers_every_registered_source(tmp_path: Path) -> None:
    """Every source registry row becomes one check row."""

    seed_root(tmp_path)

    report = build_official_source_check_report(tmp_path, fetch_source=fetch_fixture)

    assert report.sources_checked == 4
    assert {item.source_id for item in report.items} == {
        "crs",
        "ccr",
        "legiscan",
        "federal_osha",
    }


def test_checker_detects_newer_and_not_newer_markers(tmp_path: Path) -> None:
    """Visible source markers are compared with local manifest markers."""

    seed_root(tmp_path)

    report = build_official_source_check_report(tmp_path, fetch_source=fetch_fixture)
    statuses = {item.source_id: item.status for item in report.items}

    assert statuses["ccr"] == NEWER_MARKER
    assert statuses["legiscan"] == NO_NEWER_MARKER
    assert statuses["crs"] == REACHABLE


def test_checker_marks_challenge_pages_as_blocked(tmp_path: Path) -> None:
    """Challenge pages are not treated as normal reachable source evidence."""

    seed_root(tmp_path)

    def blocked_fetch(source: dict[str, object]) -> LiveFetchResult:
        return LiveFetchResult(
            requested_url=str(source["url"]),
            final_url="https://unblock.federalregister.gov",
            status_code=200,
            text="captcha challenge",
            fetched_at=datetime(2026, 7, 14, tzinfo=UTC),
        )

    report = build_official_source_check_report(tmp_path, fetch_source=blocked_fetch)

    assert all(item.status == BLOCKED for item in report.items)
    assert report.blocked_sources == 4


def test_checker_writes_report_rows_and_docs(tmp_path: Path) -> None:
    """Writing creates control-plane JSON, JSONL rows, and an audit document."""

    seed_root(tmp_path)

    report = write_official_source_check_report(tmp_path, fetch_source=fetch_fixture)

    assert report.sources_checked == 4
    assert (tmp_path / "_CONTROL_PLANE" / "OFFICIAL_SOURCE_CHECK_REPORT.json").exists()
    assert (tmp_path / "_CONTROL_PLANE" / "OFFICIAL_SOURCE_CHECKS.jsonl").exists()
    assert (
        tmp_path / "docs" / "audits" / f"OFFICIAL_SOURCE_CHECK_REPORT_{date.today().isoformat()}.md"
    ).exists()


def test_fetch_uses_ag_opinions_fallback(monkeypatch: object) -> None:
    """The AG checker retries the current opinions page when the registry URL is stale."""

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.urls: list[str] = []

        def get(self, url: str) -> object:
            self.urls.append(url)
            if url == "https://coag.gov/opinions/":
                raise RuntimeError("404")
            return type(
                "Response",
                (),
                {
                    "url": url,
                    "status_code": 200,
                    "text": "2026 Formal AG Opinions",
                },
            )()

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "geode.pipeline.official_source_checker.GeodeHttpClient",
        FakeClient,
    )

    result = _fetch_registered_source(
        {
            "source_id": "ag_opinions",
            "url": "https://coag.gov/opinions/",
        }
    )

    assert result.final_url == "https://coag.gov/attorney-general-opinions/"
    assert result.status_code == 200


def test_fetch_uses_legiscan_api_path_without_leaking_key(monkeypatch: object) -> None:
    """The LegiScan checker uses the API path and redacts the key in report-facing URLs."""

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.urls: list[str] = []

        def get(self, url: str) -> object:
            self.urls.append(url)
            return type(
                "Response",
                (),
                {
                    "url": url,
                    "status_code": 200,
                    "text": json.dumps(
                        {
                            "status": "OK",
                            "sessions": [
                                {"year_start": 2025, "year_end": 2025},
                                {"year_start": 2026, "year_end": 2026},
                            ],
                        }
                    ),
                },
            )()

        def close(self) -> None:
            return None

    monkeypatch.setenv("LEGISCAN_API_KEY", "secret-test-key")
    monkeypatch.setattr(
        "geode.pipeline.official_source_checker.GeodeHttpClient",
        FakeClient,
    )

    result = _fetch_registered_source(
        {
            "source_id": "legiscan",
            "url": "https://legiscan.com/CO",
            "api_url": "https://api.legiscan.com/",
        }
    )

    assert result.status_code == 200
    assert "op=getSessionList" in result.requested_url
    assert "state=CO" in result.requested_url
    assert "secret-test-key" not in result.requested_url
    assert "secret-test-key" not in result.final_url
    assert _source_marker("legiscan", result.text) == "2026-01-01"


def test_fetch_marks_legiscan_api_key_as_configuration_required(
    monkeypatch: object,
) -> None:
    """Missing LegiScan credentials produce a clear setup status, not a block."""

    monkeypatch.delenv("LEGISCAN_API_KEY", raising=False)

    result = _fetch_registered_source(
        {
            "source_id": "legiscan",
            "url": "https://legiscan.com/CO",
            "api_url": "https://api.legiscan.com/",
        }
    )

    assert result.status_code is None
    assert result.error is not None
    assert _status_from_fetch(result, None, "2026-07-06") == CONFIG_REQUIRED


def test_edocket_search_page_is_reachability_only() -> None:
    """Dates inside the eDocket agency list are not treated as freshness markers."""

    assert _source_marker("colorado_edocket", "Rules removed 07/11/2019") is None
