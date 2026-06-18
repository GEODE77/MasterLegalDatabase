"""Tests for canonical connector raw-archive path helpers."""

from __future__ import annotations

from pathlib import Path

from geode.connectors.archive_paths import (
    ccr_rule_document_path,
    download_manifest_path,
    executive_order_pdf_path,
    failure_manifest_path,
    legiscan_bill_json_path,
    raw_connector_dir,
    register_publication_path,
    temp_path_for,
)


def test_raw_connector_dirs_match_project_layout() -> None:
    """Connector IDs resolve to Project Geode raw archive subdirectories."""

    raw_root = Path("_RAW_ARCHIVE")

    assert raw_connector_dir(raw_root, "ccr") == Path("_RAW_ARCHIVE/ccr")
    assert raw_connector_dir(raw_root, "colorado_register") == Path("_RAW_ARCHIVE/register")
    assert raw_connector_dir(raw_root, "executive_orders") == Path("_RAW_ARCHIVE/exec_orders")
    assert raw_connector_dir(raw_root, "coprrr") == Path("_RAW_ARCHIVE/supplementary/coprrr")


def test_source_artifact_paths_are_stable_and_predictable() -> None:
    """Source item IDs map to deterministic archive artifact filenames."""

    assert ccr_rule_document_path(Path("ccr"), "5_CCR_1001-9", "docx") == Path(
        "ccr/5_CCR_1001-9.docx"
    )
    assert register_publication_path(
        Path("register"),
        "2024-01-10",
        "https://www.sos.state.co.us/pubs/CCR/register_2024-01-10.html?download=1",
    ) == Path("register/register_2024-01-10.html")
    assert executive_order_pdf_path(Path("exec_orders"), "EO-2024-001") == Path(
        "exec_orders/EO-2024-001.pdf"
    )
    assert legiscan_bill_json_path(Path("legiscan"), 2023, 12345) == Path(
        "legiscan/2023/12345.json"
    )


def test_manifest_and_temp_paths_are_standardized() -> None:
    """Manifests and temp files use the same names across connectors."""

    archive_dir = Path("_RAW_ARCHIVE/ccr")
    target = archive_dir / "5_CCR_1001-9.docx"

    assert download_manifest_path(archive_dir) == Path("_RAW_ARCHIVE/ccr/download_manifest.jsonl")
    assert failure_manifest_path(archive_dir) == Path("_RAW_ARCHIVE/ccr/download_failures.jsonl")
    assert temp_path_for(target) == Path("_RAW_ARCHIVE/ccr/5_CCR_1001-9.docx.tmp")
