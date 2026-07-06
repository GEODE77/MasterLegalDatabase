# Legislation Document Download Report

Generated: 2026-06-25

## Purpose

This report documents the LegiScan/Colorado bill document attachment acquisition run.
The goal was to move beyond bill metadata and download the document files referenced by
LegiScan bill records: bill texts, amendments, and supplements.

## Implemented

- Added a resumable document-download pipeline for archived LegiScan bill metadata.
- Added a CLI entry point:
  - `python -m geode.connectors.legiscan_documents`
  - `geode-legislation-documents`
- Added normalized document metadata outputs under:
  - `03_Legislation/_documents/bill_documents.jsonl`
  - `03_Legislation/_documents/bill_documents.csv`
  - `03_Legislation/_documents/bill_document_summary.json`
- Added raw document archive outputs under:
  - `_RAW_ARCHIVE/legiscan_documents/`
- Added a durable queue and manifest:
  - `_RAW_ARCHIVE/legiscan_documents/bill_document_queue.jsonl`
  - `_RAW_ARCHIVE/legiscan_documents/download_manifest.jsonl`
- Added resume behavior:
  - downloaded files are skipped when the manifest and checksum match the file.
  - permanent missing links are skipped on later runs.
  - rate-limited items remain retryable.
- Added safer source behavior:
  - 429 responses are marked `pending_retry`.
  - new runs stop after a 429 instead of creating a long failure streak.
  - stale 404 links are marked `failed_permanent`.
- Added queue reuse so resume runs no longer reparse all raw bill JSON files before
  downloading.

## Live Validation Run

The live source validation discovered:

- Total document work items: `85,848`
- Text documents: `57,695`
- Amendments: `16,372`
- Supplements: `11,781`

Current live acquisition state:

- Downloaded: `14,546`
- Permanent missing source links: `74`
- Pending retry from source rate limiting: `3,759`
- Not yet attempted: `67,469`

The current summary artifact is:

`03_Legislation/_documents/bill_document_summary.json`

## Commands Run

Focused tests:

```powershell
python -m pytest tests\test_legiscan_documents.py tests\test_legiscan.py tests\test_legislation_pipeline.py -q
```

Result:

`19 passed`

Lint:

```powershell
python -m ruff check geode\connectors\legiscan_documents.py tests\test_legiscan_documents.py pyproject.toml
```

Result:

`All checks passed`

Discovery-only inventory:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --discovery-only --json
```

Result:

`85,848` document work items discovered.

Small proof run:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 25 --year 2025 --category texts --delay 0.25 --json
```

Result:

`25` downloaded, `0` failed.

Controlled 500-document run:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 500 --delay 0.20 --json
```

Result:

`500` additional documents downloaded, `0` failed.

Controlled 2,000-document run:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 2000 --delay 0.10 --json
```

Result:

`2,000` additional documents downloaded, `0` failed.

Controlled 10,000-document run:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 10000 --delay 0.10 --json
```

Result:

`10,000` additional documents downloaded, `0` failed.

Long 20,000-document run:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 20000 --delay 0.10 --json
```

Result:

The run hit source-side `429` rate limiting before completion. The process was stopped,
and the code was patched so future 429s stop the current run cleanly instead of
continuing to generate repeated temporary failures.

Conservative resume probe:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 1 --delay 2.0 --max-retries 1 --json
```

Result:

`1` additional document downloaded. This proved the source could be accessed again at a
slower rate.

Conservative 100-document run:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 100 --delay 0.75 --max-retries 1 --json
```

Result:

`62` additional documents downloaded. `38` stale Colorado source links returned `404`
and are now tracked as permanent missing links.

No-network summary reconciliation:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 0 --json
```

Result:

Summary and normalized document metadata were rewritten from the existing queue and
manifest without performing network downloads.

## Findings

The document pipeline works and can download at scale, but the live source imposes
practical pacing limits.

The fast runs succeeded until the source began returning `429` responses. That is a
source-side rate limit, not a parsing or architecture failure. The downloader now treats
that as a temporary retry state and stops safely.

Some older 2017 Colorado document links are stale and return `404`. Tests against HTTPS,
lowercase path variants, and LegiScan document URLs did not recover the sampled file.
These are now recorded as `failed_permanent` so they are auditable and do not block
future resume runs.

## Current Status

The document acquisition path is operational and resume-safe.

Full completion was not achieved during this run because the public source rate-limited
the faster batch and the remaining workload is large:

- Remaining unattempted: `67,469`
- Temporary retry backlog: `3,759`

At a conservative pace of `0.75` seconds between requests, the remaining live download
work is a multi-hour run. It should be run in staged batches so source health and failure
patterns can be monitored.

## Recommended Next Commands

Continue at a conservative pace:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 1000 --delay 0.75 --max-retries 1 --json
```

If that completes without 429 responses, continue in larger conservative chunks:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 5000 --delay 0.75 --max-retries 1 --json
```

Refresh only the dataset summary without downloading:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --max-documents 0 --json
```

Force a queue refresh after new bill metadata is added:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --refresh-queue --max-documents 0 --json
```

## Success Signals

- `downloaded` increases in `03_Legislation/_documents/bill_document_summary.json`.
- `pending` decreases.
- `pending_retry` decreases after source rate limits cool down.
- `failed_permanent` may increase for stale source links, especially older documents.
- `failed` should remain `0` or very low. Nonzero `failed` means a real pipeline or
  network issue needs review.

## 2026-06-29 Legacy Archive Wrapper Repair

Further safe-bulk validation found that many older `www.leg.state.co.us` document URLs
return a `200 OK` HTML archive wrapper page instead of the expected PDF. Earlier runs
had counted those wrapper pages as successful downloads because the HTTP request itself
succeeded.

The connector now:

- rejects HTML archive wrappers when a PDF/DOC/DOCX is expected;
- reclassifies stale manifest rows that previously stored those wrappers as downloads;
- treats known legacy Colorado archive binary-document URLs as permanent source gaps
  without repeatedly requesting them;
- supports `--max-batches` for bounded safe-bulk validation runs.

Validated commands:

```powershell
python -m pytest tests\test_legiscan_documents.py tests\test_legiscan.py tests\test_legislation_pipeline.py -q
python -m ruff check geode\connectors\legiscan_documents.py tests\test_legiscan_documents.py pyproject.toml
python -m geode.connectors.legiscan_documents --output-root . --max-documents 0 --json
python -m geode.connectors.legiscan_documents --output-root . --safe-bulk --batch-size 100 --delay 2.0 --max-retries 1 --cooldown-seconds 900 --max-rate-limit-pauses 3 --rate-limit-delay-multiplier 1.5 --max-batches 1 --json
```

Latest status after validation:

- Records total: `85,848`
- Downloaded: `21,326`
- Permanent source gaps: `19,706`
- Retryable failures: `0`
- Pending retry: `0`
- Pending: `44,816`

The best next full continuation command is:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --safe-bulk --batch-size 500 --delay 2.0 --max-retries 1 --cooldown-seconds 900 --max-rate-limit-pauses 3 --rate-limit-delay-multiplier 1.5 --json
```

## 2026-06-30 Bulk Document Completion

The LegiScan bill document acquisition was completed through the safe-bulk path.

Final document state:

- Total document records: `85,848`
- Downloaded source documents: `61,883`
- Permanent source gaps: `23,965`
- Pending documents: `0`
- Retry backlog: `0`
- Active failures: `0`

Operational changes made during completion:

- Transient source/server errors such as `500` are now treated as retryable states,
  not hard pipeline failures.
- Safe-bulk logs now describe retryable source conditions more accurately instead
  of labeling every retry condition as a rate limit.
- The final run used controlled faster batches after the 2-second run proved healthy
  but too slow for practical completion.

Final successful acquisition command shape:

```powershell
python -m geode.connectors.legiscan_documents --output-root . --safe-bulk --batch-size 1000 --delay 0.75 --timeout-seconds 30 --max-retries 2 --cooldown-seconds 900 --max-rate-limit-pauses 3 --rate-limit-delay-multiplier 1.5 --max-batches 30 --json
```

Final normalization/index refresh:

```powershell
python -m geode.connectors.legiscan_pipeline --output-root . --json
```

Legislation dataset state after refresh:

- Bill records: `12,453`
- Raw bill files: `12,453`
- Legislation index rows: `12,453`
- Failed bill files: `0`
- Bill-to-statute crosswalk rows currently extracted: `7`

Final validation:

```powershell
python -m pytest tests\test_legiscan_documents.py tests\test_legiscan.py tests\test_legislation_pipeline.py -q
python -m ruff check geode\connectors\legiscan_documents.py tests\test_legiscan_documents.py geode\connectors\legiscan_pipeline.py tests\test_legislation_pipeline.py pyproject.toml
```

Result:

- `28` focused tests passed.
- Ruff checks passed.
