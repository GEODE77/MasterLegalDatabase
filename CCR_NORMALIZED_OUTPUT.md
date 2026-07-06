# CCR Normalized Output

This document describes the bulk CCR archive-to-normalized output flow.

The normalized flow is written by `geode.connectors.ccr_dataset.write_ccr_dataset`,
which is called automatically by the CCR bulk runner after discovery/download work:

```bash
python -m geode.connectors.ccr_bulk --output-root . --max-items 100 --resume
```

The flow is deterministic and rebuilds normalized outputs from CCR acquisition
artifacts, primarily:

- `_RAW_ARCHIVE/ccr/ccr_bulk_queue.jsonl`
- `_RAW_ARCHIVE/ccr/download_manifest.jsonl`

It does not fabricate final parsed legal text. Bulk records are stored as
`regulation_rule_acquisition` metadata until a later text-extraction/parser stage can
produce full schema-valid `RegulationRule` records.

## Final Directory Structure

Under the selected output root, the bulk path now populates:

```text
02_Regulations_CCR/
  _index.jsonl
  _meta/
    ccr_normalized_meta.jsonl
  _normalized/
    ccr_normalized_records.jsonl
    ccr_normalization_summary.json
    records/
      {canonical_item_id}.json
  _dataset/
    ccr_items.jsonl
    ccr_items.csv
    ccr_dataset_summary.json
```

The `_dataset/` files are the analyzable acquisition table. The `_normalized/`,
`_meta/`, and `_index.jsonl` files are the final CCR layer population for bulk
acquisition metadata.

## Normalized Record Fields

Each `02_Regulations_CCR/_normalized/records/{id}.json` record contains:

| Field | Description |
|---|---|
| `id` | Stable Geode CCR acquisition ID, such as `5_CCR_1001-9`. |
| `canonical_item_id` | Same stable canonical item ID, included for explicitness. |
| `entity_type` | `regulation_rule_acquisition` until full legal-text parsing is available. |
| `title` | Best title available from SOS metadata, usually the CCR citation. |
| `rule_name` | Non-citation rule name when available. |
| `department` / `department_normalized` | Raw and normalized department text. |
| `agency` / `agency_normalized` | Raw and normalized agency/division/board text. |
| `division_board_program` | Board/division/program value when clearly present in metadata. |
| `ccr_citation` | Citation such as `5 CCR 1001-9`. |
| `department_number` | Parsed leading CCR department/title number when available. |
| `chapter` | Parsed chapter/series number when available. |
| `rule_number` | Parsed rule number when available. |
| `source_page_url` | SOS rule-info or source page URL. |
| `document_url` | Selected SOS document URL when resolved. |
| `archive_raw_file_path` | Raw downloaded file path from `_RAW_ARCHIVE/ccr`. |
| `normalized_output_path` | Root-relative per-record normalized JSON path. |
| `metadata_output_path` | Root-relative consolidated metadata JSONL path. |
| `content_type` | Expected content type inferred from source format. |
| `source_format` | Source format such as `pdf`, `docx`, or `doc`. |
| `discovery_timestamp` | First queue timestamp for the item. |
| `retrieval_timestamp` | Download/failure timestamp when available. |
| `normalization_timestamp` | Time the normalized record was written. |
| `normalization_status` | `normalized` when the final layer record has been written. |
| `status` | Current acquisition status: `discovered`, `resolved`, `downloaded`, `skipped_existing`, `failed_permanent`, `blocked`, or `pending_retry`. |
| `checksum_sha256` | Raw file checksum when downloaded. |
| `size_bytes` | Raw file size when downloaded. |
| `raw_file_exists` | Whether the referenced raw file exists at normalization time. |
| `text_extraction_status` | Currently `not_attempted`; conversion is a later stage. |
| `text_output_path` | Future text derivative path, currently null. |
| `notes` / `error` | Operator notes and failure/blocking detail. |

## Raw-To-Normalized Mapping

The mapping is intentionally traceable:

- queue item ID -> `id` and `canonical_item_id`
- queue first timestamp -> `discovery_timestamp`
- latest queue status / manifest status -> `status`
- manifest `source_url` -> `document_url`
- manifest `source_page_url` -> `source_page_url`
- manifest `archive_path` -> `archive_raw_file_path`
- manifest `sha256` -> `checksum_sha256`
- manifest `size_bytes` -> `size_bytes`
- normalized record path -> `normalized_output_path`

Raw files are never modified or moved by normalization.

## Rerun And Resume Behavior

Normalization is rebuild-based:

- queue and manifest rows are collapsed by stable item ID
- the latest acquisition state is written
- `_index.jsonl`, `_meta/ccr_normalized_meta.jsonl`, and
  `_normalized/ccr_normalized_records.jsonl` are rewritten atomically
- per-record JSON files are overwritten atomically
- stale generated JSON files under `_normalized/records/` are removed when no longer
  present in the current normalized record set

This prevents duplicate drift across resumed runs. Existing files are written through
the repository atomic write helpers, which snapshot prior versions under `_SNAPSHOTS`.

## Limitations

- This is a normalized acquisition metadata flow, not full legal-text extraction.
- Existing PDF/DOC/DOCX conversion helpers are not invoked by the bulk normalization
  step because large-scale conversion needs separate quality and performance controls.
- Full schema-valid `RegulationRule` records still require extracted text, enabling
  statute discovery, effective dates, summaries, subject tags, and industry tags.
