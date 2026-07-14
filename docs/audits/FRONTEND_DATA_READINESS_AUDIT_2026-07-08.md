# Frontend Data Readiness Audit

Historical note: this audit describes a former frontend direction. Geode is now
backend-only; these findings are retained as dated evidence and are not current
architecture.

Generated: 2026-07-08

## Purpose

This audit answers two questions.

1. Can the frontend use the recent recovered downloads, especially EO-2019-007?
2. What should the frontend build, layer by layer, so users can understand what the processed legal data actually says?

This is a product-readiness audit. It does not certify legal correctness, and it does not authorize public reliance without the existing freshness, reviewer, and publication gates.

## Executive Finding

The recovered executive-order download is now frontend-usable.

EO-2019-007 is present in the executive-order records, present in the layer index, present in the refreshed retrieval catalog, and present in the rebuilt frontend SQLite read index. Search and detail lookup both return the order. The old issue where the recovered order was source-backed but not discoverable has been fixed.

The broader processed corpus is usable for frontend discovery and basic source-backed browsing. The current corpus has 57,155 records, zero corpus-usability issues, and complete retrieval catalog coverage. The main frontend opportunity is no longer basic readability. The opportunity is better interpretation of the structure already present: source trust, timelines, relationships, authority pages, rulemaking lifecycle, agency power, and compliance paths.

## Recent Download Audit

### EO-2019-007 Recovery

Frontend readiness status: pass.

Evidence found:

- Structured record exists: `EO-2019-007`.
- Governor field is filled: `Jared Polis`.
- Signed date is filled: `2019-05-31`.
- Official source URL points to the Colorado State Publications Library PDF.
- Raw source path points to the manual intake archive.
- Executive-order layer count is now 535.
- Retrieval catalog now contains 57,155 records and includes EO-2019-007.
- Frontend read index now contains 57,155 entities and returns EO-2019-007 through search and detail lookup.
- Next-download dashboard no longer sends agents back to the recovered executive-order PDF.

Remaining frontend caution:

- The PDF text extraction contains OCR errors in the full text. The frontend should display this kind of order with a visible "source text extracted from PDF" note and a direct official-source link. The structured fields are usable, but the full-text reader should not pretend OCR is pristine.

### Recent Download Dashboard State

Current status:

- All seven layers pass readability checks.
- Blocked download queue is clear for EO-2019-007.
- Recent-download audit remains `warn` only because of known LegiScan document-coverage gaps and one future freshness item.
- That warning is not about the recovered executive order.

### Process Issue Found And Fixed

Problem found:

- A frontend build command stalled because an interrupted Next.js build process continued running in the background.
- A prior `pnpm` path also failed against a zero-byte temporary file in the OneDrive-backed project folder.
- The sandbox blocked Next worker creation with `spawn EPERM`.

Fix applied:

- Stopped the runaway Node build process.
- Marked forum/profile pages as dynamic so build-time static generation does not try to resolve live local app data.
- Hardened the personalization API so empty/invalid tracking requests return a clean 400 response instead of noisy server errors.
- Reran the build outside the sandbox with an isolated output folder.

Verification:

- Next production build completed successfully.
- Build compiled in 35.7 seconds and completed in about 84 seconds.
- The temporary audit build output was cleaned up afterward.

## Whole Corpus Frontend Readiness

### Current Corpus Size

| Layer | Records | Frontend Readiness |
| --- | ---: | --- |
| Statutes | 34,717 | Ready for citation pages, hierarchy browsing, and topic discovery |
| Regulations | 1,035 | Ready for rule pages, requirement extraction, and industry filtering |
| Legislation | 12,453 | Ready for bill search, bill timelines, and statute-impact views |
| Rulemaking | 7,955 | Ready for notice timelines and regulation lifecycle views |
| Executive Orders | 535 | Ready for governor timeline and source-backed order pages |
| Session Laws | 437 | Ready for chapter history and law-change views |
| Supplementary | 23 | Ready for support-document pages and review queues |

### Current Trust State

Source strength now covers all 57,155 records.

- 53,035 records have direct full-text source support.
- 4,120 records have official-listing-plus-document support.
- Average source strength score is 0.987.
- Zero records are marked low accuracy.
- Zero missing source files were found in the refreshed source-to-output audit.

Frontend meaning:

- The frontend can confidently show a trust panel for every record.
- Rulemaking and supplementary materials need extra visual care because many are not as deep as direct full-text sources.
- The frontend should never hide source strength. It should make source strength part of every serious legal answer.

### Current Relationship State

Relationship records checked: 9,980.

Relationship files available:

- regulation to statute
- statute to regulation
- bill to statute
- rulemaking to regulation
- agency to statute
- amendment history

Frontend meaning:

- Geode already has enough relationship data for a useful authority map.
- The frontend should avoid showing a giant whole-corpus graph by default.
- Better approach: scoped relationship views that start from one record, one agency, one citation, or one topic.

## Current Frontend Capability

The frontend can currently:

- Show operational dashboard counts from the manifest.
- Show source watcher and queue information.
- Search through the rebuilt SQLite read index.
- Return EO-2019-007 from direct search.
- Show detail records from the read index.
- Show basic relationship counts.
- Show static or lightly dynamic manager workspaces.

The frontend does not yet fully capture:

- What a statute, rule, bill, notice, or order says in a user-centered way.
- Why a source should be trusted.
- How one authority changed another authority.
- Which agency has authority over a given rule or topic.
- What a user should do next based on a source-backed requirement.
- Where an item sits in time.
- Which records need human review before stronger public use.

## Design Research Used

External references reviewed:

- [Blacklight](https://projectblacklight.org/) is a strong model for library-style discovery, faceted search, and source browsing. It is used by many institutional discovery systems and is designed around finding records across collections.
- [Cytoscape.js](https://js.cytoscape.org/) is a strong fit for legal relationship maps because it is a graph visualization and analysis library with JSON data support, layouts, selectors, and graph algorithms.
- [vis-timeline](https://visjs.github.io/vis-timeline/docs/timeline/) is a good fit for legal chronology because it supports interactive date items, date ranges, groups, zooming, and custom styling.
- [Observable Plot](https://observablehq.com/plot/) is a good fit for audit and coverage views because it supports layered marks, scales, transforms, facets, and concise chart construction.

Recommendation from research:

- Use Blacklight-like discovery patterns for browsing.
- Use Cytoscape-style scoped graph views for relationships.
- Use vis-timeline-style grouped timelines for rulemaking, bills, executive orders, and source freshness.
- Use Observable Plot-style charts for audit coverage, confidence, source strength, and freshness summaries.

No dependency should be added without a separate approval step. The current audit only identifies the best-fit frontend patterns.

## Specific Frontend Applications

### 1. Authority Lens

Primary purpose:

Show one legal record as a complete, source-backed authority page.

Applies to:

- statutes
- regulations
- bills
- rulemaking notices
- executive orders
- session laws
- supplementary documents

What it should show:

- title
- citation
- source strength
- source URL
- source archive path
- last checked date
- full text or extracted text
- related records
- timeline events
- known gaps

Why it matters:

This should become the basic frontend building block. Every search result, relationship edge, timeline event, and compliance answer should be able to open an Authority Lens page.

First version:

- Use the existing read index and detail lookup.
- Add source trust, related records, and direct official-source buttons.

### 2. Source Trust Panel

Primary purpose:

Make trust visible on every record and every answer.

What it should show:

- direct full-text source or official-listing-plus-document
- source URL
- raw archive status
- last checked date
- confidence score
- freshness status
- human review status if applicable

Why it matters:

Geode is not just a search tool. It is a source-backed legal data system. Users must see whether the record is strong, medium, stale, or awaiting review.

Best first implementation:

- Put this on Authority Lens first.
- Then reuse it in Ask Geode, Search, Compliance Paths, and Review Workbench.

### 3. Colorado Legal Library

Primary purpose:

Turn the file tree into a browseable legal library.

Inspired by:

- Blacklight-style discovery systems.

What it should show:

- search box
- citation filters
- layer filters
- agency filters
- year filters
- source strength filters
- relationship count filters
- freshness filters

Why it matters:

The current data is ready for discovery, but users should not need to understand the repository structure.

### 4. Regulatory Terrain Map

Primary purpose:

Show all legal authority touching a topic, industry, or activity.

Example user question:

"What Colorado authority affects a manufacturer with air emissions and hazardous waste?"

What it should include:

- statutes
- regulations
- agencies
- rulemaking notices
- bills
- session laws
- executive orders where relevant

Frontend shape:

- left side: topic filters
- center: grouped result lanes
- right side: source trust and related authority

Why it matters:

This is the most practical way to show what the law "says" without pretending one record answers everything.

### 5. Agency Power Map

Primary purpose:

Show what authority each agency has and where it comes from.

Uses:

- agency-to-statute crosswalk
- regulation-to-statute crosswalk
- rulemaking-to-regulation crosswalk

What it should show:

- agency
- enabling statutes
- rules administered
- rulemaking activity
- source strength
- open review items

Frontend shape:

- scoped graph around one agency
- list view fallback
- filters for department, source strength, and active rulemaking

Why it matters:

This is one of Geode's most unique potential tools. It can show how power flows from statute to agency to rule.

### 6. Rulemaking Lifecycle Board

Primary purpose:

Show the life of regulatory change.

Uses:

- rulemaking notices
- eDocket details
- rulemaking-to-regulation links
- Colorado Register dates

What it should show:

- proposed notices
- adopted notices
- amended rules
- repealed rules
- effective dates
- affected CCR rule
- source documents

Frontend shape:

- grouped timeline
- lanes by agency or rule
- status filters
- source documents attached to each event

Why it matters:

Rulemaking is not a simple record list. It is a process. A lifecycle board captures that process in a way users can act on.

### 7. Law Change Radar

Primary purpose:

Answer: "What changed since this date?"

Uses:

- bills
- session laws
- rulemaking
- executive orders
- update log
- amendment history

What it should show:

- date range selector
- layer toggles
- changed authority
- source-backed reason for change
- affected statutes or rules

Frontend shape:

- timeline plus grouped change list
- each item opens Authority Lens

Why it matters:

This turns the corpus into a monitoring product, not just a static library.

### 8. Compliance Path Builder

Primary purpose:

Guide a user from a business/activity profile to source-backed requirements.

Uses:

- regulations
- statutes
- rule units
- industry filters
- relationship data
- source trust

What it should show:

- user profile inputs
- likely applicable requirements
- source-backed citations
- next steps
- uncertainty warnings
- reviewer-needed flags

Important boundary:

This must not give unsupported legal advice. It should say which source-backed requirements may apply and why.

### 9. Executive Action Timeline

Primary purpose:

Make executive orders understandable by governor, date, topic, and source.

Uses:

- executive order records
- signed dates
- governor names
- source URLs
- full text

What it should show:

- governor timeline
- order list by year
- topic and keyword filters
- order detail page
- official source link
- OCR quality notice when appropriate

Why it matters:

EO-2019-007 shows the need well. A recovered order should not only be "in the data"; users should be able to see when it happened, who issued it, what it directed, and where the official PDF is.

### 10. Session Law And Bill Impact View

Primary purpose:

Show how bills and session laws affect codified law.

Uses:

- bills
- session laws
- bill-to-statute links
- amendment history

What it should show:

- bill
- session law chapter
- affected statutes
- dates
- official documents
- current CRS destination

Why it matters:

This makes legislative history useful for policy work and compliance research.

### 11. Source Repair Workbench

Primary purpose:

Give reviewers one screen for records that need stronger source support.

Uses:

- source limitation register
- source repair dashboard
- modern LegiScan repair queue
- source-to-output audit
- human review workflow

What it should show:

- open repair items
- reason for weakness
- official source needed
- current source status
- action command or manual instructions
- before/after impact on frontend readiness

Why it matters:

This makes data-quality work visible and prevents agents from repeatedly rediscovering the same source gaps.

### 12. Audit Command Center

Primary purpose:

Turn control-plane reports into a readable operations dashboard.

Uses:

- recent download audit
- corpus usability audit
- source strength report
- source-to-output audit
- source watcher dashboard
- next-download dashboard

What it should show:

- current record count
- audit pass/warn/fail
- source strength distribution
- layer freshness
- unresolved blockers
- next authorized download area

Why it matters:

Geode already produces strong audit artifacts. The frontend should make them understandable without requiring users to open JSON files.

## Layer-By-Layer Frontend Capture Plan

### Statutes

What they say:

Statutes define legal authority, duties, definitions, programs, penalties, and powers.

Best frontend capture:

- citation-first authority pages
- title/article/section hierarchy
- definition callouts
- "rules under this statute" section
- "bills or session laws affecting this statute" section

Unique application:

Statutory Backbone View: a structural map showing how a title breaks down into articles, parts, and sections, with relationship counts attached.

### Regulations

What they say:

Regulations turn statutory authority into agency-administered rules and practical requirements.

Best frontend capture:

- CCR rule pages
- agency filter
- industry filter
- requirement cards
- enabling authority links
- rule-unit review status

Unique application:

Requirement Strip: a compact panel that extracts duties, deadlines, records, reports, permits, and exceptions from a rule.

### Legislation

What it says:

Bills show proposed or enacted policy movement, sponsors, subjects, and affected law.

Best frontend capture:

- bill pages
- session filter
- status timeline
- affected statute list
- document coverage warning when official PDFs are missing

Unique application:

Bill Impact Radar: a view that clusters bills by the laws and agencies they affect.

### Rulemaking

What it says:

Rulemaking records show proposed, adopted, amended, or repealed regulatory action.

Best frontend capture:

- lifecycle timeline
- agency lanes
- affected rule cards
- eDocket document links
- source-depth labels

Unique application:

Rulemaking Conveyor: a board that follows one rule from notice to adoption to effective date.

### Executive Orders

What they say:

Executive orders show directives from the governor, often tied to emergencies, agencies, operational actions, or time-limited policy decisions.

Best frontend capture:

- governor timeline
- order detail page
- directive extraction
- agency mentions
- source PDF panel

Unique application:

Governor Action Ledger: a timeline by governor showing directives, durations, affected agencies, and source-backed text.

### Session Laws

What they say:

Session laws are enacted chapters that often explain how bills became law and what codified law changed.

Best frontend capture:

- chapter pages
- enacted date
- bill link
- affected CRS links
- statutory destination

Unique application:

From Bill To CRS: a guided path from bill, to session law, to current statute.

### Supplementary

What it says:

Supplementary documents support interpretation, policy review, program oversight, and reform work.

Best frontend capture:

- document pages
- interpreted statutes
- affected programs
- reviewer status
- source strength label

Unique application:

Policy Evidence Shelf: a research panel attached to statutes, agencies, and topics showing AG opinions, COPRRR reviews, and other support materials.

## Prioritized Build Recommendation

### Priority 1: Authority Lens Plus Source Trust Panel

Reason:

This gives every record a usable frontend home and makes trust visible immediately.

Scope:

- authority detail route
- source trust panel
- related-record list
- official source link
- freshness and confidence display

Why first:

It improves every layer at once.

### Priority 2: Colorado Legal Library

Reason:

Users need a better discovery surface before advanced visualizations.

Scope:

- faceted browse
- layer filters
- source strength filters
- date filters
- citation-first search

### Priority 3: Rulemaking Lifecycle Board

Reason:

Rulemaking is high-value and currently hard to understand as plain records.

Scope:

- grouped timeline
- agency lanes
- notice type filters
- affected rule links

### Priority 4: Agency Power Map

Reason:

This is uniquely valuable because Geode has crosswalks that can show authority flow.

Scope:

- scoped agency graph
- statute/rule links
- relationship evidence
- list fallback for accessibility

### Priority 5: Compliance Path Builder

Reason:

This is likely the highest user-value feature, but it should come after Authority Lens and Source Trust because it must rely on clear source-backed record pages.

Scope:

- user profile inputs
- requirement candidates
- source-backed citations
- uncertainty and review warnings

## Data And Frontend Gaps To Fix Before Larger Public Use

1. Rulemaking source depth should be visually labeled.
   Many rulemaking records are official-listing-plus-document instead of direct full-text source.

2. Supplementary documents need better relationship extraction.
   They are useful, but the frontend needs program-to-statute and opinion-to-statute links to make them powerful.

3. LegiScan document gaps need a public-safe explanation.
   There are 23,965 permanent source-coverage gaps across 2010-2026, including 41 modern-year items. The frontend should not hide this. It should show document coverage honestly.

4. OCR quality needs a visible note.
   Executive-order PDFs and other scanned documents can contain imperfect text. Users should see official PDF links and OCR caution where needed.

5. Build and dev workflows should avoid shared `.next` conflicts.
   Production verification should use a separate build folder, and live-data pages should remain dynamic.

6. Audit scope should avoid snapshots and runtime user data.
   The corrected corpus usability audit now checks current legal corpus files instead of scanning old snapshots and local frontend runtime data.

## Changes Made During This Audit

The audit required several small readiness fixes:

- Refreshed retrieval catalog to 57,155 records.
- Rebuilt frontend SQLite read index to 57,155 entities.
- Refreshed corpus usability audit to 57,155 records with zero issues.
- Refreshed recent download audit so EO-2019-007 is no longer shown as blocked.
- Refreshed source-to-output and source-strength reports.
- Fixed the recent-download audit so it no longer reports stale hard-coded corpus numbers.
- Fixed corpus usability audit scope so it skips snapshots and frontend runtime user data.
- Marked forum and profile pages dynamic to avoid static-build work against live data.
- Hardened personalization request parsing.
- Verified the Next production build after stopping the stalled process.

## Verification Summary

Passed:

- `python -m geode.validate --layer 05_Executive_Orders`
- `python -m geode.validate --layer all`
- `python -m geode.pipeline.retrieval_catalog --root . --write --json`
- `python -m geode.web.index --root . --database geode/web/data/structured_output/commons.sqlite3 --rebuild`
- direct search for `EO-2019-007`
- detail lookup for `EO-2019-007`
- `pytest tests/test_recent_download_audit.py tests/test_corpus_usability_audit.py tests/test_retrieval_catalog.py -v`
- `python -m geode.pipeline.corpus_usability_audit --root . --write`
- `python -m geode.pipeline.recent_download_audit --root . --write --json`
- `python -m geode.pipeline.source_quality_operating_layer --root . --json`
- Next production build using the bundled Node runtime and isolated output folder

Warnings remaining:

- LegiScan permanent document gaps remain a known source-coverage issue.
- One future freshness item remains in the freshness verification queue.
- External reliance readiness is still false because named reviewer assignments and live official freshness verification remain required.

## Authorization Recommendation

Recommended next authorized frontend build:

Build Authority Lens plus Source Trust Panel first.

Why:

It is the smallest high-value frontend improvement that benefits every layer. It would make the recovered EO-2019-007 visibly source-backed, while also creating the reusable record page needed for timelines, graphs, compliance paths, and Ask Geode answers.

Recommended follow-up after that:

Build Colorado Legal Library, then Rulemaking Lifecycle Board, then Agency Power Map.
