# CCR ID And State Model

This document describes the canonical identity and run-state model used by the
CCR discovery, retrieval, normalization, and resume paths.

## Canonical ID Strategy

CCR item identity is centralized in `geode.connectors.ccr_identity`.

The canonical ID is selected in this order:

1. Official CCR citation from metadata, page URLs, document URLs, or page content.
   - Example: `5 CCR 1001-9` becomes `5_CCR_1001-9`.
   - Already-normalized IDs such as `5_CCR_1001-9` map back to the same ID.
2. SOS rule ID when a citation is not yet available.
   - Example: `ruleId=3154` becomes `CCR_RULEID_3154`.
3. SOS rule-version ID when only a document URL is available.
   - Example: `ruleVersionId=11979` becomes `CCR_RULEVERSION_11979`.
4. Deterministic URL hash fallback.
   - Example: `CCR_URL_{sha256-prefix}`.

The citation is preferred because it is stable across single-rule and bulk runs. SOS
IDs are used only as deterministic fallbacks until discovery or rule-info resolution
finds the official citation.

## Where The ID Is Used

The same canonical ID is used across:

- `ccr_bulk_queue.jsonl` as `item_id`
- `download_manifest.jsonl` as `document_id`
- `download_failures.jsonl` as `document_id`
- `ccr_bulk_failures.jsonl` as `item_id`
- `_RAW_ARCHIVE/ccr/{id}.{pdf|doc|docx}` raw document paths
- `02_Regulations_CCR/_dataset/ccr_items.{jsonl,csv}` as `id`
- `02_Regulations_CCR/_normalized/records/{id}.json`
- `02_Regulations_CCR/_index.jsonl` and `_meta/ccr_normalized_meta.jsonl`
- Single-rule CCR pipeline output stems when a resolved citation is available

This prevents duplicate drift between a bulk-discovered item and a later single-rule
run for the same CCR citation.

## Status Model

The active status vocabulary is:

| Status | Meaning |
|---|---|
| `discovered` | Found on an SOS agency/index page; detail page may not be resolved yet. |
| `resolved` | Rule-info page was resolved to document URLs. |
| `downloaded` | Raw archive file exists and manifest metadata matches the file. |
| `normalized` | Final layer metadata record has been written under `02_Regulations_CCR/`; stored as `normalization_status` so acquisition `status` is not lost. |
| `skipped_existing` | Bulk retrieval found an already-valid raw archive file. |
| `failed_permanent` | Non-retryable failure recorded for operator review. |
| `blocked` | 403/challenge/access-denied behavior was detected and logged. |
| `pending_retry` | Reserved for retryable deferred failures; current runs resolve retries inline. |

Legacy rows are normalized during read:

- `indexed` is treated as `discovered`.
- `failed` is treated as `failed_permanent`.

## Artifact Relationships

Operational artifacts live under `_RAW_ARCHIVE/ccr`:

- `ccr_bulk_queue.jsonl` is append-only workflow state.
- `ccr_bulk_checkpoint.json` stores the latest bulk-run counters and last item.
- `ccr_bulk_summary.json` stores deterministic run totals and output paths.
- `ccr_bulk_failures.jsonl` stores bulk phase failures.
- `download_manifest.jsonl` stores raw document acquisition state.
- `download_failures.jsonl` stores document retrieval failures and blocked outcomes.

Final normalized acquisition outputs live under `02_Regulations_CCR/`:

- `_dataset/ccr_items.jsonl`
- `_dataset/ccr_items.csv`
- `_dataset/ccr_dataset_summary.json`
- `_normalized/records/{id}.json`
- `_normalized/ccr_normalized_records.jsonl`
- `_normalized/ccr_normalization_summary.json`
- `_meta/ccr_normalized_meta.jsonl`
- `_index.jsonl`

## Resume Reconciliation Rules

Resume uses `reconcile_download_state` before fetching document content.

- If the manifest says `downloaded`, the file must exist, have a supported document
  signature, and match the manifest checksum.
- If a valid raw file exists but the manifest is missing or incomplete, the downloader
  appends a repaired `downloaded` manifest row and skips the network request.
- If metadata exists but the file is missing or checksum-invalid, the item is treated
  as recoverable and is fetched again.
- If a prior manifest row is `blocked` or `failed_permanent`, that terminal state is
  preserved for auditability.
- Bulk resume counts terminal queued items toward `--max-items`, so a resumed limited
  run does not silently discover extra work beyond the requested cap.
- Normalization is rebuild-based and collapses queue/manifest rows by canonical ID, so
  reruns update the latest state without multiplying records.

## Consistency Expectations

For a healthy completed item:

- queue latest status is `downloaded` or `skipped_existing`
- manifest latest status is `downloaded`
- raw archive path exists
- normalized dataset has one record for the canonical ID
- normalized per-record JSON exists under `02_Regulations_CCR/_normalized/records/`
- normalized per-record JSON has `normalization_status` set to `normalized`

For a blocked item:

- queue latest status is `blocked`
- manifest or failure row records `blocked`
- failure rows include the same canonical ID and diagnostic error text
- normalized outputs preserve the blocked status and error notes

For an interrupted run:

- checkpoint status may be `running`, `paused`, or `interrupted`
- queue and manifest rows remain append-only
- rerunning with `--resume` continues from latest per-item state
