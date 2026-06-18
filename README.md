# Project Geode

Project Geode is an AI-first regulatory intelligence backend for Colorado legal
authority. This first milestone establishes the repository foundation, control
plane, validation commands, and a fixture-first Colorado Revised Statutes (CRS)
ingestion path.

## Getting Started

Project Geode is built sample-first. Install the package, generate deterministic
sample bills, and validate the pipeline before connecting live Colorado General
Assembly downloads.

Install the local package:

```powershell
pip install -e .
```

Generate and seed sample data:

```powershell
python scripts/generate_sample_data.py --seed
```

Run the full sample pipeline:

```powershell
python -m geode.pipeline.run --sample
```

Preview a run without executing stages:

```powershell
python -m geode.pipeline.run --sample --dry-run
```

Run on live Colorado bill PDFs only when ready:

```powershell
python -m geode.pipeline.run --scrape --session 2025a
```

## Current Milestone

- Python 3.11+ package skeleton under `geode/`
- Pydantic v2 schemas for the 12 master-design entity types and operational records
- Expanded control plane for schema, ontology, sources, agencies, crosswalks, and timeline
- Safe file I/O helpers for UTF-8, atomic writes, JSONL streaming, snapshots,
  and raw archive write protection
- CRS fixture parser and pipeline writer
- Validation and integrity CLI modules
- Offline 8-layer pipeline contracts for deterministic extraction,
  provider-neutral LLM responses, ensemble decisions, critique scorecards,
  validation gates, and routing
- Pytest coverage for schemas, extraction, writing, pipeline, and validation

## Setup

Install Python 3.11+ and git, then create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

For the deterministic bill pipeline modules, install the pipeline requirements:

```powershell
pip install -r requirements.txt
```

For hardened public-site scraping, including optional Chrome TLS
impersonation for Colorado Secretary of State CCR downloads, install the
scraping extra:

```powershell
pip install -e ".[scraping]"
```

## Commands

Foundation and CRS control-plane commands:

```powershell
python -m geode.pipeline.run --layer crs `
  --input _RAW_ARCHIVE\crs\sample.txt `
  --title 25 `
  --publication-year 2025
python -m geode.validate --layer 01_Statutes_CRS
python -m geode.validate --layer all
python -m geode.integrity_check
pytest tests/ -v --cov=geode --cov-report=term-missing
```

Bulk source-download commands:

```powershell
$env:GEODE_DATA_ROOT = "C:\GeodeData"
python -m geode.connectors.run --connectors ccr --root $env:GEODE_DATA_ROOT --delay 1 --http-max-retries 4
python -m geode.connectors.run --connectors ccr,colorado_register --root $env:GEODE_DATA_ROOT
python -m geode.connectors.run --connectors all --root $env:GEODE_DATA_ROOT --delay 1 --discovery-delay 0.25
python -m geode.connectors.run --connectors ccr --root $env:GEODE_DATA_ROOT --max-downloads 100 --delay 1
```

After `pip install -e .`, the equivalent console script is:

```powershell
geode-bulk-download --connectors ccr,colorado_register --root $env:GEODE_DATA_ROOT
```

Use `python -m geode.connectors.run --help` for all runtime options. The
bulk-download entry point writes raw source artifacts under `_RAW_ARCHIVE/`,
connector manifests beside those artifacts, failure manifests when item
downloads fail, and `_CONTROL_PLANE/BULK_DOWNLOAD_QUALITY_REPORT.json` unless
`--no-quality-report` is passed. LegiScan downloads require `LEGISCAN_API_KEY`
or `--legiscan-api-key`. Use `--delay` for item-download pacing,
`--discovery-delay` for CCR browse-page pacing, and `--max-downloads` to cap
non-skipped download attempts per connector in a resumable batch.

`geode.connectors.run` is the operational entry point for raw source bulk
downloads. The direct connector functions remain available for tests and
programmatic use, while `geode.pipeline.run` and `run_pipeline.py` remain the
separate bill/CRS processing pipeline commands.

### Storage Boundary

Source code, schemas, tests, docs, fixtures, taxonomies, and curated control
plane files belong in Git. Generated bulk artifacts belong in a data root,
preferably outside the source checkout and outside OneDrive or other sync
folders for large live runs. The ignored generated paths include
`_RAW_ARCHIVE/`, `_SNAPSHOTS/`, `_CONTROL_PLANE/BULK_DOWNLOAD_QUALITY_REPORT.json`,
`data/raw_pdfs/`, `data/extracted_text/`, `data/sample/`, and
`data/structured_output/`. The tracked `.gitkeep` files keep expected local
directories visible without committing run output.

Bill pipeline commands:

```powershell
python run_pipeline.py --sample
python run_pipeline.py --sample --dry-run
python run_pipeline.py --scrape --session 2025a
python run_pipeline.py --start-stage 3 --end-stage 7
```

Colorado Secretary of State fetch diagnostics:

```powershell
python scripts/diagnose_fetch.py https://www.sos.state.co.us/
python scripts/diagnose_fetch.py "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=3154"
```

Live downloads are opt-in. The default workflow is to validate with sample data
before running `--scrape`.

## Pipeline Stages

Project Geode's bill pipeline has seven numbered deterministic stages plus one
optional live-download stage. No stage makes LLM API calls.

Optional Stage 0: **SCRAPE**
Downloads bill PDFs from the Colorado General Assembly. This stage only runs
when `--scrape` is passed and requires `--session`, for example `2025a`.

Stage 1: **EXTRACT**
Converts PDFs in `data/raw_pdfs/` to raw extracted text JSON in
`data/extracted_text/`. The extractor uses `pdfplumber` first and PyMuPDF as a
fallback.

Stage 2: **PARSE**
Parses bill structure with deterministic regex and rule-based logic: bill
number, title, sponsors, numbered sections, CRS references, effective dates,
and appropriations.

Stage 3: **ENRICH**
Extracts additional entities from parsed bills, including committees, dates,
fiscal impact, penalties, and definitions.

Stage 4: **VALIDATE**
Runs JSON schema validation plus completeness and integrity checks. The stage
writes `validation_report.json`.

Stage 5: **GRAPH**
Builds a cross-reference network where bills are linked by shared CRS
references. Outputs include `bill_graph.json` and `crs_title_index.json`.

Stage 6: **FORMAT**
Writes final AI-readable Markdown or JSON files to
`data/structured_output/bills/`.

Stage 7: **TAG**
Runs deterministic industry tagging using CRS-based NAICS mappings. Outputs
include `industry_index.json` and `theme_index.json`.

## Data Architecture

Project Geode separates canonical legal documents from query and relationship
surfaces.

Layer 1 is the numbered corpus directories. These hold canonical documents and
metadata for each legal authority layer:

- `01_Statutes_CRS/`
- `02_Regulations_CCR/`
- `03_Legislation/`
- `04_Rulemaking/`
- `05_Executive_Orders/`
- `06_Session_Laws/`
- `07_Supplementary/`

Layer 2 is `_INDICES/`. It is the query layer for derived lookups such as
`industry_index.json` and `theme_index.json`. The bill pipeline also writes
stage-local index artifacts under `data/structured_output/indices/` while the
system is being tested with generated bills.

`_CROSSWALKS/` stores linkages between statutes, regulations, bills, agencies,
rule units, and other entities. `_CONTROL_PLANE/` stores the manifest, master
schema, ontology, source registry, agency registry, update log, and timeline
index. `taxonomies/` stores static NAICS and CRS reference tables used by
deterministic tagging.

Sample data lives in `data/sample/`. It is generated by
`scripts/generate_sample_data.py` and mimics extractor output, so the parser,
entity extractor, validator, graph builder, formatter, and tagger can be tested
without downloading real bills.

AI agents should use the system in this order:

1. Read `_INDICES/industry_index.json` for NAICS-based lookup.
2. Read `_INDICES/theme_index.json` for theme-based lookup.
3. Read the relevant bill files or layer documents for full content.
4. Read `_CROSSWALKS/` to find related statutes, regulations, agencies, and bills.

```text
01_Statutes_CRS/                          Layer 1 canonical CRS documents
02_Regulations_CCR/                       Layer 1 canonical CCR documents
03_Legislation/                           Layer 1 canonical bill/session data
04_Rulemaking/                            Layer 1 canonical rulemaking data
05_Executive_Orders/                      Layer 1 canonical executive orders
06_Session_Laws/                          Layer 1 canonical session laws
07_Supplementary/                         Layer 1 supplementary authorities
_INDICES/
|-- industry_index.json                   NAICS lookup
`-- theme_index.json                      theme lookup
_CROSSWALKS/                              relationship records
_CONTROL_PLANE/                           manifest, schema, ontology, registries
taxonomies/
|-- crs_title_map.json
|-- naics_hierarchy.json
|-- keyword_to_naics.json
`-- committee_to_naics.json
```

## Industry Tagging

Industry tagging is deterministic and NAICS-based. The primary method is CRS
section amendment targeting: bills are tagged according to the CRS titles and
articles they amend or reference. Keyword and committee mappings are secondary
signals, not the core method.

The NAICS hierarchy is represented from 2-digit sector to 3-digit subsector to
4-digit industry group. For example, `31-33` covers manufacturing, while `3271`
identifies clay product and refractory manufacturing.

Each bill receives an applicability scope:

- `universal`: applies across all industries or touches many sectors.
- `broad`: touches several sectors.
- `narrow`: touches one or two sectors.
- `targeted`: touches specific subsectors or industry groups.

Tagging output is written as index data:

- `_INDICES/industry_index.json`: bill to NAICS industries, scope, themes, and confidence.
- `_INDICES/theme_index.json`: theme to bills reverse index.

## Testing

Generate sample data:

```powershell
python scripts/generate_sample_data.py --seed
```

Run tests:

```powershell
pytest tests/
```

Validate the pipeline end-to-end with sample data:

```powershell
python -m geode.pipeline.run --sample
```

Run the complete test suite:

```powershell
pytest tests/
```
