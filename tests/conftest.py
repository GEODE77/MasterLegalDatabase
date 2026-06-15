"""Shared pytest fixtures for Project Geode tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from geode.pipeline.writer import ensure_project_structure


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """Create an isolated Geode project root for tests."""

    ensure_project_structure(tmp_path)
    control = tmp_path / "_CONTROL_PLANE"
    control.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).parents[1]
    for name in (
        "MASTER_SCHEMA.json",
        "ONTOLOGY.json",
        "AGENCY_REGISTRY.json",
        "SOURCE_REGISTRY.json",
        "MASTER_MANIFEST.json",
        "PILOT_TEST_SET.json",
    ):
        shutil.copyfile(repo_root / "_CONTROL_PLANE" / name, control / name)
    (control / "UPDATE_LOG.jsonl").write_text("", encoding="utf-8")
    (control / "MASTER_TIMELINE_INDEX.jsonl").write_text("", encoding="utf-8")
    for layer in (
        "01_Statutes_CRS",
        "02_Regulations_CCR",
        "03_Legislation",
        "04_Rulemaking",
        "05_Executive_Orders",
        "06_Session_Laws",
        "07_Supplementary",
    ):
        (tmp_path / layer).mkdir(parents=True, exist_ok=True)
        (tmp_path / layer / "_index.jsonl").write_text("", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def crs_fixture_path() -> Path:
    """Return the CRS fixture path."""

    return Path(__file__).parent / "fixtures" / "crs" / "crs_title_25_fixture.txt"


@pytest.fixture()
def legiscan_fixture_path() -> Path:
    """Return the LegiScan bill fixture path."""

    return Path(__file__).parent / "fixtures" / "legiscan" / "sb23_016.json"
