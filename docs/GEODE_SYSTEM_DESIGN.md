# GEODE_SYSTEM_DESIGN.md — Project Geode Master Reference

> **Single source of truth for the entire Project Geode system architecture.**
> Read by AI agents via `@docs/GEODE_SYSTEM_DESIGN.md`. NOT auto-loaded — that role belongs to `AGENTS.md`.

---

# B1. System Overview & Vision

**Project Geode** is a backend-first regulatory intelligence database for
Colorado legal authority. It serves AI models, agents, APIs, search, retrieval,
ingestion, and legal data analysis.

Geode's jurisdiction model follows the full Colorado authority hierarchy:

1. State
2. County
3. Municipal

The current corpus is state-first. The architecture extends to county and
municipal authority by adding source registries, schemas, indexes, crosswalks,
and freshness rules for those local layers without changing the backend-first
role of the system.

The local pilot adds two explicit layers: county authorities and district
authorities. Local identity records are published before local rules so the
system can distinguish a known authority with incomplete rule collection from
an authority that has not yet been inventoried.

| # | Layer | Content | Source Owner | Est. Records |
|---|-------|---------|-------------|-------------|
| 1 | **CRS** | 44 titles of codified statutory law | Legislative Legal Services | ~10,000+ |
| 2 | **CCR** | Administrative rules from 100+ agencies | Secretary of State | ~4,000+ |
| 3 | **Legislation** | Bills 2010-present, historical to 1861 | General Assembly + LegiScan | ~8,000+ |
| 4 | **Colorado Register** | Rulemaking notices | Secretary of State | ~2,000+ |
| 5 | **Executive Orders** | Governor's orders | Governor's Office | ~200+ |
| 6 | **Supplementary** | AG opinions, COPRRR reviews | AG, DORA | ~700+ |

**Vision:** AI and agent workflows use Geode to check bill duplication,
identify state/county/municipal authority overlap, map compliance obligations,
measure burden, and produce cited research outputs. Downstream tools may be
built on top of Geode, but this repository is the backend knowledge and
orchestration layer.

**Current Direction:** Data collection and structuring remain foundational.
The new centerpiece is the orchestration engine: deterministic Python code that
sits between an LLM and the Geode knowledge layer, decides what to retrieve,
assembles evidence, applies hard accuracy gates, and only then allows the LLM
to write a structured answer.

**Role separation:**

- Geode = knowledge layer.
- Orchestration engine = decision, retrieval, verification, and output control.
- LLM = writer and synthesis layer only.

Markdown policies and prompts are soft orchestration. They guide the model but
do not enforce accuracy. Code gates are hard orchestration and are
authoritative.

---

# B1A. Orchestration Engine

The orchestration engine runs in six ordered layers.

| # | Layer | Responsibility |
|---|-------|----------------|
| 1 | **Input & Interpretation** | Normalize the request; classify question type, legal domain, jurisdiction, entities, time period, and ambiguity. |
| 2 | **Planning & Retrieval** | Decide which control-plane files, indexes, legal texts, metadata sidecars, crosswalks, timelines, and source records must be read. |
| 3 | **Evidence & Reasoning** | Assemble verified passages, structured records, relationship chains, conflicts, and absence findings. |
| 4 | **Accuracy & Verification (hard gates)** | Enforce grounding, citation verification, currency, completeness, faithfulness, and absence verification in code. |
| 5 | **Output Control** | Require structured, cited, confidence-rated output and reject responses that fail the answer contract. |
| 6 | **Platform & Operations** | Manage source freshness, snapshots, audit logs, reliance policy, reviewer workflows, and operational reporting. |

The LLM never decides which law applies, whether evidence is sufficient, or
whether an absence claim is allowed. Those decisions belong to deterministic
code. If evidence is missing, stale, conflicting, or outside Geode's coverage,
the orchestrator must expose that limitation instead of allowing the model to
fill the gap.

---

# B2. Data Source Registry

The sources below are the current state-authority registry. County and
municipal authority sources must be added through the same registry pattern:
official source owner, access method, freshness policy, schema mapping, and
source URL. No county or municipal source may be treated as covered until it is
registered, ingested, validated, and visible in the manifest.

## Source: CRS

| Property | Detail |
|----------|--------|
| **Description** | Complete codified statutory law, 44 titles |
| **Owner** | Office of Legislative Legal Services |
| **Format** | SGML (bulk), HTML (online) |
| **Access** | Free on request. Contact: yelena.love@coleg.gov, 303-866-2295 |
| **URL** | https://leg.colorado.gov/colorado-revised-statutes |
| **Update** | Annually (May-Jul) |
| **Gaps** | No versioned historical snapshots in machine-readable form |
| **Priority** | CRITICAL |

## Source: CCR

| Property | Detail |
|----------|--------|
| **Description** | All administrative rules from 100+ agencies under ~20 departments |
| **Owner** | Secretary of State |
| **Format** | PDF and DOCX (many rules have both) |
| **Access** | No bulk download or API — scrape rule-by-rule |
| **URL** | https://www.sos.state.co.us/CCR/Welcome.do |
| **eDocket** | https://www.sos.state.co.us/CCR/eDocketPublic.do |
| **Update** | Continuous (rulemaking year-round) |
| **Gaps** | No centralized statute-to-regulation crosswalk; must be constructed |
| **Priority** | CRITICAL |

## Source: LegiScan

| Property | Detail |
|----------|--------|
| **Description** | Structured bill data: text, sponsors, votes, status, subjects |
| **Owner** | LegiScan (third-party) |
| **Format** | JSON/CSV, CC BY 4.0 |
| **Access** | Free API (key required) |
| **URL** | https://legiscan.com/CO |
| **Coverage** | 2010-present |
| **Update** | Weekly during session, monthly off |
| **Gaps** | Pre-2010 via CU Law: https://scholar.law.colorado.edu/session-laws-1861-1900/ |
| **Priority** | IMPORTANT |

## Source: Colorado Register

| Property | Detail |
|----------|--------|
| **Description** | Rulemaking notices: proposed, adopted, emergency |
| **Owner** | Secretary of State |
| **Format** | HTML + PDF, twice monthly |
| **URL** | https://www.sos.state.co.us/CCR/RegisterHome.do |
| **Coverage** | Archives back to 2012 |
| **Update** | Twice monthly (~10th and 25th) |
| **Priority** | IMPORTANT |

## Source: Executive Orders

| Property | Detail |
|----------|--------|
| **Description** | Governor's executive orders |
| **Owner** | Governor's Office |
| **Format** | PDF + HTML |
| **URL** | https://www.colorado.gov/governor/executive-orders |
| **Update** | Irregular (~10-30/yr) |
| **Priority** | SUPPLEMENTARY |

## Source: COPRRR

| Property | Detail |
|----------|--------|
| **Description** | Sunrise/sunset reviews of licensing programs |
| **Owner** | DORA |
| **Format** | PDF reports |
| **URL** | https://coprrr.colorado.gov/ |
| **Update** | Quarterly |
| **Priority** | SUPPLEMENTARY |

## Source: AG Opinions

| Property | Detail |
|----------|--------|
| **Description** | Formal AG opinions interpreting state law |
| **Owner** | AG's Office |
| **Format** | PDF |
| **URL** | https://coag.gov/opinions/ |
| **Update** | Irregular |
| **Priority** | SUPPLEMENTARY |

---

# B3. File System Architecture

| Data Type | Organization | Rationale |
|-----------|-------------|-----------|
| Living documents (statutes, regs) | **Structural** by title/dept | Identity is legal citation, not date. Filing by date fragments current law. |
| Event documents (bills, rulemaking) | **Chronological** by year/decade | Discrete events with unambiguous timestamps. |
| Crosswalks/indexes | **Flat** | Relationship tables — must be fully loadable. |

MASTER_TIMELINE_INDEX bridges both with a unified chronological overlay.

*(Full directory tree: see AGENTS.md section A2.)*

---

# B4. Schema Definitions

12 entity types. Full field tables for the 3 most complex; compact examples for the rest.

## `statute_section`

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `entity_type` | const "statute_section" | Y | Type discriminator |
| `id` | string | Y | CRS-{title}-{article}-{section} |
| `title_num` | int | Y | CRS title 1-44 |
| `title_name` | string | Y | Title name |
| `article_num` | int | Y | Article number |
| `article_name` | string | Y | Article name |
| `part_num` | int | N | Part number |
| `part_name` | string | N | Part name |
| `section_num` | string | Y | Full section number |
| `section_heading` | string | Y | Official heading |
| `full_text` | string | Y | Complete text unmodified |
| `effective_date` | ISO date | N | Date this version took effect |
| `last_amended_session` | string | N | Session year |
| `last_amended_by` | array[string] | N | Bill IDs |
| `history_note` | string | N | Legislative history |
| `subject_tags` | array[string] | Y | From ONTOLOGY |
| `industry_tags` | array[string] | Y | From ONTOLOGY |
| `cross_references_outbound` | array[string] | N | CRS IDs referenced |
| `enabling_agencies` | array[string] | N | Agency codes |
| `related_regulations` | array[string] | N | CCR IDs |
| `source_url` | URL | Y | Official source |
| `data_retrieved` | ISO date | Y | Fetch date |
| `data_version` | string | Y | Version ID |
| `confidence` | object | Y | Per-field scores |

```json
{"entity_type":"statute_section","id":"CRS-25-7-109","title_num":25,"title_name":"Public Health and Environment","article_num":7,"article_name":"Air Quality Control","section_num":"25-7-109","section_heading":"Emission control regulations","full_text":"(1) The commission shall promulgate...","effective_date":"2023-07-01","last_amended_by":["SB23-016"],"subject_tags":["air_quality","emissions"],"industry_tags":["manufacturing","energy"],"source_url":"https://leg.colorado.gov/colorado-revised-statutes","data_retrieved":"2026-06-10","data_version":"2025_session_final","confidence":{"overall":0.95}}
```

## `regulation_rule`

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `entity_type` | const "regulation_rule" | Y | Type discriminator |
| `id` | string | Y | {dept}_CCR_{number} |
| `ccr_number` | string | Y | Official CCR number |
| `title` | string | Y | Rule title |
| `department` | string | Y | Department name |
| `department_code` | string | Y | Dept numeric code |
| `agency` | string | Y | Issuing agency |
| `agency_code` | string | Y | From AGENCY_REGISTRY |
| `enabling_statutes` | array[string] | Y | CRS IDs |
| `effective_date` | ISO date | Y | Effective date |
| `status` | enum | Y | active|repealed|superseded|emergency |
| `full_text` | string | Y | Complete text |
| `chunk_level_3_summary` | string | Y | Plain-English summary |
| `subject_tags` | array[string] | Y | From ONTOLOGY |
| `industry_tags` | array[string] | Y | From ONTOLOGY |
| `compliance_keywords` | array[string] | N | From ONTOLOGY |
| `source_url` | URL | Y | Official source |
| `source_format` | enum | Y | pdf|docx |
| `extraction_method` | string | Y | E.g. docx_structural_parse |
| `confidence` | object | Y | Per-field scores |

```json
{"entity_type":"regulation_rule","id":"5_CCR_1001-9","ccr_number":"5 CCR 1001-9","title":"Regulation 3 - Stationary Source Permitting","department":"Public Health and Environment","department_code":"1000","agency":"Air Quality Control Commission","agency_code":"CDPHE_AQCC","enabling_statutes":["CRS-25-7-109","CRS-25-7-110"],"effective_date":"2024-01-15","status":"active","full_text":"PART A...","chunk_level_3_summary":"Establishes permitting for stationary air pollution sources.","subject_tags":["air_quality","permitting"],"industry_tags":["manufacturing","energy"],"source_url":"https://www.sos.state.co.us/CCR/","source_format":"docx","extraction_method":"docx_structural_parse","confidence":{"overall":0.94}}
```

## `bill`

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `entity_type` | const "bill" | Y | Discriminator |
| `id` | string | Y | SB23-016 |
| `session` | string | Y | Year |
| `chamber` | enum | Y | Senate|House |
| `bill_number` | string | Y | Number |
| `title` | string | Y | Short title |
| `sponsors` | array[object] | Y | {name,party,chamber,role} |
| `status` | string | Y | signed|vetoed|in_committee... |
| `status_date` | ISO date | Y | Latest status date |
| `introduced_date` | ISO date | Y | Intro date |
| `statutes_amended` | array[string] | N | CRS IDs amended |
| `statutes_created` | array[string] | N | CRS IDs created |
| `statutes_repealed` | array[string] | N | CRS IDs repealed |
| `subject_tags` | array[string] | Y | From ONTOLOGY |
| `source_url` | URL | Y | LegiScan/leg.colorado.gov |
| `confidence` | object | Y | Scores |

```json
{"entity_type":"bill","id":"SB23-016","session":"2023","chamber":"Senate","bill_number":"016","title":"Air Quality Control Amendments","sponsors":[{"name":"Doe, Jane","party":"D","chamber":"Senate","role":"primary"}],"status":"signed","status_date":"2023-06-02","introduced_date":"2023-01-15","statutes_amended":["CRS-25-7-109"],"subject_tags":["air_quality"],"source_url":"https://legiscan.com/CO/bill/SB23-016/2023","confidence":{"overall":0.98}}
```

## `rulemaking_notice`
A rulemaking notice from the Colorado Register.
```json
{"entity_type":"rulemaking_notice","id":"RM-2023-00847","notice_type":"adopted","ccr_rule_affected":"5_CCR_1001-9","agency_code":"CDPHE_AQCC","summary":"Amendments to Reg 3 updating thresholds.","effective_date":"2024-01-15","publication_date":"2023-12-10","subject_tags":["air_quality"],"source_url":"https://www.sos.state.co.us/CCR/eDocketPublic.do","confidence":{"overall":0.92}}
```

## `executive_order`
A Governor's executive order.
```json
{"entity_type":"executive_order","id":"EO-2025-003","order_number":"D 2025 003","title":"State Agency Use of AI","governor":"Polis, Jared","signed_date":"2025-03-01","status":"active","full_text":"WHEREAS...","summary":"Directs state agencies to develop AI use policies.","statutes_cited":["CRS-24-37.5-101"],"subject_tags":["technology","ai_governance"],"source_url":"https://www.colorado.gov/governor/executive-orders","confidence":{"overall":0.90}}
```

## `session_law`
An enacted law from a legislative session.
```json
{"entity_type":"session_law","id":"SL-2023-142","session_year":"2023","chapter":"142","bill_id":"SB23-016","title":"Air Quality Amendments","effective_date":"2023-07-01","statutes_affected":["CRS-25-7-109"],"summary":"Amends CRS 25-7-109.","subject_tags":["air_quality"],"source_url":"https://leg.colorado.gov/session-laws","confidence":{"overall":0.85}}
```

## `ag_opinion`
A formal AG opinion.
```json
{"entity_type":"ag_opinion","id":"AGO-2024-001","opinion_number":"24-01","title":"Municipal Authority over Short-Term Rentals","attorney_general":"Weiser, Phil","issued_date":"2024-03-15","statutes_interpreted":["CRS-29-20-104"],"summary":"Municipalities have broad authority to regulate STRs.","subject_tags":["housing","municipal_authority"],"source_url":"https://coag.gov/opinions/","confidence":{"overall":0.88}}
```

## `coprrr_review`
A COPRRR sunrise/sunset review.
```json
{"entity_type":"coprrr_review","id":"COPRRR-2023-AUD","review_type":"sunset","program_reviewed":"State Board of Accountancy","agency_code":"DORA_DPO","publication_date":"2023-10-15","recommendation":"continue with modifications","summary":"Continue accountancy licensing with modifications.","subject_tags":["professional_licensing"],"source_url":"https://coprrr.colorado.gov/","confidence":{"overall":0.85}}
```

## `rule_unit`
An atomic obligation extracted from a regulation.
```json
{"entity_type":"rule_unit","id":"6_CCR_1007-2_2.2_1","parent_regulation_id":"6_CCR_1007-2","source_section":"Part 2, Section 2.2(1)","rule_type":"prohibition","regulated_entity":"Any person seeking to operate a solid waste facility","action_required":"Must obtain certificate of designation before operating","enabling_statute":["CRS-30-20-102"],"plain_english_summary":"Cannot operate a solid waste facility without a certificate from local government.","subject_tags":["solid_waste","permitting"],"confidence":{"overall":0.91}}
```

## `crosswalk_entry`
A relationship record linking two entities.
```json
{"source_id":"5_CCR_1001-9","source_type":"regulation_rule","target_id":"CRS-25-7-109","target_type":"statute_section","relationship":"authorized_by","confidence":0.95,"source_evidence":"Promulgated pursuant to section 25-7-109, C.R.S.","data_retrieved":"2026-06-12"}
```

## `timeline_event`
An event in the unified chronological spine.
```json
{"id":"TE-2023-07-01-001","date":"2023-07-01","event_type":"bill_signed","entity_id":"SB23-016","entity_type":"bill","description":"SB23-016 signed - amends CRS 25-7-109","affects":["CRS-25-7-109"],"layer":"03_Legislation","file_path":"03_Legislation/2023/bills_2023.jsonl"}
```

## `agency`
A Colorado state agency.
```json
{"entity_type":"agency","id":"CDPHE_AQCC","agency_name":"Air Quality Control Commission","agency_abbreviation":"AQCC","department":"Public Health and Environment","department_code":"1000","enabling_statutes":["CRS-25-7-104","CRS-25-7-105"],"ccr_prefix":"5 CCR 1001-","regulation_count":14,"website_url":"https://cdphe.colorado.gov/aqcc"}
```

---

# B5. Ontology & Controlled Vocabulary

AI extractors MUST only use tags from this vocabulary.

## Subject Tags (Hierarchical)

**environment** (10): `air_quality`, `water_quality`, `solid_waste`, `hazardous_waste`, `land_use`, `environmental_cleanup`, `climate_change`, `natural_resources`, `wildlife`, `water_rights`
**public_health** (9): `communicable_disease`, `food_safety`, `drinking_water`, `radiation_control`, `health_facilities`, `emergency_medical`, `behavioral_health`, `substance_abuse`, `vital_records`
**labor_employment** (7): `wages_hours`, `workplace_safety`, `workers_compensation`, `unemployment_insurance`, `employment_discrimination`, `child_labor`, `paid_leave`
**professional_licensing** (8): `medical_licensing`, `legal_licensing`, `engineering_licensing`, `contractor_licensing`, `real_estate_licensing`, `financial_licensing`, `cosmetology`, `accountancy`
**business_regulation** (9): `corporate_registration`, `securities`, `insurance`, `banking`, `consumer_protection`, `trade_practices`, `cannabis_regulation`, `alcohol_regulation`, `gaming`
**energy** (6): `oil_gas`, `renewable_energy`, `utility_regulation`, `pipeline_safety`, `mining`, `electric_vehicles`
**transportation** (5): `motor_vehicles`, `highways`, `public_transit`, `vehicle_emissions`, `commercial_vehicles`
**education** (5): `k12_education`, `higher_education`, `charter_schools`, `school_safety`, `teacher_licensing`
**housing** (7): `building_codes`, `affordable_housing`, `landlord_tenant`, `short_term_rentals`, `construction_standards`, `mobile_homes`, `homeowner_associations`
**compliance** (7): `permitting`, `reporting`, `inspection`, `enforcement`, `penalties`, `disclosure`, `recordkeeping`
**government_operations** (7): `state_operations`, `procurement`, `elections`, `open_records`, `administrative_procedure`, `rulemaking`, `sunset_review`
**technology** (5): `data_privacy`, `cybersecurity`, `ai_governance`, `broadband`, `telecommunications`
**agriculture** (5): `crop_regulation`, `livestock`, `pesticides`, `organic_certification`, `water_irrigation`
**criminal_justice** (5): `sentencing`, `corrections`, `probation`, `victims_rights`, `juvenile_justice`

**Total: 14 parents + 95 children = 109 tags**

## Industry Tags (NAICS)

| Tag | NAICS | Description |
|-----|-------|-------------|
| `agriculture` | 11 | Agriculture/forestry/fishing |
| `mining` | 21 | Mining/quarrying/oil-gas |
| `utilities` | 22 | Electric/gas/water |
| `construction` | 23 | Building/specialty |
| `manufacturing` | 31-33 | All manufacturing |
| `wholesale_trade` | 42 | Wholesalers |
| `retail_trade` | 44-45 | Retail |
| `transportation_warehousing` | 48-49 | Transport/warehousing |
| `information` | 51 | Publishing/telecom |
| `finance_insurance` | 52 | Banking/insurance |
| `real_estate` | 53 | Real estate/leasing |
| `professional_services` | 54 | Legal/accounting/engineering |
| `management_companies` | 55 | Holding companies |
| `administrative_support` | 56 | Employment svcs/security |
| `education_services` | 61 | Schools/colleges |
| `healthcare` | 62 | Hospitals/physicians |
| `arts_entertainment` | 71 | Arts/recreation |
| `accommodation_food` | 72 | Hotels/restaurants |
| `other_services` | 81 | Repair/personal care |
| `public_administration` | 92 | Government programs |
| `cannabis` | N/A | CO-specific marijuana |
| `oil_gas` | 211-213 | Extraction+support |
| `small_business` | N/A | Cross-cutting |

**Total: 23 industry tags**

## Compliance Keywords (20)

`permit_required`, `license_required`, `registration_required`, `reporting`, `disclosure`, `recordkeeping`, `inspection`, `monitoring`, `fees`, `penalty`, `fine`, `enforcement_action`, `hearing_required`, `public_notice`, `annual_filing`, `bonding_required`, `insurance_required`, `training_required`, `certification_required`, `background_check`

## Enumerations

**rule_type:** obligation, prohibition, permission, definition, condition, exception, penalty, reporting, standard, procedure
**relationship_type:** authorized_by, implements, amends, creates, repeals, cites, supersedes, modified_by, interprets, reviews
**event_type:** bill_signed, bill_introduced, rule_effective, rule_proposed, executive_order, session_law, constitution_amendment
**status:** active, repealed, superseded, emergency, expired, rescinded, in_committee, signed, vetoed

---

# B6. Two-Tier Storage Model

**Tier 1: Index** (`_index.jsonl`) — metadata only, ~200-500 bytes/record, AI loads FIRST
**Tier 2: Content** (`.md` + `_meta/*.jsonl`) — full text + metadata, ~2-20 KB/record

| File Type | Max Size | Rationale |
|-----------|---------|-----------|
| Index files | 5 MB | Must fit in context window |
| Content .md | 15 MB | Fast load times |
| Metadata sidecars | 10 MB | Streamable |
| Crosswalk files | 3 MB | Fully loadable for traversal |
| Control plane | 500 KB ea | Instant on every session |

**Splitting:** CRS by article groups, CCR by agency, crosswalks by department.

**AI Retrieval:** Manifest(2KB) -> Index(2-5MB) -> Content(1-15MB) -> Meta(1-10MB) -> Crosswalks(500KB) -> Timeline(1MB). **Max ~15-20MB per query from ~500MB corpus.**

---

# B7. Chunking Strategy

## Level 1: Section Chunk (500-5000 tokens)
One complete section. ATOMIC — never split. Markdown `####` boundary. For precise legal questions.

## Level 2: Subsection Chunk (100-1000 tokens)
Individual subsection with **parent_context** field:
```json
{"subsection_id":"CRS-25-7-109-1-a","label":"(1)(a)","parent_context":"Subsection (1)(a) of CRS 25-7-109 Emission control regulations, Title 25 Article 7","text":"The technical feasibility and economic reasonableness..."}
```

## Level 3: Summary Chunk (50-200 tokens)
AI-generated plain-English summary. For discovery and broad questions.

## Heading-to-Chunk Mapping
```
# Title        -> file boundary
## Article     -> article boundary
### Part       -> part boundary
#### Section   -> LEVEL 1 CHUNK BOUNDARY
  (1)          -> Level 2
    (a)        -> Level 2
```

**Flow:** Broad -> search Level 3 -> identify sections -> search Level 2 -> retrieve Level 1 for citation.

---

# B8. Crosswalk & Relationship Engine

## Relationship Graph

```
  REGULATIONS ---authorized_by---> STATUTES
    (CCR)    <--implements-------- (CRS)
      |                               |
      | modified_by                   | amended_by
      v                               v
  RULEMAKING                      BILLS / SESSION LAWS
      |                               |
      +-----------+-------------------+
                  v
              AGENCIES
```

### `regulation_to_statute.jsonl`
CCR rule -> enabling CRS section(s)
```json
{"source_id":"5_CCR_1001-9","source_type":"regulation_rule","target_id":"CRS-25-7-109","target_type":"statute_section","relationship":"authorized_by","confidence":0.95,"source_evidence":"Promulgated pursuant to section 25-7-109, C.R.S.","data_retrieved":"2026-06-12"}
```

### `statute_to_regulation.jsonl`
CRS section -> all regs underneath (derived/reverse)
```json
{"source_id":"CRS-25-7-109","source_type":"statute_section","target_ids":["5_CCR_1001-9","5_CCR_1001-5"],"target_type":"regulation_rule","relationship":"implements","total_regs":2,"agencies":["CDPHE_AQCC"],"data_retrieved":"2026-06-12"}
```

### `bill_to_statute.jsonl`
Bill -> CRS sections amended/created/repealed
```json
{"source_id":"SB23-016","source_type":"bill","session":"2023","statutes_amended":["CRS-25-7-109"],"statutes_created":[],"statutes_repealed":[],"status":"signed","effective_date":"2023-07-01","data_retrieved":"2026-06-12"}
```

### `rulemaking_to_regulation.jsonl`
Register notice -> CCR rule modified
```json
{"source_id":"RM-2023-00847","source_type":"rulemaking_notice","target_id":"5_CCR_1001-9","target_type":"regulation_rule","relationship":"modified_by","notice_type":"adopted","effective_date":"2024-01-15","data_retrieved":"2026-06-12"}
```

### `agency_to_statute.jsonl`
Agency -> enabling statutes + regulations issued
```json
{"source_id":"CDPHE_AQCC","source_type":"agency","enabling_statutes":["CRS-25-7-104","CRS-25-7-105"],"regulations_issued":["5_CCR_1001-3","5_CCR_1001-5","5_CCR_1001-9"],"reg_count":14,"data_retrieved":"2026-06-12"}
```

### `amendment_history.jsonl`
Chronological change chain per entity
```json
{"entity_id":"CRS-25-7-109","entity_type":"statute_section","history":[{"date":"1992-07-01","action":"enacted","bill":null},{"date":"2007-05-01","action":"amended","bill":"HB07-1341"},{"date":"2023-07-01","action":"amended","bill":"SB23-016"}]}
```

### MASTER_TIMELINE_INDEX.jsonl
Unified chronological spine:
```json
{"id":"TE-1861-09-09-001","date":"1861-09-09","event_type":"session_law","entity_id":"SL-1861-001","description":"First Territorial Legislative Assembly convenes","layer":"06_Session_Laws","file_path":"06_Session_Laws/1861/session_laws_1861.jsonl"}
{"id":"TE-2023-07-01-001","date":"2023-07-01","event_type":"bill_signed","entity_id":"SB23-016","description":"SB23-016 signed - amends CRS 25-7-109","affects":["CRS-25-7-109"],"layer":"03_Legislation","file_path":"03_Legislation/2023/bills_2023.jsonl"}
```

---

# B9. The 8-Layer Ingestion Enhancement Pipeline

This pipeline improves extraction and data quality during ingestion. It is not
the same thing as the orchestration engine. The ingestion pipeline creates and
validates knowledge-layer records. The orchestration engine later decides what
records to retrieve and whether an answer may be emitted.

## End-to-End Flow

```
RAW SOURCE (PDF/DOCX)
    |
    v
L1: DETERMINISTIC EXTRACTION (regex + structure)
    |
    v
L2: SOURCE FINGERPRINTING (SHA-256 + preservation score)
    |
    +------------------+
    v                  v
  Model A (GPT-4o)  Model B (Claude)    <-- L3: LLM EXTRACTION
    |                  |
    +--------+---------+
             v
L4: ENSEMBLE VOTING (field-by-field agreement)
    |
    v
L5: CONSTITUTIONAL CRITIQUE (8 principles, 19 dims, 3 cycles)
    |
    v
L6: DETERMINISTIC VALIDATION (schema, IDs, dates, hallucination canary)
    |
    v
L7: CONFIDENCE SCORING + ROUTING
    |
    +------+--------+--------+
    v      v        v        v
  AUTO   FLAG    QUARANTINE  REJECT
 ACCEPT ACCEPT   (~10%)   (hallucination)
 (~70%) (~20%)
    |      |        |
    v      v        v
 PROJECT PROJECT   HUMAN REVIEW
  GEODE   GEODE

(After bulk ingestion)
    v
L8: ADVERSARIAL SPOT-CHECK (5 test suites)
```

## Layer 1: Deterministic Extraction
**Defends against:** Text corruption, structure misidentification

### Regex Patterns
```python
PATTERNS = {
    "ccr_number": r"(\d{1,2}\s+CCR\s+[\d]+-[\d]+(?:-[\d]+)?)",
    "crs_citation": r"(?:section|\u00a7|sec\.)\s*([\d]+-[\d]+-[\d]+(?:\.\d+)?(?:\s*\([^)]+\))*),?\s*C\.R\.S\.",
    "crs_citation_alt": r"C\.R\.S\.\s*\u00a7?\s*([\d]+-[\d]+-[\d]+(?:\.\d+)?)",
    "part_boundary": r"^(?:PART|Part)\s+(\d+|[A-Z]|[IVX]+)[.\s]",
    "section_number": r"^(\d+\.\d+(?:\.\d+)?)\s",
    "subsection_number": r"^\((\d{1,3})\)",
    "subsection_letter": r"^\(([a-z]{1,2})\)",
    "subsection_roman": r"^\(([IVXivx]+)\)",
    "defined_term": r'["\u201c]([^"\u201d]+)["\u201d]\s+means\b',
    "effective_date": r"[Ee]ffective\s+(\w+\s+\d{1,2},?\s+\d{4})",
    "adopted_date": r"[Aa]dopted\s+(\w+\s+\d{1,2},?\s+\d{4})",
    "cfr_citation": r"(\d+\s+C\.?F\.?R\.?\s+[\d.]+(?:\([^)]+\))?)",
    "usc_citation": r"(\d+\s+U\.?S\.?C\.?\s+(?:\u00a7\s*)?[\d]+[a-z]?)",
}
```

**Algorithm:** Convert to MD -> split lines -> test each against patterns (part > section > subsection) -> build tree -> run metadata patterns -> flag `needs_llm` for anything regex missed.

## Layer 2: Source Fingerprinting
**Defends against:** Corruption, staleness

- At download: SHA-256 hash + URL + timestamp + size
- After conversion: preservation_score = shared_tokens / source_tokens
- Threshold: < 0.95 -> FLAG for review
- On updates: re-download, compare hash. Different -> re-ingest. Same -> skip.

## Layer 3: LLM Semantic Extraction
**Defends against:** Structure errors, citation misses

LLM receives BOTH source MD AND regex results. Five tasks:

**Task A — Structure Verification:** Verify part/section/subsection hierarchy from regex parse. Return corrected structure JSON with correction notes.

**Task B — Deep Citation Extraction:** Find all citations regex missed: implicit refs, shorthand, federal refs. Return canonical_form, as_written, location, found_by.

**Task C — Rule Unit Decomposition:** Decompose into atomic rule units. Each = ONE obligation/prohibition/etc. Return rule_id, rule_type, regulated_entity, action_required, conditions, exceptions, enabling_statute, temporal, penalties, plain_english_summary. Follow Geode Constitution P1-P8.

**Task D — Ontology Tagging:** Assign 2-5 subject_tags, 1-3 industry_tags, 0-5 compliance_keywords from ONTOLOGY.json ONLY. No invented tags.

**Task E — Summary Generation:** 2-3 sentences: what it requires, who it applies to, key obligations. Business owner must understand. 50-200 tokens. No info beyond source.


## Layer 4: Cross-Model Ensemble Voting
**Defends against:** Hallucination, misclassification

Run L3 with TWO models (GPT-4o + Claude), identical inputs.

**Exact match** (dates, CCR numbers, citations): Both agree -> ACCEPT (0.99). One matches regex -> ACCEPT that (0.90). All differ -> QUARANTINE.
**Semantic match** (rule_type, entity, tags): >0.90 similarity -> ACCEPT. 0.70-0.90 -> FLAG. <0.70 -> QUARANTINE.
**List fields** (exceptions, cross-refs): Intersection -> ACCEPT. Symmetric diff -> VERIFY. Union of verified.
**Text fields** (summaries): Check for ungrounded claims. Both grounded -> select better. One ungrounded -> use the other.

## Layer 5: Constitutional Self-Critique
**Defends against:** Hallucination, omission

**Constitution:** P1 Source Fidelity | P2 Completeness | P3 Exception Preservation | P4 Citation Completeness | P5 No Interpretation | P6 Atomicity | P7 Temporal Precision | P8 Entity Clarity *(full text: AGENTS.md A5)*

**19 Judge Dimensions:**
M1-M5 (Metadata): Source fidelity, Citation accuracy, Agency attribution, Temporal accuracy, Cross-ref completeness
D1-D5 (Definitions): Term completeness, Definition accuracy, Scope correctness, Exception coverage, Dependency tracking
R1-R9 (Rule Semantics): Type classification, Entity ID, Action completeness, Condition fidelity, Logical structure, Granularity, Penalty linkage, Summary accuracy, No hallucination

Each scored 1-5. >=4 passes. 3 needs repair. <=2 critical.

**Repair:** Max 3 iterations, upstream-first: Cycle 1 (M1,M2,M4,M5), Cycle 2 (D1-D5,R6), Cycle 3 (R1-R5,R7-R9). R9<5 after 3 cycles -> REJECT. Still failing -> QUARANTINE.

## Layer 6: Deterministic Validation
**Defends against:** Metadata/format/logic errors

| # | Check | Fail Action |
|---|-------|-------------|
| 1 | Schema compliance (fields, types, dates) | REJECT |
| 2 | ID uniqueness across system | REJECT |
| 3 | Referential integrity (cited IDs exist) | FLAG |
| 4 | Date logic (effective>=adopted, not future, not pre-1876) | QUARANTINE |
| 5 | Text integrity + hallucination canary (summary cites no statutes absent from source) | REJECT on canary |
| 6 | Cross-record consistency (agency in registry, under claimed dept) | FLAG |

## Layer 7: Confidence Scoring & Routing

```
field_confidence = 0.30*source + 0.25*critique + 0.25*validation + 0.20*token_prob

source_score: 1.0=regex, 0.9=ensemble_agreed, 0.7=one_LLM+regex, 0.4=repaired, 0.1=uncertain
critique_score: dimension_score / 5.0
validation_score: 1.0=all_passed, 0.5=flagged, 0.0=failed
token_prob: geometric_mean_logprobs (0.5 if unavailable)

Record composite: weighted mean, 2x weight on ccr_number, enabling_statutes, effective_date, rule_type
```

| Confidence | Route | Expected % |
|-----------|-------|-----------|
| >= 0.85 | AUTO-ACCEPT | ~70% |
| 0.60-0.84 | FLAG-ACCEPT (mark low fields) | ~20% |
| < 0.60 | QUARANTINE | ~10% |
| Any R9 < 5 | REJECT (re-extract) | ~2% |

## Layer 8: Adversarial Spot-Check
**Run after bulk ingestion.**

| # | Suite | Description |
|---|-------|-------------|
| 1 | Ground truth | Compare to 10-15 human extractions. P/R/F1 per field. |
| 2 | Edge cases | Repealed rules, 50+ cross-refs, complex tables, tracked changes, 200+ pages, 1-paragraph rules |
| 3 | Consistency | Same doc 3x. Metadata identical, summaries may vary. |
| 4 | Cross-layer coherence | 50 random regs: crosswalks match metadata, statutes exist, agencies linked |
| 5 | Q&A validation | 20 real questions answered from DB, human verifies |

---

# B10. Ingestion Pipeline Architecture

| Connector | Source | Method | Frequency | Complexity |
|-----------|--------|--------|-----------|------------|
| CRS Parser | SGML bulk | Parse XML/SGML | Annually | Medium |
| CCR Scraper | SOS website | Download DOCX/PDF | Quarterly | **High** |
| LegiScan Client | LegiScan API | JSON pull | Weekly/Monthly | Low |
| Register Scraper | SOS Register | HTML scrape | Twice monthly | Medium |
| Exec Orders | Governor site | HTML+PDF | Monthly | Low |
| COPRRR | DORA site | PDF download | Quarterly | Medium |

```
Connectors -> Normalization (schema, IDs, tags, cross-refs)
    -> Validation Gate (schema, uniqueness, integrity, freshness)
    -> Storage Writer (atomic 7 steps: archive, write .md+meta, update index, crosswalks, timeline, log, manifest)
```

---

# B11. Freshness & Update System

| Layer | Cadence | Staleness Policy |
|-------|---------|-----------------|
| Statutes | Annually | max 365d, alert 330d |
| Regulations | Monthly | max 45d, alert 30d |
| Bills | Weekly (session) / Monthly | max 14d, alert 10d |
| Rulemaking | Twice monthly | max 20d, alert 15d |
| Exec Orders | Monthly | max 60d, alert 45d |
| Supplementary | Quarterly | max 120d, alert 90d |

**Workflow:** Trigger -> source check -> delta extraction -> full 8-layer pipeline -> atomic write -> freshness certificate.

**UPDATE_LOG.jsonl:**
```json
{"timestamp":"2026-07-15T10:00:00Z","layer":"02_regulations","action":"refresh","records_added":12,"records_modified":34,"records_removed":2,"pipeline_version":"1.2.0","duration_seconds":847}
```

---

# B12. Quality Assurance

## Ingestion Checks (Layer 6)

| # | Check | Fail Action |
|---|-------|-------------|
| 1 | Schema compliance | REJECT |
| 2 | ID uniqueness | REJECT |
| 3 | Referential integrity | FLAG |
| 4 | Date logic | QUARANTINE |
| 5 | Text integrity + hallucination canary | REJECT/FLAG |
| 6 | Cross-record consistency | FLAG |

## Monthly Integrity Checks

| # | Check | Action |
|---|-------|--------|
| 1 | Orphan regulations | Report |
| 2 | Dead crosswalks | Archive+flag |
| 3 | Tag coverage gaps | Queue for AI tagging |
| 4 | Missing summaries | Queue for AI summary |
| 5 | Crosswalk completeness | Extract+add |

## Adversarial Suites

| # | Suite | Method |
|---|-------|--------|
| 1 | Ground truth | P/R/F1 vs human extraction |
| 2 | Edge cases | Tricky docs stress test |
| 3 | Consistency | Same doc 3x |
| 4 | Cross-layer coherence | 50 random regs |
| 5 | Q&A validation | 20 questions, human verified |

---

# B13. Markdown + JSON Hybrid Architecture

> **Markdown carries the law. JSON carries the data about the law.**

**Why Markdown:** ~2x token savings vs JSON, better embeddings (LLMs trained on MD), natural chunking on headings, human-debuggable.

**Why JSON for metadata:** Schema validation (Pydantic), machine parsing (json.loads), crosswalk traversal (ID-to-ID), controlled vocabulary enforcement.

**In practice:** Every regulation has TWO files: `.md` (legal text + YAML frontmatter) and `_meta/*.jsonl` (structured metadata). AI reads JSONL for filtering, MD for legal text.

---

# B14. PDF/DOCX Conversion Paths

**Key finding:** Many CCR rules have DOCX alongside PDF. Always prefer DOCX. CCR PDFs are text-based (no OCR needed for most).

| Path | Source | Accuracy | Speed | Tools |
|------|--------|----------|-------|-------|
| 1 (DOCX) | Word docs | ~98%+ | Seconds | python-docx + markitdown |
| 2 (Text PDF) | Digital PDFs | ~90-95% | 25 pg/sec | marker or markitdown |
| 3 (Scanned) | Image PDFs | ~80-90% | Minutes | Tesseract / Azure AI |

| Tool | Accuracy | Speed | GPU | DOCX | Tables | Best For |
|------|----------|-------|-----|------|--------|---------|
| MarkItDown | 4/5 | 5/5 | No | Yes | 3/5 | Clean digital, speed |
| Marker | 5/5 | 4/5 | Optional | No | 4/5 | Complex layouts, max accuracy |
| Docling | 5/5 | 3/5 | Optional | Yes | 5/5 | Enterprise, tables |

**Routing:** DOCX available? -> Path 1. Text extractable? -> Path 2 (simple: MarkItDown; complex: Marker+LLM). Otherwise -> Path 3 (OCR).

**Expected:** ~40-50% Path 1, ~45-55% Path 2, ~0-5% Path 3.

---

# B15. AI Consumption Contract

Geode is designed to be read by an AI through a controlled sequence, not as a
human document library. The existing orchestration stages remain authoritative:
interpret the question, resolve jurisdiction and time, build a coverage plan,
retrieve evidence, assemble exact passages, verify the answer, and disclose
limits. The control plane now makes that sequence explicit in:

- `_CONTROL_PLANE/AI_READ_ORDER.json`
- `_CONTROL_PLANE/AI_QUERY_CONTRACT.json`
- `_CONTROL_PLANE/AI_RETRIEVAL_CONTRACT.json`
- `_CONTROL_PLANE/AI_ANSWER_CONTRACT.json`
- `_CONTROL_PLANE/AI_READINESS_REPORT.json`

The AI must use source-backed passages, not catalog summaries. Each passage
must carry its source path, source hash, location, and exact passage hash.
Local material marked `source_preservation_only` remains available for audit
and future review but cannot support an answer. Unknown currency, unresolved
geography, missing coverage, and conflicts are surfaced as limitations and
lower confidence rather than being silently resolved.

---

# B16. Local Evidence Promotion

Preserved local sources move into AI-answer use only through
`geode.pipeline.local_promotion`. The pipeline creates reviewer packets,
requires a reviewer decision tied to the preserved source hash, checks exact
section and page or line provenance, validates the structured rule unit, and
creates a snapshot before any active metadata is changed. A successful
promotion changes `semantic_status` to `semantic_ready`; rejected or incomplete
decisions remain unavailable to answer retrieval. The promotion report and
local golden evaluation are part of the control plane and validation gates.

---

*End of GEODE_SYSTEM_DESIGN.md | v1.3 | 2026-07-15 | Sections B1-B16*
