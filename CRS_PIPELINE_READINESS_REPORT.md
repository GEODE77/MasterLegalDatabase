# CRS Pipeline Readiness Report

Generated: 2026-06-23

## Objective

Work through the next Geode pipeline area after CCR and Colorado Register/eDocket:
Colorado Revised Statutes (CRS), under `01_Statutes_CRS/`.

## What Exists

The repository already had:

- `geode/connectors/crs_parser.py`
  - parses fixture-style CRS Markdown
  - parses SGML-like CRS title files
  - validates output through `StatuteSection`
- `geode/pipeline/run.py`
  - supported one CRS input file at a time
- `geode/pipeline/writer.py`
  - writes CRS title Markdown
  - writes section metadata JSONL
  - writes `01_Statutes_CRS/_index.jsonl`
  - updates the master manifest
- `tests/fixtures/crs/crs_title_25_fixture.txt`
  - small two-section CRS fixture for deterministic testing
- `01_Statutes_CRS/`
  - existed, but `_index.jsonl` was empty before this CRS pass
- `_RAW_ARCHIVE/crs/`
  - exists, but currently contains no official CRS source package

## What Was Implemented

### 1. Bulk CRS Runner

Added `geode/connectors/crs_bulk.py`.

The new runner can process all supported CRS source files under:

```text
_RAW_ARCHIVE/crs/
```

Supported source file patterns:

- `.sgml`
- `.xml`
- `.txt`
- `.md`

It writes:

```text
01_Statutes_CRS/_meta/crs_bulk_summary.json
```

It reports:

- discovered source files
- parsed titles
- sections written
- skipped files
- failed files
- per-file status

### 2. CRS Source Metadata Detection

Updated `geode/connectors/crs_parser.py`.

Added source detection for:

- fixture/frontmatter files
- SGML-like CRS title files

This lets bulk ingestion infer title number and publication year when available
from the source file itself.

### 3. CRS Bulk CLI Integration

Updated `geode/pipeline/run.py`.

New CRS bulk command:

```powershell
python -m geode.pipeline.run --layer crs --bulk --root .
```

Optional source directory:

```powershell
python -m geode.pipeline.run --layer crs --bulk --root . --input-dir _RAW_ARCHIVE/crs
```

Dry run:

```powershell
python -m geode.pipeline.run --layer crs --bulk --root . --dry-run
```

### 4. Statute-to-Regulation Crosswalk Builder

Added `geode/connectors/crs_crosswalk.py`.

The existing file:

```text
_CROSSWALKS/regulation_to_statute.jsonl
```

already had CCR-to-CRS candidate links. The new builder creates the inverse:

```text
_CROSSWALKS/statute_to_regulation.jsonl
```

The inverse relationship uses:

```text
relationship = "implements"
```

### 5. Crosswalk False-Positive Guard

During validation, the first inverse crosswalk pass exposed false positives in
the existing CCR-to-CRS candidates. Examples looked like CRS IDs but were really:

- phone numbers
- tracking numbers
- effective dates
- federal or technical references

The inverse builder was tightened so it only promotes rows where:

- the target looks like a plausible Colorado CRS ID, and
- the source evidence ties that specific citation to CRS/statutory wording

This intentionally favors precision over broad recall.

## Actual Run Results

Command run:

```powershell
python -m geode.pipeline.run --layer crs --bulk --root .
```

Result:

- CRS source files discovered: `0`
- CRS titles parsed: `0`
- CRS sections written: `0`
- failed CRS files: `0`
- skipped CRS files: `0`

This is conclusive: the official CRS source package is not currently present in
`_RAW_ARCHIVE/crs/`, so Geode cannot yet populate `01_Statutes_CRS/` with real
statute sections.

Crosswalk result:

- input `regulation_to_statute` rows: `696`
- output `statute_to_regulation` rows: `619`
- skipped ambiguous/implausible rows: `77`

## Validation

Layer validation:

```powershell
python -m geode.validate --layer 01_Statutes_CRS
```

Result: passed.

Focused tests:

```powershell
python -m pytest tests\test_crs_bulk.py tests\test_pipeline.py tests\test_remaining_connectors.py tests\test_validation.py -q
```

Result: `27 passed`.

Lint:

```powershell
python -m ruff check geode\connectors\crs_parser.py geode\connectors\crs_bulk.py geode\connectors\crs_crosswalk.py geode\pipeline\run.py tests\test_crs_bulk.py tests\test_pipeline.py tests\test_remaining_connectors.py tests\test_validation.py
```

Result: passed.

## Files Changed

- `geode/connectors/crs_parser.py`
- `geode/connectors/crs_bulk.py`
- `geode/connectors/crs_crosswalk.py`
- `geode/pipeline/run.py`
- `tests/test_crs_bulk.py`
- `01_Statutes_CRS/_meta/crs_bulk_summary.json`
- `_CROSSWALKS/statute_to_regulation.jsonl`

## Current CRS State

CRS ingestion architecture is now ready for a real bulk source package.

However, real CRS data is not yet loaded because the source files are absent.
The source registry says CRS bulk SGML is available by request from the Office
of Legislative Legal Services, not through an open public bulk endpoint.

Required source location once obtained:

```text
_RAW_ARCHIVE/crs/
```

Then run:

```powershell
python -m geode.pipeline.run --layer crs --bulk --root .
python -m geode.validate --layer 01_Statutes_CRS
```

## Conclusion

The CRS pipeline itself is operational for archived CRS source files.

What is blocked is not code execution. The blocker is source availability:
Geode needs the official CRS SGML/source package placed under `_RAW_ARCHIVE/crs/`
before it can populate `01_Statutes_CRS/` with the full Colorado Revised
Statutes.
