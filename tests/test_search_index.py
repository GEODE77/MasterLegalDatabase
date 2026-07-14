from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from geode.utils.file_io import RawArchiveWriteError
from geode.search.db import CorpusRepository
from geode.search.detail_index import detail_index
from geode.search.index import build_index
from geode.search.query_index import query_index


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


def test_detail_index_returns_evidence_page_payload(tmp_path: Path) -> None:
    root = _write_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    detail = detail_index(database_path, "CRS-25-7-109")

    assert detail is not None
    assert detail["entity"]["geode_id"] == "CRS-25-7-109"
    assert "commission shall promulgate rules" in detail["chunks"][0]["text"]
    assert detail["relations"][0]["related_id"] == "5_CCR_1001-9"
    assert detail["relations"][0]["direction"] == "inbound"
    assert detail["timeline_events"][0]["event_id"] == "TE-2023-07-01-001"
    assert detail["source_versions"][0]["version_label"] == "current"


def test_build_index_reads_text_from_jsonl_backed_records(tmp_path: Path) -> None:
    root = _write_jsonl_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    detail = detail_index(database_path, "EO-2026-001")

    assert detail is not None
    assert "Declaring a disaster emergency" in detail["chunks"][0]["text"]
    assert "CRS-24-33.5-704" in detail["chunks"][0]["text"]


def test_query_index_respects_explicit_authority_type_intent(tmp_path: Path) -> None:
    root = _write_intent_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    executive_results = query_index(database_path, "executive order", limit=3)
    opinion_results = query_index(database_path, "AG opinion", limit=3)

    assert executive_results[0].id == "EO-2026-001"
    assert executive_results[0].layer == "05_Executive_Orders"
    assert "Matched the requested authority type." in executive_results[0].matchReasons
    assert "Matched the title, citation, ID, or record type." in executive_results[0].matchReasons
    assert opinion_results[0].id == "AGO-2026-001"
    assert opinion_results[0].layer == "07_Supplementary"
    assert "Matched the requested authority type." in opinion_results[0].matchReasons


def test_query_index_prioritizes_operational_compliance_results(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    results = query_index(
        database_path,
        "air permitting obligations for manufacturing",
        limit=3,
    )

    assert results[0].id == "5_CCR_1001-9"
    assert results[0].layer == "02_Regulations_CCR"
    assert results[0].relationshipCount == 1
    assert "Matched an operational topic in the question." in results[0].matchReasons
    assert "Matched obligation or compliance language." in results[0].matchReasons
    assert "Connected to related authority in Geode." in results[0].matchReasons
    assert "CRS-42-2-107" not in [result.id for result in results]


def test_query_index_ignores_human_filler_words_in_operational_questions(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    results = query_index(
        database_path,
        "Which Colorado rules should leadership review before expanding a manufacturing line?",
        limit=3,
    )

    assert results[0].id == "5_CCR_1001-9"
    assert "Matched an operational topic in the question." in results[0].matchReasons


def test_query_index_keeps_exact_citation_priority(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    results = query_index(database_path, "CRS 25-7-109", limit=3)

    assert results[0].id == "CRS-25-7-109"
    assert "Matched a known citation or alias." in results[0].matchReasons


def test_query_index_keeps_exact_ccr_priority_without_alias(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("DELETE FROM aliases WHERE geode_id = ?", ("5_CCR_1001-9",))

    results = query_index(database_path, "5 CCR 1001-9", limit=3)

    assert results[0].id == "5_CCR_1001-9"
    assert "Matched an exact citation or Geode ID." in results[0].matchReasons


def test_build_index_does_not_let_event_alias_replace_core_rule(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    rulemaking = root / "04_Rulemaking"
    rulemaking.mkdir()
    (rulemaking / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "RM-2026-same-citation",
                "entity_type": "rulemaking_notice",
                "citation": "5 CCR 1001-9",
                "title": "5 CCR 1001-9",
                "path": "04_Rulemaking/rulemaking.jsonl",
                "source_url": "https://example.test/rulemaking",
                "confidence": 0.8,
                "publication_year": 2026,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (rulemaking / "rulemaking.jsonl").write_text(
        json.dumps(
            {
                "id": "RM-2026-same-citation",
                "title": "5 CCR 1001-9",
                "summary": "Rulemaking notice for 5 CCR 1001-9.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    repository = CorpusRepository(database_path)
    entity = repository.resolve_entity("5 CCR 1001-9")

    assert entity is not None
    assert entity.geode_id == "5_CCR_1001-9"


def test_query_index_prioritizes_federal_osha_safety_sources(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    _add_federal_osha_fixture(root)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    expectations = {
        "Hazard communication requirements Colorado.": "FED-CFR-29-1910.1200",
        "Compliance requirements for machine guarding.": "FED-CFR-29-1910.212",
        "Rules governing workplace exposure to silica.": "FED-CFR-29-1910.1053",
        "Lockout tagout requirements.": "FED-CFR-29-1910.147",
        "Personal protective equipment rules.": "FED-CFR-29-1910.132",
        "Respirator requirements for dusty production work.": "FED-CFR-29-1910.134",
        "Confined space requirements in manufacturing.": "FED-CFR-29-1910.146",
        "Forklift safety requirements in a production facility.": "FED-CFR-29-1910.178",
        "Hot work requirements in an industrial plant.": "FED-CFR-29-1910.252",
        "Requirements for workplace injury logs.": "FED-CFR-29-1904",
        "OSHA requirements Colorado employers.": "FED-USC-29-654",
    }

    for query, expected_id in expectations.items():
        results = query_index(database_path, query, limit=3)
        assert results[0].id == expected_id
        assert results[0].entityType == "federal_standard"


def test_query_index_diversifies_broad_manufacturing_questions(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    _add_multidomain_fixture(root)
    _add_federal_osha_fixture(root)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    results = query_index(
        database_path,
        "Manufacturing change affecting dust, wastewater, waste disposal, hourly workers, and contractor safety.",
        limit=8,
    )
    result_ids = [result.id for result in results]

    assert any(result_id.startswith("5_CCR_1001") for result_id in result_ids)
    assert any(result_id.startswith("5_CCR_1002") for result_id in result_ids)
    assert any(result_id.startswith("6_CCR_1007") for result_id in result_ids)
    assert any(result_id.startswith("7_CCR_1103") for result_id in result_ids)
    assert any(result_id.startswith("FED-") for result_id in result_ids)


def test_query_index_keeps_environmental_coverage_for_runtime_changes(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    _add_multidomain_fixture(root)
    _add_federal_osha_fixture(root)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    results = query_index(
        database_path,
        (
            "Increasing production by extending equipment runtime may trigger permit, "
            "reporting, wage-hour, safety, and inspection obligations."
        ),
        limit=8,
    )
    result_ids = [result.id for result in results]

    assert any(result_id.startswith("5_CCR_1001") for result_id in result_ids)
    assert any(result_id.startswith("5_CCR_1002") for result_id in result_ids)
    assert any(result_id.startswith("6_CCR_1007") for result_id in result_ids)
    assert any(result_id.startswith("7_CCR_1103") for result_id in result_ids)
    assert any(result_id.startswith("FED-") for result_id in result_ids)


def test_query_index_keeps_air_permits_with_specific_guarding_terms(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    _add_multidomain_fixture(root)
    _add_federal_osha_fixture(root)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    results = query_index(
        database_path,
        (
            "Automation increases output and creates equipment guarding, final wage, "
            "discrimination, production-related permit, and record obligations."
        ),
        limit=8,
    )
    result_ids = [result.id for result in results]

    assert any(result_id.startswith("5_CCR_1001") for result_id in result_ids)
    assert any(result_id.startswith("7_CCR_1103") for result_id in result_ids)
    assert any(result_id.startswith("FED-") for result_id in result_ids)


def test_query_index_routes_vague_approval_to_operating_permits(tmp_path: Path) -> None:
    root = _write_operational_fixture_corpus(tmp_path)
    _add_multidomain_fixture(root)
    _add_off_target_approval_fixture(root)
    database_path = root / "data" / "structured_output" / "commons.sqlite3"
    build_index(root=root, database_path=database_path, rebuild=True)

    results = query_index(database_path, "we already have approval", limit=6)
    result_ids = [result.id for result in results]

    assert any(result_id.startswith("5_CCR_1001") for result_id in result_ids)
    assert any(result_id.startswith("5_CCR_1002") for result_id in result_ids)
    assert any(result_id.startswith("6_CCR_1007") for result_id in result_ids)
    assert "1_CCR_203-2" not in result_ids
    assert "4_CCR_740-1" not in result_ids


def test_build_index_refuses_raw_archive_database_path(tmp_path: Path) -> None:
    root = _write_fixture_corpus(tmp_path)
    raw_database = root / "_RAW_ARCHIVE" / "commons.sqlite3"

    with pytest.raises(RawArchiveWriteError):
        build_index(root=root, database_path=raw_database, rebuild=True)


def test_app_factory_import_does_not_require_fastapi(tmp_path: Path) -> None:
    from geode.search.app import create_app

    if importlib.util.find_spec("fastapi") is None:
        with pytest.raises(RuntimeError, match="FastAPI is not installed"):
            create_app(project_root=tmp_path, database_path=tmp_path / "index.sqlite3")
    else:
        app = create_app(project_root=tmp_path, database_path=tmp_path / "index.sqlite3")
        assert app.title == "Geode Read API"


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


def _write_jsonl_fixture_corpus(root: Path) -> Path:
    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps({"project": "Geode", "fixture": True}),
        encoding="utf-8",
    )
    (control / "MASTER_TIMELINE_INDEX.jsonl").write_text("", encoding="utf-8")

    orders = root / "05_Executive_Orders" / "2020_2029"
    orders.mkdir(parents=True)
    order_path = orders / "exec_orders_2020_2029.jsonl"
    order_path.write_text(
        json.dumps(
            {
                "id": "EO-2026-001",
                "entity_type": "executive_order",
                "order_number": "D 2026 001",
                "title": "D 2026-001",
                "summary": "Declaring a disaster emergency.",
                "full_text": "Declaring a disaster emergency under CRS-24-33.5-704.",
                "statutes_cited": ["CRS-24-33.5-704"],
                "source_url": "https://example.test/order.pdf",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "05_Executive_Orders" / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "EO-2026-001",
                "entity_type": "executive_order",
                "citation": "D 2026 001",
                "title": "D 2026-001",
                "path": "05_Executive_Orders/2020_2029/exec_orders_2020_2029.jsonl",
                "source_url": "https://example.test/order.pdf",
                "confidence": 0.8,
                "publication_year": 2026,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _write_intent_fixture_corpus(root: Path) -> Path:
    root = _write_jsonl_fixture_corpus(root)
    statutes = root / "01_Statutes_CRS"
    statutes.mkdir(exist_ok=True)
    content_path = statutes / "crs_title_24.md"
    content_path.write_text(
        "\n".join(
            [
                "---",
                "id: CRS-24-1-101",
                "citation: CRS 24-1-101",
                "title: Executive order and opinion references",
                "---",
                "The governor may issue an executive order.",
                "The department may request an advisory opinion.",
            ]
        ),
        encoding="utf-8",
    )
    (statutes / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "CRS-24-1-101",
                "entity_type": "statute_section",
                "citation": "CRS 24-1-101",
                "title": "Executive order and opinion references",
                "content_path": "01_Statutes_CRS/crs_title_24.md",
                "source_url": "https://example.test/statute",
                "confidence": 0.9,
                "publication_year": 2026,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    supplementary = root / "07_Supplementary" / "ag_opinions"
    supplementary.mkdir(parents=True)
    (root / "07_Supplementary" / "_meta").mkdir(parents=True)
    (supplementary / "ag_opinions_2026.jsonl").write_text(
        json.dumps(
            {
                "id": "AGO-2026-001",
                "entity_type": "ag_opinion",
                "opinion_number": "26-001",
                "title": "Formal AG opinion",
                "summary": "Attorney General opinion on public authority.",
                "source_url": "https://example.test/ag-opinion.pdf",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "07_Supplementary" / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "AGO-2026-001",
                "entity_type": "ag_opinion",
                "citation": "26-001",
                "title": "Formal AG opinion",
                "path": "07_Supplementary/ag_opinions/ag_opinions_2026.jsonl",
                "source_url": "https://example.test/ag-opinion.pdf",
                "confidence": 0.8,
                "publication_year": 2026,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _write_operational_fixture_corpus(root: Path) -> Path:
    control = root / "_CONTROL_PLANE"
    control.mkdir(parents=True)
    (control / "MASTER_MANIFEST.json").write_text(
        json.dumps({"project": "Geode", "fixture": True}),
        encoding="utf-8",
    )
    (control / "MASTER_TIMELINE_INDEX.jsonl").write_text("", encoding="utf-8")

    statutes = root / "01_Statutes_CRS"
    statutes.mkdir()
    (statutes / "crs_title_25.md").write_text(
        "\n".join(
            [
                "---",
                "id: CRS-25-7-109",
                "citation: CRS 25-7-109",
                "title: Air quality authority",
                "---",
                "The commission may adopt air quality rules for industrial facilities.",
            ]
        ),
        encoding="utf-8",
    )
    (statutes / "_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "CRS-25-7-109",
                        "entity_type": "statute_section",
                        "citation": "CRS 25-7-109",
                        "title": "Air quality authority",
                        "content_path": "01_Statutes_CRS/crs_title_25.md",
                        "source_url": "https://example.test/statute",
                        "confidence": 0.9,
                        "publication_year": 2026,
                    }
                ),
                json.dumps(
                    {
                        "id": "CRS-42-2-107",
                        "entity_type": "statute_section",
                        "citation": "CRS 42-2-107",
                        "title": "Repair permit application",
                        "content_path": "01_Statutes_CRS/crs_title_42.md",
                        "source_url": "https://example.test/driver-permit",
                        "confidence": 0.9,
                        "publication_year": 2026,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (statutes / "crs_title_42.md").write_text(
        "\n".join(
            [
                "---",
                "id: CRS-42-2-107",
                "citation: CRS 42-2-107",
                "title: Repair permit application",
                "---",
                "A repair permit application must be filed before the license is issued.",
            ]
        ),
        encoding="utf-8",
    )

    regulations = root / "02_Regulations_CCR"
    rules = regulations / "_rules"
    rules.mkdir(parents=True)
    (rules / "5_CCR_1001-9.md").write_text(
        "\n".join(
            [
                "---",
                "id: 5_CCR_1001-9",
                "citation: 5 CCR 1001-9",
                "title: Air emissions permitting",
                "---",
                "A manufacturing facility shall obtain an air emissions permit before operating.",
                "The facility must keep records and report emissions to the division.",
            ]
        ),
        encoding="utf-8",
    )
    (regulations / "_index.jsonl").write_text(
        json.dumps(
            {
                "id": "5_CCR_1001-9",
                "entity_type": "regulation_rule",
                "citation": "5 CCR 1001-9",
                "title": "Air emissions permitting",
                "path": "02_Regulations_CCR/_rules/5_CCR_1001-9.md",
                "source_url": "https://example.test/rule",
                "confidence": 0.88,
                "publication_year": 2026,
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
                "confidence": 0.9,
                "source_evidence": "Authority for air emissions permitting.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _add_federal_osha_fixture(root: Path) -> None:
    supplementary = root / "07_Supplementary" / "federal_osha"
    supplementary.mkdir(parents=True)
    records = [
        {
            "id": "FED-CFR-29-1910.1200",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.1200",
            "title": "Hazard communication",
            "summary": "OSHA hazard communication standard for chemicals, labels, SDS, and training.",
            "full_text": "OSHA hazard communication hazardous chemicals labels safety data sheets SDS training.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.1200",
        },
        {
            "id": "FED-CFR-29-1910.212",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.212",
            "title": "General requirements for all machines",
            "summary": "OSHA machine guarding standard for points of operation and machine hazards.",
            "full_text": "OSHA machine guarding guard machines point of operation production equipment.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.212",
        },
        {
            "id": "FED-CFR-29-1910.1053",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.1053",
            "title": "Respirable crystalline silica",
            "summary": "OSHA silica standard for workplace exposure to respirable crystalline silica.",
            "full_text": "OSHA silica workplace exposure respirable crystalline silica exposure assessment.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.1053",
        },
        {
            "id": "FED-USC-29-654",
            "entity_type": "federal_standard",
            "citation": "29 U.S.C. 654",
            "title": "Duties of employers and employees",
            "summary": "OSHA employer duties and general duty clause.",
            "full_text": "OSHA employer employers compliance duties general duty clause recognized hazards.",
            "source_url": "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title29-section654&num=0&edition=prelim",
        },
        {
            "id": "FED-CFR-29-1910.147",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.147",
            "title": "The control of hazardous energy (lockout/tagout)",
            "summary": "OSHA lockout/tagout standard for hazardous energy control.",
            "full_text": "OSHA lockout tagout LOTO control of hazardous energy energized machinery.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.147",
        },
        {
            "id": "FED-CFR-29-1910.132",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.132",
            "title": "General requirements - personal protective equipment",
            "summary": "OSHA personal protective equipment standard for PPE and hazard assessment.",
            "full_text": "OSHA PPE personal protective equipment hazard assessment employee protection.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.132",
        },
        {
            "id": "FED-CFR-29-1910.134",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.134",
            "title": "Respiratory protection",
            "summary": "OSHA respiratory protection standard for respirator programs.",
            "full_text": "OSHA respirator respirators respiratory protection dust fumes fit testing.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.134",
        },
        {
            "id": "FED-CFR-29-1910.146",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.146",
            "title": "Permit-required confined spaces",
            "summary": "OSHA permit-required confined space standard for general industry.",
            "full_text": "OSHA confined space confined spaces permit required entry rescue.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.146",
        },
        {
            "id": "FED-CFR-29-1910.178",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.178",
            "title": "Powered industrial trucks",
            "summary": "OSHA powered industrial truck standard for forklift operations.",
            "full_text": "OSHA forklift forklifts powered industrial trucks operator training warehouse.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.178",
        },
        {
            "id": "FED-CFR-29-1910.252",
            "entity_type": "federal_standard",
            "citation": "29 CFR 1910.252",
            "title": "General requirements for welding, cutting, and brazing",
            "summary": "OSHA welding, cutting, and brazing requirements for hot work.",
            "full_text": "OSHA hot work welding cutting brazing fire prevention industrial plant.",
            "source_url": "https://www.ecfr.gov/current/title-29/part-1910/section-1910.252",
        },
        {
            "id": "FED-CFR-29-1904",
            "entity_type": "federal_standard",
            "citation": "29 CFR Part 1904",
            "title": "Recording and reporting occupational injuries and illnesses",
            "summary": "OSHA injury and illness recording and reporting rules.",
            "full_text": "OSHA injury log injury logs workplace injury reporting illness records OSHA 300.",
            "source_url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XVII/part-1904",
        },
    ]
    data_path = supplementary / "osha_standards_2026.jsonl"
    data_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    (root / "07_Supplementary" / "_index.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "id": record["id"],
                    "entity_type": "federal_standard",
                    "citation": record["citation"],
                    "title": record["title"],
                    "path": "07_Supplementary/federal_osha/osha_standards_2026.jsonl",
                    "source_url": record["source_url"],
                    "confidence": 0.92,
                    "publication_year": 2026,
                }
            )
            for record in records
        )
        + "\n",
        encoding="utf-8",
    )


def _add_multidomain_fixture(root: Path) -> None:
    rules = root / "02_Regulations_CCR" / "_rules"
    records = [
        {
            "id": "5_CCR_1002-61",
            "citation": "5 CCR 1002-61",
            "title": "Water discharge permitting",
            "text": "Industrial wastewater discharge stormwater process water permit monitoring records.",
        },
        {
            "id": "6_CCR_1007-3",
            "citation": "6 CCR 1007-3",
            "title": "Hazardous waste generator requirements",
            "text": "Hazardous waste generator disposal accumulation labeling inspection records.",
        },
        {
            "id": "7_CCR_1103-1",
            "citation": "7 CCR 1103-1",
            "title": "Colorado wage order",
            "text": "Hourly employees wages overtime meal rest breaks payroll records.",
        },
    ]
    index_path = root / "02_Regulations_CCR" / "_index.jsonl"
    existing_index = index_path.read_text(encoding="utf-8")
    index_rows = []
    for record in records:
        path = rules / f"{record['id']}.md"
        path.write_text(
            "\n".join(
                [
                    "---",
                    f"id: {record['id']}",
                    f"citation: {record['citation']}",
                    f"title: {record['title']}",
                    "---",
                    record["text"],
                ]
            ),
            encoding="utf-8",
        )
        index_rows.append(
            json.dumps(
                {
                    "id": record["id"],
                    "entity_type": "regulation_rule",
                    "citation": record["citation"],
                    "title": record["title"],
                    "path": f"02_Regulations_CCR/_rules/{record['id']}.md",
                    "source_url": "https://example.test/multidomain",
                    "confidence": 0.88,
                    "publication_year": 2026,
                }
            )
        )
    index_path.write_text(existing_index + "\n".join(index_rows) + "\n", encoding="utf-8")


def _add_off_target_approval_fixture(root: Path) -> None:
    rules = root / "02_Regulations_CCR" / "_rules"
    records = [
        {
            "id": "1_CCR_203-2",
            "citation": "1 CCR 203-2",
            "title": "Liquor festival permits",
            "text": "Liquor festival permit approval by the state licensing authority.",
        },
        {
            "id": "4_CCR_740-1",
            "citation": "4 CCR 740-1",
            "title": "Combative sports promotion permits",
            "text": "Promotion permit approval for a combative sports event.",
        },
    ]
    index_path = root / "02_Regulations_CCR" / "_index.jsonl"
    existing_index = index_path.read_text(encoding="utf-8")
    index_rows = []
    for record in records:
        path = rules / f"{record['id']}.md"
        path.write_text(
            "\n".join(
                [
                    "---",
                    f"id: {record['id']}",
                    f"citation: {record['citation']}",
                    f"title: {record['title']}",
                    "---",
                    record["text"],
                ]
            ),
            encoding="utf-8",
        )
        index_rows.append(
            json.dumps(
                {
                    "id": record["id"],
                    "entity_type": "regulation_rule",
                    "citation": record["citation"],
                    "title": record["title"],
                    "path": f"02_Regulations_CCR/_rules/{record['id']}.md",
                    "source_url": "https://example.test/off-target-approval",
                    "confidence": 0.88,
                    "publication_year": 2026,
                }
            )
        )
    index_path.write_text(existing_index + "\n".join(index_rows) + "\n", encoding="utf-8")
