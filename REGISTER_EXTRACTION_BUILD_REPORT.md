# Register Extraction Build Report

Generated: 2026-06-23

## What Was Implemented

Geode now has a stronger Colorado Register extraction path that is tied into the
existing `geode.connectors.register_pipeline` runner.

Completed build items:

- Added table-first extraction for Colorado Register publications.
- Preserved source provenance on normalized rulemaking notices:
  - source section heading
  - source row number
  - source evidence preview
  - notice-type rule source
  - field confidence scores
- Added extraction quality artifacts:
  - aggregate quality report
  - extraction gap report
  - quarantine report
  - high-confidence review sample
  - low-confidence review sample
  - quarantine review sample
- Added optional eDocket detail-page fetching from discovered Register tracking
  numbers.
- Added optional eDocket attachment archiving for linked PDF/DOC files.
- Added the `_RAW_ARCHIVE/edocket` archive path mapping.
- Fixed an extraction-layer lint defect where `geode.extractors.ensemble` used
  LLM helper functions without importing them.

## Validated Results

Local Register normalization from the existing archive completed successfully:

- Source Register publications: 437
- Normalized rulemaking notices: 7,933
- Publications with extracted notices: 437
- Extraction failures: 0
- Gap rows: 0
- Quarantine rows: 0
- eDocket references in normalized notices: 314
- Rulemaking-to-regulation crosswalk rows: 7,933

Full live eDocket run completed successfully:

- Detail pages requested: 314
- Detail pages fetched or reused: 314
- Detail pages newly downloaded: 309
- Detail pages reused from prior proof run: 5
- Detail-page failures: 0
- Linked attachments downloaded or reused: 515
- Linked attachments newly downloaded: 506
- Linked attachments reused from prior proof run: 9
- Attachment failures: 0

## Main Output Locations

- `04_Rulemaking/_dataset/rulemaking_notices.jsonl`
- `04_Rulemaking/_dataset/rulemaking_notices.csv`
- `04_Rulemaking/_dataset/rulemaking_summary.json`
- `04_Rulemaking/_dataset/edocket_details.jsonl`
- `04_Rulemaking/_dataset/edocket_documents.jsonl`
- `04_Rulemaking/_quality/register_extraction_quality.json`
- `04_Rulemaking/_quality/register_extraction_gaps.jsonl`
- `04_Rulemaking/_quality/register_extraction_quarantine.jsonl`
- `04_Rulemaking/_index.jsonl`
- `04_Rulemaking/{year}/register_{year}_Q{quarter}.jsonl`
- `_CROSSWALKS/rulemaking_to_regulation.jsonl`
- `_RAW_ARCHIVE/edocket/`

## Commands Run

Local archived Register normalization:

```powershell
python -m geode.connectors.register_pipeline --output-root . --json
```

Live eDocket detail proof:

```powershell
python -m geode.connectors.register_pipeline --output-root . --fetch-edocket-details --max-edocket-details 5 --edocket-delay 1.0 --json
```

Live eDocket attachment proof:

```powershell
python -m geode.connectors.register_pipeline --output-root . --fetch-edocket-details --max-edocket-details 5 --download-edocket-documents --edocket-delay 1.0 --json
```

Full live eDocket detail and attachment run:

```powershell
python -m geode.connectors.register_pipeline --output-root . --fetch-edocket-details --download-edocket-documents --edocket-delay 1.0 --json
```

Layer validation:

```powershell
python -m geode.validate --layer 04_Rulemaking
```

Focused tests:

```powershell
python -m pytest tests\test_register_table_parser.py tests\test_register_pipeline.py tests\test_archive_paths.py tests\test_remaining_connectors.py -q
```

Full tests:

```powershell
python -m pytest tests -q
```

Repository lint:

```powershell
python -m ruff check geode tests
```

## Validation Status

- Focused tests: 27 passed.
- Full tests: 222 passed.
- Repository lint: passed.
- `04_Rulemaking` validation: passed.
- Live Register re-download was not rerun during this build; the normalization
  run used the already downloaded 437-publication Register archive.
- Live eDocket detail and attachment fetching completed for all 314 discovered
  eDocket tracking numbers.

## Remaining Limits

- The Register table extractor is deterministic and evidence-preserving, but it
  still does not legally interpret the text.
- eDocket fetching starts from eDocket links already visible in Register-derived
  records. It is not a separate, independent eDocket crawler.
- Full eDocket attachment backfill for all discovered tracking numbers was run
  successfully in this coding session.
- If the Secretary of State site blocks a future run, Geode records the failure
  instead of attempting evasive behavior.

## Recommended Next Operator Command

To verify the current completed eDocket outputs:

```powershell
python -m geode.validate --layer 04_Rulemaking
```
