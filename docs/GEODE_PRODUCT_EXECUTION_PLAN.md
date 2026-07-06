# Geode Product Execution Plan

## Purpose

This plan turns the Geode master product direction into an execution sequence that preserves the
current Project Geode data architecture.

Geode should become a structured regulatory intelligence system. It should help users move from
source law to relationships, evidence, operational impact, and review paths. It should not become
a decorative dashboard, a fake AI chat interface, or a separate app database that competes with the
canonical corpus.

## Source-Of-Truth Rule

The existing Geode corpus remains the source of truth:

- `_RAW_ARCHIVE/` stores original downloaded material and must not be modified by product work.
- `_CONTROL_PLANE/` describes what exists, freshness, schemas, sources, and agencies.
- Layer folders store canonical Markdown and JSONL records.
- `_CROSSWALKS/` stores relationship records.
- `_SNAPSHOTS/` protects overwritten records.
- Validation and integrity checks remain the gate before canonical data changes.

Product indexes, API views, and web pages are derived from this corpus. They can be rebuilt from the
canonical files and must not become independent legal truth.

## Product Object Alignment

The master plan's product objects map to current Geode concepts this way:

| Product concept | Geode foundation | Execution decision |
| --- | --- | --- |
| Document | layer record or Markdown file | Use as the browsable source object. |
| Section | parsed heading or schema section | Derive for Explore before storing as canonical data. |
| Citation | citation extractor and crosswalks | Store unresolved citations when targets are unknown. |
| Relationship | `_CROSSWALKS/*.jsonl` | Use as the first graph substrate. |
| Requirement | `rule_unit` | Use "Requirement" as the product label for validated rule units. |
| Profile | product-layer object | Keep out of canonical corpus. |
| Impact assessment | derived result | Must include evidence and uncertainty. |
| Compliance path | derived review workflow | Must link every step to source evidence. |
| Change event | timeline/version record | Start with Updates before full diff. |

## Execution Sequence

### Phase 1: Product Foundation

Create this execution plan and a current-state audit. Do not change active download code, raw
archives, connectors, or shared ingest outputs.

Success looks like:

- Product direction is documented.
- Current gaps are visible.
- The source-of-truth boundary is explicit.

### Phase 2: Derived Product Index

Build a read-only product index layer that reads from the corpus and exposes product-ready objects:

- regulations
- relationships
- candidate requirements
- profile impact results
- compliance review steps

This can start as in-process TypeScript helpers for the current Next.js app. A persistent database
or rebuild command can follow after the product shape is proven.

Success looks like:

- Product pages do not manually duplicate file-reading logic.
- Derived data can be rebuilt from current corpus files.
- Missing data is shown as unknown instead of invented.

### Phase 3: Route Separation

Separate public marketing routes from internal product routes.

Public routes:

- `/`
- `/about`
- `/pricing`
- `/trust`
- `/sign-in`

Internal product routes:

- `/app/dashboard`
- `/app/explore`
- `/app/impact`
- `/app/compliance-paths`
- `/app/updates`
- `/app/settings`

Existing legacy routes may remain as compatibility paths while the product is moved.

### Phase 4: Explore MVP

Build Explore first. It should be the bridge between source data and all later product features.

The first version should focus on CCR regulations because the current corpus already has real CCR
records.

Explore should show:

- source document list
- selected regulation text
- citation, title, agency, and source link
- related statutes and rulemaking notices from crosswalks
- candidate requirement evidence
- uncertainty where Geode lacks data

### Phase 5: Requirement Layer

Use "Requirement" only as the user-facing product name for source-backed rule units. Until full
rule units are validated, label extracted items as candidate requirements or review signals.

Each requirement-like item must include:

- citation
- source excerpt
- reason it was surfaced
- confidence or uncertainty

### Phase 6: Impact Lens MVP

Add simple profiles and deterministic impact scoring.

Impact Lens should group results into:

- High Impact
- Medium Impact
- Low Impact
- Informational
- Unknown / Insufficient Data

Every result must explain why it appears. The explanation matters more than the numeric score.

### Phase 7: Compliance Path Builder MVP

Generate source-backed review paths. The first version should avoid final legal advice and should
frame each path as review work.

Each step must include:

- action type
- source citation
- source excerpt
- reason for inclusion
- status

### Phase 8: Updates Before Diff

Start with a simple Updates page based on ingestion activity, rulemaking records, and available
timeline data. Full regulation diff should wait until version storage is stable.

### Phase 9: Graph Later

Do not prioritize a visual graph until relationship coverage is reliable. The right early graph is
a structured relationship panel inside Explore.

## Safe Work Boundary During Active Downloads

Product work should not interfere with another active download process if it avoids:

- `_RAW_ARCHIVE/`
- connector modules under `geode/connectors/`
- active pipeline modules under `geode/pipeline/`
- manifest or index rewrites while ingestion is running
- bulk index rebuilds over half-written data

Read-only product pages may read completed corpus files. If active ingestion is still running,
derived product data should be treated as a snapshot of what was complete at read time.

## Recommended First Deliverable

The first durable product deliverable is:

> Explore MVP for CCR regulations with source text, relationships, candidate requirements, and
> clear missing-data signals.

This proves the product direction without weakening the corpus.

## Implemented Product Foundation

The first execution pass added these pieces:

- `/app/dashboard`
- `/app/explore`
- `/app/impact`
- `/app/compliance-paths`
- `/app/updates`
- `/app/settings`
- read-only product index helpers under `geode/web/src/lib/product/`
- source-backed product APIs under `/api/product/*`
- isolated build output support through `NEXT_DIST_DIR`

Current product API routes:

- `GET /api/product/regulations`
- `GET /api/product/regulations/[id]`
- `GET /api/product/impact`
- `GET /api/product/compliance-paths`
- `GET /api/product/updates`
- `GET /api/product/rule-units`

These APIs are product views over the corpus. They do not write canonical data.

## Implemented Rule-Unit Readiness Milestone

The product layer now has a forward-compatible rule-unit read path.

Current state:

- Geode has a `rule_unit` schema and tests.
- The current corpus does not yet contain canonical rule-unit records.
- Explore, Impact Lens, Compliance Paths, and product APIs now label requirement-like items as
  either `validated_rule_unit` or `candidate_signal`.
- When rule-unit JSONL files are added later, the product layer will read them first and stop using
  candidate signals for those regulations.

Expected rule-unit source files:

- `02_Regulations_CCR/_meta/rule_units.jsonl`
- `02_Regulations_CCR/_meta/ccr_rule_units.jsonl`
- `02_Regulations_CCR/_rule_units.jsonl`
- `data/structured_output/rule_units.jsonl`

This milestone improves trust. It lets Geode show useful review signals today while making it clear
that final requirement extraction depends on validated rule units.

## Implemented Deterministic Rule-Unit Extraction Milestone

Geode now has a first rule-unit production path for completed CCR Markdown records.

What it does:

- Reads `02_Regulations_CCR/_index.jsonl` and matching files in `02_Regulations_CCR/_rules/`.
- Extracts only source sentences with clear legal action language such as `shall`, `must`,
  `shall not`, `may not`, and `is required to`.
- Skips front-matter sections like definitions, purpose, statutory authority, history, and basis
  statements during this first deterministic requirement pass.
- Keeps the source sentence as both the evidence and the first-pass summary.
- Requires a visible regulated-entity phrase before writing a rule unit.
- Validates every record through the existing `RuleUnit` schema before writing.
- Writes the output to `02_Regulations_CCR/_meta/rule_units.jsonl`.
- Writes run details to `02_Regulations_CCR/_meta/rule_units_summary.json`.
- Writes quality-gate records to `02_Regulations_CCR/_meta/rule_units_quality.jsonl`.
- Writes pending review tasks to `02_Regulations_CCR/_meta/rule_units_review_queue.jsonl`.
- Writes review queue totals to `02_Regulations_CCR/_meta/rule_units_review_summary.json`.

Current run result:

- Records considered: 1,035
- Records with rule units: 652
- Rule units written: 13,059
- Failed records: 0
- High-quality rule units: 9,228
- Medium-quality rule units: 3,299
- Needs-review rule units: 532
- Pending review queue items: 532
- Split candidates: 67
- Revise candidates: 532
- Quarantine candidates: 1

This is still a deterministic first pass. It is useful because it gives Explore, Impact Lens, and
Compliance Paths real validated rule-unit records to work from, but it should not be treated as the
final high-precision extraction layer. The quality gate now scores source fidelity, atomicity,
exception capture, entity clarity, and temporal precision. Records that pass schema validation but
show quality risks remain available, but are separated for review.

## Implemented Needs-Review Workflow

The 532 needs-review rule units now have their own workflow instead of living only as a quality
count.

Each review task includes:

- pending status
- priority
- source sentence
- nearby source context
- current rule-unit record
- quality scores and issues
- allowed outcomes: approve, split, revise, quarantine
- suggested outcomes based on the quality issue

Product access:

- `GET /api/product/rule-units/review`
- `/app/review`

## Implemented Persistent Review Decisions

Review decisions now have an append-only log. This keeps the generated queue intact while recording
the human or model-assisted decision that should happen later.

Decision log:

- `02_Regulations_CCR/_meta/rule_units_review_decisions.jsonl`
- `02_Regulations_CCR/_meta/rule_units_review_decisions_summary.json`

Allowed outcomes:

- `approve`
- `split`
- `revise`
- `quarantine`

Rules:

- Decisions preserve the original source sentence.
- Decisions preserve the current extracted rule unit.
- `split` and `revise` decisions require proposed replacement rule units.
- The decision log does not mutate `rule_units.jsonl`.
- Canonical changes still require a later apply step.

Product access:

- `GET /api/product/rule-units/review/decisions`
- `POST /api/product/rule-units/review/decisions`

## Implemented Guarded Apply Proposal

Review decisions can now be converted into a proposed canonical patch without mutating
`rule_units.jsonl`.

Apply proposal:

- `02_Regulations_CCR/_meta/rule_units_apply_proposal.json`

Current proposal:

- Source rule units: 13,059
- Resulting rule units: 13,059
- Decisions considered: 0
- Proposed changes: 0
- Ready to apply: true

Rules:

- `approve` keeps the current rule unit.
- `quarantine` proposes removing the current rule unit.
- `revise` and `split` propose replacing the current rule unit with validated replacements.
- Invalid replacement records block the proposal.
- The proposal does not change canonical data.

Product access:

- `GET /api/product/rule-units/review/apply-proposal`

## Implemented Guarded Apply Command

Review decisions can now be applied to the canonical rule-unit file, but only through an explicit
guarded command.

Apply summary:

- `02_Regulations_CCR/_meta/rule_units_apply_summary.json`

Command access:

- `python -m geode.pipeline.rule_units --output-root . --apply-decisions --json`
- `python -m geode.pipeline.rule_units --output-root . --apply-decisions --allow-noop-apply --json`

Product access:

- `POST /api/product/rule-units/review/apply-proposal`
- `POST /api/product/rule-units/review/apply-proposal` with `{"action":"rebuild"}`
- Required confirmation phrase: `APPLY_RULE_UNIT_DECISIONS`

Rules:

- The apply command first rebuilds the proposal.
- Invalid replacement rule units block the apply.
- A run with no review decisions is refused unless no-op apply is explicitly allowed.
- A run that would not change canonical data is refused unless no-op apply is explicitly allowed.
- Real canonical changes are validated against the full `rule_units.jsonl` result.
- The previous canonical file is protected through the existing snapshot-and-atomic-write path.

Current state:

- No review decisions have been logged yet.
- No canonical apply has been performed on the live corpus.
- The current proposal remains a no-op over 13,059 source-backed rule units.

## Implemented Browser Review Controls

The review page can now record decisions from the browser while leaving canonical rule units
unchanged.

Product access:

- `/app/review`
- `POST /api/product/rule-units/review/decisions`
- `POST /api/product/rule-units/review/apply-proposal` with `{"action":"rebuild"}`

Reviewer actions:

- choose an allowed outcome
- record a rationale
- enter replacement records for `revise` and `split`
- save the decision to the append-only log
- rebuild the apply proposal preview after a save

Rules:

- Saving a review decision does not change `rule_units.jsonl`.
- The browser marks saved items during the current session to reduce accidental duplicate saves.
- The apply proposal still validates replacements before a later canonical apply.
- The final apply action still requires the explicit confirmation phrase.

Current state:

- The UI path exists, but no real review decision has been submitted during validation.
- The current proposal remains a no-op until real decisions are logged.

## Implemented Browser Apply Confirmation Panel

The review page now includes the final guarded apply panel for confirmed canonical changes.

Product access:

- `/app/review`
- `POST /api/product/rule-units/review/apply-proposal`

Reviewer actions:

- see how many canonical changes are in the current proposal
- see whether the apply proposal is ready or blocked
- review the first proposed rule-unit changes in the batch
- type the exact confirmation phrase before applying
- run the guarded apply command from the browser
- see the apply result message after completion

Rules:

- The apply button stays disabled unless the confirmation phrase is exact.
- The apply button stays disabled when there are no canonical changes.
- Approve-only decisions do not unlock the canonical apply action because they do not change
  `rule_units.jsonl`.
- The guarded backend command still validates the full proposal before writing canonical data.
- The previous canonical file is still protected by snapshot-and-atomic-write behavior.

Current state:

- No real review decision has been submitted during validation.
- No canonical apply has been performed from the browser.
- The current proposal remains a no-op until real decisions are logged.

## Next Recommended Product Milestone

The next milestone should make the review queue decision-aware. Items with logged decisions should
be visually separated from untouched pending items, and the queue should offer filters for pending,
approved, revised, split, quarantined, and canonical-change-ready batches.

## Implemented Decision-Aware Review Queue

The review queue is now decision-aware.

What changed:

- Review queue items now show whether they are pending, approved, revised, split, or quarantined.
- Items with existing logged decisions are visually separated and cannot be accidentally decided
  again from the browser.
- The review API supports status filters and returns a status summary.
- The review page has filters for pending, approved, revised, split, quarantined,
  canonical-change-ready, and all queue items.
- Canonical-change-ready items are surfaced separately when the guarded apply proposal has valid
  remove or replace changes.
- Step 3 now has a control-plane gate:
  `python -m geode.validation.step3_gate --root . --write --json`.

Current Step 3 gate result:

- Ready for Step 3 completion: yes
- Review queue items: 532
- Blockers: 0
- Deferred work: review the remaining queue items, apply only reviewed canonical changes, and add
  formal legal review before external reliance.

## Implemented Formal Review Packet Handoff

The review queue now has a formal packet handoff layer.

What changed:

- `python -m geode.pipeline.review_packets --root . --write --json` builds one review packet for
  every needs-review rule unit.
- Packets merge the review queue, latest logged decision when present, guarded apply readiness, the
  source sentence, source context, quality issues, current extraction, and reviewer instruction.
- Packets preserve a reliance boundary: they are not legal advice, do not change canonical law, and
  should not be externally relied on until reviewed.
- Packet output is written to:
  `02_Regulations_CCR/_meta/rule_units_review_packets.jsonl`.
- Packet summary is written to:
  `02_Regulations_CCR/_meta/rule_units_review_packets_summary.json`.
- Product access:
  - `GET /api/product/review-packets`
  - `/app/review-packets`
- Step 4 now has a control-plane gate:
  `python -m geode.validation.step4_gate --root . --write --json`.

Current Step 4 gate result:

- Ready for Step 4 completion: yes
- Formal review packets: 532
- Pending packets: 532
- Blockers: 0
- Deferred work: complete formal packet review, apply only reviewed canonical changes, and define
  production reliance policy.

## Implemented Production Reliance Policy

Geode now has a machine-readable reliance policy for reviewed outputs.

What changed:

- `python -m geode.pipeline.reliance_policy --root . --write --json` writes
  `_CONTROL_PLANE/RELIANCE_POLICY.json`.
- The policy defines approval levels:
  - research only
  - internal review
  - production reliance
- The policy defines reviewer roles:
  - data reviewer
  - corpus maintainer
  - legal reviewer
- The policy defines approval criteria for source fidelity, canonical validation, logged review
  decisions, and legal reviewer approval.
- The policy defines external-use limits and canonical-change rules.
- Product access:
  - `GET /api/product/reliance-policy`
  - `/app/reliance-policy`
- Step 5 now has a control-plane gate:
  `python -m geode.validation.step5_gate --root . --write --json`.

Current Step 5 gate result:

- Ready for Step 5 completion: yes
- Blockers: 0
- Deferred work: assign named reviewers, work the 532 review packets, and publish reviewer SOP
  training.

## Implemented Reviewer Operations Setup

Geode now has reviewer assignment slots and operating instructions.

What changed:

- `python -m geode.pipeline.reviewer_operations --root . --write --json` writes:
  - `_CONTROL_PLANE/REVIEWER_ASSIGNMENTS.json`
  - `_CONTROL_PLANE/REVIEWER_OPERATIONS_SUMMARY.json`
  - `docs/GEODE_REVIEWER_SOP.md`
- Reviewer assignment slots are created from the reliance policy roles:
  - data reviewer
  - corpus maintainer
  - legal reviewer
- No real people are assigned automatically. Each slot remains unassigned until a project owner
  authorizes named reviewers.
- The SOP defines boundaries, reviewer responsibilities, escalation paths, and the operating flow
  from packet review through guarded apply and legal review.
- Product access:
  - `GET /api/product/reviewer-operations`
  - `/app/reviewer-operations`
- Step 6 now has a control-plane gate:
  `python -m geode.validation.step6_gate --root . --write --json`.

Current Step 6 gate result:

- Ready for Step 6 completion: yes
- Required roles: 3
- Assigned roles: 0
- Unassigned roles: 3
- Blockers: 0
- Deferred work: name reviewers, train reviewers on the SOP, and start packet review.

## Implemented Update Ledger Before Full Text Diff

Geode now has a source-backed update ledger that can be used before a full legal text diff system
exists.

What changed:

- `python -m geode.pipeline.update_ledger --root . --write --json` writes:
  - `_CONTROL_PLANE/UPDATE_LEDGER.jsonl`
  - `_CONTROL_PLANE/UPDATE_LEDGER_SUMMARY.json`
- The ledger combines existing evidence from:
  - `_CONTROL_PLANE/MASTER_MANIFEST.json`
  - `_CONTROL_PLANE/UPDATE_LOG.jsonl`
  - `_CONTROL_PLANE/MASTER_TIMELINE_INDEX.jsonl`
  - Step readiness reports
- The ledger does not invent legal changes and does not compare full source text yet.
- Full text diff is clearly marked as queued, not ready.
- Product access:
  - `GET /api/product/updates`
  - `/app/updates`
- Step 8 now has a control-plane gate:
  `python -m geode.validation.step8_gate --root . --write --json`.

Current Step 8 gate result:

- Ready for Step 8 completion: yes
- Update ledger events: 2,618
- Blockers: 0
- Deferred work: add full legal text diff, add stable snapshot comparison, assign reviewers, and
  work the pending review packets.

## Implemented Relationship Coverage Before Visual Graph

Geode now measures relationship coverage before attempting a visual graph.

What changed:

- `python -m geode.pipeline.relationship_coverage --root . --write --json` writes:
  - `_CONTROL_PLANE/RELATIONSHIP_COVERAGE.jsonl`
  - `_CONTROL_PLANE/RELATIONSHIP_COVERAGE_REPORT.json`
- The report measures:
  - total relationship records
  - crosswalk file health
  - source and target coverage
  - missing source, target, and evidence counts
  - low-confidence relationship counts
  - duplicate relationship counts
  - CCR regulation relationship coverage
- The product now exposes relationship health at:
  - `GET /api/product/relationships`
  - `/app/relationships`
- Step 9 now has a control-plane gate:
  `python -m geode.validation.step9_gate --root . --write --json`.

Current Step 9 gate result:

- Ready for Step 9 completion: yes
- Relationship records measured: 9,958
- Crosswalk files checked: 6
- CCR regulations with relationships: 925 of 1,035
- CCR relationship coverage: 89%
- Blockers: 0
- Visual graph status: deferred
- Deferred work: build a visual graph only after relationship coverage and target resolution are
  stronger.

## Implemented Remaining Buildable Foundations

Geode now has buildable foundations for the remaining post-Step-9 work.

What changed:

- `python -m geode.pipeline.relationship_backfill --root . --write --json` populated:
  - `_CROSSWALKS/agency_to_statute.jsonl`
  - `_CROSSWALKS/amendment_history.jsonl`
  - `_CONTROL_PLANE/RELATIONSHIP_BACKFILL_SUMMARY.json`
- `python -m geode.pipeline.change_tracking --root . --write --json` writes:
  - `_CONTROL_PLANE/FULL_TEXT_DIFF.jsonl`
  - `_CONTROL_PLANE/FULL_TEXT_DIFF_SUMMARY.json`
  - `_CONTROL_PLANE/SOURCE_FRESHNESS_REPORT.json`
- `python -m geode.pipeline.retrieval_catalog --root . --write --json` writes:
  - `_CONTROL_PLANE/RETRIEVAL_CATALOG.jsonl`
  - `_CONTROL_PLANE/RETRIEVAL_CATALOG_SUMMARY.json`
- `python -m geode.pipeline.operations_readiness --root . --write --json` writes:
  - `_CONTROL_PLANE/PRODUCTION_READINESS_REPORT.json`
  - `_CONTROL_PLANE/REMAINING_WORK_QUEUE.json`
- Product access:
  - `GET /api/product/system`
  - `/app/system`

Current remaining-foundation results:

- Agency-to-statute rows: 696
- Amendment-history rows: 7
- Local text files checked for diff: 1,106
- Files with prior snapshots: 553
- Files changed against prior local snapshot: 53
- Retrieval catalog records: 57,127 across 7 layers
- Stale local manifest layers: 0
- Open remaining work items: 4

Work that still cannot honestly be completed by code alone:

- Assign 3 real reviewer roles.
- Review 532 pending review packets.
- Run official external source refresh checks with network access.
- Obtain legal reviewer approval before external reliance.
