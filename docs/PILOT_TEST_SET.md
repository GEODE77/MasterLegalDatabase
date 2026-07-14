# PILOT TEST SET — Phase 4A
## 15 CCR Rules Selected for Pilot Ingestion

> **Purpose:** These 15 regulations will be the first documents processed through
> the full 8-layer enhancement pipeline to validate the entire Project Geode system.
>
> **Selection criteria:** Breadth across departments, mix of DOCX and PDF,
> range of sizes, variety of subject matter and structure types.

---

## Summary Table

| # | CCR Number | Title | Department | Format | Size | Key Test |
|---|-----------|-------|-----------|--------|------|----------|
| 1 | 5 CCR 1001-5 | Stationary Source Permitting (Reg 3) | Public Health & Env | DOCX | Large | Air quality, permitting, manufacturing |
| 2 | 5 CCR 1001-9 | Oil & Gas Emissions (Reg 7) | Public Health & Env | DOCX | Large | Energy, oil_gas, complex structure |
| 3 | 6 CCR 1007-2 | Solid Waste Disposal Sites | Public Health & Env | DOCX | Medium | Solid waste, our reference example |
| 4 | 1 CCR 201-2 | Income Tax | Revenue | DOCX | Large | Tax tables, rate schedules, finance |
| 5 | 1 CCR 201-4 | Sales and Use Tax | Revenue | DOCX | Large | Retail, business, high cross-ref count |
| 6 | 7 CCR 1103-1 | Minimum Wage | Labor & Employment | DOCX | Short | Wages, labor, simple baseline |
| 7 | 7 CCR 1103-7 | Overtime & Min Pay (COMPS Order) | Labor & Employment | DOCX | Medium | Workplace standards, heavily referenced |
| 8 | 2 CCR 502-1 | Behavioral Health | Human Services | DOCX | Large | Healthcare, definitions-heavy |
| 9 | 12 CCR 2509-2 | Referral and Assessment (Child Welfare) | Human Services | DOCX | Medium | Human services, different structure |
| 10 | 3 CCR 716-1 | Real Estate Brokers | DORA | DOCX | Medium | Professional licensing, real estate |
| 11 | 4 CCR 801-1 | State Personnel Board Rules | Personnel & Admin | DOCX | Very Large | Government ops, stress test (longest doc) |
| 12 | 2 CCR 404-1 | Oil and Gas Conservation | Natural Resources | DOCX | Large | Oil_gas, mining, complex cross-refs |
| 13 | 8 CCR 1202-10 | Pesticide Applicators Act | Agriculture | DOCX | Short | Agriculture, pesticides, simple |
| 14 | 1 CCR 301-39 | Educator Licensing | Education | DOCX | Medium | Education, teacher licensing |
| 15 | 8 CCR 1507-1 | Peace Officers Standards (POST) | Public Safety | DOCX | Medium | Criminal justice, training |

---

## Rule 1: 5 CCR 1001-5

**Title:** Regulation Number 3 — Stationary Source Permitting and Air Pollutant Emission Notice Requirements
**Department:** Department of Public Health and Environment (Code: 1000)
**Agency:** Air Quality Control Commission (AQCC)
**Format Available:** PDF + DOCX
**Estimated Size:** Large (~200+ pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2337

**Why Selected:**
- Core air quality permitting regulation — directly relevant to manufacturing
- Many CRS citations (25-7-109, 25-7-110, etc.) — tests citation extraction
- Complex multi-part structure (Parts A-F) — tests structure parser
- DOCX available — tests Path 1 conversion
- Used throughout our design conversations as a reference example

---

## Rule 2: 5 CCR 1001-9

**Title:** Regulation Number 7 — Control of Emissions from Oil and Gas Operations
**Department:** Department of Public Health and Environment (Code: 1000)
**Agency:** Air Quality Control Commission (AQCC)
**Format Available:** PDF + DOCX
**Estimated Size:** Large (~150+ pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2341

**Why Selected:**
- Oil and gas industry is a major CO regulatory focus
- Tests energy/oil_gas industry tags
- Multi-part structure (Parts A-C) with technical standards
- Cross-references both state and federal (40 CFR) regulations — tests federal citation extraction

---

## Rule 3: 6 CCR 1007-2

**Title:** Solid Waste Disposal Sites and Facilities
**Department:** Department of Public Health and Environment (Code: 1000)
**Agency:** Hazardous Materials and Waste Management Division (HMWMD)
**Format Available:** PDF + DOCX
**Estimated Size:** Medium (~50-80 pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2367

**Why Selected:**
- Used as our primary example throughout the design phase
- Clean definitions section — tests defined_term regex
- Clear enabling statute (CRS 30-20-102) — tests statute linkage
- Moderate complexity — good middle ground between simple and complex

---

## Rule 4: 1 CCR 201-2

**Title:** Income Tax
**Department:** Department of Revenue (Code: 900)
**Agency:** Taxation Division
**Format Available:** PDF + DOCX
**Estimated Size:** Large (~200+ pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=1936

**Why Selected:**
- Tax regulations contain tables, rate schedules, and formulas — tests table handling
- Heavily cross-references CRS Title 39 (Taxation) — tests high citation volume
- Affects every business in Colorado — high practical relevance
- Very frequently amended (many rulemaking entries visible) — tests versioning

---

## Rule 5: 1 CCR 201-4

**Title:** Sales and Use Tax
**Department:** Department of Revenue (Code: 900)
**Agency:** Taxation Division
**Format Available:** PDF + DOCX
**Estimated Size:** Large (~150+ pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=1938

**Why Selected:**
- Sales tax rules are the most commonly referenced by small businesses
- Extensive exemption lists — tests exception extraction (Principle 3)
- Many cross-references to CRS Title 39 articles
- Tests retail_trade and business_regulation tags

---

## Rule 6: 7 CCR 1103-1

**Title:** Minimum Wage
**Department:** Department of Labor and Employment (Code: 300)
**Agency:** Division of Labor Standards and Statistics
**Format Available:** PDF + DOCX (expected)
**Estimated Size:** Short (~5-15 pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=3154

**Why Selected:**
- Short, simple regulation — tests pipeline on minimal input
- Clear obligations — good baseline for rule unit decomposition
- Tests wages_hours and labor_employment tags
- Verifies pipeline doesn't crash on very short documents

---

## Rule 7: 7 CCR 1103-7

**Title:** Colorado Overtime and Minimum Pay Standards Order (COMPS Order)
**Department:** Department of Labor and Employment (Code: 300)
**Agency:** Division of Labor Standards and Statistics
**Format Available:** PDF + DOCX (expected)
**Estimated Size:** Medium (~30-50 pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=3574

**Why Selected:**
- One of the most referenced employment regulations in Colorado
- Contains exemptions, industry-specific rules, and wage tables
- Tests workplace_safety, wages_hours, and multiple industry tags
- Tests exception preservation across multiple regulated entity types

---

## Rule 8: 2 CCR 502-1

**Title:** Behavioral Health
**Department:** Department of Human Services (Code: 700)
**Agency:** Behavioral Health Administration
**Format Available:** PDF + DOCX
**Estimated Size:** Large (~150+ pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2157

**Why Selected:**
- Definition-heavy regulation — stress tests defined_term extraction
- Healthcare/behavioral health domain — tests those ontology tags
- Complex licensing requirements — tests multiple rule types
- Has had emergency rules — tests status handling

---

## Rule 9: 12 CCR 2509-2

**Title:** Referral and Assessment (Child Welfare)
**Department:** Department of Human Services (Code: 700)
**Agency:** Division of Child Welfare
**Format Available:** PDF + DOCX
**Estimated Size:** Medium (~40-60 pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2821

**Why Selected:**
- Completely different structure from environmental regulations
- Social services domain — new territory for the pipeline
- Tests whether the structure parser handles varied formatting
- Cross-references multiple CRS titles (19, 26) — tests multi-title citations

---

## Rule 10: 3 CCR 716-1

**Title:** Rules Regarding Real Estate Brokers
**Department:** Department of Regulatory Agencies (DORA) (Code: 800)
**Agency:** Real Estate Commission
**Format Available:** PDF + DOCX (expected)
**Estimated Size:** Medium (~40-80 pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=660

**Why Selected:**
- DORA professional licensing — different regulatory style
- Tests professional_licensing and real_estate_licensing tags
- Practice standards + ethics + disclosure requirements
- Tests multiple compliance_keywords: license_required, disclosure, fees

---

## Rule 11: 4 CCR 801-1

**Title:** State Personnel Board Rules and Personnel Director's Administrative Procedures
**Department:** Department of Personnel and Administration (Code: 1400)
**Agency:** State Personnel Board / State Personnel Director
**Format Available:** PDF + DOCX
**Estimated Size:** Very Large (~300+ pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2328

**Why Selected:**
- STRESS TEST — one of the longest regulations in the CCR
- Tests whether the pipeline handles very large documents
- Tests whether chunking and context windows hold up at scale
- Government operations domain — tests state_operations tags
- Complex hierarchical structure with many subsections

---

## Rule 12: 2 CCR 404-1

**Title:** Rules and Regulations for Oil and Gas Conservation
**Department:** Department of Natural Resources (Code: 400)
**Agency:** Colorado Oil and Gas Conservation Commission (COGCC)
**Format Available:** PDF + DOCX (expected)
**Estimated Size:** Large (~200+ pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=178

**Why Selected:**
- Major energy industry regulation — COGCC rules are widely referenced
- Tests oil_gas, mining, energy, pipeline_safety tags
- Complex technical standards with measurement specifications
- Heavy cross-referencing to both state and federal law

---

## Rule 13: 8 CCR 1202-10

**Title:** Colorado Pesticide Applicators Act Rules
**Department:** Department of Agriculture (Code: 100)
**Agency:** Division of Plant Industry
**Format Available:** PDF + DOCX (expected)
**Estimated Size:** Short (~10-20 pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=17

**Why Selected:**
- Agriculture domain — different from all other pilot rules
- Shorter, simpler structure — second baseline test
- Tests agriculture and pesticides tags
- Certification/licensing requirements — tests certification_required keyword

---

## Rule 14: 1 CCR 301-39

**Title:** Rules for the Administration of Educator Licensing Act of 1991
**Department:** Department of Education (Code: 200)
**Agency:** State Board of Education
**Format Available:** PDF + DOCX (expected)
**Estimated Size:** Medium (~50-80 pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=1870

**Why Selected:**
- Education domain — yet another distinct regulatory style
- Tests education and teacher_licensing tags
- Licensing tiers and endorsement types — test complex categorization
- References CRS Title 22 (Education) — tests education statute linking

---

## Rule 15: 8 CCR 1507-1

**Title:** Rules of the Colorado Peace Officers Standards and Training Board (POST)
**Department:** Department of Public Safety (Code: 1500)
**Agency:** Peace Officers Standards and Training Board
**Format Available:** PDF + DOCX (expected)
**Estimated Size:** Medium (~40-60 pages)
**SOS URL:** https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2696

**Why Selected:**
- Criminal justice / public safety domain
- Tests criminal_justice and training_required tags
- Certification standards for law enforcement
- Different regulatory voice and structure from other pilot rules

---

## Distribution Analysis

### Departments Covered (10 of ~20)

| Department | Code | Rules in Pilot |
|-----------|------|---------------|
| Public Health and Environment | 1000 | 3 |
| Revenue | 900 | 2 |
| Labor and Employment | 300 | 2 |
| Human Services | 700 | 2 |
| Regulatory Agencies (DORA) | 800 | 1 |
| Personnel and Administration | 1400 | 1 |
| Natural Resources | 400 | 1 |
| Agriculture | 100 | 1 |
| Education | 200 | 1 |
| Public Safety | 1500 | 1 |

### Format Mix

| Format | Count | % |
|--------|-------|---|
| DOCX confirmed available | 8 | 53% |
| DOCX expected available | 7 | 47% |
| PDF only | 0 | 0% |

*Note: If any 'expected DOCX' rules only have PDF, that tests the Path 2 conversion.*

### Size Mix

| Size | Count | What It Tests |
|------|-------|--------------|
| Short (5-20 pages) | 2 | Pipeline handles minimal input without crashing |
| Medium (30-80 pages) | 6 | Typical regulation size — the bulk of the CCR |
| Large (100-200+ pages) | 6 | Heavy extraction, chunking efficiency, context limits |
| Very Large (300+ pages) | 1 | Stress test — does the pipeline hold up at scale? |

### Ontology Tag Coverage

| Subject Tags Tested | Industry Tags Tested |
|--------------------|--------------------|
| air_quality, emissions, permitting | manufacturing, energy |
| solid_waste, environmental_compliance | waste_management |
| oil_gas, pipeline_safety, mining | oil_gas, mining |
| wages_hours, workplace_safety | small_business |
| behavioral_health, health_facilities | healthcare |
| professional_licensing, real_estate_licensing | real_estate |
| state_operations, government_operations | public_administration |
| agriculture, pesticides | agriculture |
| education, teacher_licensing | education_services |
| criminal_justice, training_required | public_administration |
| consumer_protection, reporting | retail_trade, finance_insurance |

### Pipeline Areas Tested

| Area | Rules That Stress It |
|-----------|---------------------|
| DOCX conversion (Path 1) | All 15 (if DOCX available) |
| PDF conversion (Path 2) | Any where DOCX is unexpectedly absent |
| CRS citation regex | Rules 1-5, 12 (heavy CRS citing) |
| Federal citation regex (CFR/USC) | Rules 2, 12 (federal cross-refs) |
| Defined term extraction | Rules 3, 8, 9 (definition-heavy) |
| Table handling | Rules 4, 5, 7 (rate tables, fee schedules) |
| Long document handling | Rule 11 (300+ pages stress test) |
| Short document handling | Rules 6, 13 (5-20 pages baseline) |
| Exception extraction (P3) | Rules 5, 7 (extensive exemption lists) |
| Multi-part structure | Rules 1, 2, 8 (Parts A-F) |
| Ensemble voting (disagreement) | Unknown — we'll discover where models disagree |
| Constitutional critique | All 15 — evaluated against all 19 dimensions |

---

*Generated: 2026-06-12*
*For use in Phase 4A of the Project Geode build plan.*
