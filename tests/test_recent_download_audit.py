"""Recent download audit tests."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.recent_download_audit import (
    FAIL,
    PASS,
    WARN,
    combine_statuses,
    corpus_usability_signal,
    recent_layer_ids,
)


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


def test_corpus_usability_signal_uses_current_manifest_and_retrieval_catalog(
    tmp_path: Path,
) -> None:
    """Corpus signal should not use stale hard-coded record counts."""

    control = tmp_path / "_CONTROL_PLANE"
    control.mkdir()
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps({"data_layers": [{"id": "05_Executive_Orders", "record_count": 535}]}),
        encoding="utf-8",
    )
    (control / "RETRIEVAL_CATALOG_SUMMARY.json").write_text(
        json.dumps({"records_written": 535}),
        encoding="utf-8",
    )
    (control / "CORPUS_USABILITY_AUDIT.json").write_text(
        json.dumps({"total_index_records_checked": 534, "issue_count": 0}),
        encoding="utf-8",
    )

    signal = corpus_usability_signal(tmp_path)

    assert signal.status == WARN
    assert "535" in signal.detail
    assert "stale" in signal.detail
