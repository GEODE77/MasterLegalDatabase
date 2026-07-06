# Geode Product Current-State Audit

## Scope

This audit records the current state before product execution. It intentionally avoids changing
download, connector, raw archive, manifest, and ingest pipeline files.

## Current Strengths

Geode already has a strong source-data foundation:

- `02_Regulations_CCR` contains real CCR data.
- `03_Legislation` contains real bill data.
- `04_Rulemaking` contains real Colorado Register data.
- `_CONTROL_PLANE/MASTER_MANIFEST.json` tracks layer readiness and freshness.
- `_CONTROL_PLANE/MASTER_SCHEMA.json` defines canonical legal record types.
- `_CROSSWALKS/` contains relationship files.
- `geode/schemas/models.py` contains strict Pydantic models.
- `geode/validation/` and `geode/integrity_check.py` support validation.
- The web app already has a regulation search and regulation detail reader.

## Current Data Readiness

Based on the manifest:

| Layer | Current status | Product implication |
| --- | --- | --- |
| CRS statutes | empty | Explore can start with CCR, but statute text is not ready. |
| CCR regulations | ready | Best first product source. |
| Legislation | ready | Useful for Updates and future legislative history. |
| Rulemaking | ready | Useful for Updates and regulation relationships. |
| Executive orders | empty | Defer product support. |
| Session laws | empty | Defer full legal history. |
| Supplementary | empty | Defer AG/COPRRR features. |

## Current Web App Shape

Existing public or product routes include:

- `/`
- `/about`
- `/pricing`
- `/trust`
- `/sign-in`
- `/onboarding`
- `/dashboard`
- `/query`
- `/regulations`
- `/regulations/[id]`
- `/forum`
- `/settings`
- `/internal/heuristics`

The current product shell points users to Forum, Query, Regulations, Activity, and Settings. The
master plan's product navigation does not yet exist as first-class routes:

- Explore
- Impact Lens
- Compliance Paths
- Updates

## Current Product Gap

The current experience is closer to:

> search and read regulations

The master plan calls for:

> source-backed regulatory intelligence by relationship, profile impact, and review path

The gap is product organization and derived intelligence, not the absence of all data.

## Risks

1. Building Impact Lens before requirements and relationships are explainable could create results
   that look more certain than the corpus supports.
2. Rewriting route structure without compatibility paths could disrupt existing pages.
3. Editing control-plane or connector files during active downloads could collide with ingestion.
4. Calling candidate extraction "requirements" too early could imply more certainty than exists.

## Execution Decision

Proceed in this order:

1. Keep corpus files authoritative.
2. Add read-only product index helpers.
3. Add `/app/...` internal product routes while preserving legacy routes.
4. Build Explore first.
5. Add Impact Lens and Compliance Paths as evidence-backed MVP surfaces.
6. Defer full graph and full diff until relationships and versioning are stronger.
