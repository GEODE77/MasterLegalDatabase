"""Pipeline integration tests."""

from __future__ import annotations

import shutil
from pathlib import Path

from geode.pipeline.run import run_crs_pipeline
from geode.utils.file_io import iter_jsonl, load_json


def test_crs_pipeline_writes_markdown_metadata_index_and_manifest(
    project_root: Path,
    crs_fixture_path: Path,
) -> None:
    """The CRS fixture pipeline writes all expected output contracts."""

    archive_input = project_root / "_RAW_ARCHIVE" / "crs" / "crs_title_25_fixture.txt"
    shutil.copyfile(crs_fixture_path, archive_input)
    outputs = run_crs_pipeline(project_root, archive_input, "25", 2025)

    title_path = project_root / "01_Statutes_CRS" / "crs_title_25.md"
    meta_path = project_root / "01_Statutes_CRS" / "_meta" / "crs_title_25_meta.jsonl"
    index_path = project_root / "01_Statutes_CRS" / "_index.jsonl"
    manifest_path = project_root / "_CONTROL_PLANE" / "MASTER_MANIFEST.json"
    log_path = project_root / "_CONTROL_PLANE" / "UPDATE_LOG.jsonl"

    assert title_path in outputs
    assert title_path.read_text(encoding="utf-8").startswith("---\n")
    metadata_rows = list(iter_jsonl(meta_path))
    index_rows = list(iter_jsonl(index_path))
    assert len(metadata_rows) == 2
    assert metadata_rows[0]["entity_type"] == "statute_section"
    assert metadata_rows[0]["id"] == "CRS-25-7-109"
    assert "entity_id" not in metadata_rows[0]
    assert "full_text" in metadata_rows[0]
    assert metadata_rows[0]["confidence"]["overall"] == 1.0
    assert len(index_rows) == 2
    assert index_rows[0]["id"] == "CRS-25-7-109"
    manifest = load_json(manifest_path)
    crs_layer = next(
        layer for layer in manifest["data_layers"] if layer["id"] == "01_Statutes_CRS"
    )
    assert crs_layer["record_count"] == 2
    assert len(list(iter_jsonl(log_path))) == 1
