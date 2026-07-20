from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from geode.utils.file_io import RawArchiveWriteError
from geode.web.db import CorpusRepository
from geode.web.index import build_index


def test_build_index_serves_entities_search_relations_and_timeline(tmp_path: Path) -> None:
    root = _write_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"

    result = build_index(root=root, database_path=database_path, rebuild=True)

    assert result.entity_count == 1
    assert result.alias_count >= 3
    assert result.chunk_count >= 1
    assert result.relation_count == 1
    assert result.timeline_count == 1

    repository = CorpusRepository(database_path)
    entity = repository.resolve_entity("CRS 25-7-109")

    assert entity is not None
    assert entity.geode_id == "CRS-25-7-109"
    assert entity.title == "Emission Control Regulations"
    assert entity.layer == "01_Statutes_CRS"

    results = repository.search_entities("promulgate rules")
    assert [result.entity.geode_id for result in results] == ["CRS-25-7-109"]
    assert results[0].match_reason == "text matched"

    chunks = repository.list_chunks("CRS-25-7-109")
    assert chunks
    assert "commission shall promulgate rules" in chunks[0].text

    relations = repository.list_relations("CRS-25-7-109")
    assert len(relations) == 1
    assert relations[0].source_geode_id == "5_CCR_1001-9"
    assert relations[0].relationship == "authorized_by"

    timeline = repository.list_timeline_events("CRS-25-7-109")
    assert len(timeline) == 1
    assert timeline[0].event_type == "bill_signed"

    source_versions = repository.list_source_versions("CRS-25-7-109")
    assert len(source_versions) == 1
    assert source_versions[0].version_label == "current"
    assert source_versions[0].sha256 == entity.sha256


def test_build_index_is_idempotent_for_same_corpus(tmp_path: Path) -> None:
    root = _write_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"

    first = build_index(root=root, database_path=database_path, rebuild=True)
    second = build_index(root=root, database_path=database_path, rebuild=True)

    assert first == second
    repository = CorpusRepository(database_path)
    assert repository.latest_index_run() is not None
    assert len(repository.search_entities("CRS 25-7-109")) == 1


def test_build_index_refuses_raw_archive_database_path(tmp_path: Path) -> None:
    root = _write_fixture_corpus(tmp_path)
    raw_database = root / "_RAW_ARCHIVE" / "commons.sqlite3"

    with pytest.raises(RawArchiveWriteError):
        build_index(root=root, database_path=raw_database, rebuild=True)


def test_app_factory_import_does_not_require_fastapi(tmp_path: Path) -> None:
    from geode.web.app import create_app

    if importlib.util.find_spec("fastapi") is None:
        with pytest.raises(RuntimeError, match="FastAPI is not installed"):
            create_app(project_root=tmp_path, database_path=tmp_path / "index.sqlite3")
    else:
        app = create_app(project_root=tmp_path, database_path=tmp_path / "index.sqlite3")
        assert app.title == "Geode Commons Read API"


def _write_fixture_corpus(root: Path) -> Path:
    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps({"project": "Geode", "fixture": True}),
        encoding="utf-8",
    )
    (control / "MASTER_TIMELINE_INDEX.jsonl").write_text(
        json.dumps(
            {
                "id": "TE-2023-07-01-001",
                "date": "2023-07-01",
                "event_type": "bill_signed",
                "entity_id": "CRS-25-7-109",
                "description": "SB23-016 signed and amended CRS 25-7-109.",
                "file_path": "03_Legislation/2023/bills_2023.jsonl",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    statutes = root / "01_Statutes_CRS"
    statutes.mkdir()
    content_path = statutes / "crs_title_25.md"
    content_path.write_text(
        "\n".join(
            [
                "---",
                "id: CRS-25-7-109",
                "citation: CRS 25-7-109",
                "title: Emission Control Regulations",
                "source_url: https://leg.colorado.gov/colorado-revised-statutes",
                "confidence: 0.95",
                "---",
                "# Title 25",
                "#### CRS 25-7-109. Emission control regulations.",
                "The commission shall promulgate rules for emission control.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (statutes / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "CRS-25-7-109",
                "entity_type": "statute_section",
                "citation": "CRS 25-7-109",
                "title": "Emission Control Regulations",
                "content_path": "01_Statutes_CRS/crs_title_25.md",
                "source_url": "https://leg.colorado.gov/colorado-revised-statutes",
                "confidence": {"overall": 0.95},
                "subject_tags": ["environment"],
                "industry_tags": ["31-33"],
                "publication_year": 2026,
                "status": "current",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    crosswalks = root / "_CROSSWALKS"
    crosswalks.mkdir()
    (crosswalks / "regulation_to_statute.jsonl").write_text(
        json.dumps(
            {
                "source_id": "5_CCR_1001-9",
                "source_type": "regulation_rule",
                "target_id": "CRS-25-7-109",
                "target_type": "statute_section",
                "relationship": "authorized_by",
                "confidence": 0.91,
                "source_evidence": "Promulgated pursuant to CRS 25-7-109.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    return root
