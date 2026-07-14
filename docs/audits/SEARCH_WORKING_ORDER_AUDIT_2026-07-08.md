# Search Working Order Audit - 2026-07-08

Historical note: this audit includes former frontend verification details.
Geode is now backend-only; retain this file as dated evidence, not current
architecture.

## Scope

Audited the public Geode search path:

- Query page summary behavior
- `/api/query` search flow
- Local Python read-index search
- SQLite read-index contents
- CCR citation handling
- Off-OneDrive production build path

## Findings

1. Exact CCR citation searches were too broad.
   A search such as `5 CCR 1001-14` could return nearby `5 CCR 1001-*` records before the exact rule.

2. CCR rule text was not fully represented in the search database.
   The index builder preferred compact metadata sidecars over the richer CCR Markdown rule files.

3. Human-style questions over-weighted filler words.
   Phrases such as `should leadership review before expanding...` could steer the scan toward weak terms.

4. Citation aliases could be overwritten by later event records.
   Rulemaking notices using the same citation text could replace the core CCR rule alias.

5. OneDrive continued to interfere with build output and temporary files.
   Production build verification needs to run outside OneDrive.

## Fixes Completed

- Added exact citation-shaped matching for CCR and CRS identifiers.
- Updated the read-index builder to prefer CCR rule Markdown text over metadata summaries.
- Raised the direct indexing limit for CCR rule Markdown while keeping a smaller limit for broad files.
- Added stop words and topic-first chunk scanning for more natural questions.
- Changed alias insertion so later event records do not overwrite core authority aliases.
- Updated the off-OneDrive build script to use a fresh temp folder per run.
- Added a `.gitignore` rule for locked `geode/web/_tmp_*` files.
- Rebuilt the local search database from a tested temp database after snapshotting the prior copy.

## Verification

- `pytest tests/test_web_index.py -q` passed.
- Frontend TypeScript check passed.
- Frontend lint passed.
- Off-OneDrive production build passed.
- Smoke search for `5 CCR 1001-14` now returns `5_CCR_1001-14` first with CCR rule text.
- Alias `5 ccr 1001 14` now resolves to `5_CCR_1001-14`.

## Remaining Watch Item

Broad operational questions can still return several legally plausible sources. That is expected for a local keyword/ranking system with no AI API, but ranking can continue to improve by adding curated domain boosts for common business scenarios.
