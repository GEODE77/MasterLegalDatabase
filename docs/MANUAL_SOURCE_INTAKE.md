# Manual Source Intake

Manual source intake is the controlled path for official documents that cannot be
collected by Geode's automated downloaders.

It is meant for cases like `EO-2019-007`, where the official public link exists but
returns a sign-in page instead of the source document.

## What This Does

Manual intake preserves an official source file in:

`_RAW_ARCHIVE/manual_intake/`

It also writes:

- `_RAW_ARCHIVE/manual_intake/manual_source_intake_manifest.jsonl`
- `_CONTROL_PLANE/MANUAL_SOURCE_INTAKE_LEDGER.jsonl`
- `_CONTROL_PLANE/MANUAL_SOURCE_INTAKE_REPORT.json`

Each intake records the source file name, official source owner, reviewer, custody note,
hash, size, and archive path.

## What This Does Not Do

Manual intake does not automatically make the document part of a structured Geode layer.

After intake, the related layer still needs a pipeline rebuild and source-to-output audit.
For `EO-2019-007`, that means the Executive Orders layer must be rebuilt using the
manually archived artifact, then validated and audited.

## Required Information

Every manual intake needs:

- record ID, such as `EO-2019-007`
- Geode layer, such as `05_Executive_Orders`
- official source name
- acquisition method
- who or where the file came from
- reviewer name
- custody note
- original file

An official URL should be included when one exists.

## Command Shape

Run this first as a dry run:

```powershell
python -m geode.pipeline.manual_source_intake `
  --root . `
  --source-file "C:\path\to\official-file.pdf" `
  --record-id EO-2019-007 `
  --layer-id 05_Executive_Orders `
  --official-source-name "Colorado Governor's Office" `
  --official-source-url "https://www.colorado.gov/governor/2019-executive-orders" `
  --acquisition-method state_archives_request `
  --received-from "Colorado State Archives" `
  --reviewer-name "Reviewer Name" `
  --custody-note "Received as an official replacement source artifact for EO-2019-007." `
  --json
```

If the dry run looks correct, add `--apply` to archive the file.

## Boundary

Only official source artifacts should enter this workflow. Do not use edited,
OCR-corrected, summarized, or reformatted files as raw source evidence.
