# CCR Normalized Acquisition Dataset Schema

The CCR acquisition dataset is written under:

`02_Regulations_CCR/_dataset/`

It is generated from the append-only CCR bulk queue and download manifest, so it can be
rebuilt safely after resumed runs without multiplying duplicate items.

## Artifacts

- `ccr_items.jsonl` - one normalized CCR acquisition record per line.
- `ccr_items.csv` - the same records with stable column order for spreadsheet analysis.
- `ccr_dataset_summary.json` - counts, input artifact paths, and duplicate-collapse stats.

Downloaded source documents remain in `_RAW_ARCHIVE/ccr/`; dataset rows reference their
stored paths without copying or transforming the raw source files.

## Record Fields

| Field | Type | Notes |
|---|---|---|
| `record_id` | string | Stable internal ID, usually canonical CCR ID such as `5_CCR_1001-9`. |
| `title` | string or null | Best available title. Current SOS browse metadata usually supplies the CCR citation. |
| `rule_name` | string or null | Populated only when a non-citation rule name is available. |
| `department` | string or null | Department text as acquired from SOS/manifest. |
| `department_normalized` | string or null | Whitespace-normalized department with leading numeric display codes removed. |
| `agency` | string or null | Agency, board, division, or program text as acquired. |
| `agency_normalized` | string or null | Whitespace-normalized agency with leading numeric display codes removed. |
| `division_board_program` | string or null | Set from normalized agency when it clearly names a board, commission, division, office, or program. |
| `ccr_citation` | string or null | Citation such as `5 CCR 1001-9`. |
| `department_number` | string or null | Parsed leading CCR number when available. |
| `chapter` | string or null | Parsed chapter/series value when available. |
| `rule_number` | string or null | Parsed rule number after the CCR chapter dash when available. |
| `source_page_url` | string or null | SOS page used to discover or resolve the rule. |
| `document_url` | string or null | PDF/DOC/DOCX attachment URL selected for retrieval. |
| `file_path` | string or null | Stored raw file path from the manifest or expected queue target. |
| `content_type` | string or null | Expected content type inferred from source format/path. |
| `source_format` | string or null | `pdf`, `docx`, `doc`, `html`, etc. when known. |
| `download_status` | string | Current acquisition status: `indexed`, `resolved`, `downloaded`, `skipped_existing`, `failed`, `blocked`, or `unknown`. |
| `discovery_timestamp` | datetime or null | First queue timestamp for the item. |
| `retrieval_timestamp` | datetime or null | Manifest download/failure timestamp or terminal queue timestamp. |
| `checksum_sha256` | string or null | SHA-256 for downloaded raw file when available. |
| `size_bytes` | integer or null | Raw file size from manifest when available. |
| `text_extraction_status` | string | Currently `not_attempted`; extraction exists elsewhere but is not part of acquisition. |
| `raw_file_exists` | boolean | Whether the stored raw file path exists at dataset generation time. |
| `notes` | string or null | Compact operator note for pending, failed, blocked, or missing-file states. |
| `error` | string or null | Failure/blocking error text when recorded. |

## Idempotency

The writer collapses queue rows by `record_id`, preserving the latest event for each
item and the first discovery timestamp. It also collapses download manifest rows by
`record_id`, preserving the latest manifest row. The JSONL, CSV, and summary are then
rewritten atomically, so rerunning after a resume updates records instead of appending
duplicates.
