# Geode Backend Current-State Audit

## Scope

This audit records the current backend state before further orchestration work.
It intentionally avoids changing download, connector, raw archive, manifest,
and ingest pipeline files.

## Current Strengths

Geode already has a strong source-data foundation:

- `01_Statutes_CRS` contains CRS data.
- `02_Regulations_CCR` contains CCR data and rule-unit review artifacts.
- `03_Legislation` contains bill data.
- `04_Rulemaking` contains Colorado Register and rulemaking data.
- `_CONTROL_PLANE/MASTER_MANIFEST.json` tracks layer readiness and freshness.
- `_CONTROL_PLANE/MASTER_SCHEMA.json` defines canonical legal record types.
- `_CROSSWALKS/` contains relationship files.
- `geode/schemas/models.py` contains strict Pydantic models.
- `geode/validation/` and `geode/integrity_check.py` support validation.
- `geode/orchestration/` now carries deterministic orchestration config and
  policy files.

## Current Direction

Geode is a backend-first regulatory intelligence database for Colorado
authority across state, county, and municipal levels. The state corpus is the
current foundation. County and municipal coverage must not be implied until
those sources are registered, ingested, validated, and visible in the manifest.

## Orchestration Readiness

The orchestration engine should run in six layers:

1. **Input & Interpretation**
2. **Planning & Retrieval**
3. **Evidence & Reasoning**
4. **Accuracy & Verification (hard gates)**
5. **Output Control**
6. **Platform & Operations**

Current strengths:

- Existing control-plane files support manifest, source, schema, agency, and
  freshness checks.
- Existing indexes and crosswalks support retrieval planning.
- Existing validation and integrity modules support hard-gate implementation.
- Existing rule-unit quality and review artifacts support confidence and
  reliance boundaries.

Current gaps:

- Evidence-packet format needs to be formalized.
- Answer-contract format needs to be formalized.
- Absence verification needs explicit test coverage.
- County and municipal source coverage is not yet represented as validated
  corpus data.

## Risks

1. Letting the LLM choose sources directly would weaken accuracy.
2. Treating prompts as enforcement would blur the soft-vs-hard boundary.
3. Claiming county or municipal coverage before source registration would
   invent coverage.
4. Calling candidate extraction final without review could imply more certainty
   than the corpus supports.

## Execution Decision

Proceed in this order:

1. Keep corpus files authoritative.
2. Complete orchestration policies and contracts.
3. Build retrieval plans and evidence packets from the existing corpus.
4. Enforce hard gates before output.
5. Stabilize state authority coverage.
6. Add county and municipal coverage only through registered, validated sources.
