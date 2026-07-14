# Source-To-Output Accuracy Audit

Generated: 2026-07-07T23:49:15.977037+00:00

This audit compares Geode output records to the local source files recorded for them.

- Records checked: 57,155
- Independent raw-archive source records: 57,155
- Source text checked: 57,155
- High accuracy: 53,035
- Medium accuracy: 4,120
- Low accuracy: 0
- Metadata only: 0
- Not independently source-checkable: 0
- Missing source files: 0
- Missing output files: 0
- Output record missing inside output file: 0
- Raw hash mismatches: 0

## Layer Summary

| Layer | Records | Raw Source | Text Checked | High | Medium | Low | Metadata Only | Not Independent | Missing Source | Missing Output | Missing Record | Hash Mismatch |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01_Statutes_CRS | 34,717 | 34,717 | 34,717 | 34,715 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 02_Regulations_CCR | 1,035 | 1,035 | 1,035 | 1,035 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 03_Legislation | 12,453 | 12,453 | 12,453 | 12,453 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 04_Rulemaking | 7,955 | 7,955 | 7,955 | 3,860 | 4,095 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 05_Executive_Orders | 535 | 535 | 535 | 535 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 06_Session_Laws | 437 | 437 | 437 | 437 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 07_Supplementary | 23 | 23 | 23 | 0 | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Lowest-Evidence Samples

- None.

## Files

- Machine report: `_CONTROL_PLANE/SOURCE_TO_OUTPUT_ACCURACY_AUDIT.json`
- Per-record rows: `_CONTROL_PLANE/SOURCE_TO_OUTPUT_ACCURACY_RECORDS.jsonl`
- Repair queue: `_CONTROL_PLANE/SOURCE_TO_OUTPUT_ACCURACY_REPAIR_QUEUE.json`

## Boundary

This audit compares Geode's local structured output to the local source files recorded for each item. It does not prove the source file is the newest official law, and PDF text checks are identity/evidence checks rather than full legal redlines.
