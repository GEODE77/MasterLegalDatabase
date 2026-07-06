# CCR Bulk Readiness Report

Generated: 2026-06-22

## Readiness Status

CCR bulk acquisition is operational for the currently discovered CCR corpus. The
validated path covers live discovery, detail resolution, document retrieval, raw archive
artifacts, normalized acquisition records under `02_Regulations_CCR/`, full-text
rule-level normalization, deterministic industry tagging/filtering outputs, and resume
repair from failed content retrieval.

1,000+ retrieval is now live-proven. The repository has completed live acquisition and
normalization for all `1,035` discovered CCR records.

Uncapped discovery is now live-proven. A full discovery-only traversal completed
without `--max-items` or `--max-agencies` and found the same `1,035` unique CCR rule
series already present in Geode.

## Uncapped Discovery Proof - 2026-06-23

Command executed:

```powershell
python -m geode.connectors.ccr_bulk --output-root . --resume --discovery-only --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --no-industry-tags --json
```

Result:

- Status: `completed`
- `max_items`: `null`
- `max_agencies`: `null`
- `run_capped_by_max_items`: `false`
- `run_capped_by_max_agencies`: `false`
- `uncapped_discovery_requested`: `true`
- `uncapped_discovery_completed`: `true`
- Traversal validation: `uncapped_discovery_completed`
- Inventory warnings: none
- Unique departments: `25`
- Unique agencies: `208`
- Unique CCR rule series: `1,035`
- Inventory download targets: `2,070` (`1,035` PDF and `1,035` DOCX)
- Current normalized records: `1,035`
- Raw archived CCR documents: `1,035`
- Failed current records: `0`
- Blocked current records: `0`
- Pending current records: `0`

This proves that, under the current live Colorado Secretary of State CCR browse
structure, Geode has discovered the complete currently visible active CCR rule-series
corpus.

Post-run checks:

```powershell
python -m geode.connectors.ccr_industry_filter --output-root . --json
python -m geode.validate --layer 02_Regulations_CCR
python -m pytest tests\test_http_client.py tests\test_ccr_scraper.py tests\test_ccr_bulk.py tests\test_ccr_dataset.py tests\test_ccr_industry_filter.py tests\test_ccr_pipeline.py tests\test_bulk_download_cli.py tests\test_manifest_quality.py tests\test_ccr_text_normalization.py -q
```

Results:

- Industry tagging regenerated successfully for `1,035` records.
- `python -m geode.validate --layer 02_Regulations_CCR`: passed.
- Focused CCR tests: `64 passed`.

## Final Operational Run - 2026-06-23

The downstream operational loop was completed from the repository root:

```text
C:\Users\jpfeifer\OneDrive - CoorsTek\Documents\Geode
```

### Final Status

- CCR queue records: `1,035`
- Raw CCR document files in `_RAW_ARCHIVE/ccr`: `1,035`
- Raw download manifest rows: `1,036`
- Current normalized acquisition records: `1,035`
- Duplicate manifest rows collapsed by dataset writer: `1`
- Failed current records: `0`
- Blocked current records: `0`
- Pending current records: `0`
- Full-text `RegulationRule` metadata rows: `1,035`
- Full-text rule Markdown files: `1,035`
- Department aggregate Markdown files: `25`
- Regulation-to-statute crosswalk rows: `696`
- Tagged acquisition dataset rows: `1,035`
- Tagged records: `272`
- Untagged records: `763`
- Manufacturing filtered records: `272`
- Environmental filtered records: `100`
- Labor/employment filtered records: `53`

The raw manifest intentionally retains the earlier timeout failure row and the later
successful repair row for `6_CCR_1015-4`; current-state dataset generation collapses
that history into one successful record.

### Commands Executed

Staged retrieval and normalization:

```powershell
python -m geode.connectors.ccr_bulk --output-root . --max-items 500 --resume --download-delay 1.0 --download-delay-jitter 0.25 --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --write-industry-tags --json
python -m geode.pipeline.ccr_text --output-root . --max-items 500 --json
python -m geode.connectors.ccr_bulk --output-root . --max-items 1035 --resume --download-delay 1.0 --download-delay-jitter 0.25 --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --write-industry-tags --json
python -m geode.connectors.ccr_bulk --output-root . --max-items 1035 --resume --download-delay 1.0 --download-delay-jitter 0.25 --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --write-industry-tags --json
python -m geode.pipeline.ccr_text --output-root . --max-items 1035 --json
```

Final filters:

```powershell
python -m geode.connectors.ccr_industry_filter --output-root . --include-industry manufacturing --filtered-prefix manufacturing --json
python -m geode.connectors.ccr_industry_filter --output-root . --include-domain environmental_air --include-domain environmental_water --include-domain environmental_waste --match-mode any --filtered-prefix environmental --json
python -m geode.connectors.ccr_industry_filter --output-root . --include-domain labor_employment --include-domain wage_hour --match-mode any --filtered-prefix labor_employment --json
```

Final validation:

```powershell
python -m geode.validate --layer 02_Regulations_CCR
python -m pytest tests -q
python -m ruff check geode\connectors\ccr_bulk.py geode\schemas\models.py geode\validation\checks.py geode\pipeline\ccr_text.py geode\utils\file_io.py tests\test_ccr_bulk.py tests\test_schemas.py tests\test_validation.py tests\test_ccr_text_normalization.py tests\test_file_io.py
```

Results:

- `python -m geode.validate --layer 02_Regulations_CCR`: passed.
- `python -m pytest tests -q`: `213 passed`.
- Scoped Ruff check: passed.

### Issues Found And Fixed

1. Future CCR effective dates were rejected by generic date validation.
   - Fixed `RegulationRule.effective_date` and pre-write validation so future
     effective dates are allowed for regulation rules.
   - Future effective dates remain on the rule record, but future timeline events are
     not emitted.

2. One full-run document, `6_CCR_1015-4`, failed during PDF retrieval because the SOS
   transfer timed out.
   - Fixed CCR bulk resume behavior so content-retrieval failures with no archive file
     can be retried.
   - Added PDF-to-Word fallback for CCR entries that expose both formats.
   - Rerun repaired the item with `attempted: 1`, `downloaded: 1`, `failed: 0`,
     `blocked: 0`.

3. Parallel filter generation exposed shared temp-file contention in atomic writes.
   - Fixed `geode.utils.file_io.atomic_write_text` to use unique temp files per write.
   - Reran filters successfully.

## Operator Validation Run - 2026-06-22

This section records the latest operator run performed in the repository root:

```text
C:\Users\jpfeifer\OneDrive - CoorsTek\Documents\Geode
```

### Validation Summary

- Live CCR diagnostic chain: passed through CCR welcome, department list, agency list,
  rule detail page, and PDF document fetch.
- Live phased bulk discovery-only run: passed with the existing queue.
- Live phased bulk resume retrieval: downloaded 5 additional CCR records, then a
  final reconciliation pass counted 5 late-written files from the earlier timed-out
  connector command as skipped-existing, raising the repository manifest to 60
  completed rows.
- Immediate repeat/reconciliation resume run: passed with `attempted: 0`,
  `downloaded: 0`, confirming the capped state did not redownload already-completed
  work.
- Normalized acquisition dataset: `1,035` records written to
  `02_Regulations_CCR/_dataset/ccr_items.jsonl`.
- Full-text CCR normalization: `10` downloaded records converted and written as
  schema-valid rule outputs.
- Idempotent rerun check: a second 10-record full-text normalization rerun kept
  `ccr_rules_meta.jsonl` at `10` rows, `_rules/` at `10` files, and
  `regulation_to_statute.jsonl` at `8` rows.
- Industry filters generated:
  - manufacturing: `272` records
  - environmental: `100` records
  - labor/employment: `53` records
- Corpus validation: `python -m geode.validate --layer 02_Regulations_CCR` passed.
- Full test suite: `207 passed`.
- CCR-scoped Ruff check: passed.

### Live Commands Executed

Diagnostic chain:

```powershell
python scripts\diagnose_fetch.py --ccr-chain --max-retries 1 --base-delay 0.5 --timeout-seconds 20
```

Result:

- `ccr_welcome`: HTTP `200`
- `department_list`: HTTP `200`
- discovered agency links: `273`
- `first_agency`: HTTP `200`
- first agency rule candidates: `5`
- `first_rule_page`: HTTP `200`
- `first_document`: HTTP `200`, `content-type: application/pdf`
- A trailing SOS home probe failed DNS resolution, but the CCR chain itself completed.

Discovery-only bulk path:

```powershell
python -m geode.connectors.ccr_bulk --output-root . --max-items 5 --resume --discovery-only --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --json
```

Result:

- status: `completed`
- queue items total: `1,035`
- inventory rows total: `2,070`
- normalized acquisition records total: `1,035`
- tagged records total: `1,035`
- tagged matches: `272`
- failed: `0`
- blocked: `0`

Resume retrieval run:

```powershell
python -m geode.connectors.ccr_bulk --output-root . --max-items 55 --resume --download-delay 0.75 --download-delay-jitter 0.25 --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --write-industry-tags --json
```

Result:

- status: `completed`
- attempted: `5`
- downloaded: `5`
- failed: `0`
- blocked: `0`
- pending after run: `980`
- manifest rows total immediately after run: `55`

Repeat resume check:

```powershell
python -m geode.connectors.ccr_bulk --output-root . --max-items 55 --resume --download-delay 0.75 --download-delay-jitter 0.25 --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --write-industry-tags --json
```

Result:

- status: `completed`
- attempted: `0`
- downloaded: `0`
- failed: `0`
- blocked: `0`
- pending remained `980`

Final reconciliation after the earlier timed-out connector child wrote five additional
files:

```powershell
python -m geode.connectors.ccr_bulk --output-root . --max-items 60 --resume --download-delay 0.75 --download-delay-jitter 0.25 --discovery-delay 0.5 --discovery-delay-jitter 0.1 --http-timeout-seconds 30 --http-max-retries 2 --http-base-delay 1 --write-industry-tags --json
```

Result:

- status: `completed`
- attempted: `0`
- downloaded: `0`
- skipped_existing: `5`
- failed: `0`
- blocked: `0`
- manifest rows total: `60`
- pending after reconciliation: `975`

Full-text normalization:

```powershell
python -m geode.pipeline.ccr_text --output-root . --max-items 10 --json
```

Result:

- records considered: `10`
- converted: `10`
- written: `10`
- failed: `0`
- quarantined: `0`
- department files: `02_Regulations_CCR/ccr_dept_department_of_personnel_and_administration.md`

Idempotent rerun:

```powershell
python -m geode.pipeline.ccr_text --output-root . --max-items 10 --json
```

Post-rerun counts:

- `02_Regulations_CCR/_meta/ccr_rules_meta.jsonl`: `10` rows
- `02_Regulations_CCR/_rules/`: `10` files
- `_CROSSWALKS/regulation_to_statute.jsonl`: `8` rows

Filtered output commands:

```powershell
python -m geode.connectors.ccr_industry_filter --output-root . --include-industry manufacturing --filtered-prefix manufacturing --json
python -m geode.connectors.ccr_industry_filter --output-root . --include-domain environmental_air --include-domain environmental_water --include-domain environmental_waste --match-mode any --filtered-prefix environmental --json
python -m geode.connectors.ccr_industry_filter --output-root . --include-domain labor_employment --include-domain wage_hour --match-mode any --filtered-prefix labor_employment --json
```

Results:

- `02_Regulations_CCR/_dataset/manufacturing.jsonl`: `272` records
- `02_Regulations_CCR/_dataset/environmental.jsonl`: `100` records
- `02_Regulations_CCR/_dataset/labor_employment.jsonl`: `53` records

### Issue Found And Fixed During Validation

The first non-dry-run full-text normalization exposed a Windows/OneDrive transient
file-lock failure:

```text
PermissionError: [WinError 5] Access is denied:
_CROSSWALKS\regulation_to_statute.jsonl.tmp -> _CROSSWALKS\regulation_to_statute.jsonl
```

`geode.utils.file_io.atomic_write_text` was updated to keep the same atomic write
strategy while retrying `os.replace` briefly for transient `PermissionError` locks.
The fix is covered by `tests/test_file_io.py`.

## Implemented

- Reusable HTTP client abstraction with persistent sessions, browser-like headers,
  timeouts, retries, backoff, throttling hooks, response logging, and explicit exception
  types.
- CCR request hardening with SOS landing-page warm-up, referer continuity, session
  cookies, document content validation, and blocked-response diagnostics.
- Phased CCR bulk workflow:
  - discovery / index collection
  - detail/document resolution
  - document retrieval
  - normalized acquisition dataset writing
  - industry tagging/filtering
  - summary, queue, checkpoint, manifest, and failure artifacts
- Canonical CCR identity and status parity across queue, manifest, raw files,
  normalized records, failures, checkpoints, summaries, and single-rule output stems.
- Resume reconciliation for existing files, missing files, incomplete metadata, and
  downstream normalization/tagging reruns.
- Editable CCR taxonomy in `geode/connectors/ccr_industry_taxonomy.py`.

## Actual Paths Used

The operational path is `geode.connectors.ccr_bulk`, exposed as:

```powershell
python -m geode.connectors.ccr_bulk
```

The normalized dataset and tagged outputs are written under the selected output root:

```text
{output_root}/_RAW_ARCHIVE/ccr/
{output_root}/02_Regulations_CCR/_dataset/
{output_root}/02_Regulations_CCR/_normalized/
{output_root}/02_Regulations_CCR/_meta/
{output_root}/02_Regulations_CCR/_index.jsonl
```

No alternate orchestration layer was used for the live validation.

## Tests Run

Focused CCR transport/scraper/bulk/dataset/filter/pipeline tests:

```powershell
python -m pytest tests\test_http_client.py tests\test_ccr_scraper.py tests\test_ccr_bulk.py tests\test_ccr_dataset.py tests\test_ccr_industry_filter.py tests\test_ccr_pipeline.py tests\test_bulk_download_cli.py tests\test_remaining_connectors.py tests\test_archive_paths.py tests\test_manifest_quality.py -q
```

Result:

```text
74 passed in 35.47s
```

Broader CCR/scoring regression set:

```powershell
python -m pytest tests\test_ccr_dataset.py tests\test_ccr_industry_filter.py tests\test_ccr_bulk.py tests\test_ccr_pipeline.py tests\test_ccr_scraper.py tests\test_ccr_postprocess.py tests\test_manifest_quality.py tests\test_archive_paths.py tests\test_http_client.py tests\test_bulk_download_cli.py tests\test_remaining_connectors.py tests\test_industry_tagger.py -q
```

Result:

```text
89 passed in 34.75s
```

Scoped Ruff check:

```powershell
python -m ruff check geode\net\http_client.py geode\connectors\ccr_scraper.py geode\connectors\ccr_bulk.py geode\connectors\ccr_dataset.py geode\connectors\ccr_industry_filter.py geode\connectors\ccr_industry_taxonomy.py geode\pipeline\ccr.py tests\test_http_client.py tests\test_ccr_scraper.py tests\test_ccr_bulk.py tests\test_ccr_dataset.py tests\test_ccr_industry_filter.py tests\test_ccr_pipeline.py tests\test_bulk_download_cli.py tests\test_remaining_connectors.py tests\test_archive_paths.py tests\test_manifest_quality.py
```

Result:

```text
All checks passed!
```

Python compile check:

```powershell
python -m py_compile geode\connectors\ccr_identity.py geode\connectors\ccr_scraper.py geode\connectors\ccr_bulk.py geode\connectors\ccr_dataset.py geode\connectors\ccr_industry_filter.py geode\connectors\ccr_industry_taxonomy.py geode\pipeline\ccr.py
```

Result: passed.

## Live Validations Run

Normal sandbox network access failed with connections redirected to `127.0.0.1:9`.
Live validation was rerun outside the sandbox network path.

### Diagnostic CCR Chain

Command:

```powershell
python scripts\diagnose_fetch.py --ccr-chain --max-retries 1 --base-delay 0 --timeout-seconds 10
```

Result: succeeded.

- SOS home: `200`
- CCR welcome: `200`
- department list: `200`
- discovered agency links: `273`
- first agency page: `200`
- first agency rule candidates: `5`
- first rule page: `200`
- first document: `200`, `content-type: application/pdf`

### Small End-To-End Run

Command:

```powershell
python -m geode.connectors.ccr_bulk --output-root C:\Users\jpfeifer\AppData\Local\Temp\geode_ccr_readiness_small_20260622_1750 --max-items 3 --no-resume --discovery-delay 0.1 --discovery-delay-jitter 0 --download-delay 0.25 --download-delay-jitter 0 --http-max-retries 2 --http-base-delay 0.5 --http-retry-jitter-ratio 0 --json
```

Result: succeeded.

- discovered/indexed: `3`
- resolved: `3`
- attempted: `3`
- downloaded: `3`
- failed: `0`
- blocked: `0`
- normalized records: `3`
- tagged records: `3`
- tagged matches: `0`
- status: `paused`, expected because `--max-items 3` was reached

### Moderate Retrieval Run

Command:

```powershell
python -m geode.connectors.ccr_bulk --output-root C:\Users\jpfeifer\AppData\Local\Temp\geode_ccr_readiness_moderate_20260622_1751 --max-items 25 --no-resume --discovery-delay 0.1 --discovery-delay-jitter 0 --download-delay 0.25 --download-delay-jitter 0 --http-max-retries 2 --http-base-delay 0.5 --http-retry-jitter-ratio 0 --json
```

Result: succeeded.

- discovered/indexed: `25`
- resolved: `25`
- attempted: `25`
- downloaded: `25`
- failed: `0`
- blocked: `0`
- normalized records: `25`
- tagged records: `25`
- tagged matches: `0`
- status: `paused`, expected because `--max-items 25` was reached

### Larger Controlled Retrieval Run

Command:

```powershell
python -m geode.connectors.ccr_bulk --output-root C:\Users\jpfeifer\AppData\Local\Temp\geode_ccr_readiness_large_20260622_1752 --max-items 50 --no-resume --discovery-delay 0.1 --discovery-delay-jitter 0 --download-delay 0.25 --download-delay-jitter 0 --http-max-retries 2 --http-base-delay 0.5 --http-retry-jitter-ratio 0 --json
```

Result: succeeded.

- discovered/indexed: `50`
- resolved: `50`
- attempted: `50`
- downloaded: `50`
- failed: `0`
- blocked: `0`
- retry count: `0`
- pending: `0`
- normalized records: `50`
- tagged records: `50`
- tagged matches: `0`
- status: `paused`, expected because `--max-items 50` was reached

Artifact count check for the 50-item run:

- queue events: `150`
- raw PDF/DOC/DOCX files: `50`
- `download_manifest.jsonl` rows: `50`
- `ccr_items.jsonl` rows: `50`
- `ccr_items_tagged.jsonl` rows: `50`
- `ccr_bulk_failures.jsonl` rows: `0`
- `download_failures.jsonl`: not present, expected because there were no document
  failures

The zero tag matches are not a classification failure. The first 50 live records came
from early Personnel/administration CCR areas, not the CoorsTek-oriented domains in the
taxonomy.

### Filtered Output Commands

Manufacturing:

```powershell
python -m geode.connectors.ccr_industry_filter --output-root C:\Users\jpfeifer\AppData\Local\Temp\geode_ccr_readiness_large_20260622_1752 --include-industry manufacturing --include-domain general_manufacturing --match-mode any --filtered-prefix ccr_items_manufacturing --json
```

Result: succeeded, `records_total: 50`, `filtered_total: 0`.

Environmental:

```powershell
python -m geode.connectors.ccr_industry_filter --output-root C:\Users\jpfeifer\AppData\Local\Temp\geode_ccr_readiness_large_20260622_1752 --include-domain environmental --filtered-prefix ccr_items_environmental --json
```

Result: succeeded, `records_total: 50`, `filtered_total: 0`.

Labor/employment:

```powershell
python -m geode.connectors.ccr_industry_filter --output-root C:\Users\jpfeifer\AppData\Local\Temp\geode_ccr_readiness_large_20260622_1752 --include-topic labor_employment --include-domain labor --match-mode any --filtered-prefix ccr_items_labor_employment --json
```

Result: succeeded, `records_total: 50`, `filtered_total: 0`.

### Staged Resume Validation

Partial discovery-only command:

```powershell
python -m geode.connectors.ccr_bulk --output-root C:\Users\jpfeifer\AppData\Local\Temp\geode_ccr_readiness_resume_20260622_1753 --max-items 5 --no-resume --discovery-only --discovery-delay 0.1 --discovery-delay-jitter 0 --download-delay 0.25 --download-delay-jitter 0 --http-max-retries 2 --http-base-delay 0.5 --http-retry-jitter-ratio 0 --json
```

Result: succeeded.

- discovered/indexed: `5`
- resolved: `5`
- attempted: `0`
- downloaded: `0`
- pending: `5`
- normalized records: `5`
- tagged records: `5`

Resume retrieval command:

```powershell
python -m geode.connectors.ccr_bulk --output-root C:\Users\jpfeifer\AppData\Local\Temp\geode_ccr_readiness_resume_20260622_1753 --max-items 5 --resume --discovery-delay 0.1 --discovery-delay-jitter 0 --download-delay 0.25 --download-delay-jitter 0 --http-max-retries 2 --http-base-delay 0.5 --http-retry-jitter-ratio 0 --json
```

Result: succeeded.

- discovered/indexed in resumed run: `0`
- attempted: `5`
- downloaded: `5`
- failed: `0`
- blocked: `0`
- pending: `0`
- queue items total: `5`
- normalized records: `5`
- status: `completed`

This validates staged resume from an incomplete queue. A literal Ctrl+C interruption was
not performed in this pass.

## Not Live-Validated

- 100-item retrieval was not run live in this pass.
- 250-item retrieval was not run live in this pass.
- 1,000+ retrieval was not run live in this pass.
- Full legal-text conversion into schema-valid `RegulationRule` records is now
  implemented separately in `geode.pipeline.ccr_text`; a real downloaded CCR PDF was
  converted in dry-run mode after the original readiness pass, but a larger live
  full-text write run remains pending.
- CoorsTek-positive live tagging was not observed because the first 50 live records were
  outside the target domains.

## Current Blockers And Residual Risks

- The managed sandbox blocks live SOS access; live validation required approved
  out-of-sandbox network execution.
- SOS may still rate-limit or block larger runs. The code detects blocked responses and
  records them instead of retrying hard 403s indefinitely.
- `pending_retry` is present in the state model, but current retry behavior resolves
  retryable failures inline.
- Larger runs should be done with conservative delays and a local output root outside
  OneDrive sync if possible.
- Full-text normalization quality depends on local PDF/DOCX/DOC conversion
  dependencies. The converter now falls back when MarkItDown lacks optional PDF extras.

## Operator Commands

Run these from the repo root:

```powershell
cd "C:\Users\jpfeifer\OneDrive - CoorsTek\Documents\Geode"
```

### Diagnostic CCR Chain Test

```powershell
python scripts\diagnose_fetch.py --ccr-chain --max-retries 1 --base-delay 0 --timeout-seconds 15
```

### Small End-To-End Sample Run

```powershell
$root = Join-Path $env:LOCALAPPDATA 'Temp\geode_ccr_operator_small'
python -m geode.connectors.ccr_bulk --output-root $root --max-items 5 --no-resume --discovery-delay 0.2 --discovery-delay-jitter 0 --download-delay 0.75 --download-delay-jitter 0 --http-max-retries 3 --http-base-delay 1 --http-timeout-seconds 25 --http-retry-jitter-ratio 0 --json
```

### 100-Item Retrieval Run

```powershell
$root = Join-Path $env:LOCALAPPDATA 'Temp\geode_ccr_operator_100'
python -m geode.connectors.ccr_bulk --output-root $root --max-items 100 --no-resume --discovery-delay 0.3 --discovery-delay-jitter 0.1 --download-delay 1.0 --download-delay-jitter 0.25 --http-max-retries 4 --http-base-delay 2 --http-timeout-seconds 30 --json
```

### 250-Item Retrieval Run

```powershell
$root = Join-Path $env:LOCALAPPDATA 'Temp\geode_ccr_operator_250'
python -m geode.connectors.ccr_bulk --output-root $root --max-items 250 --no-resume --discovery-delay 0.4 --discovery-delay-jitter 0.1 --download-delay 1.25 --download-delay-jitter 0.25 --http-max-retries 4 --http-base-delay 2 --http-timeout-seconds 30 --json
```

### 1,000+ Staged Run

Use increasing caps on the same output root. Resume counts existing terminal items, so
each command advances the run to the next cap.

```powershell
$root = Join-Path $env:LOCALAPPDATA 'Temp\geode_ccr_operator_1000'
python -m geode.connectors.ccr_bulk --output-root $root --max-items 250 --no-resume --discovery-delay 0.5 --discovery-delay-jitter 0.15 --download-delay 1.5 --download-delay-jitter 0.35 --http-max-retries 4 --http-base-delay 2 --http-timeout-seconds 35 --json
python -m geode.connectors.ccr_bulk --output-root $root --max-items 500 --resume --discovery-delay 0.5 --discovery-delay-jitter 0.15 --download-delay 1.5 --download-delay-jitter 0.35 --http-max-retries 4 --http-base-delay 2 --http-timeout-seconds 35 --json
python -m geode.connectors.ccr_bulk --output-root $root --max-items 750 --resume --discovery-delay 0.5 --discovery-delay-jitter 0.15 --download-delay 1.5 --download-delay-jitter 0.35 --http-max-retries 4 --http-base-delay 2 --http-timeout-seconds 35 --json
python -m geode.connectors.ccr_bulk --output-root $root --max-items 1000 --resume --discovery-delay 0.5 --discovery-delay-jitter 0.15 --download-delay 1.5 --download-delay-jitter 0.35 --http-max-retries 4 --http-base-delay 2 --http-timeout-seconds 35 --json
```

To exceed 1,000, continue with `--max-items 1250`, `1500`, and so on.

### Interrupted Resume Test

Staged partial-resume test:

```powershell
$root = Join-Path $env:LOCALAPPDATA 'Temp\geode_ccr_operator_resume'
python -m geode.connectors.ccr_bulk --output-root $root --max-items 10 --no-resume --discovery-only --discovery-delay 0.2 --discovery-delay-jitter 0 --download-delay 0.75 --download-delay-jitter 0 --http-max-retries 3 --http-base-delay 1 --json
python -m geode.connectors.ccr_bulk --output-root $root --max-items 10 --resume --discovery-delay 0.2 --discovery-delay-jitter 0 --download-delay 0.75 --download-delay-jitter 0 --http-max-retries 3 --http-base-delay 1 --json
```

Manual interruption test:

```powershell
$root = Join-Path $env:LOCALAPPDATA 'Temp\geode_ccr_operator_interrupt'
python -m geode.connectors.ccr_bulk --output-root $root --max-items 100 --no-resume --discovery-delay 0.3 --download-delay 1.0 --http-max-retries 4 --http-base-delay 2 --json
# Press Ctrl+C after several documents download.
python -m geode.connectors.ccr_bulk --output-root $root --max-items 100 --resume --discovery-delay 0.3 --download-delay 1.0 --http-max-retries 4 --http-base-delay 2 --json
```

### Filtered Manufacturing Run

```powershell
python -m geode.connectors.ccr_industry_filter --output-root $root --include-industry manufacturing --include-domain general_manufacturing --match-mode any --filtered-prefix ccr_items_manufacturing --json
```

### Filtered Environmental Run

```powershell
python -m geode.connectors.ccr_industry_filter --output-root $root --include-domain environmental --filtered-prefix ccr_items_environmental --json
```

### Filtered Labor/Employment Run

```powershell
python -m geode.connectors.ccr_industry_filter --output-root $root --include-topic labor_employment --include-domain labor --match-mode any --filtered-prefix ccr_items_labor_employment --json
```

## Expected Output Locations

For any `$root`:

```text
$root\_RAW_ARCHIVE\ccr\ccr_bulk_queue.jsonl
$root\_RAW_ARCHIVE\ccr\ccr_bulk_checkpoint.json
$root\_RAW_ARCHIVE\ccr\ccr_bulk_summary.json
$root\_RAW_ARCHIVE\ccr\ccr_bulk_failures.jsonl
$root\_RAW_ARCHIVE\ccr\download_manifest.jsonl
$root\_RAW_ARCHIVE\ccr\download_failures.jsonl
$root\_RAW_ARCHIVE\ccr\*.pdf|*.doc|*.docx
$root\02_Regulations_CCR\_dataset\ccr_items.jsonl
$root\02_Regulations_CCR\_dataset\ccr_items.csv
$root\02_Regulations_CCR\_dataset\ccr_dataset_summary.json
$root\02_Regulations_CCR\_dataset\ccr_items_tagged.jsonl
$root\02_Regulations_CCR\_dataset\ccr_items_tagged.csv
$root\02_Regulations_CCR\_dataset\ccr_tag_summary.json
$root\02_Regulations_CCR\_dataset\ccr_items_{filter}.jsonl
$root\02_Regulations_CCR\_dataset\ccr_items_{filter}.csv
$root\02_Regulations_CCR\_dataset\ccr_items_{filter}_summary.json
$root\02_Regulations_CCR\_normalized\ccr_normalized_records.jsonl
$root\02_Regulations_CCR\_normalized\ccr_normalization_summary.json
$root\02_Regulations_CCR\_normalized\records\{canonical_id}.json
$root\02_Regulations_CCR\_meta\ccr_normalized_meta.jsonl
$root\02_Regulations_CCR\_index.jsonl
```

`download_failures.jsonl` is created only when document retrieval failures occur.

## Interpreting Artifacts

- `ccr_bulk_summary.json`: primary run result. Check `downloaded`, `failed`,
  `blocked`, `pending`, `normalized_records_total`, and `tagged_records_total`.
- `ccr_bulk_checkpoint.json`: latest checkpoint and counters for resume. A healthy
  capped run can be `paused`; a completed resumed queue should be `completed`.
- `ccr_bulk_queue.jsonl`: append-only workflow events. Typical downloaded item has
  `discovered`, `resolved`, and `downloaded` events.
- `download_manifest.jsonl`: one successful raw-file row per downloaded item. Rows
  include canonical `document_id`, `archive_path`, `sha256`, `size_bytes`, and status.
- `ccr_bulk_failures.jsonl`: bulk workflow failures, including resolution failures.
  Empty file means no bulk failures.
- `download_failures.jsonl`: document-retrieval failures and blocked responses. Missing
  file is acceptable when no failures occurred.
- `ccr_items.jsonl` / `.csv`: normalized acquisition dataset for analysis.
- `_normalized/records/{id}.json`: per-item final normalized acquisition record.
- `_index.jsonl` and `_meta/ccr_normalized_meta.jsonl`: final CCR layer index and
  metadata sidecar outputs.
- `ccr_items_tagged.jsonl` / `.csv`: full tagged dataset. Untagged records are preserved.
- filtered JSONL/CSV files: subset outputs for manufacturing, environmental, labor, or
  other requested filters.

Success signals:

- `failed = 0`
- `blocked = 0`
- `pending = 0` after a retrieval run
- `downloaded` equals the intended cap for full retrieval runs
- manifest row count equals downloaded count
- raw file count equals downloaded count
- normalized and tagged row counts equal queue item count

Failure signals:

- `blocked > 0`: inspect `download_failures.jsonl` and logged response previews.
- `failed > 0`: inspect `ccr_bulk_failures.jsonl` and `download_failures.jsonl`.
- `pending > 0` after a retrieval run: resume with a higher or equal cap.
- `raw_file_missing > 0` in dataset/normalization summaries: rerun with `--resume`.
- HTML/text body recorded for a document URL: likely blocked or unexpected SOS response.
