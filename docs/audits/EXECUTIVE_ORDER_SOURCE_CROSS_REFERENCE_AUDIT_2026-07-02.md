# Executive Order Source Cross-Reference Audit - 2026-07-02

## Scope

This audit covers the Executive Orders refresh that ran on 2026-07-02.

No new valid Executive Order PDF was downloaded during the final refresh. The run
cross-checked 535 official source entries, skipped 534 already-valid archived PDFs, and
queued 1 failed official download.

## Original Source Check

The live Colorado Governor Executive Orders listing was checked again.

- Official entries discovered: 535
- Unique Executive Order IDs discovered: 535
- EO-2019-007 present in the official listing: yes
- EO-2019-007 listing page: `https://www.colorado.gov/governor/2019-executive-orders`
- EO-2019-007 official download URL:
  `https://drive.google.com/uc?export=download&id=0B7w3bkFgg92dZ1ZiX2pKb1Z0eDdVZTdndmFaN1pLNEE2bnZj`

A targeted fetch of the EO-2019-007 official download URL returned:

- HTTP status: 200
- Final URL host: `accounts.google.com`
- Content type: `text/html; charset=utf-8`
- Bytes received: 939,207
- Result: rejected as a Google sign-in or preview page, not an Executive Order PDF

## Local Archive Cross-Check

The local Executive Orders archive and structured output were cross-referenced.

- Download manifest rows: 535
- Latest manifest IDs: 535
- Failure rows: 1
- Failed ID: EO-2019-007
- Structured Executive Order records: 534
- Executive Order index rows: 534

Integrity checks:

- Structured records missing raw PDFs: 0
- Raw PDF hash mismatches against manifest: 0
- Structured records missing manifest rows: 0
- Structured records missing index rows: 0
- Structured source URL mismatches against manifest: 0
- Raw artifacts not represented in structured output: EO-2019-007 only

## Source-To-Output Result

The broader source-to-output audit was also refreshed.

- Total Geode records checked: 57,154
- Executive Order records checked: 534
- Executive Order high-accuracy records: 534
- Executive Order medium-accuracy records: 0
- Executive Order low-accuracy records: 0

## Conclusion

The Executive Orders layer is internally consistent for the 534 usable records. Each
structured Executive Order points back to a raw archived source PDF, the raw PDF hashes
match the manifest, and the structured index matches the output records.

EO-2019-007 is correctly excluded from structured output because the current official
download route returns a Google sign-in page instead of the Executive Order PDF. This is
now queued as blocked work rather than counted as a valid source.

## Remaining Action

Request a valid official EO-2019-007 copy from the Governor's Office or State Archives.
Once that source artifact is available, add it through the official source-intake
workflow and rerun the Executive Orders source-anchoring and source-to-output audits.
