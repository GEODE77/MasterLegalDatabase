# Legislation Bulk Acquisition Report

Generated: 2026-06-25

## Outcome

The controlled LegiScan bulk acquisition completed successfully for all Colorado sessions
returned by LegiScan.

Final result:

- LegiScan sessions processed: `22`
- Expected LegiScan items from session master lists: `12,453`
- Raw archived JSON files: `12,453`
- Normalized Geode legislation records: `12,453`
- Normalization failures: `0`
- Duplicate normalized IDs: `0`
- Final-run download failures: `0`
- Bill-to-statute crosswalk rows currently extracted: `7`

Official output locations:

- `_RAW_ARCHIVE/legiscan/`
- `_RAW_ARCHIVE/legiscan/download_manifest.jsonl`
- `03_Legislation/_dataset/bills.jsonl`
- `03_Legislation/_dataset/bills.csv`
- `03_Legislation/_dataset/legislation_summary.json`
- `03_Legislation/_meta/bills_meta.jsonl`
- `03_Legislation/_index.jsonl`
- `03_Legislation/{year}/bills_{year}.jsonl`
- `_CROSSWALKS/bill_to_statute.jsonl`

## Final Year Counts

| Year | Records |
|---|---:|
| 2010 | 784 |
| 2011 | 710 |
| 2012 | 645 |
| 2013 | 734 |
| 2014 | 710 |
| 2015 | 762 |
| 2016 | 788 |
| 2017 | 769 |
| 2018 | 784 |
| 2019 | 654 |
| 2020 | 748 |
| 2021 | 678 |
| 2022 | 717 |
| 2023 | 696 |
| 2024 | 792 |
| 2025 | 768 |
| 2026 | 714 |

Total: `12,453`

## Problems Found and Fixed During the Run

### 1. Live LegiScan bill detail shape differed from fixture shape

The live `getBill` response used `bill_number`, while the client originally expected
`number`.

Fix:

- Updated `geode/connectors/legiscan_client.py` to accept either field.
- Added regression coverage in `tests/test_legiscan.py`.

### 2. API key appeared in third-party HTTP logs during the first probe

The first diagnostic request printed the full URL through `httpx` logging.

Fix:

- Updated `geode/utils/logging.py` to suppress `httpx` and `httpcore` INFO logging.

Security note:

- The key is not stored in source code.
- If the first diagnostic terminal output is saved in any shared location, rotate the
  LegiScan key.

### 3. Colorado bill numbers can be four digits

Real records such as `HB1001` did not fit the earlier three-digit-only bill schema.

Fix:

- Updated `geode/schemas/models.py` to allow three- or four-digit bill numbers.
- Updated `geode/connectors/legiscan_transformer.py` to preserve `HB1001` as
  `HB25-1001`, not incorrectly collapse it.

### 4. LegiScan includes resolutions and memorials in the legislation stream

The initial schema only accepted bill and joint/concurrent resolution prefixes. Live data
also included:

- `HR`
- `HM`
- `SR`
- `SM`
- `HJM`
- `SJM`

Fix:

- Updated the transformer and schema to accept these as valid legislation-layer records.
- Added regression tests.

### 5. Special sessions reused regular-session bill numbers

Colorado special sessions can reuse bill numbers such as `HB1001`. A plain ID like
`HB25-1001` would collide with the regular session.

Fix:

- Added special-session-aware IDs using the LegiScan URL/session suffix.
- Example:
  - Regular session: `HB25-1001`
  - First special session: `HB25X1-1001`
- Verified final duplicate count is `0`.

### 6. OneDrive/Windows file locking interrupted a manifest write

One manifest append hit a transient Windows/OneDrive access-denied error.

Fix:

- Updated `geode/connectors/legiscan_client.py` to use unique temp files and retry atomic
  replacement for raw archive and manifest writes.
- Reconciled the archive afterward.

## Commands Run

Representative acquisition commands:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --max-downloads 500 --delay 0.25 --json
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --max-downloads 1000 --delay 0.25 --json
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --max-downloads 2500 --delay 0.25 --json
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --max-downloads 1500 --delay 0.25 --json
```

Archive-only reconciliation command:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --json
```

Layer validation:

```powershell
python -m geode.validate --layer 03_Legislation
```

## Validation Results

Final legislation layer validation:

- `python -m geode.validate --layer 03_Legislation`
- Result: passed

Focused tests:

- `python -m pytest tests\test_legiscan.py tests\test_legislation_pipeline.py tests\test_schemas.py -q`
- Result: `22 passed`

Lint:

- `python -m ruff check geode tests`
- Result: passed

Full test suite:

- `python -m pytest tests -q`
- Result: blocked by unrelated web module import:
  - `ModuleNotFoundError: No module named 'geode.web.db'`

This web-index failure is outside the LegiScan acquisition path. The current `geode/web`
tree contains frontend files, but the Python backend module expected by
`tests/test_web_index.py` is not present.

## Current Known Notes

- The manifest contains `12,453` successful `downloaded` rows and `8` historical failed
  rows from interrupted or pre-fix attempts. This is acceptable audit history because every
  final raw file exists and every final raw file normalized successfully.
- `bill_to_statute` currently has only `7` rows. That reflects the current citation
  extraction from LegiScan metadata/body fields, not a download failure. A deeper bill text
  document extraction pass may increase this substantially later.
- Bulk acquisition is complete for LegiScan's available Colorado sessions as of this run.

## Operational Recommendation

Future refreshes should use the same resumable command:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --download --all-sessions --max-downloads 1000 --delay 0.25 --json
python -m geode.validate --layer 03_Legislation
```

If the run is interrupted, reconcile with:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --json
python -m geode.validate --layer 03_Legislation
```

