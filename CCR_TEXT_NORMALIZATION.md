# CCR Text Normalization

This document describes the CCR raw-document to `RegulationRule` normalization stage.

The stage is implemented in `geode.pipeline.ccr_text` and uses the existing acquisition
outputs as input. It does not create a parallel downloader or identity system.

## Input Artifacts

The normal input is the existing CCR bulk output under an operator-selected output root:

```text
_RAW_ARCHIVE/ccr/ccr_bulk_queue.jsonl
_RAW_ARCHIVE/ccr/download_manifest.jsonl
_RAW_ARCHIVE/ccr/*.pdf|*.docx|*.doc
02_Regulations_CCR/_dataset/ccr_items.jsonl
```

If `ccr_items.jsonl` is stale or missing, the text-normalization command first rebuilds
the normalized acquisition dataset from queue and manifest artifacts.

## Output Artifacts

The stage writes schema-validated `regulation_rule` records through
`geode.pipeline.writer.write_record`:

```text
02_Regulations_CCR/_rules/{canonical_id}.md
02_Regulations_CCR/_meta/ccr_rules_meta.jsonl
02_Regulations_CCR/_index.jsonl
02_Regulations_CCR/ccr_dept_{department_slug}.md
02_Regulations_CCR/_normalized/ccr_text_normalization_summary.json
_CROSSWALKS/regulation_to_statute.jsonl
_CONTROL_PLANE/MASTER_TIMELINE_INDEX.jsonl
_CONTROL_PLANE/UPDATE_LOG.jsonl
_CONTROL_PLANE/MASTER_MANIFEST.json
```

The per-rule Markdown files are the writer-managed canonical text outputs. The
department Markdown files are rebuilt aggregate views from `ccr_rules_meta.jsonl` so
resumed staged runs do not drop previously normalized records.

## Record Construction

For each downloaded CCR acquisition record, the stage:

- resolves the raw archive file path
- converts PDF/DOCX/DOC to Markdown with the existing converter
- extracts CRS citations from the converted text
- extracts an explicit effective date only when one appears in source text
- derives subject and industry tags from the existing deterministic CCR tagger
- derives controlled compliance keywords from source text
- validates the resulting payload as `RegulationRule`
- writes through `write_record`, including crosswalks and timeline events when present

If an effective date cannot be extracted, `effective_date` is `null`. The schema allows
this so Geode does not invent dates.

## Commands

Normalize downloaded CCR records into full-text regulation records:

```powershell
python -m geode.pipeline.ccr_text --output-root . --max-items 100 --json
```

Equivalent via the existing pipeline runner:

```powershell
python -m geode.pipeline.run --layer ccr --normalize-text --root . --max-items 100
```

Run only selected canonical IDs:

```powershell
python -m geode.pipeline.ccr_text --output-root . --record-id 5_CCR_1001-9 --json
```

Run the CCR pilot set listed in `_CONTROL_PLANE/PILOT_TEST_SET.json`:

```powershell
python -m geode.pipeline.ccr_text --output-root . --pilot --json
```

Preview without writes:

```powershell
python -m geode.pipeline.ccr_text --output-root . --max-items 10 --dry-run --json
```

## Resume Behavior

The writer upserts by record ID in metadata, index, crosswalk, timeline, and manifest
artifacts. Rerunning the command updates the same canonical records instead of creating
duplicates.

Rows without downloaded raw files are skipped. Rows with non-citation fallback IDs are
quarantined rather than forced into invalid `RegulationRule` IDs.

## Limits

- This is deterministic structural normalization, not full semantic rule-unit parsing.
- PDF/DOCX/DOC conversion quality depends on available local converter dependencies.
- Effective dates are extracted only from explicit source text patterns.
- Crosswalks currently use extracted CRS citations with `relationship: cites`; deeper
  `authorized_by` classification remains future work.
