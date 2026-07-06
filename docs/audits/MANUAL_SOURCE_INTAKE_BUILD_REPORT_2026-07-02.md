# Manual Source Intake Build Report - 2026-07-02

## Result

Geode now has a controlled manual source intake workflow for official documents that
cannot be collected through automated downloaders.

This was built for blocked-source cases such as `EO-2019-007`, where the official public
download currently returns a Google sign-in page instead of a usable Executive Order PDF.

## Added

- Executable intake module: `geode/pipeline/manual_source_intake.py`
- Command alias: `geode-manual-source-intake`
- Control-plane policy: `_CONTROL_PLANE/MANUAL_SOURCE_INTAKE_POLICY.json`
- Control-plane report: `_CONTROL_PLANE/MANUAL_SOURCE_INTAKE_REPORT.json`
- Human guide: `docs/MANUAL_SOURCE_INTAKE.md`
- Request template: `docs/templates/MANUAL_SOURCE_INTAKE_REQUEST_TEMPLATE.md`

## Controls

The workflow:

- rejects unofficial source URLs when a URL is provided
- rejects empty source files
- rejects source files already inside `_RAW_ARCHIVE`
- blocks duplicate intake of the same file for the same record by default
- writes the received file to `_RAW_ARCHIVE/manual_intake/`
- records SHA-256, size, reviewer, source owner, custody note, and archive path
- annotates a matching blocked-download queue item as pending pipeline rebuild

## Boundary

Manual intake archives official source evidence only. It does not automatically structure
the document, certify the law, or mark a blocked item complete.

For `EO-2019-007`, the next step after receiving a valid official copy is:

1. Run manual source intake with `--apply`.
2. Rebuild the Executive Orders layer using the manually archived artifact.
3. Rerun source anchoring, validation, and source-to-output accuracy audits.

## Verification

Focused tests passed:

- `tests/test_manual_source_intake.py`
- `tests/test_operations_readiness.py`
- `tests/test_remaining_connectors.py`
- `tests/test_exec_orders_source_anchoring.py`

Operations readiness now reports `MANUAL-SOURCE-INTAKE` as ready.
