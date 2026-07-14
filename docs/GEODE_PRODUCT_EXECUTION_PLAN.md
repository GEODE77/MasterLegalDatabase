# Geode Backend Execution Plan

## Purpose

This plan describes Geode as a backend regulatory intelligence database for
Colorado legal authority across the state, county, and municipal hierarchy. Its
consumers are AI models, agents, APIs, search systems, ingestion operators, and
downstream tools.

The central product is the orchestration engine: deterministic Python code that
sits between an LLM and the Geode knowledge layer. The LLM writes; it does not
decide.

## Source-Of-Truth Rule

The existing Geode corpus remains the source of truth:

- `_RAW_ARCHIVE/` stores original downloaded material and must not be modified.
- `_CONTROL_PLANE/` describes what exists, freshness, schemas, sources, and agencies.
- Layer folders store canonical Markdown and JSONL records.
- `_CROSSWALKS/` stores relationship records.
- `_SNAPSHOTS/` protects overwritten records.
- Validation and integrity checks remain the gate before canonical data changes.

APIs, exports, search indexes, and orchestrated answers are derived from this
corpus. They can be rebuilt and must not become independent legal truth.

## Architecture Direction

The orchestration engine runs in six ordered layers:

1. **Input & Interpretation** - normalize requests and identify topic,
   jurisdiction, entities, time period, ambiguity, and answer shape.
2. **Planning & Retrieval** - choose the required manifest entries, indexes,
   legal texts, metadata, crosswalks, timelines, and source records.
3. **Evidence & Reasoning** - assemble verified source passages, structured
   records, relationship chains, conflicts, and absence findings.
4. **Accuracy & Verification (hard gates)** - enforce grounding, citation
   verification, currency, completeness, faithfulness, and absence verification
   in code.
5. **Output Control** - require structured, cited, confidence-rated output and
   reject answers that fail the contract.
6. **Platform & Operations** - manage freshness, audit logs, source registries,
   snapshots, reliance policy, and review workflows.

Markdown policies and prompts are soft orchestration. They guide the model.
Hard gates are code and are authoritative.

## Execution Sequence

### Phase 1: Narrative And Architecture Reconciliation

Update project documentation and agent context so every active file describes
Geode as backend-first, state-to-county-to-municipal in scope, and driven by the
orchestration engine.

### Phase 2: Orchestration Policy Completion

Turn placeholder policies into real orchestration contracts:

- grounding policy
- citation policy
- currency policy
- completeness policy
- absence-verification policy
- output-contract policy

Each policy should name which checks are advisory and which checks are enforced
in code.

### Phase 3: Retrieval Planning Contract

Define a machine-readable retrieval plan format. It should record:

- question type
- jurisdiction scope
- required source layers
- files to inspect
- crosswalks to inspect
- freshness requirements
- absence checks required
- expected answer shape

### Phase 4: Evidence Packet Contract

Define the structured evidence packet passed to the LLM. It should include
source IDs, citations, source excerpts, relationship records, freshness state,
missing coverage, and confidence inputs.

### Phase 5: Hard Gate Enforcement

Implement or strengthen code gates for:

- grounding
- citation verification
- currency
- completeness
- faithfulness
- absence verification
- answer contract validation

An answer that fails a gate must halt, request more retrieval, or emit a
structured limitation.

### Phase 6: State Authority Stabilization

Continue improving the current state-level corpus before expanding local
authority:

- CRS
- CCR
- legislation
- rulemaking
- executive orders
- session laws
- supplementary sources

### Phase 7: County And Municipal Expansion

Add county and municipal authority only through the same controls used for
state authority: official source registry, schemas, indexes, freshness rules,
validation, crosswalks, and manifest visibility.

## Preserved Rule-Unit Review Boundary

The prior plan created valid rule-unit review controls that remain relevant as
backend operations:

- `02_Regulations_CCR/_meta/rule_units.jsonl`
- `02_Regulations_CCR/_meta/rule_units_summary.json`
- `02_Regulations_CCR/_meta/rule_units_quality.jsonl`
- `02_Regulations_CCR/_meta/rule_units_review_queue.jsonl`
- `02_Regulations_CCR/_meta/rule_units_review_summary.json`
- `02_Regulations_CCR/_meta/rule_units_review_decisions.jsonl`
- `02_Regulations_CCR/_meta/rule_units_apply_proposal.json`

Review decisions must remain append-only until an explicit guarded apply step.
Canonical changes still require schema validation, snapshot protection, and
atomic writes.

## Safe Work Boundary During Active Downloads

Backend orchestration work should not interfere with active ingestion if it
avoids:

- `_RAW_ARCHIVE/`
- connector modules under `geode/connectors/`
- active pipeline modules under `geode/pipeline/`
- manifest or index rewrites while ingestion is running
- bulk rebuilds over half-written data

Read-only orchestration may inspect completed corpus files. If ingestion is in
progress, derived evidence should be treated as a snapshot of what was complete
at read time.

## Recommended Next Milestone

The next durable milestone is a formal evidence-packet and answer-contract
implementation. That will make the LLM's role explicit: it writes from verified
evidence and cannot bypass hard accuracy gates.
