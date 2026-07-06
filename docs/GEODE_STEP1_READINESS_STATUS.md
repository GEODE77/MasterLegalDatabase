# Geode Step 1 Readiness Status

Generated: 2026-06-30

## Current Gate Result

Geode is ready to enter Step 2.

Step 1 requires the legal corpus to be collected, structured, indexed, and quality-gated before
query and retrieval work becomes the main focus. The current readiness gate shows:

- Complete layers: 0 of 7
- Ready layers: 7 of 7
- Partial layers: 0 of 7
- Blocked layers: 0 of 7
- Empty layers: 0 of 7
- Ready for Step 2: yes

The machine-readable gate report is:

```text
_CONTROL_PLANE/STEP1_READINESS_REPORT.json
```

## Status Meaning

The gate now uses five status levels:

- `complete`: the layer is fully collected, structured, indexed, and declared complete.
- `ready`: the layer has enough structured records and source evidence to be useful in Geode.
- `partial`: the layer has useful starter coverage, but it is not broad enough to treat as Step 1 done.
- `blocked`: some source evidence exists, but the layer has no usable structured corpus yet.
- `empty`: the layer has no structured records and no raw source evidence yet.

Step 2 should not become the main workstream until every required layer is at least `ready`.
The long-term target is for each layer to become `complete`.

## Ready Layers

These layers currently have structured indexes, manifest counts, and raw source evidence:

- `02_Regulations_CCR`
- `03_Legislation`
- `04_Rulemaking`
- `01_Statutes_CRS`
- `05_Executive_Orders`
- `06_Session_Laws`
- `07_Supplementary`

## Remaining Coverage Notes

No layer is blocked or empty. Some layers still have long-term improvement opportunities, but they
no longer block Step 2 query and retrieval work.

## Source-Specific Status

### CRS

The official CRS bulk source package has been archived and structured.

Current structured output:

- 34,717 statute-section records
- 46 CRS title files
- `01_Statutes_CRS/_index.jsonl`
- `01_Statutes_CRS/_meta/crs_subject_index.jsonl`
- raw source archive under `_RAW_ARCHIVE/crs/2025-10-01/`

### Executive Orders

The executive-order connector now follows the official Governor year pages and downloads the
Governor-linked source documents.

Current structured output:

- 533 executive-order records
- `05_Executive_Orders/_index.jsonl`
- decade JSONL output under `05_Executive_Orders/`
- raw PDFs under `_RAW_ARCHIVE/exec_orders/`

Two downloaded PDFs were left out because their signed dates could not be extracted from the
source text without guessing: `EO-2019-007` and `EO-2019-010`.

### Session Laws

The session-law collector now structures the current official General Assembly session-law table.

Current structured output:

- 437 records
- `06_Session_Laws/_index.jsonl`
- `06_Session_Laws/_meta/session_laws_meta.jsonl`
- `06_Session_Laws/2026/session_laws_2026.jsonl`
- raw source-page evidence under `_RAW_ARCHIVE/crs/session_laws/`

This layer is ready in the Step 1 gate. Historical expansion remains a future improvement.

### Supplementary Documents

The supplementary layer now includes Attorney General opinions and COPRRR reviews.

Current structured output:

- 2 AG opinion records
- 17 COPRRR review records
- `07_Supplementary/_index.jsonl`
- `07_Supplementary/_meta/ag_opinions_meta.jsonl`
- `07_Supplementary/_meta/coprrr_reviews_meta.jsonl`
- `07_Supplementary/ag_opinions/ag_opinions_2024.jsonl`
- `07_Supplementary/ag_opinions/ag_opinions_2026.jsonl`
- `07_Supplementary/coprrr_reviews/coprrr_reviews_2025.jsonl`
- raw PDFs under `_RAW_ARCHIVE/supplementary/ag_opinions/`
- raw PDFs under `_RAW_ARCHIVE/supplementary/coprrr/`

This layer is ready in the Step 1 gate.

## Step 2 Gate

Do not treat Geode as being in Step 2 until the readiness command reports:

```text
ready_for_step_2: true
```

Run the gate with:

```powershell
python -m geode.validation.step1_gate --root . --write --json
```

## Next Execution Focus

Step 2 can begin: build query and retrieval over the ready corpus.

Recommended cleanup before or during early Step 2:

1. Add a small exception report for the 2 executive-order PDFs missing extractable signed dates.
2. Preserve alternate CRS effective-version records in a sidecar, since the main CRS layer keeps
   one current/latest record per CRS section ID.
3. Expand historical session-law coverage when an official historical source is available.
