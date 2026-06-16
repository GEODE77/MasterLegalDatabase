# CODEX PHASE PROMPTS — Project Geode Build Plan

> **How to use this file:**
> 1. Copy ONE phase at a time into Codex
> 2. Ensure `AGENTS.md` is at the repo root (Codex reads it automatically)
> 3. Ensure `docs/GEODE_SYSTEM_DESIGN.md` is in place
> 4. When a prompt says 'CONTEXT: @docs/GEODE_SYSTEM_DESIGN.md section BX',
>    Codex will read that file for the detailed specifications
> 5. Use HIGH or EXTRA HIGH reasoning for Phases 1 and 2
> 6. For Phases 2+, consider running `/plan` first to let Codex propose before coding
>
> **Execution order:** Phase 0 -> 1A-1E -> 2A-2K -> 3A-3F -> 4A-4E
> Each phase builds on the outputs of previous phases.

---

# Phase 0: Repository Scaffolding

**GOAL:** Create the complete Project Geode directory structure with all folders,
empty placeholder files, and the foundational configuration.

**CONTEXT:** Read `AGENTS.md` section A2 for the full repository tree. Read
`@docs/GEODE_SYSTEM_DESIGN.md` section B3 for architecture rationale.

**TASK:**

1. Create every directory shown in AGENTS.md A2:
   - `_CONTROL_PLANE/`
   - `01_Statutes_CRS/` with `_meta/` subdirectory
   - `02_Regulations_CCR/` with `_meta/` subdirectory
   - `03_Legislation/` with year subdirectories for 2010-2026
   - `04_Rulemaking/` with year subdirectories for 2012-2026
   - `05_Executive_Orders/` with decade subdirectories (1876_1899, 1900_1949, 1950_1999, 2000_2009, 2010_2019, 2020_2029)
   - `06_Session_Laws/` with year subdirectories for 2010-2026
   - `07_Supplementary/` with `ag_opinions/` and `coprrr_reviews/`
   - `_CROSSWALKS/`
   - `_RAW_ARCHIVE/` with subdirs: ccr/, crs/, legiscan/, register/, exec_orders/, supplementary/
   - `_QUARANTINE/`
   - `_SNAPSHOTS/`
   - `geode/` with subpackages: schemas/, extractors/, connectors/, pipeline/, validation/, scoring/, utils/
   - `tests/` with adversarial/ and fixtures/
   - `docs/`

2. Create empty `_index.jsonl` files in every data layer directory (01 through 07)

3. Create empty placeholder files:
   - `_CONTROL_PLANE/MASTER_MANIFEST.json` -> `{}`
   - `_CONTROL_PLANE/MASTER_SCHEMA.json` -> `{}`
   - `_CONTROL_PLANE/ONTOLOGY.json` -> `{}`
   - `_CONTROL_PLANE/AGENCY_REGISTRY.json` -> `[]`
   - `_CONTROL_PLANE/SOURCE_REGISTRY.json` -> `[]`
   - `_CONTROL_PLANE/MASTER_TIMELINE_INDEX.jsonl` -> empty
   - `_CONTROL_PLANE/UPDATE_LOG.jsonl` -> empty
   - `_CONTROL_PLANE/README.md` -> "# Project Geode Control Plane"
   - All `_CROSSWALKS/*.jsonl` files -> empty (regulation_to_statute, statute_to_regulation, bill_to_statute, rulemaking_to_regulation, agency_to_statute, amendment_history)
   - `_QUARANTINE/quarantine_log.jsonl` -> empty

4. Create `__init__.py` in `geode/` and ALL subpackages

5. Create `pyproject.toml` with project name 'geode', Python >=3.11, placeholder dependencies

**CONSTRAINTS:**
- Follow exact naming conventions from AGENTS.md A3
- UTF-8 encoding on all files
- No synthetic data in placeholders — just empty structures

**DONE WHEN:**
- `find . -type d | sort` shows all expected directories
- All JSON files parse without error
- All Python files import without error
- `tree` output matches AGENTS.md A2 structure

---

# Phase 1A: MASTER_SCHEMA.json

**GOAL:** Generate the complete `_CONTROL_PLANE/MASTER_SCHEMA.json` with formal
JSON Schema definitions for all 12 entity types.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B4 has complete field
specifications, types, required/optional flags, and example records for:
statute_section, regulation_rule, bill, rulemaking_notice, executive_order,
session_law, ag_opinion, coprrr_review, rule_unit, crosswalk_entry,
timeline_event, agency.

**TASK:**
1. Generate `_CONTROL_PLANE/MASTER_SCHEMA.json` using JSON Schema draft 2020-12
2. Include a `$defs` section with all 12 entity type schemas
3. Each schema must have:
   - All fields with correct types and `description` on every property
   - `required` arrays matching section B4
   - `enum` constraints for controlled fields (status, rule_type, notice_type, etc.)
   - `pattern` constraints for ID formats (from AGENTS.md A3 ID Conventions)
   - Date fields with `format: "date"` for ISO 8601
   - A reusable ConfidenceScore `$ref` definition
   - An `examples` array with one complete valid record per type (from B4)

**CONSTRAINTS:**
- Valid JSON Schema draft 2020-12 syntax only
- All enum values must match section B5 (Ontology)
- ID patterns must match AGENTS.md A3 conventions exactly
- File must be valid JSON parseable by any JSON Schema validator

**DONE WHEN:**
- File parses as valid JSON
- All 12 entity types defined with all fields from B4
- Every required field listed in `required` array
- Running a JSON Schema validator against each example passes

---

# Phase 1B: ONTOLOGY.json

**GOAL:** Generate `_CONTROL_PLANE/ONTOLOGY.json` — the full controlled vocabulary.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B5.

**TASK:** Generate with these top-level keys:
1. `subject_tags` — hierarchical object with 14 parent categories, each containing
   a description and children array. 85+ child tags total. Parents: environment,
   public_health, labor_employment, professional_licensing, business_regulation,
   energy, transportation, education, housing, compliance, government_operations,
   technology, agriculture, criminal_justice.
2. `industry_tags` — array of 23 objects with tag, naics_prefix, description
3. `compliance_keywords` — array of 20 strings
4. `rule_type_enum` — 10 values: obligation, prohibition, permission, definition,
   condition, exception, penalty, reporting, standard, procedure
5. `relationship_type_enum` — 10 values: authorized_by, implements, amends,
   creates, repeals, cites, supersedes, modified_by, interprets, reviews
6. `event_type_enum` — 7 values
7. `status_enum` — 9 values: active, repealed, superseded, emergency, expired,
   rescinded, in_committee, signed, vetoed

**CONSTRAINTS:**
- Every tag used anywhere in the system MUST appear in this file
- Subject tags must have parent-child hierarchy
- Industry tags must include NAICS prefixes
- No duplicates within any category

**DONE WHEN:**
- Valid JSON, >= 99 subject tags, >= 23 industry tags, >= 20 compliance keywords
- All enum arrays populated, every child tag has valid parent

---

# Phase 1C: AGENCY_REGISTRY.json

**GOAL:** Generate `_CONTROL_PLANE/AGENCY_REGISTRY.json` — all Colorado
departments and their rulemaking agencies.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` sections B2 and B4 (agency entity).

**TASK:** JSON array of agency objects. Research and include ALL major Colorado
departments that issue regulations via the CCR. The CCR organizes by department number:
- Dept 1 (100s): Agriculture
- Dept 2 (200s): Education
- Dept 3 (300s): Labor and Employment
- Dept 4 (400s): Natural Resources
- Dept 5 (500s/1000s): Public Health and Environment
- Dept 6 (600s): Higher Education
- Dept 7 (700s): Human Services
- Dept 8 (800s): Regulatory Agencies (DORA)
- Dept 9 (900s): Revenue
- Depts 10-20: Corrections, Law, Local Affairs, Military, Personnel,
  Public Safety, Transportation, State, Treasury, Judicial, Early Childhood

For each agency include: entity_type, id (agency_code), agency_name,
agency_abbreviation, department, department_code, ccr_prefix (if known),
enabling_statutes (if known, else null), website_url (if known), notes.

**CONSTRAINTS:**
- ONLY real, verifiable Colorado agency names
- Department codes must match CCR numbering
- Uncertain fields set to null with explanatory note
- Do NOT fabricate agencies

**DONE WHEN:**
- Valid JSON array, all ~20 departments with top-level agencies
- Each entry conforms to agency schema from MASTER_SCHEMA.json

---

# Phase 1D: SOURCE_REGISTRY.json

**GOAL:** Generate `_CONTROL_PLANE/SOURCE_REGISTRY.json` — every data source.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B2.

**TASK:** JSON array, one object per source. For each include:
source_id, source_name, description, owner, url, api_url (or null),
format, access_method (bulk_download|api|scrape|email_request),
access_notes (specific instructions — e.g., CRS: email yelena.love@coleg.gov,
303-866-2295), coverage_start, coverage_end, update_frequency, known_gaps (array),
priority (critical|important|supplementary), target_layer, connector_type,
estimated_records, license, contact.

Include all 7 sources: CRS, CCR, LegiScan, Colorado Register, Executive Orders,
COPRRR, AG Opinions.

**CONSTRAINTS:**
- All URLs must be real, publicly accessible
- CRS contact info included (yelena.love@coleg.gov, 303-866-2295)
- Known gaps reflect actual limitations from our design conversations

**DONE WHEN:** Valid JSON array, all 7 sources, all URLs real, CRS contact included

---

# Phase 1E: MASTER_MANIFEST.json

**GOAL:** Generate the initial `_CONTROL_PLANE/MASTER_MANIFEST.json`.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` sections B6 and B11.

**TASK:** Generate with:
1. `project` metadata: name "Project Geode", description, version "0.1.0", created_date
2. `data_layers` array — one per layer (01-07) with: id, path, entity_type,
   record_count (0), source, format, last_ingested (null), currency (null),
   index_file path, known_gaps, last_checked (null), staleness_days (null), status ("empty")
3. `crosswalks_available` — list all 6 crosswalk filenames
4. `freshness_policy` — from B11: statutes 365/330, regulations 45/30,
   legislation 14/10, rulemaking 20/15, exec_orders 60/45, session_laws 365/330,
   supplementary 120/90
5. `system_info` — pipeline_version "0.1.0", schema_version "1.0", ontology_version "1.0"

**CONSTRAINTS:** Valid JSON, thresholds match B11 exactly, paths match repo structure

**DONE WHEN:** Valid JSON, all 7 layers, freshness policy matches B11, paths correct

---

# Phase 2A: Python Package Setup

**GOAL:** Set up the `geode` Python package with configuration, dependencies, and utilities.

**CONTEXT:** AGENTS.md section A4 (Coding Standards).

**TASK:**
1. `pyproject.toml` — name 'geode', Python >=3.11, dependencies: pydantic>=2.0,
   pymupdf, python-docx, markitdown, httpx, openai, anthropic, orjson.
   Dev deps: pytest, pytest-cov, ruff, mypy. CLI entry points for geode.validate,
   geode.integrity_check, geode.pipeline.run, geode.freshness_report
2. `geode/__init__.py` with `__version__ = '0.1.0'`
3. `__init__.py` in all subpackages
4. `geode/utils/file_io.py`:
   - `read_jsonl(path: Path) -> Iterator[dict]` — streaming line-by-line
   - `write_jsonl(path: Path, records: Iterable[dict])` — atomic (temp+rename)
   - `read_json(path: Path) -> dict`
   - `write_json(path: Path, data: dict)` — atomic
   - `append_jsonl(path: Path, record: dict)` — single-line append
5. `geode/utils/hashing.py`:
   - `compute_sha256(file_path: Path) -> str`
   - `compute_preservation_score(source_text: str, output_text: str) -> dict`
6. `geode/utils/logging.py` — configured logger setup
7. `tests/test_utils.py` — tests for file_io and hashing

**CONSTRAINTS:**
- Type hints on all functions, Google-style docstrings
- pathlib exclusively, streaming JSONL, atomic writes (temp+rename)
- UTF-8 no BOM, logging module not print()

**DONE WHEN:** `pip install -e .` works, `import geode` works, `pytest tests/test_utils.py` passes

---

# Phase 2B: Schema Validation Module

**GOAL:** Pydantic models for all 12 entity types + validation functions.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B4 (all schemas), B5 (enums).

**TASK:**
1. `geode/schemas/models.py` — Pydantic v2 models:
   StatuteSection, RegulationRule, Bill, RulemakingNotice, ExecutiveOrder,
   SessionLaw, AgOpinion, CopRRRReview, RuleUnit, CrosswalkEntry, TimelineEvent, Agency
   Plus: ConfidenceScore, FieldConfidence (reusable)
   Each model: all fields from B4, field_validators for ID patterns, enum constraints
   via Literal/StrEnum, custom validators for date logic, model_config with examples
2. `geode/schemas/validators.py`:
   - `validate_record(data: dict) -> tuple[bool, list[str]]`
   - `validate_layer(layer_path: Path) -> ValidationReport`
3. `tests/test_schemas.py` — test each B4 example validates, test missing required
   fields fail, test invalid IDs fail, test impossible dates fail, test bad tags fail

**CONSTRAINTS:** Pydantic v2 syntax, enums match ONTOLOGY.json, clear error messages

**DONE WHEN:** All 12 models defined, `pytest tests/test_schemas.py` passes >= 90% coverage

---

# Phase 2C: Regex Extraction Module

**GOAL:** Build Layer 1 of the enhancement pipeline — deterministic extraction.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B9, Layer 1.

**TASK:**
1. `geode/extractors/regex_patterns.py` — PATTERNS dict with pre-compiled regexes:
   ccr_number, crs_citation (multiple formats), crs_citation_alt, part_boundary,
   section_number, subsection_number, subsection_letter, subsection_roman,
   subsubsection_letter, defined_term, effective_date, adopted_date,
   cfr_citation, usc_citation, department, agency
   (All patterns listed in B9 Layer 1)
2. `geode/extractors/structure_parser.py`:
   - `parse_structure(markdown_text: str) -> StructureTree` — build hierarchy
     from heading detection + regex numbering
   - `StructureTree` dataclass: Part -> Section -> Subsection nesting
   - `extract_metadata(text: str) -> dict` — run all patterns, return fields
     with confidence flags ('deterministic' or 'needs_llm')
3. `geode/extractors/citation_extractor.py`:
   - `extract_crs_citations(text: str) -> list[Citation]`
   - `extract_ccr_references(text: str) -> list[Citation]`
   - `extract_federal_references(text: str) -> list[Citation]`
   - `extract_defined_terms(text: str) -> list[str]`
   - Citation dataclass: canonical_form, as_written, location, found_by
4. `tests/test_extractors.py` + `tests/fixtures/` with real CO legal text samples
   At least 5 positive and 3 negative cases per pattern

**CONSTRAINTS:** Pre-compiled patterns, handle all CO citation styles from B9,
type hints + docstrings on everything

**DONE WHEN:** Patterns extract correctly from samples, structure parser builds
correct hierarchy, `pytest tests/test_extractors.py` passes

---

# Phase 2D-2E: Source Fingerprinting + Markdown Conversion

**GOAL:** Build Layer 2 (fingerprinting) and the document conversion module.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B9 Layer 2 and section B14.

**TASK:**
1. `geode/extractors/fingerprint.py`:
   - `fingerprint_source(file_path: Path, source_url: str) -> SourceFingerprint`
   - `compute_preservation_score(source_text: str, output_text: str) -> PreservationReport`
   - `verify_integrity(stored_hash: str, file_path: Path) -> bool`
   SourceFingerprint and PreservationReport as Pydantic models
   Preservation threshold: < 0.95 triggers flag
2. `geode/extractors/converter.py`:
   - `select_conversion_path(rule_entry: dict) -> str` — routing from B14:
     DOCX available? -> path_1_docx. Text extractable? -> path_2 (simple: markitdown,
     complex: marker+llm). Otherwise -> path_3_ocr
   - `convert_docx_to_markdown(docx_path: Path) -> ConversionResult`
   - `convert_pdf_to_markdown(pdf_path: Path, use_llm: bool = False) -> ConversionResult`
   - `detect_if_scanned(pdf_path: Path) -> bool`
   ConversionResult: markdown_text, conversion_path, tool_used, preservation_score, fingerprint
3. Tests for both modules

**CONSTRAINTS:** SHA-256 via hashlib, never modify _RAW_ARCHIVE/, graceful fallbacks
if markitdown not installed

**DONE WHEN:** Can fingerprint + verify files, can convert sample DOCX to Markdown,
tests pass

---

# Phase 2F-2G: LLM Extraction + Ensemble Voting

**GOAL:** Build Layers 3 (LLM extraction) and 4 (ensemble voting).

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B9, Layers 3 and 4.

**TASK:**
1. `geode/extractors/llm_extractor.py` — 5 task functions:
   - `extract_structure(markdown, regex_structure, model) -> dict` (Task A)
   - `extract_citations(markdown, regex_citations, model) -> list` (Task B)
   - `decompose_rule_units(markdown, ontology, model) -> list` (Task C)
   - `assign_tags(text, summary, ontology, model) -> dict` (Task D)
   - `generate_summary(markdown, model) -> str` (Task E)
   ALL prompts must embed the Geode Constitution (P1-P8 from AGENTS.md A5).
   Support both 'openai' and 'anthropic' via model parameter.
   Prompt text for each task is specified in B9 Layer 3.
2. `geode/extractors/ensemble.py`:
   - `run_ensemble_extraction(markdown, regex_output) -> EnsembleResult`
     Runs all 5 tasks with TWO models in parallel
   - `compare_exact_fields(field_a, field_b, field_regex) -> FieldResult`
   - `compare_semantic_fields(field_a, field_b) -> FieldResult`
   - `compare_list_fields(list_a, list_b) -> FieldResult`
   - `compare_text_fields(text_a, text_b, source) -> FieldResult`
   Agreement thresholds from B9 Layer 4:
   Exact: both agree=0.99, one+regex=0.90, all differ=quarantine
   Semantic: >0.90=accept, 0.70-0.90=flag, <0.70=quarantine
   Lists: intersection=accept, diff=verify, union of verified
   Text: check grounding, reject ungrounded claims
3. Tests with mocked API responses — NO real API calls in tests

**CONSTRAINTS:** Async-capable, Geode Constitution in all prompts, log all
prompts sent and responses received, mocked tests only

**DONE WHEN:** All 5 prompts match B9 Layer 3, ensemble voting handles agree/disagree/partial,
tests pass without API keys

---

# Phase 2H-2I: Constitutional Critique + Confidence Scoring

**GOAL:** Build Layers 5 (critique) and 7 (scoring/routing).

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B9, Layers 5 and 7.

**TASK:**
1. `geode/pipeline/critique.py`:
   - `GEODE_CONSTITUTION` — all 8 principles as structured constant
   - `JUDGE_DIMENSIONS` — all 19 dimensions:
     M1-M5 (Source fidelity, Citation accuracy, Agency attribution, Temporal accuracy, Cross-ref completeness)
     D1-D5 (Term completeness, Definition accuracy, Scope correctness, Exception coverage, Dependency tracking)
     R1-R9 (Rule type, Entity ID, Action completeness, Condition fidelity, Logical structure, Granularity, Penalty linkage, Summary accuracy, No hallucination)
   - `critique(extraction, source_markdown, model) -> ScoreCard` — evaluate 19 dims
   - `repair(extraction, source_markdown, score_card, model) -> dict` — fix failures
   - `run_critique_loop(extraction, source_markdown, max_iterations=3) -> CritiqueResult`
     Upstream-first repair: Cycle 1 (M1,M2,M4,M5), Cycle 2 (D1-D5,R6), Cycle 3 (R1-R5,R7-R9)
     If R9 < 5 after 3 cycles -> REJECT. Still failing -> QUARANTINE.
   ScoreCard and CritiqueResult as Pydantic models
2. `geode/scoring/confidence.py`:
   - `compute_field_confidence(source_score, critique_score, validation_score, token_prob) -> float`
     Formula: 0.30*source + 0.25*critique + 0.25*validation + 0.20*token_prob
     source_score: 1.0=regex, 0.9=ensemble, 0.7=one+regex, 0.4=repaired, 0.1=uncertain
   - `compute_record_confidence(field_scores: dict) -> float`
     Weighted mean, 2x on: ccr_number, enabling_statutes, effective_date, rule_type
   - `route_record(confidence: float, has_hallucination: bool) -> str`
     >= 0.85 -> "auto_accept", 0.60-0.84 -> "flag_accept",
     < 0.60 -> "quarantine", hallucination -> "reject"
3. Tests with mocked LLM responses

**CONSTRAINTS:** Constitution verbatim in prompts, max 3 iterations (no infinite loops),
R9<5 = mandatory reject, formula exact match to B9 Layer 7

**DONE WHEN:** Critique evaluates 19 dims, repair respects ordering + cap,
confidence formula correct, routing correct at boundaries, tests pass

---

# Phase 2J-2K: Storage Writer + Validation Checks

**GOAL:** Build the atomic storage writer and all validation/integrity checks.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` sections B6, B10, B11, B12.

**TASK:**
1. `geode/pipeline/writer.py`:
   - `write_record(record: dict, layer_config: dict) -> WriteResult`
     Performs ALL 7 steps atomically (all succeed or all roll back):
     a. Archive old version to _SNAPSHOTS/ (if updating)
     b. Append/update Markdown content file
     c. Append/update JSONL metadata sidecar
     d. Update _index.jsonl
     e. Update relevant crosswalk files in _CROSSWALKS/
     f. Append to MASTER_TIMELINE_INDEX.jsonl
     g. Append to UPDATE_LOG.jsonl and refresh MASTER_MANIFEST.json
   - `write_to_quarantine(record: dict, reason: str)`
2. `geode/validation/checks.py` — 6 ingestion checks:
   - check_schema_compliance (Pydantic validation)
   - check_id_uniqueness (scan index files)
   - check_referential_integrity (cited IDs exist)
   - check_date_logic (effective >= adopted, not future, not pre-1876)
   - check_text_integrity (non-empty + HALLUCINATION CANARY: summary must not
     cite statutes absent from full_text)
   - check_cross_record_consistency (agency in registry, under correct dept)
   - `run_all_checks(record: dict) -> ValidationResult`
3. `geode/validation/integrity.py` — 5 monthly checks:
   - check_orphan_regulations, check_dead_crosswalks, check_tag_coverage,
     check_summary_coverage, check_crosswalk_completeness
   - `run_integrity_check() -> IntegrityReport`
4. CLI entry points: `python -m geode.validate --layer {name}`,
   `python -m geode.integrity_check`
5. Tests for writer (mock filesystem) and validation modules

**CONSTRAINTS:** Atomic writes (temp+rename), hallucination canary mandatory,
writer rolls back on any failure

**DONE WHEN:** Writer creates all 7 outputs, checks work on valid + invalid records,
CLI runs on empty repo, tests pass

---

# Phase 3A: CCR Scraper Connector

**GOAL:** Build the connector that downloads all CCR rules from the Secretary of State.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` sections B2 (CCR source) and B14 (prefer DOCX).

**TASK:**
1. `geode/connectors/ccr_scraper.py`:
   - `discover_all_rules() -> list[CCRRuleEntry]` — crawl CCR browse pages,
     catalog every rule: CCR number, department, agency, PDF URL, DOCX URL (if available)
   - `download_rule(entry: CCRRuleEntry, archive_dir: Path) -> Path`
     — download DOCX (preferred) or PDF to _RAW_ARCHIVE/ccr/
   - `download_all_rules(archive_dir, delay=1.0) -> DownloadReport`
     — full download with rate limiting, progress tracking, resume support
2. Requirements:
   - Always prefer DOCX over PDF when both available
   - SHA-256 hash immediately after download
   - Log every download to `_RAW_ARCHIVE/ccr/download_manifest.jsonl`
   - Retry 3x on HTTP errors, then log + skip
   - Configurable delay between requests (default 1 sec)
   - Resume: check manifest for already-downloaded, skip those
3. Tests with mocked HTTP responses

**CONSTRAINTS:** Rate limiting mandatory, never re-download if hash matches,
all downloads fingerprinted

**DONE WHEN:** Can discover rules from at least one department, download 5+ samples,
all logged + fingerprinted, tests pass

---

# Phase 3B: LegiScan Client Connector

**GOAL:** Pull all Colorado legislative data from LegiScan API.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` section B2 (LegiScan).

**TASK:**
1. `geode/connectors/legiscan_client.py`:
   - `get_session_list() -> list[Session]`
   - `get_session_bills(session_id: int) -> list[BillSummary]`
   - `get_bill_detail(bill_id: int) -> BillDetail`
   - `download_session(session_year, archive_dir) -> list[dict]`
   - `download_all_sessions(archive_dir) -> DownloadReport`
2. `geode/connectors/legiscan_transformer.py`:
   - `transform_bill(raw_bill: dict, ontology: dict) -> dict`
     Maps LegiScan JSON -> Geode bill schema
     Extracts statute references from bill text
     Maps LegiScan subjects to Geode ontology tags
3. Tests with sample LegiScan JSON fixtures (no API key for tests)

**CONSTRAINTS:** API key from env var LEGISCAN_API_KEY, respect rate limits,
raw JSON to _RAW_ARCHIVE/legiscan/, transformer output validates against bill schema

**DONE WHEN:** Transformer produces valid bill records from fixture data, tests pass

---

# Phase 3C-3F: Remaining Connectors + Orchestrator

**GOAL:** Build remaining source connectors and the download orchestrator.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` sections B2 and B10.

**TASK:**
1. `geode/connectors/register_scraper.py` — Colorado Register
   Scrape twice-monthly publications, extract rulemaking notices with:
   notice_type, ccr_rule_affected, agency, hearing_date, effective_date, summary
2. `geode/connectors/crs_parser.py` — CRS SGML parser
   Parse bulk SGML: Title > Article > Part > Section
   Output Markdown files per title + JSONL metadata
3. `geode/connectors/exec_orders_scraper.py` — Executive Orders
   Scrape Governor's website, download PDFs, extract text + metadata
4. `geode/connectors/orchestrator.py`:
   - `run_full_download(config: dict) -> OrchestratorReport`
   - Coordinates all connectors in sequence
   - Manages _RAW_ARCHIVE/ organization
   - Tracks progress, handles failures gracefully
   - Supports running individual connectors or all together
5. Tests for each connector with mocked responses

**CONSTRAINTS:** Each connector independently runnable, all raw files to
_RAW_ARCHIVE/ subdirs, all fingerprinted + logged

**DONE WHEN:** Each processes sample data, orchestrator runs, tests pass

---

# Phase 4A-4E: Pilot Ingestion Run

**GOAL:** Run the full enhancement pipeline on 10-15 real CCR rules to validate
the entire system end-to-end.

**CONTEXT:** `@docs/GEODE_SYSTEM_DESIGN.md` sections B9, B10, B12.

**TASK:**

**4A — Select Pilot Set:**
Pick 10-15 CCR rules from different departments for breadth:
- 2-3 from Public Health and Environment (dept 1000)
- 2-3 from Labor and Employment (dept 300)
- 2-3 from Natural Resources (dept 400)
- 2-3 from Regulatory Agencies / DORA (dept 800)
- 2-3 from Revenue (dept 900)
Include mix of DOCX and PDF sources. Include 1 short and 1 long (100+ pages).

**4B — Run Full Pipeline:**
For each pilot rule, execute all 8 layers:
1. Layer 1: Deterministic extraction (regex + structure)
2. Layer 2: Source fingerprinting (hash chain)
3. Layers 3+4: Dual-model LLM extraction + ensemble voting
4. Layer 5: Constitutional critique with up to 3 repair cycles
5. Layer 6: Deterministic validation (all 6 checks)
6. Layer 7: Confidence scoring and routing

**4C — Generate All Outputs:**
For each passing rule, write:
- Markdown content file in 02_Regulations_CCR/
- JSONL metadata sidecar in 02_Regulations_CCR/_meta/
- Index entry in 02_Regulations_CCR/_index.jsonl
- Crosswalk entries (regulation_to_statute, agency_to_statute)
- Timeline event(s) in MASTER_TIMELINE_INDEX.jsonl
- Update log entry in UPDATE_LOG.jsonl
- Updated MASTER_MANIFEST.json with new counts

**4D — Run Integrity Checks:**
- `python -m geode.validate --layer 02_Regulations_CCR`
- `python -m geode.integrity_check`
- Verify: no schema errors, no orphan references, all crosswalks valid

**4E — Quality Report:**
Generate report showing:
- Records processed vs auto-accepted vs flagged vs quarantined
- Average confidence scores per field type
- Most common extraction errors
- Conversion path distribution (DOCX vs PDF)
- Time per record through pipeline
- Total API cost for pilot run
- Recommendations for pipeline adjustments before bulk ingestion

**CONSTRAINTS:**
- Use REAL CCR documents downloaded from SOS website
- Run the FULL pipeline — do not skip layers
- Log everything for audit trail
- Quarantined records must have clear failure reasons

**DONE WHEN:**
- 10-15 regulation records in the database with full metadata
- All crosswalk entries created and valid
- Integrity check passes with no critical errors
- Quality report generated with actionable metrics
- Auto-accept rate >= 70% (if lower, document why and recommend fixes)

---

*End of CODEX_PHASE_PROMPTS.md*
*16 phases total: Phase 0 + Phase 1A-1E + Phase 2A-2K + Phase 3A-3F + Phase 4A-4E*
*Generated: 2026-06-12*