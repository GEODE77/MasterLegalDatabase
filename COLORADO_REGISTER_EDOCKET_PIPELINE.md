# Colorado Register And eDocket Pipeline

This pipeline expands Geode beyond active CCR rule documents by normalizing
Colorado Register rulemaking notices and preserving eDocket references when they
are visible in the source text.

## Purpose

The CCR pipeline captures current active regulations. The Register/eDocket
pipeline captures rulemaking activity around those regulations, including
proposed, adopted, emergency, amended, and hearing-related notices when those
details are present in source publications.

## Operational Flow

```text
_RAW_ARCHIVE/register/download_manifest.jsonl
-> archived Colorado Register HTML/PDF publications
-> table-first rulemaking notice extraction
-> 04_Rulemaking/
-> _CROSSWALKS/rulemaking_to_regulation.jsonl
```

## Outputs

The normalized pipeline writes:

- `04_Rulemaking/_dataset/rulemaking_notices.jsonl`
- `04_Rulemaking/_dataset/rulemaking_notices.csv`
- `04_Rulemaking/_dataset/rulemaking_summary.json`
- `04_Rulemaking/_meta/rulemaking_notices_meta.jsonl`
- `04_Rulemaking/_index.jsonl`
- `04_Rulemaking/{year}/register_{year}_Q{quarter}.jsonl`
- `04_Rulemaking/_quality/register_extraction_quality.json`
- `04_Rulemaking/_quality/register_extraction_gaps.jsonl`
- `04_Rulemaking/_quality/register_extraction_quarantine.jsonl`
- `04_Rulemaking/_quality/review_sample_high_confidence.jsonl`
- `04_Rulemaking/_quality/review_sample_low_confidence.jsonl`
- `04_Rulemaking/_quality/review_sample_quarantine.jsonl`
- `04_Rulemaking/_dataset/edocket_details.jsonl` when eDocket detail fetching is enabled
- `04_Rulemaking/_dataset/edocket_documents.jsonl` when eDocket detail fetching is enabled
- `_CROSSWALKS/rulemaking_to_regulation.jsonl`

## Record Fields

Each normalized rulemaking notice includes the base Geode
`rulemaking_notice` schema plus optional Register/eDocket traceability fields:

- `id`
- `title`
- `notice_type`
- `ccr_rule_affected`
- `ccr_citation`
- `agency_code`
- `agency`
- `summary`
- `publication_date`
- `hearing_date`
- `effective_date`
- `edocket_tracking_number`
- `edocket_url`
- `subject_tags`
- `source_url`
- `source_path`
- `raw_text_path`
- `extraction_method`
- `source_section_heading`
- `source_row_number`
- `source_evidence`
- `notice_type_source`
- `field_confidence`
- `confidence`

## Commands

Normalize already archived Register publications:

```powershell
python -m geode.connectors.register_pipeline --output-root . --json
```

Attempt live Register download, then normalize:

```powershell
python -m geode.connectors.register_pipeline --output-root . --download --delay 1.0 --json
```

Attempt historical Register backfill by year range, then normalize:

```powershell
python -m geode.connectors.register_pipeline --output-root . --download --start-year 2012 --end-year 2026 --delay 1.0 --json
```

Fetch a small controlled eDocket detail sample from already normalized Register
records:

```powershell
python -m geode.connectors.register_pipeline --output-root . --fetch-edocket-details --max-edocket-details 5 --edocket-delay 1.0 --json
```

Fetch eDocket detail pages and archive linked PDF/DOC attachments:

```powershell
python -m geode.connectors.register_pipeline --output-root . --fetch-edocket-details --download-edocket-documents --max-edocket-details 5 --edocket-delay 1.0 --json
```

Fetch all currently discovered eDocket detail pages and linked attachments at a
conservative pace:

```powershell
python -m geode.connectors.register_pipeline --output-root . --fetch-edocket-details --download-edocket-documents --edocket-delay 1.0 --json
```

Run through the existing general connector downloader:

```powershell
python -m geode.connectors.run --connectors colorado_register --root . --delay 1.0 --json
```

## Current Live Access Note

On 2026-06-23, the archived Register normalization path completed from local
raw files. The live eDocket detail and attachment path also completed for all
314 discovered tracking numbers, archiving 314 detail pages and 515 linked
PDF/DOC attachments with no blocked or failed records. The code does not
implement evasive anti-bot behavior; if the source blocks a future run, the
failure is recorded rather than bypassed.

## Known Limitations

- eDocket detail fetching starts from tracking numbers visible in normalized
  Register records.
- eDocket attachment downloading is explicit and optional.
- PDF extraction depends on the repository's existing document conversion stack.
- The first-pass Register extractor is deterministic and table-oriented. It does
  not claim legal interpretation; it preserves source evidence for review.
