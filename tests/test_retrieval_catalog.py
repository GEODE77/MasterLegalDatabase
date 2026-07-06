"""Tests for retrieval catalog generation."""

from __future__ import annotations

import json
from pathlib import Path

from geode.pipeline.retrieval_catalog import build_retrieval_catalog, write_retrieval_catalog
from geode.utils.file_io import iter_jsonl


def test_retrieval_catalog_reads_manifest_layer_indexes(tmp_path: Path) -> None:
    """Catalog should summarize layer index records from the manifest."""

    _write_catalog_fixture(tmp_path)

    records, summary = build_retrieval_catalog(tmp_path)

    assert len(records) == 1
    assert records[0].id == "1_CCR_101-1"
    assert records[0].retrieval_text
    assert summary.layer_counts == {"02_Regulations_CCR": 1}


def test_write_retrieval_catalog_outputs_jsonl_and_summary(tmp_path: Path) -> None:
    """Catalog writer should create JSONL and summary files."""

    _write_catalog_fixture(tmp_path)

    summary = write_retrieval_catalog(tmp_path)

    assert summary.records_written == 1
    assert len(list(iter_jsonl(tmp_path / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG.jsonl"))) == 1
    assert (tmp_path / "_CONTROL_PLANE" / "RETRIEVAL_CATALOG_SUMMARY.json").exists()


def _write_catalog_fixture(root: Path) -> None:
    """Write minimal manifest and layer index."""

    control = root / "_CONTROL_PLANE"
    layer = root / "02_Regulations_CCR"
    control.mkdir()
    layer.mkdir()
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps(
            {
                "data_layers": [
                    {
                        "id": "02_Regulations_CCR",
                        "index_file": "02_Regulations_CCR/_index.jsonl",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (layer / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "1_CCR_101-1",
                "entity_type": "regulation_rule",
                "title": "Test Rule",
                "citation": "1 CCR 101-1",
                "tags": ["test"],
                "confidence": 0.9,
            }
        )
        + "\n",
        encoding="utf-8",
    )
