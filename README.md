# Project Geode

Project Geode is an AI-first regulatory intelligence backend for Colorado legal
authority. This first milestone establishes the repository foundation, control
plane, validation commands, and a fixture-first Colorado Revised Statutes (CRS)
ingestion path.

## Current Milestone

- Python 3.11+ package skeleton under `geode/`
- Pydantic v2 schemas for the 12 master-design entity types and operational records
- Expanded control plane for schema, ontology, sources, agencies, crosswalks, and timeline
- Safe file I/O helpers for UTF-8, atomic writes, JSONL streaming, snapshots,
  and raw archive write protection
- CRS fixture parser and pipeline writer
- Validation and integrity CLI modules
- Offline 8-layer pipeline contracts for deterministic extraction, provider-neutral
  LLM responses, ensemble decisions, critique scorecards, validation gates, and routing
- Pytest coverage for schemas, extraction, writing, pipeline, and validation

## Setup

Install Python 3.11+ and git, then create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Commands

```powershell
python -m geode.pipeline.run --layer crs --input _RAW_ARCHIVE\crs\sample.txt --title 25 --publication-year 2025
python -m geode.validate --layer 01_Statutes_CRS
python -m geode.validate --layer all
python -m geode.integrity_check
pytest tests/ -v --cov=geode --cov-report=term-missing
```

Live downloads are intentionally out of scope for this milestone. Source
registry entries record verified CRS source pages so acquisition can be added
after the fixture pipeline is stable.
