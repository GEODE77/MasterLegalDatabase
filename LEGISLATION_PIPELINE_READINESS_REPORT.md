# Legislation Pipeline Readiness Report

Generated: 2026-06-23

## Purpose

This pass reviewed and improved the bills and legislation path in Geode. The goal was to
audit before changing anything, then make targeted changes that improve bill acquisition,
normalization, validation, and long-run operator readiness.

## Five-Step Review

### 1. Actual System Audited

Relevant files and paths found:

- `geode/connectors/legiscan_client.py`
  - Existing LegiScan API client.
  - Supports Colorado session discovery, bill list retrieval, bill detail retrieval,
    raw JSON archiving, manifest-backed resume, per-run download caps, and delay between
    requests.
- `geode/connectors/legiscan_transformer.py`
  - Existing transformer from LegiScan raw JSON into Geode `Bill` records.
- `geode/pipeline/run.py`
  - Existing sample bill processing workflow.
  - Writes to `data/structured_output/`, not the official `03_Legislation/` layer.
- `03_Legislation/`
  - Official legislation layer exists.
  - Before this pass, it did not have a complete archive-to-normalized bulk path.
- `_RAW_ARCHIVE/legiscan/`
  - Raw LegiScan archive location exists.
  - Current live workspace has zero archived raw bill JSON files.
- `_CROSSWALKS/`
  - Existing crosswalk layer. The bill-to-statute output now writes here as
    `_CROSSWALKS/bill_to_statute.jsonl`.
- `_CONTROL_PLANE/ONTOLOGY.json`
  - Controlled vocabulary used to prevent invented or stale tags.
- `_CONTROL_PLANE/MASTER_MANIFEST.json`
  - Updated by the new legislation normalization path.

### 2. Gaps Found

- The repository had a LegiScan downloader, but no clean bulk normalization bridge from
  `_RAW_ARCHIVE/legiscan/` into the official `03_Legislation/` layer.
- The sample bill workflow worked conceptually but depended on packages that were not
  declared as runtime dependencies:
  - `jsonschema`
  - `networkx`
  - `jinja2`
- The existing transformer emitted stale or non-ontology tags for labor/employment and tax.
- The downloader had detailed session accounting internally, but the public one-session
  path only returned raw bills. That made operator reporting weaker than it needed to be.
- Live LegiScan download is currently blocked because `LEGISCAN_API_KEY` is not configured.

### 3. Changes Implemented

- Added `geode/connectors/legiscan_pipeline.py`
  - Normalizes archived LegiScan bill JSON into:
    - `03_Legislation/_dataset/bills.jsonl`
    - `03_Legislation/_dataset/bills.csv`
    - `03_Legislation/_dataset/legislation_summary.json`
    - `03_Legislation/_meta/bills_meta.jsonl`
    - `03_Legislation/_index.jsonl`
    - `03_Legislation/{year}/bills_{year}.jsonl`
    - `_CROSSWALKS/bill_to_statute.jsonl`
  - Deduplicates by canonical Geode bill ID.
  - Validates records through the existing `Bill` schema.
  - Produces empty but auditable outputs when no archive files exist.
  - Can optionally download from LegiScan first, then normalize.
- Updated `geode/connectors/legiscan_client.py`
  - Added `download_session_report()` so callers can get detailed download accounting
    without importing private helper functions.
- Updated `geode/connectors/legiscan_transformer.py`
  - Changed labor/employment tagging to the current ontology tag:
    `labor_employment`.
  - Removed the stale tax tag mapping because the current ontology does not define a tax
    tag.
- Updated `pyproject.toml`
  - Added missing runtime dependencies for the bill sample workflow:
    `jinja2`, `jsonschema`, and `networkx`.
  - Added the `geode-legislation-pipeline` CLI entry point.
- Added `tests/test_legislation_pipeline.py`
  - Covers archived LegiScan normalization.
  - Covers empty archive behavior.
  - Covers current ontology tag behavior.

### 4. Validation Run

Commands executed:

```powershell
python -m pytest tests\test_legislation_pipeline.py tests\test_legiscan.py -q
```

Result:

- `8 passed`

```powershell
python -m ruff check geode\connectors\legiscan_client.py geode\connectors\legiscan_transformer.py geode\connectors\legiscan_pipeline.py tests\test_legiscan.py tests\test_legislation_pipeline.py
```

Result:

- `All checks passed`

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --json
```

Result:

- Completed successfully.
- `raw_files_total`: `0`
- `records_total`: `0`
- `failed_files`: `0`
- Empty official output files were created under `03_Legislation/`.

```powershell
python -m geode.validate --layer 03_Legislation
```

Result:

- Validation passed for `03_Legislation`.

```powershell
python -m geode.pipeline.run --root . --sample --format both
```

Result:

- Sample mode completed.
- Parsed/skipped existing sample inputs: 5 already present.
- Enriched: 5
- Validated: 5 pass, 0 warn, 0 fail
- Graph generated: 5 bills, 1 edge
- Formatted: 5 bills, 10 output files
- Tagged: 5 bills
- Indexes generated:
  - `bill_graph.json`
  - `industry_index.json`
  - `theme_index.json`

```powershell
python -m pytest tests -q
```

Result:

- `229 passed`

```powershell
python -m ruff check geode tests
```

Result:

- `All checks passed`

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --session-year 2026 --max-downloads 1 --json
```

Result:

- Failed before network access because `LEGISCAN_API_KEY` is not configured.
- Error:
  - `LEGISCAN_API_KEY is required for live LegiScan calls`

### 5. Readiness Assessment

The legislation pipeline is now structurally ready to process archived LegiScan bill data
into the official Geode legislation layer.

The live acquisition path is not yet proven in this environment because the LegiScan API key
is missing. Once the API key is configured, the downloader can be run in capped batches,
with resume support through `_RAW_ARCHIVE/legiscan/download_manifest.jsonl`.

## Output Locations

Official legislation outputs:

- `03_Legislation/_dataset/bills.jsonl`
- `03_Legislation/_dataset/bills.csv`
- `03_Legislation/_dataset/legislation_summary.json`
- `03_Legislation/_meta/bills_meta.jsonl`
- `03_Legislation/_index.jsonl`
- `03_Legislation/{year}/bills_{year}.jsonl`

Raw source archive:

- `_RAW_ARCHIVE/legiscan/{year}/{bill_id}.json`

Download manifest:

- `_RAW_ARCHIVE/legiscan/download_manifest.jsonl`

Crosswalk output:

- `_CROSSWALKS/bill_to_statute.jsonl`

Sample bill workflow outputs:

- `data/structured_output/bills/`
- `data/structured_output/indices/`
- `data/structured_output/validation_report.json`

## Operator Commands

### Set API Key

Use the real LegiScan API key before live downloads:

```powershell
$env:LEGISCAN_API_KEY = "YOUR_KEY_HERE"
```

### Small Controlled 2026 Download

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --session-year 2026 --max-downloads 25 --delay 0.25 --json
```

### Normalize Existing Archive Only

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --json
```

### Validate Official Legislation Layer

```powershell
python -m geode.validate --layer 03_Legislation
```

### Larger Single-Session Download

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --session-year 2026 --max-downloads 250 --delay 0.25 --json
```

### All Sessions, Capped

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --max-downloads 500 --delay 0.25 --json
```

### Continue All Sessions

Run the same command again. Existing downloaded bills are skipped by manifest and checksum:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --max-downloads 500 --delay 0.25 --json
```

### Uncapped All-Session Run

Use this only after capped runs are stable:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --delay 0.25 --json
```

## Success Signals

- `download_manifest.jsonl` gains one row per attempted bill.
- Raw bill JSON appears under `_RAW_ARCHIVE/legiscan/{year}/`.
- `03_Legislation/_dataset/bills.jsonl` record count increases.
- `03_Legislation/_index.jsonl` record count matches the official dataset.
- `_CROSSWALKS/bill_to_statute.jsonl` gains rows when bills mention CRS citations.
- `legislation_summary.json` reports:
  - `raw_files_total`
  - `records_total`
  - `failed_files`
  - `downloaded_bills`
  - `download_failed`
- `python -m geode.validate --layer 03_Legislation` passes.

## Failure Signals

- `LEGISCAN_API_KEY is required for live LegiScan calls`
  - The API key is missing.
- `download_failed` is greater than zero
  - Some bill fetches failed. Check `_RAW_ARCHIVE/legiscan/download_manifest.jsonl`.
- `failed_files` is greater than zero
  - Some archived JSON files could not be transformed into valid Geode bill records.
- Validation fails for `03_Legislation`
  - The normalized layer has schema or file-layout issues that should be fixed before a
    larger run.

## Remaining Blockers

- A real `LEGISCAN_API_KEY` must be configured before live bill acquisition can run.
- The current workspace has no archived LegiScan bill JSON files, so the official
  legislation layer is structurally ready but not populated with real bill records yet.
- The sample bill workflow writes to `data/structured_output/`. It is useful for local
  parsing, validation, formatting, graph, and tagging checks, but it is separate from the
  official `03_Legislation/` corpus.

## 2026-06-24 API Key Validation Update

The LegiScan API key was tested with a one-bill live 2025 session probe. The key is not
stored in tracked source code. It should be supplied through `LEGISCAN_API_KEY` at runtime.

Initial live probe findings:

- LegiScan API authentication worked.
- `getSessionList` worked.
- `getMasterList` worked.
- `getBill` worked.
- The first probe exposed two real integration issues:
  - Third-party HTTP logging printed the full request URL, including the API key.
  - The live `getBill` response used `bill_number`, while the client expected `number`.

Fixes completed after the probe:

- Suppressed `httpx` and `httpcore` INFO logging in CLI logging setup so API keys are not
  printed in request URLs.
- Updated the client to accept either `number` or `bill_number` from LegiScan bill-detail
  responses.
- Updated bill-number parsing so real Colorado bill numbers such as `HB1001` normalize to
  `HB25-1001`.
- Updated the `Bill` schema to allow three- or four-digit Colorado bill numbers.
- Fixed sponsor chamber normalization so LegiScan `Rep` sponsors become `House` and
  `Sen` sponsors become `Senate`.

Second live probe result:

- Command shape:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --session-year 2025 --max-downloads 1 --delay 0.25 --json
```

- Result:
  - `downloaded_bills`: `1`
  - `download_failed`: `0`
  - `raw_files_total`: `1`
  - `records_total`: `1`
  - `failed_files`: `0`
  - Normalized bill: `HB25-1001`
  - Output year file: `03_Legislation/2025/bills_2025.jsonl`

Post-fix validation:

```powershell
python -m pytest tests\test_legiscan.py tests\test_legislation_pipeline.py tests\test_schemas.py -q
```

Result:

- `20 passed`

```powershell
python -m pytest tests -q
```

Result:

- `231 passed`

```powershell
python -m ruff check geode tests
```

Result:

- `All checks passed`

```powershell
python -m geode.validate --layer 03_Legislation
```

Result:

- Validation passed for `03_Legislation`.

## LegiScan Bulk Strategy

Recommended run strategy:

1. Start with one current session and a small cap.
   - Purpose: prove authentication, live response shape, archive writing, normalization,
     validation, and manifest behavior.
   - Current proof has already succeeded for 2025 with one bill.

2. Expand the same session in controlled chunks.
   - Recommended command:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --session-year 2025 --max-downloads 100 --delay 0.25 --json
python -m geode.validate --layer 03_Legislation
```

3. Continue the same command until the session is complete.
   - The manifest skips already downloaded bill files.
   - Each run should increase `raw_files_total` and `records_total` until the session is
     exhausted.

4. Move to all sessions with a conservative cap.
   - Recommended command:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --max-downloads 500 --delay 0.25 --json
python -m geode.validate --layer 03_Legislation
```

5. Only run uncapped after capped all-session runs are stable.
   - Recommended command:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --delay 0.25 --json
python -m geode.validate --layer 03_Legislation
```

Operational rule:

- If `download_failed` or `failed_files` becomes greater than zero, stop expansion and inspect:
  - `_RAW_ARCHIVE/legiscan/download_manifest.jsonl`
  - `03_Legislation/_dataset/legislation_summary.json`

Security note:

- Because the first diagnostic run printed the key through third-party HTTP logging before the
  logging fix was applied, rotate the LegiScan API key if that terminal output is stored in
  any shared or persistent location.

## 2026-06-25 Bulk Acquisition Completion

The controlled LegiScan bulk acquisition was completed after the readiness work above.

Final bulk result:

- Raw archived LegiScan JSON files: `12,453`
- Normalized legislation records: `12,453`
- Failed normalized files: `0`
- Duplicate normalized IDs: `0`
- Final `03_Legislation` validation: passed

Detailed run report:

- `LEGISLATION_BULK_ACQUISITION_REPORT.md`
