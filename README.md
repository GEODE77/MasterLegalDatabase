# Project Geode

Project Geode is a backend-first regulatory intelligence database for Colorado
law and regulation. It is built for AI retrieval, agentic workflows, search,
ingestion, legal data analysis, and source-backed answer generation.

Geode stores official legal source material, normalized metadata, relationship
records, freshness state, provenance, and audit trails. AI systems use those
records through deterministic retrieval and verification layers before any
answer is written.

## Product Direction

Geode is the backend knowledge layer for Colorado legal authority.

Current coverage is state-first:

- Colorado Revised Statutes
- Code of Colorado Regulations
- legislation and bill history
- Colorado Register and rulemaking notices
- executive orders
- session laws
- AG opinions, COPRRR reviews, and other supplementary sources
- county authorities and ordinances (pilot coverage)
- district authorities and policies (school and water-family pilot coverage)

The jurisdiction model expands from state authority to county and municipal
authority. New county and local sources must be added through the same source
registry, schema, ingestion, validation, freshness, and provenance controls used
for state sources.

## Core Architecture

Geode separates source preservation, normalized records, retrieval, and answer
control.

- `_RAW_ARCHIVE/` preserves original source files and must not be modified.
- Numbered corpus directories hold canonical Markdown and JSONL records.
- `_CONTROL_PLANE/` records manifests, schemas, source registries, freshness,
  audits, timelines, and operational state.
- `_CROSSWALKS/` stores relationships between laws, regulations, agencies,
  bills, rulemaking events, and amendments.
- `08_County_Authorities/` and `09_District_Authorities/` store local authority
  identities and normalized local rules.
- `geode/` contains ingestion, parsing, validation, retrieval, search, API, and
  orchestration code.
- `tests/` verifies schemas, ingestion behavior, retrieval, gates, and backend
  operations.

## AI Retrieval Model

AI agents should not choose legal sources from memory. Retrieval follows a fixed
sequence:

1. Read `_CONTROL_PLANE/MASTER_MANIFEST.json`.
2. Search relevant layer indexes and retrieval catalogs.
3. Load only the needed canonical text and metadata sidecars.
4. Traverse `_CROSSWALKS/` for relationships.
5. Check freshness, provenance, and audit state.
6. Pass hard verification gates before producing an answer.

The LLM is the writer and synthesizer. Deterministic Python code decides what
evidence is needed and whether the answer is allowed.

## Ingestion And Normalization

Ingestion starts from official or approved sources, writes raw material into the
archive, converts source formats, extracts structure, validates records, updates
indexes, and records provenance.

Important ingestion rules:

- Preserve raw source files before writing derived records.
- Validate records with schemas before writing.
- Use JSONL for streamable metadata and relationship records.
- Use Markdown for canonical legal text.
- Use atomic writes and snapshots for overwrite protection.
- Record source URLs, retrieval dates, hashes, and confidence.

## Search And Indexing

Geode uses lightweight indexes for discovery and targeted retrieval. Search and
API layers are derived from the canonical corpus and can be rebuilt.

Relevant commands include:

```powershell
geode-search-index --root . --rebuild
geode-api
geode-validate --layer all
geode-integrity-check
```

## Source Freshness And Auditability

Freshness is tracked per source layer. The system distinguishes local freshness
from live official-source refresh. Audit trails are kept for updates, API usage,
key administration, relationship checks, source limitations, review queues, and
remaining work.

Geode should state missing coverage directly. It must not imply that a county,
municipality, source, date range, or legal topic is covered until it appears in
the manifest and has passed validation.

## Setup

Install Python 3.11+ and create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Optional extras:

```powershell
python -m pip install -e ".[api]"
python -m pip install -e ".[scraping]"
```

Run tests:

```powershell
pytest tests/
```

Run validation:

```powershell
python -m geode.validate --layer all
python -m geode.integrity_check
```

## Bulk Source Collection

Use connector commands for controlled source collection:

```powershell
$env:GEODE_DATA_ROOT = "C:\GeodeData"
python -m geode.connectors.run --connectors ccr,colorado_register --root $env:GEODE_DATA_ROOT
python -m geode.connectors.run --connectors all --root $env:GEODE_DATA_ROOT --delay 1 --discovery-delay 0.25
```

LegiScan downloads require `LEGISCAN_API_KEY` or `--legiscan-api-key`.

Generated bulk data should normally live outside the source checkout and outside
sync-managed folders. Source code, schemas, curated docs, tests, and curated
control-plane files belong in Git; large generated outputs do not.

## Current Priority

The next durable work is to strengthen the backend retrieval and orchestration
layer:

- formal retrieval plans
- evidence packet format
- citation and grounding gates
- absence verification
- source freshness checks
- county and municipal source registry expansion
- county and district source collection, geography-aware retrieval, and
  local-to-state crosswalks
- stronger search/indexing over canonical and metadata records
