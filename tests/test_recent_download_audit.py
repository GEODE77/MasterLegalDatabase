"""Recent download audit tests."""

from __future__ import annotations

from geode.pipeline.recent_download_audit import FAIL, PASS, WARN, combine_statuses, recent_layer_ids


def test_recent_layer_ids_include_refreshed_and_pending_freshness_layers() -> None:
    """Audited layers come from refreshed sources and freshness items."""

    manifest = {
        "data_layers": [
            {"id": "01_Statutes_CRS"},
            {"id": "03_Legislation"},
            {"id": "05_Executive_Orders"},
        ]
    }
    freshness = {
        "refreshed_sources": ["03_Legislation"],
        "items": [{"layer_id": "05_Executive_Orders"}],
    }

    assert recent_layer_ids(manifest, freshness) == ["03_Legislation", "05_Executive_Orders"]


def test_combine_statuses_prefers_fail_then_warn() -> None:
    """Failures outrank warnings, and warnings outrank pass."""

    assert combine_statuses([PASS, WARN]) == WARN
    assert combine_statuses([PASS, WARN, FAIL]) == FAIL
    assert combine_statuses([PASS, PASS]) == PASS
