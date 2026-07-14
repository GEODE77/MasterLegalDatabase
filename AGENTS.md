# AGENTS.md — Project Geode

> **This file is the persistent project-level context for all AI coding agents
> (Codex, Copilot, etc.). It is read automatically at the start of every task.
> Do not delete or rename this file.**
>
> For full system architecture, reference `@docs/GEODE_SYSTEM_DESIGN.md`.

---

## A1. Project Identity

**Project Geode** is a backend-first regulatory intelligence database that
organizes Colorado legal authority for **AI-first consumption**, search,
retrieval, ingestion, and agentic workflows.

Geode serves AI models and agents through structured source data, deterministic
retrieval, hard verification gates, and cited outputs. The jurisdiction model is
the full Colorado authority hierarchy:

1. State authority
2. County authority
3. Municipal authority

The current corpus is state-first and expands outward to county and municipal
authority without changing the backend-first design.

The platform ingests, normalizes, cross-links, and quality-scores these current
state authority layers:

| # | Layer | Content | Source Owner | Est. Records |
|---|-------|---------|-------------|-------------|
| 1 | **Colorado Revised Statutes (CRS)** | 44 titles of codified statutory law | Office of Legislative Legal Services | ~10,000+ sections |
| 2 | **Code of Colorado Regulations (CCR)** | Administrative rules from 100+ agencies under ~20 departments | Secretary of State | ~4,000+ rules |
| 3 | **Legislation (Bills)** | All bills in the General Assembly, 2010-present; historical back to 1861 | General Assembly + LegiScan | ~8,000+ bills |
| 4 | **Colorado Register / eDocket** | Rulemaking notices: proposed, adopted, amended, repealed | Secretary of State | ~2,000+ notices |
| 5 | **Executive Orders** | Governor's executive orders | Governor's Office | ~200+ orders |
| 6 | **Supplementary** | AG opinions, COPRRR sunrise/sunset reviews, session laws | AG Office, DORA | ~700+ documents |

**AI models and agents are the primary consumers of this data.** Every design
decision - file format, naming, storage architecture, chunking, validation, and
retrieval - optimizes for machine readability, structured evidence, and
agentic workflows.

### Orchestration Engine

Geode's centerpiece is the orchestration engine: a deterministic Python
pipeline that sits between an LLM and the Geode knowledge layer.

The orchestration engine runs in six ordered layers:

1. **Input & Interpretation** - normalize the question, identify legal domain,
   jurisdiction, entities, time period, and ambiguity.
2. **Planning & Retrieval** - decide which indexes, corpus files, crosswalks,
   timelines, and source records must be read.
3. **Evidence & Reasoning** - assemble verified source passages, structured
   records, relationship chains, and absence findings.
4. **Accuracy & Verification (hard gates)** - enforce grounding, citation
   verification, currency, completeness, faithfulness, and absence verification
   in code.
5. **Output Control** - require structured, cited, confidence-rated output and
   reject answers that do not match the answer contract.
6. **Platform & Operations** - manage freshness, audit logs, reliance policy,
   source registries, snapshots, and review workflows across the system.

Markdown instructions and prompts are soft orchestration. They guide the model,
but they do not enforce accuracy. Code gates are hard orchestration and are
authoritative. The LLM is the writer and synthesizer; it is not the
decision-maker. Geode is the knowledge layer. The orchestration engine decides
what evidence is needed and verifies whether the answer is allowed.

### Long-Term Vision

- **Legislative agents** check whether a proposed bill duplicates or conflicts
  with existing law or regulation.
- **Compliance agents** identify which state, county, and municipal authorities
  may apply to a fact pattern.
- **Research agents** identify regulatory overlap, compliance burden, and
  reform opportunities.
- **Policy agents** measure practical regulatory impact - costs, burdens,
  reporting duties, permitting complexity, and authority conflicts.

### Immediate Focus: Step 1

Step 1 remains **data collection and structuring**: finding, downloading,
converting, and storing Colorado legal data in a machine-readable,
AI-optimized format with quality assurance at every stage. The current
direction adds the deterministic orchestration engine that turns the knowledge
layer into verified, cited, confidence-rated answers for AI and agent use.

---

## A2. Repository Structure

**Hybrid structural/chronological design:**
- Living documents (statutes, regulations) → **structural** by title/department
- Event documents (bills, rulemaking, exec orders) → **chronological** by year/decade
- MASTER_TIMELINE_INDEX provides unified chronological overlay across all layers

```
Project_Geode/
|
|-- AGENTS.md                                <-- YOU ARE HERE
|-- docs/
|   +-- GEODE_SYSTEM_DESIGN.md               <-- Full architecture reference
|
|-- _CONTROL_PLANE/                           <-- AI reads this FIRST
|   |-- MASTER_MANIFEST.json                  What data exists, where, how fresh
|   |-- MASTER_SCHEMA.json                    Entity type definitions (12 types)
|   |-- ONTOLOGY.json                         Controlled vocabulary for tags
|   |-- AGENCY_REGISTRY.json                  All CO departments + agencies
|   |-- SOURCE_REGISTRY.json                  Every data source with URL/format
|   |-- MASTER_TIMELINE_INDEX.jsonl            Unified chronological spine
|   |-- UPDATE_LOG.jsonl                      Append-only change log
|   +-- README.md                             Human-readable overview
|
|-- 01_Statutes_CRS/                          STRUCTURAL (by Title)
|   |-- _index.jsonl                          Metadata-only index
|   |-- _meta/                                JSON metadata sidecars
|   |   +-- crs_title_01_meta.jsonl ... crs_title_44_meta.jsonl
|   +-- crs_title_01.md ... crs_title_44.md   Full legal text in Markdown
|
|-- 02_Regulations_CCR/                       STRUCTURAL (by Department)
|   |-- _index.jsonl
|   |-- _meta/ccr_dept_*_meta.jsonl
|   +-- ccr_dept_*.md
|
|-- 03_Legislation/                           CHRONOLOGICAL (by Year)
|   |-- _index.jsonl
|   +-- {1861..2026}/bills_{year}.jsonl
|
|-- 04_Rulemaking/                            CHRONOLOGICAL (Year + Quarter)
|   |-- _index.jsonl
|   +-- {2012..2026}/register_{year}_Q{1..4}.jsonl
|
|-- 05_Executive_Orders/                      CHRONOLOGICAL (by Decade)
|   |-- _index.jsonl
|   +-- {1876_1899 .. 2020_2029}/exec_orders_*.jsonl
|
|-- 06_Session_Laws/                          CHRONOLOGICAL (by Year)
|   |-- _index.jsonl
|   +-- {1861..2025}/session_laws_{year}.jsonl
|
|-- 07_Supplementary/                         CHRONOLOGICAL (by Decade)
|   |-- _index.jsonl
|   |-- ag_opinions/ag_opinions_*.jsonl
|   +-- coprrr_reviews/coprrr_*.jsonl
|
|-- _CROSSWALKS/                              Relationship engine
|   |-- regulation_to_statute.jsonl            CCR rule -> enabling CRS section(s)
|   |-- statute_to_regulation.jsonl            CRS section -> all regs underneath
|   |-- bill_to_statute.jsonl                  Bill -> CRS sections amended/created/repealed
|   |-- rulemaking_to_regulation.jsonl         Register notice -> CCR rule modified
|   |-- agency_to_statute.jsonl                Agency -> enabling/governing statutes
|   +-- amendment_history.jsonl                Chronological chain per entity
|
|-- _RAW_ARCHIVE/                             Source of truth (NEVER modify)
|   |-- ccr/        Original PDFs/DOCX from SOS
|   |-- crs/        Original SGML from General Assembly
|   |-- legiscan/   Original JSON from LegiScan API
|   |-- register/   Colorado Register publications
|   |-- exec_orders/ Executive order PDFs
|   +-- supplementary/
|
|-- _QUARANTINE/                              Failed extractions awaiting review
|   +-- quarantine_log.jsonl
|
|-- _SNAPSHOTS/                               Point-in-time versioning
|   +-- snapshot_YYYY-MM-DD/manifest.json
|
|-- geode/                                    Python package
|   |-- __init__.py
|   |-- orchestration/ Deterministic query planning, retrieval, verification,
|   |                  output-control policies, and hard gates
|   |-- schemas/       Pydantic models (models.py, validators.py)
|   |-- extractors/    regex_patterns.py, structure_parser.py,
|   |                  citation_extractor.py, fingerprint.py,
|   |                  converter.py, llm_extractor.py, ensemble.py
|   |-- connectors/    ccr_scraper.py, legiscan_client.py,
|   |                  register_scraper.py, crs_parser.py,
|   |                  exec_orders_scraper.py, orchestrator.py
|   |-- pipeline/      critique.py, writer.py, runner.py
|   |-- validation/    checks.py, integrity.py
|   |-- scoring/       confidence.py
|   +-- utils/         file_io.py, hashing.py, logging.py
|
+-- tests/
    |-- test_schemas.py, test_extractors.py, test_pipeline.py,
    |   test_validation.py, test_scoring.py
    |-- adversarial/   Edge case + red team tests
    +-- fixtures/      Sample documents for testing
```

---

## A3. File Format Conventions

### Format by Content Type

| Content Type | Format | Location | Rationale |
|-------------|--------|----------|-----------|
| Legal text (statutes, regulations) | **Markdown** (`.md`) with YAML frontmatter | Layer root dirs | Token-efficient, natural chunking on headings, best for LLM comprehension |
| Structured metadata (per-record) | **JSONL** (`.jsonl`) | `_meta/` subdirectories | Machine-parseable, streamable, one record per line |
| Index files | **JSONL** (`.jsonl`) | `_index.jsonl` per layer | Lightweight metadata-only; AI loads first to filter/search |
| Control plane files | **JSON** (`.json`) | `_CONTROL_PLANE/` | Single-document structured data |
| Crosswalk files | **JSONL** (`.jsonl`) | `_CROSSWALKS/` | Pure relationship records, streamable |
| Event data (bills, rulemaking, exec orders) | **JSONL** (`.jsonl`) | Chronological folders | Discrete events with timestamps |
| Raw source files | **Original format** | `_RAW_ARCHIVE/` | Never converted — cryptographic source of truth |

### Naming Conventions

| File Type | Pattern | Example |
|-----------|---------|---------|
| Statute Markdown | `crs_title_{NN}.md` | `crs_title_25.md` |
| Regulation Markdown | `ccr_dept_{slug}.md` | `ccr_dept_public_health.md` |
| Metadata sidecars | `{stem}_meta.jsonl` | `crs_title_25_meta.jsonl` |
| Chronological data | `{type}_{year}.jsonl` | `bills_2023.jsonl` |
| Crosswalks | `{source}_to_{target}.jsonl` | `regulation_to_statute.jsonl` |

### ID Conventions

| Entity Type | ID Format | Example |
|------------|-----------|---------|
| Statute section | `CRS-{title}-{article}-{section}` | `CRS-25-7-109` |
| Regulation rule | `{dept_num}_CCR_{number}` | `5_CCR_1001-9` |
| Rule unit | `{reg_id}_{part}_{section}_{seq}` | `6_CCR_1007-2_2.1_1` |
| Bill | `{type}{session}-{number}` | `SB23-016` |
| Session law | `SL-{year}-{chapter}` | `SL-2023-142` |
| Executive order | `EO-{year}-{number}` | `EO-2025-003` |
| AG opinion | `AGO-{year}-{number}` | `AGO-2024-001` |
| Agency | `{dept_code}_{agency_abbrev}` | `CDPHE_AQCC` |
| Timeline event | `TE-{ISO_date}-{seq}` | `TE-2023-07-01-001` |
| Rulemaking notice | `RM-{year}-{edocket}` | `RM-2023-00847` |

**All dates:** ISO 8601 — `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ` (UTC)

---

## A4. Coding Standards

- **Python 3.11+** required
- **Type hints** on ALL function signatures and return types
- **Docstrings** on ALL public functions/classes (Google style)
- **Line length:** 100 characters max
- **Imports:** `isort` ordering (stdlib > third-party > local)
- **Naming:** snake_case functions/variables, PascalCase classes, UPPER_SNAKE constants

### Key Libraries

| Purpose | Library |
|---------|---------|
| Schema validation | `pydantic >= 2.0` |
| File paths | `pathlib` (no `os.path`) |
| PDF extraction | `pymupdf` (fitz) |
| DOCX parsing | `python-docx` |
| Markdown conversion | `markitdown` |
| High-accuracy PDF | `marker` (optional, GPU) |
| HTTP | `httpx` |
| LLM (OpenAI) | `openai` |
| LLM (Anthropic) | `anthropic` |
| Logging | `logging` (stdlib) — **no print()** |
| Testing | `pytest` + `pytest-cov` (>= 90% coverage) |

### File I/O Rules

- **Streaming reads:** JSONL read line-by-line via generator. Never `json.load()` entire file.
- **Atomic writes:** Write to `{file}.tmp`, then `os.replace()` to final name.
- **Encoding:** UTF-8, no BOM.
- **JSONL:** One JSON object per line. No trailing commas. No blank lines.
- **Markdown:** YAML frontmatter between `---`. Headings: `#` Title > `##` Article > `###` Part > `####` Section.

---

## A5. Non-Negotiable Rules (The Geode Laws)

These **MUST NEVER be violated**, regardless of task or context.

### Data Integrity Rules

1. **NEVER modify files in `_RAW_ARCHIVE/`.** Written once at download, never touched again.
2. **NEVER write a record without schema validation.** Every record validates via Pydantic first.
3. **NEVER invent data.** Cannot extract? Set to `null` with `"confidence": 0.0`.
4. **NEVER overwrite without archiving.** Previous version goes to `_SNAPSHOTS/` first.
5. **ALL source URLs must be real** — official CO government sites or authorized providers.

### The Geode Constitution (8 Extraction Principles)

These govern ALL AI-assisted extraction. Embed in every LLM prompt and judge prompt.

> **PRINCIPLE 1 — SOURCE FIDELITY**
>
> Every claim in the extraction must be traceable to a specific passage in the
> source document. If it cannot be traced, it must be removed. No inference,
> assumption, or general knowledge.

> **PRINCIPLE 2 — COMPLETENESS OVER BREVITY**
>
> It is better to include a requirement that seems minor than to omit one that
> could matter. Every obligation, prohibition, exception, deadline, and reporting
> requirement must be captured.

> **PRINCIPLE 3 — EXCEPTION PRESERVATION**
>
> Exceptions and exemptions are as important as obligations. If a rule says
> "except as provided in (2)(c)", that exception must be explicitly captured and
> linked. Missing an exception can cause someone to believe they must comply when
> they are actually exempt.

> **PRINCIPLE 4 — CITATION COMPLETENESS**
>
> Every statutory citation (C.R.S.), regulatory reference (CCR), and federal
> reference (CFR/USC) must be captured in canonical form, even if only mentioned
> in passing. Implicit references ("the department as defined in article 7")
> count and must be resolved.

> **PRINCIPLE 5 — NO INTERPRETATION**
>
> The extraction must reflect what the law SAYS, not what it might MEAN. Do not
> add implications, inferences, or interpretive commentary. If the statute is
> ambiguous, preserve the ambiguity.

> **PRINCIPLE 6 — ATOMICITY**
>
> Each rule unit must contain exactly ONE obligation, prohibition, or permission.
> If a section contains three requirements, it must produce three rule units.

> **PRINCIPLE 7 — TEMPORAL PRECISION**
>
> All dates, deadlines, and effective dates must be captured exactly as stated.
> Do not convert relative dates ("within 30 days") to absolute dates.

> **PRINCIPLE 8 — ENTITY CLARITY**
>
> The regulated entity must be stated specifically enough that a reader can
> determine whether they are covered. "All persons who own or operate a solid
> waste facility" is acceptable. "Relevant parties" is not — use the source
> document's actual language.

---

## A6. Testing & Validation Commands

```bash
# Full test suite with coverage
pytest tests/ -v --cov=geode --cov-report=term-missing

# Validate specific layer or all layers
python -m geode.validate --layer 02_Regulations_CCR
python -m geode.validate --layer all

# Cross-layer integrity checks
python -m geode.integrity_check

# Run enhancement pipeline on single document
python -m geode.pipeline.run --input _RAW_ARCHIVE/ccr/example.docx --output 02_Regulations_CCR/

# Freshness report
python -m geode.freshness_report

# Adversarial spot-checks
pytest tests/adversarial/ -v
```

| Command | What It Validates | When |
|---------|------------------|------|
| `pytest tests/` | Unit tests for all modules | Every code change |
| `geode.validate --layer all` | Schema compliance for every record | Every ingestion |
| `geode.integrity_check` | ID uniqueness, referential integrity, orphans, tag/summary coverage | Monthly |
| `geode.pipeline.run` | Full 8-layer pipeline on one document | Testing new docs |
| `geode.freshness_report` | Staleness vs. policy thresholds per layer | Weekly |
| `pytest tests/adversarial/` | Ground truth, edge cases, consistency, coherence, Q&A | After pipeline changes |

---

## A7. Quick Reference: AI Retrieval Pattern

The orchestration engine should perform this retrieval sequence. The LLM should
not choose sources on its own or answer from memory.

```
Step 1: Read MASTER_MANIFEST.json          (~2 KB)    -> Know what exists
Step 2: Read relevant _index.jsonl          (~2-5 MB)  -> Filter/search records
Step 3: Read specific .md content file      (~1-15 MB) -> Get full legal text
Step 4: Read _meta/*.jsonl sidecar          (~1-10 MB) -> Get structured metadata
Step 5: Read _CROSSWALKS/*.jsonl            (~500 KB)  -> Get relationships
Step 6: Read TIMELINE_INDEX (if temporal)   (~1 MB)    -> Get chronology
```

**The AI never loads the entire database.** Any query reads at most ~15-20 MB
from a ~500+ MB corpus (0.01-0.04%). The orchestration engine must also verify
that cited records were actually retrieved and that missing coverage is stated
as missing instead of filled by inference.

### Query Type Routing

| Query Type | Example | Steps | Chunk Level |
|-----------|---------|-------|------------|
| Exact citation | "What does CRS 25-7-109 say?" | 1 -> 3 (direct ID lookup) | Level 1 (full text) |
| Compliance check | "What permits does a manufacturer need?" | 1 -> 2 -> 3 -> 5 | Level 3 then 2 |
| Legislative history | "How has air quality law changed since 2020?" | 1 -> 6 -> 5 -> 3 | Timeline + Crosswalk |
| Overlap detection | "Do any regs duplicate CRS Title 25?" | 1 -> 5 -> 2 -> 4 | Crosswalk + Level 2 |
| Broad discovery | "What laws affect energy?" | 1 -> 2 (filter by tag) -> 3 | Level 3 (summaries) |

---

*This file is the foundation of Project Geode's backend-first AI architecture.*
*For complete system design, see `docs/GEODE_SYSTEM_DESIGN.md`.*

*Last updated: 2026-07-14*
*Maintained by: Project Geode team*
