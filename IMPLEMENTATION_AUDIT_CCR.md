# CCR Implementation Audit

Audited: 2026-06-22

## Scope

This audit inspected the actual repository before implementation work for CCR scraping,
HTTP helpers, CLI entry points, output directories, parsing/normalization, and tests.
The initial audit did not change source code or data files; implementation notes below
record subsequent CCR acquisition changes.

## Completed Changes

- Standardized `geode.net.http_client` around a reusable `GeodeHttpClient` and
  `GeodeHttpClientConfig` while preserving the legacy `build_session` and `polite_get`
  helpers for existing connectors.
- Added stable request/response facades, retry/throttle/response hooks, optional
  referer and conditional GET headers, optional status/content validation, and explicit
  HTTP exception types.
- Routed CCR scraper outbound requests through the shared HTTP client abstraction,
  including SOS session priming and injected fake/test clients.
- Added focused tests for the reusable client hooks, validation errors, retry context,
  and CCR scraper compatibility with the shared client.

## Completed Changes - CCR Blocking Hardening

- Adjusted the shared HTTP client so standard `requests` sessions advertise only
  `gzip, deflate`, while `curl_cffi` sessions retain the fuller Chrome-like encoding
  profile.
- Kept CCR acquisition on the existing SOS navigation sequence: SOS home or CCR
  welcome warm-up, CCR welcome, department list, agency page, rule-info page, and
  document fetch with referers carried between linked resources.
- Added `CCRBlockedResponseError` and CCR-specific response validation for hard 403s,
  access-denied/challenge body markers, HTML/text returned where a PDF/DOC/DOCX was
  expected, empty bodies, and unexpected content types.
- Added forensic logging for blocked/unexpected CCR responses: requested URL, final
  URL, referer, status, key response headers, content type, and a bounded body preview.
- Preserved failed download manifest rows while keeping blocked failures distinguishable
  for single-rule callers and diagnostics.
- Upgraded `scripts/diagnose_fetch.py` with `--ccr-chain` to walk one live CCR discovery
  path and report the exact step that fails.
- Added focused tests for CCR blocked HTML rule pages, blocked document fetches, and
  stack-compatible `Accept-Encoding` defaults.
- Live validation with `python scripts/diagnose_fetch.py --ccr-chain --max-retries 1
  --base-delay 0 --timeout-seconds 10` succeeded outside the sandbox on 2026-06-22:
  SOS home, CCR welcome, department list, first agency page, first rule-info page,
  and first PDF fetch all returned 200.

## Completed Changes - CCR Robust Downloading

- Added configurable CCR pacing jitter for document downloads and discovery pages,
  backed by the shared `GeodeThrottle` helper in `geode.net.http_client`.
- Made retry jitter explicitly configurable through `GeodeHttpClientConfig`,
  `polite_get`, the CCR downloader, orchestrator config, and the bulk-download CLI.
- Changed CCR request retry classification so hard `403` responses are not treated as
  ordinary transient statuses; CCR retries `429` and selected `5xx` responses, while
  `403` enters the blocked-response workflow.
- Added CCR failure accounting fields: `retry_count`, `network_attempts`,
  `permanent_failed`, and `blocked`.
- Added resumable run artifacts under the CCR archive directory:
  `download_failures.jsonl`, `download_checkpoint.json`, `download_summary.json`, and
  `download_run_log.jsonl`.
- Added focused tests for retry accounting, blocked failure artifacts, summary and
  checkpoint writing, CLI option parsing, and orchestrator option propagation.

## Completed Changes - CCR Phased Bulk Workflow

- Added `geode.connectors.ccr_bulk` with a dedicated CLI path:
  `python -m geode.connectors.ccr_bulk` or `geode-ccr-bulk`.
- Added a phased CCR workflow: index discovery, detail/document URL resolution,
  optional content retrieval, normalized queue metadata, and artifact writing.
- Added `iter_rule_index_entries` to stream CCR agency-page index records separately
  from rule-info resolution and document retrieval.
- Added stable queue item IDs using canonical CCR IDs such as `5_CCR_1001-9`.
- Added append-only bulk artifacts under `_RAW_ARCHIVE/ccr`:
  `ccr_bulk_queue.jsonl`, `ccr_bulk_checkpoint.json`, `ccr_bulk_summary.json`, and
  `ccr_bulk_failures.jsonl`.
- Added CLI controls for `--max-items`, `--resume` / `--no-resume`,
  `--discovery-only` / `--dry-run`, `--output-root`, `--log-level`,
  discovery/download delays, jitter, timeout, retries, and retry backoff.
- Added deterministic tests for discovery-only queue creation, resume retrieval from
  an existing resolved queue, and CLI scaling controls.
- Live validation on 2026-06-22 succeeded for a controlled 100-item discovery-only run:
  100 indexed, 100 resolved, 0 failed, 0 blocked, with queue/checkpoint/summary
  artifacts written under a temp output root.

## Completed Changes - CCR Normalized Acquisition Dataset

- Added `geode.connectors.ccr_dataset` to rebuild a normalized CCR acquisition dataset
  from `ccr_bulk_queue.jsonl` and `download_manifest.jsonl`.
- The dataset writer emits `02_Regulations_CCR/_dataset/ccr_items.jsonl`,
  `02_Regulations_CCR/_dataset/ccr_items.csv`, and
  `02_Regulations_CCR/_dataset/ccr_dataset_summary.json`.
- The writer collapses duplicate queue/manifest rows by stable CCR record ID, preserving
  first discovery timestamps and latest acquisition state for resume-safe updates.
- `geode.connectors.ccr_bulk` now writes the normalized dataset automatically at the end
  of each bulk run and records dataset artifact paths in `ccr_bulk_summary.json`.
- Added standalone CLI access through `python -m geode.connectors.ccr_dataset` and
  `geode-ccr-dataset`.
- Documented the dataset schema in `CCR_DATASET_SCHEMA.md`.

## Completed Changes - CCR Industry Filtering

- Added a deterministic CCR metadata tagging pipeline in
  `geode.connectors.ccr_industry_filter`.
- Added an editable first-pass CoorsTek-oriented taxonomy in
  `geode.connectors.ccr_industry_taxonomy`.
- The tagger writes full tagged JSONL/CSV outputs, optional filtered JSONL/CSV outputs,
  and summary counts for industries, topics, domains, confidence buckets, CoorsTek
  relevance buckets, and matched rules.
- Tightened emitted CCR domain tags to the explicit CoorsTek-oriented domain vocabulary:
  `environmental_air`, `environmental_water`, `environmental_waste`,
  `occupational_safety`, `workplace_health`, `labor_employment`, `wage_hour`,
  `energy_utilities`, `mining_minerals_natural_resources`, `chemicals_exposure`,
  `transportation_hazmat`, `building_fire_industrial_operations`,
  `materials_product_compliance`, and `general_manufacturing`.
- Added broad filter aliases such as `environmental`, `labor`, `ehs`, `manufacturing`,
  and `coorstek` while preserving exact domain tags in the output records.
- Integrated full tagged dataset generation into the CCR bulk runner after normalized
  dataset writing, with `--no-industry-tags` available when operators need to skip it.
- Added CLI access through `python -m geode.connectors.ccr_industry_filter` and
  `geode-ccr-filter`.
- Documented filter logic, commands, and limitations in `CCR_INDUSTRY_FILTERING.md`.

## Completed Changes - CCR Bulk Normalization

- Extended `geode.connectors.ccr_dataset` so the existing CCR bulk path now populates
  final CCR layer outputs under `02_Regulations_CCR/`, not only operational `_dataset`
  CSV/JSONL files.
- Added final normalized acquisition records under
  `02_Regulations_CCR/_normalized/records/{id}.json`, plus consolidated
  `02_Regulations_CCR/_normalized/ccr_normalized_records.jsonl`.
- Added consolidated metadata at `02_Regulations_CCR/_meta/ccr_normalized_meta.jsonl`
  and a populated `02_Regulations_CCR/_index.jsonl` using the existing layer index
  schema.
- Added `ccr_normalization_summary.json` with counts for downloaded, pending, failed,
  blocked, missing raw files, and stale generated record files removed.
- Updated `geode.connectors.ccr_bulk.CCRBulkSummary` to include final normalized
  output paths and record counts.
- Documented the archive-to-normalized mapping and rerun/resume behavior in
  `CCR_NORMALIZED_OUTPUT.md`.

## Completed Changes - CCR Identity And State Parity

- Added `geode.connectors.ccr_identity` as the single canonical CCR identity helper for
  bulk discovery, document retrieval, normalized records, failure rows, and single-rule
  output stems.
- Standardized CCR IDs to prefer official citations such as `5_CCR_1001-9`, with
  deterministic fallbacks for SOS `ruleId`, `ruleVersionId`, and URL-hash-only cases.
- Updated CCR rule-info resolution so numeric single-rule inputs can be upgraded to the
  resolved official CCR citation before retrieval and output writing.
- Added download-state reconciliation so valid existing raw files repair missing
  manifest rows, missing files trigger recovery downloads, and blocked/permanent
  failure states remain auditable.
- Updated bulk queue statuses and summaries to use `discovered`, `resolved`,
  `downloaded`, `skipped_existing`, `failed_permanent`, `blocked`, and `pending_retry`
  parity, while reading legacy `indexed` and `failed` rows safely.
- Strengthened resume behavior so terminal queued items count toward `--max-items`,
  preventing limited resumed runs from discovering extra work unexpectedly.
- Updated normalized dataset summaries to expose discovered, resolved,
  failed-permanent, and pending-retry counts alongside existing download/block counts.
- Added `normalization_status` to final normalized records so the downstream
  normalized phase is explicit without overwriting acquisition status.
- Documented the canonical ID and state model in `CCR_ID_AND_STATE_MODEL.md`.

## Completed Changes - CCR Readiness Validation

- Ran focused CCR transport, scraper, bulk, dataset, industry-filter, pipeline,
  connector, archive-path, and manifest-quality tests: 74 passed.
- Ran the broader CCR/scoring regression set including postprocess and generic industry
  tagger tests: 89 passed.
- Ran scoped Ruff checks for the CCR HTTP/scraper/bulk/dataset/filter/pipeline files
  and related tests: all checks passed.
- Confirmed live sandbox network execution is blocked through `127.0.0.1:9`, then
  reran approved live validation outside the sandbox network path.
- Live diagnostic CCR chain succeeded against SOS: home page, CCR welcome, department
  list, first agency page, first rule-info page, and first PDF document all returned
  `200`.
- Live small end-to-end CCR bulk run succeeded for 3 records with discovery,
  resolution, retrieval, normalized output, tagged output, and 0 failures/blocks.
- Live moderate CCR retrieval run succeeded for 25 records with 25 downloads, 25
  normalized records, 25 tagged records, and 0 failures/blocks.
- Live larger controlled CCR retrieval run succeeded for 50 records with 50 downloads,
  50 manifest rows, 50 normalized records, 50 tagged records, and 0 failures/blocks.
- Live filtered output commands for manufacturing, environmental, and labor/employment
  subsets succeeded against the 50-record validation dataset; that early CCR slice
  produced 0 target-domain matches, as expected for Personnel/administration records.
- Live staged resume validation succeeded by creating a 5-item discovery-only queue,
  then resuming the same output root to retrieve all 5 documents without discovering
  extra items.
- Updated `CCR_BULK_READINESS_REPORT.md` with exact commands, results, output paths,
  artifact interpretation, residual risks, and staged 100/250/1000+ operator commands.

## Completed Changes - CCR Text Normalization

- Added `geode.pipeline.ccr_text` to convert downloaded CCR raw archive documents into
  schema-validated `regulation_rule` records.
- The text-normalization stage consumes the existing CCR normalized acquisition dataset
  and raw archive files; it does not create a second downloader or identity layer.
- Added conversion through the existing `geode.extractors.converter.convert_to_markdown`
  dispatcher for PDF, DOCX, and legacy DOC sources.
- Added deterministic metadata extraction for CCR citation identity, explicit effective
  dates, CRS citations, compliance keywords, industry/topic tags, and source traceability.
- Added `RegulationRule` writer integration through `geode.pipeline.writer.write_record`,
  producing per-rule Markdown, metadata, index, manifest, update-log, crosswalk, and
  timeline outputs where data is available.
- Added department-level aggregate Markdown files rebuilt from
  `02_Regulations_CCR/_meta/ccr_rules_meta.jsonl` so resumed staged runs preserve
  previously normalized rule text.
- Added CLI access through `python -m geode.pipeline.ccr_text`, `geode-ccr-text`, and
  `python -m geode.pipeline.run --layer ccr --normalize-text`.
- Added pilot-set support with `--pilot`, using `_CONTROL_PLANE/PILOT_TEST_SET.json`.
- Updated `RegulationRule` schema so unknown effective dates can remain `null` and
  legacy `doc` sources can validate without fabricated data.
- Documented the text-normalization stage in `CCR_TEXT_NORMALIZATION.md`.

## Actual Relevant Files Discovered

### CCR scraping and raw downloads

- `geode/connectors/ccr_scraper.py`
  - Implements CCR department/agency discovery from SOS browse pages.
  - Resolves `DisplayRule.do?action=ruleinfo` pages into PDF/DOC/DOCX download URLs.
  - Downloads rule source files with manifest rows, SHA-256 hashes, atomic temp writes,
    delay pacing, `max_downloads`, and manifest-based resume.
  - Warms a Secretary of State browser-like session and has explicit 403 fallback logic.
- `geode/connectors/archive_paths.py`
  - Defines canonical raw archive paths, including `_RAW_ARCHIVE/ccr`,
    `download_manifest.jsonl`, and `download_failures.jsonl`.
- `geode/connectors/orchestrator.py`
  - Wires `ccr` into the bulk connector runner and passes delay/retry/timeout options.
- `geode/connectors/run.py`
  - CLI entry point for bulk source downloads.

### HTTP request helpers

- `geode/net/http_client.py`
  - Provides `build_session`, `polite_get`, browser headers, `curl_cffi` impersonation
    when available, retries for 403/429/5xx, exponential backoff with jitter,
    `Retry-After` handling, and `GeodeFetchError`.
- `geode/net/__init__.py`
  - Re-exports the HTTP helper surface.
- `scripts/diagnose_fetch.py`
  - Diagnostic CLI that uses the hardened HTTP helper and SOS warm-up path.

### CLI entry points

- `pyproject.toml`
  - Registers `geode-bulk-download = geode.connectors.run:main`.
  - Registers `geode-pipeline-run = geode.pipeline.run:main`.
- `geode/pipeline/run.py`
  - Supports `--layer ccr --rule-id ...` for a single-rule CCR pipeline.
- `run_pipeline.py`
  - Separate legacy/sample bill pipeline command, not the CCR bulk path.

### Output directories and current state

- `_RAW_ARCHIVE/ccr/`
  - Exists. No visible downloaded CCR artifacts were present during this audit.
- `02_Regulations_CCR/_index.jsonl`
  - Exists but is empty.
- `02_Regulations_CCR/_meta/`
  - Exists, but contains `7_CCR_1103-1.docx.pdf`, which does not match the intended
    JSONL metadata-sidecar convention.
- `data/raw_pdfs/`, `data/extracted_text/`, `data/structured_output/`
  - Existing bill-pipeline operational directories with `.gitkeep` placeholders and
    a `data/structured_output/geode_commons.sqlite3` artifact.
- `_SORTED/`, `_CURATED/`, `_INDICES/`
  - Not present in the current tree, although helper code references `_SORTED/ccr`,
    `_CURATED/coorstek_core`, and README describes `_INDICES`.

### Parsing, conversion, normalization, and tagging

- `geode/extractors/converter.py`
  - Converts DOCX/PDF/DOC to Markdown using MarkItDown, python-docx, PyMuPDF, or
    mammoth depending on format and installed dependencies.
- `geode/pipeline/ccr.py`
  - Single-rule CCR pipeline: resolve/download, convert to Markdown, run deterministic
    industry tagging, and write operational outputs under `data/raw/Colorado/CCR`,
    `data/normalized/Colorado/CCR`, and `data/tagged`.
- `geode/pipeline/writer.py`
  - Generic validated corpus writer already supports `02_Regulations_CCR` outputs,
    metadata sidecars, layer indexes, crosswalks, timeline entries, manifest refresh,
    and update-log writes.
- `geode/schemas/models.py`
  - Contains `RegulationRule` and `RuleUnit` Pydantic models.
- `geode/validation/checks.py`
  - Contains schema, integrity, tag coverage, orphan regulation, and crosswalk checks.
- `geode/scoring/industry_tagger.py`
  - Deterministic NAICS/industry tagger, currently shaped around bill-like inputs and
    CRS references.
- `_CONTROL_PLANE/PILOT_TEST_SET.json` and `geode/pipeline/pilot.py`
  - Define and validate the 15 CCR pilot rules and can convert them to CCR downloader
    handoff entries.

### Tests

- `tests/test_ccr_scraper.py`
  - Covers mocked discovery, rule-info resolution, PDF/DOCX URL parsing, downloads,
    manifest rows, resume behavior, and URL unescaping.
- `tests/test_http_client.py`
  - Covers browser headers, 403 retry, retry exhaustion, backoff, timeout, Retry-After,
    and blocked/rate-limited error context.
- `tests/test_bulk_download_cli.py`
  - Covers bulk CLI parsing, aliases, caps, warning behavior, summary output, and
    nonzero failures.
- `tests/test_ccr_pipeline.py`
  - Covers the single-rule CCR pipeline and CLI routing.
- `tests/test_ccr_postprocess.py`
  - Covers copying CCR raw files into `_SORTED/ccr/CCR_<series>` folders and inventory
    summaries.
- `tests/test_manifest_quality.py`
  - Covers duplicate manifest reporting without mutating the source manifest.
- `tests/test_archive_paths.py`
  - Covers raw archive and manifest path conventions.
- `tests/test_remaining_connectors.py`
  - Covers orchestrator wiring and passing hardened HTTP options to CCR.

## Remaining Missing Pieces

- CCR text normalization now creates schema-valid `RegulationRule` records, but it is a
  first-pass deterministic parser. It does not yet split rule text into atomic
  `RuleUnit` records.
- CRS citation extraction now writes `regulation_to_statute.jsonl` entries as
  `relationship: cites`; deeper classification into `authorized_by` or `implements`
  remains future work.
- Department-level Markdown aggregate files are generated from normalized rule records,
  but a more polished department/chapter/table-of-contents renderer is still future work.
- The CCR pilot CLI path exists, but the full 15-rule pilot has not yet been live-run
  through text conversion in this environment.

## Duplicate or Inconsistent Components

- `CCRRuleEntry.preferred_url` currently prefers PDF over DOC/DOCX, while
  `SOURCE_REGISTRY.json`, `docs/GEODE_SYSTEM_DESIGN.md`, and the intended CCR strategy
  say to prefer DOCX when available.
- `geode/connectors/ccr_scraper.py` defines `_canonical_source_url` twice. The later
  definition overrides the earlier multi-pass version. This is obvious dead code, but
  it should not be deleted until covered by a focused cleanup test.
- `geode/pipeline/ccr.py` downloads raw CCR files into `data/raw/Colorado/CCR`, while
  the bulk connector and architecture use `_RAW_ARCHIVE/ccr` as the source-of-truth
  raw archive.
- `geode/pipeline/ccr.py` takes a numeric SOS `rule_id` and uses it as `ccr_number`,
  producing non-canonical IDs like `CCR-3154` or `3154` in outputs instead of
  `7_CCR_1103-1`.
- `scripts/industry_tagger.py` and `geode/scoring/industry_tagger.py` are similar but
  not identical. The packaged `geode.scoring` version is the one used by
  `geode.pipeline.run`.
- `run_pipeline.py` and `geode/pipeline/run.py` both expose bill-pipeline behavior.
  CCR work should avoid refactoring this split unless explicitly requested.
- `.gitignore` repeats the `data/raw/**/download_manifest.jsonl` rule. This is harmless
  and not CCR-blocking.

## Recommended Target Structure

- Keep `geode.net.http_client` as the single reusable HTTP abstraction.
- Keep raw CCR acquisition in `geode.connectors.ccr_scraper` and `_RAW_ARCHIVE/ccr`.
- Reuse `geode.connectors.orchestrator` and `geode.connectors.run` for resumable bulk
  source downloads.
- Adapt `geode.pipeline.ccr` to normalize downloaded CCR artifacts into schema-valid
  `RegulationRule` records and send them through `geode.pipeline.writer.write_record`.
- Reuse `_CONTROL_PLANE/PILOT_TEST_SET.json` and `geode.pipeline.pilot` for pilot
  selection instead of hardcoding pilot rule lists.
- Keep `_SORTED` and `_CURATED` helper code as optional post-download organization until
  a later prompt asks for those operational folders.
- Treat `scripts/*` and `run_pipeline.py` as legacy/bill-pipeline surfaces unless a later
  prompt explicitly targets them.

## Exact Files Best to Modify Next

For later implementation prompts, the likely minimal edit set is:

- `geode/connectors/ccr_scraper.py`
  - Align preferred format with DOCX-first policy.
  - Remove or consolidate the duplicate `_canonical_source_url` only with tests.
  - Consider adding CCR `download_failures.jsonl` parity with other connectors.
  - Improve resume checks for signature-corrected extensions.
- `geode/pipeline/ccr.py`
  - Preserve the legacy single-rule path, but consider redirecting it to consume
    `_RAW_ARCHIVE/ccr` artifacts and `geode.pipeline.ccr_text` outputs.
- `geode/pipeline/run.py`
  - CCR text normalization is now exposed through `--layer ccr --normalize-text`.
  - Keep future CLI additions small and compatible with the existing bill/CRS runner.
- `geode/pipeline/ccr_text.py`
  - Extend first-pass text normalization into rule-unit parsing and richer date/status
    extraction when needed.
- `geode/connectors/ccr_industry_taxonomy.py`
  - Extend deterministic CCR taxonomy rules as new normalized metadata or extracted
    text fields become available.
- Tests to update or add:
  - `tests/test_ccr_scraper.py`
  - `tests/test_ccr_pipeline.py`
  - `tests/test_bulk_download_cli.py` if CLI behavior changes.
  - `tests/test_ccr_postprocess.py` only if sorted/curated workflows are expanded.
  - `tests/test_manifest_quality.py` if manifest/failure reporting changes.

## Do Not Delete Yet

- Do not delete `scripts/industry_tagger.py`, `run_pipeline.py`, or duplicate pipeline
  surfaces without a separate cleanup prompt.
- Do not move or delete `02_Regulations_CCR/_meta/7_CCR_1103-1.docx.pdf` until its
  provenance is confirmed.
- Do not rewrite existing manifests in place. Keep manifest cleanup as separate report
  artifacts unless a later prompt explicitly authorizes canonical migration.

## Operator Validation Completed Changes - 2026-06-22

The CCR operator path was validated from the repository root using the actual live
workflow and current artifacts.

### Commands validated

- `python scripts\diagnose_fetch.py --ccr-chain --max-retries 1 --base-delay 0.5 --timeout-seconds 20`
  - CCR welcome, department list, agency page, rule detail page, and PDF document fetch
    returned HTTP `200`.
- `python -m geode.connectors.ccr_bulk --output-root . --max-items 5 --resume --discovery-only --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --json`
  - Completed against existing queue state.
- `python -m geode.connectors.ccr_bulk --output-root . --max-items 55 --resume --download-delay 0.75 --download-delay-jitter 0.25 --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --write-industry-tags --json`
  - Downloaded `5` additional CCR records, no failures, no blocked responses.
- Repeating the same 55-item command completed with `attempted: 0` and
  `downloaded: 0`, confirming capped resume behavior.
- `python -m geode.connectors.ccr_bulk --output-root . --max-items 60 --resume --download-delay 0.75 --download-delay-jitter 0.25 --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --write-industry-tags --json`
  - Reconciled five late-written files from the earlier timed-out connector command as
    `skipped_existing`, with `attempted: 0`, `downloaded: 0`, and no failures.
- `python -m geode.pipeline.ccr_text --output-root . --max-items 10 --json`
  - Wrote `10` full-text normalized `RegulationRule` outputs into
    `02_Regulations_CCR/`.
- Repeating the same text-normalization command preserved stable counts:
  - `02_Regulations_CCR/_meta/ccr_rules_meta.jsonl`: `10` rows
  - `02_Regulations_CCR/_rules/`: `10` files
  - `_CROSSWALKS/regulation_to_statute.jsonl`: `8` rows
- `python -m geode.validate --layer 02_Regulations_CCR`
  - Passed.
- `python -m pytest tests -q`
  - `207 passed`.

### Final artifact state

- `_RAW_ARCHIVE/ccr/download_manifest.jsonl`: `60` manifest rows.
- `02_Regulations_CCR/_dataset/ccr_items.jsonl`: `1,035` normalized acquisition
  records.
- `02_Regulations_CCR/_inventory/ccr_inventory_manifest.jsonl`: `2,070` asset rows.
- `02_Regulations_CCR/_dataset/ccr_items_tagged.jsonl`: `1,035` tagged dataset rows,
  with `272` tagged matches.
- `02_Regulations_CCR/_dataset/manufacturing.jsonl`: `272` filtered records.
- `02_Regulations_CCR/_dataset/environmental.jsonl`: `100` filtered records.
- `02_Regulations_CCR/_dataset/labor_employment.jsonl`: `53` filtered records.

### Fix made during validation

The first real text-normalization write exposed a transient Windows/OneDrive
`PermissionError` during atomic replacement of `_CROSSWALKS/regulation_to_statute.jsonl`.
`geode/utils/file_io.py` now retries short-lived `PermissionError` failures from
`os.replace`, while preserving the same temp-file-plus-replace atomic write model.
`tests/test_file_io.py` covers this behavior.
