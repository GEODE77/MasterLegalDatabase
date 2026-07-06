# Manual Source Intake Request Template

Use this template when an official source artifact is received outside the automated
download pipeline.

## Required Fields

- Record ID:
- Geode layer:
- Official source name:
- Official source URL, if available:
- Acquisition method:
- Received from:
- Reviewer name:
- Reviewer email:
- Custody note:
- Source file path:
- Expected SHA-256, if independently supplied:

## Accepted Acquisition Methods

- `official_email`
- `state_archives_request`
- `manual_official_download`
- `public_records_request`
- `other_official_transfer`

## Review Checklist

- The file came from an official source owner or official archive.
- The file is not edited, summarized, OCR-corrected, or reformatted.
- The file is not already inside `_RAW_ARCHIVE`.
- The custody note explains how the file was obtained.
- The dry run was reviewed before `--apply` was used.

## Follow-Up

After the file is archived, rebuild the related structured layer and rerun source-to-output
accuracy checks.
