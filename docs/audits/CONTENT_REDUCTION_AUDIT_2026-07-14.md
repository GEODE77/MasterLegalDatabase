# Geode Content Reduction Audit - 2026-07-14

Historical note: this audit describes a former frontend and product-surface
direction. Geode is now backend-only; these findings are retained as dated
evidence and are not current architecture.

## Bottom Line

Geode should cut visible text by roughly 60-75 percent across the active product without removing core function. The largest issue is not one bad page. It is a repeated pattern:

- A large route header explains the screen.
- The screen itself repeats the same idea in a second intro block.
- Cards contain short labels plus full explanatory sentences.
- Dashboards read like status reports instead of command surfaces.
- Search and review screens expose advanced reasoning before the user asks for it.

The product already has strong data. The interface should show state, filters, counts, source status, and next actions first. Explanations should move behind details, drawers, tooltips, or record views.

## Scope

Primary active app reviewed:

- `geode/web`

Secondary or older app surface reviewed:

- `apps/web`

The in-app browser was blocked from opening localhost by enterprise policy, so this audit is based on the visible screen source in the frontend files. Most visible copy is static in page and component files, so this is still a reliable screen-by-screen copy audit.

## Highest Impact Global Cuts

### 1. Remove Duplicate Page Introductions

The shared product chrome already shows route name, page title, short description, and sometimes an action. Many screens then add a second local intro that restates the same job.

Recommendation:

- Keep only one page-level intro.
- For product screens, prefer the shared chrome and remove local `Intro` blocks.
- For public screens, keep a single line under the title at most.

Expected reduction:

- 10-20 percent across manager and app screens.

Primary files:

- `geode/web/src/components/navigation/ProductChrome.tsx`
- `geode/web/src/components/ops/OpsWorkspace.tsx`
- `geode/web/src/app/app/*/page.tsx`

### 2. Convert Explanatory Sentences Into Status Chips

Many cards explain what the card means. The user usually needs the value, status, and next action.

Replace sentences like:

> Current, changed, blocked, or needs review.

With compact labels:

- `Current`
- `Changed`
- `Blocked`
- `Review`

Expected reduction:

- 15-25 percent on dashboards and operational pages.

### 3. Collapse Evidence, Rationale, and Warnings

Evidence matters, but it should not always be visible. By default, show only:

- Citation
- Status
- Confidence or trust level
- Source type
- Next action

Move full evidence text behind:

- `Evidence`
- `Why`
- `Source note`
- `History`
- `Review details`

Expected reduction:

- 25-50 percent on review, query, source, and detail pages.

### 4. Stop Teaching On Dashboards

Dashboards should answer:

- What changed?
- What is blocked?
- What needs review?
- What can I do now?

Dashboards should not explain how Geode works. Move education to help, docs, onboarding, or detail drawers.

Expected reduction:

- 30-50 percent on `System`, `Sources`, `Relationships`, `Updates`, `Review`, and `Publish`.

### 5. Prefer Search And Filters Before Context

On high-intent screens, search should come before explanation.

Affected screens:

- Query
- Library
- Regulations
- Explorer
- Forum
- Requirements
- Sources
- Review queue

Recommendation:

- Put the search/filter row first.
- Reduce page introductions to title plus optional one-line scope.
- Move guidance into placeholder text or empty states.

## Screen-by-Screen Audit

## Public Home

Current issue:

- The home page has a hero, three action cards, metrics, and a manager boundary note. The manager note is too verbose for a public entry screen.

Delete:

- The paragraph explaining regular users and managers.
- Repeated "open for use" language.

Condense:

- Hero title to: `Search Colorado legal data`
- Action card bodies to 2-4 word metadata: `Cited answers`, `Source index`, `Public issues`

Hide:

- Manager access explanation behind `Manager access`.

Primary action:

- `Search`

Expected reduction:

- 55-65 percent.

## Library

Current issue:

- The page explains how to use the library even though the screen should be a source index.

Delete:

- "Start with CRS, CCR, bill number, executive order, agency, or topic."
- "Every source should be treated as current, stale, blocked, or needing review before public reliance."
- "Search results should explain whether they matched..."
- "Each legal layer shows..."

Condense:

- Title to: `Legal data library`
- Source cards to: `Layer`, `Records`, `Freshness`, `Source`

Hide:

- Freshness policy behind `Freshness`.
- Search-result explanation behind `Why this result`.

Primary action:

- `Search`

Expected reduction:

- 60-75 percent.

## Query

Current issue:

- The query screen is close to the right direction, but it still explains too much before the user asks anything.
- Search lens descriptions are always visible.
- The answer view exposes many reasoning sections at once.

Delete:

- Long hero sentence about source-backed Colorado legal material.
- Instruction line about citations, agencies, topics, bill numbers, executive orders, and plain language.
- Loading detail: "Checking sources, ranking results, and shaping the lens view."

Condense:

- Hero to: `Ask Geode`
- Search label to: `Question`
- Lens descriptions to tooltips.
- Status to: `Reading sources`, `Writing answer`, `Ready`.

Hide:

- Lens guide.
- Missing facts.
- Source boundary.
- Number workbench.
- Source hierarchy.
- Expanded sources.

Default view:

- Answer
- Top citations
- Next action
- Confidence or warning

Primary action:

- `Ask`

Expected reduction:

- 50-70 percent before search.
- 40-60 percent in answer view.

## Regulations Index

Current issue:

- The screen has a good search-first shape, but result cards show full excerpts by default.

Delete:

- Hero explanation: "Browse Colorado regulation records from the public legal library."
- Empty fallback sentence can become `No matches`.

Condense:

- Hero to: `CCR`
- Stats to chips: `Records`, `Agencies`, `Checked`
- Result cards to: `Citation`, `Title`, `Trust`, `Open`

Hide:

- Excerpts behind hover, drawer, or expanded row.

Primary action:

- Search regulations.

Expected reduction:

- 45-60 percent.

## Regulation Detail

Current issue:

- Detail pages are allowed to be text-heavy, but the opening area still needs a compact record summary.

Delete:

- Fallback text like "Effective date not stated" unless the missing date is a decision risk.

Condense:

- Header to `Citation`, `Agency`, `Effective`, `Trust`.
- Notes list to badges first.

Hide:

- Full notes and related authority behind tabs.
- Source body should remain readable, but not mixed with all metadata at once.

Primary action:

- `Official source` or `Copy citation`.

Expected reduction:

- 25-40 percent in header and metadata zones.

## Authority Detail

Current issue:

- This page mixes source text, trust scoring, references, timeline, and source notes in one vertical flow.

Delete:

- "Current indexed source" when it is the default.
- Repeated headings that are empty or low value.

Condense:

- Header to a record strip: `Layer`, `Citation`, `Version`, `Trust`.
- Timeline items to `Date`, `Event`, `Open`.

Hide:

- Source note.
- Source file paths.
- Source versions.
- Trust detail.

Primary action:

- `Official source`

Expected reduction:

- 35-55 percent outside the legal text itself.

## Forum Feed

Current issue:

- The forum has strong dashboard elements, but the hero explains the board and competes with the issue filters.

Delete:

- "Use this board to find open petitions, bill positions, rulemaking work, and executive-level compliance risks."
- "Policy action board" label if the title already says it.

Condense:

- Title to: `Issue board`
- Metrics to: `Open`, `Active`, `Review`, `Linked`

Hide:

- Empty-state explanation behind a short empty state.

Primary action:

- `Create issue`

Expected reduction:

- 45-60 percent.

## Forum Record

Current issue:

- A forum record shows metadata, action framing, thread body, support signals, replies, and reply guidance. That is too much at once.

Delete:

- Repeated time displays. Keep either exact time or relative time, not both.
- "support signals on record" can become `Support`.
- Empty reply helper sentence can become `No replies`.

Condense:

- Action block to chips: `Audience`, `Source`, `Action`, `Date`, `Impact`.

Hide:

- Action explanation text.
- Long reply bodies behind collapsed thread groups when many replies exist.

Primary action:

- `Reply`

Expected reduction:

- 35-50 percent.

## Issue Composer

Current issue:

- The composer includes helper copy under fields that can be inferred from labels.

Delete:

- "Pick the closest action path. You can add more detail below."
- "Mark how visible or operationally important this record is."

Condense:

- `Issue intake` to `New issue`
- `Issue brief` to `Brief`
- `Requested action` to `Action`

Hide:

- Field guidance behind tooltips.

Primary action:

- `Create`

Expected reduction:

- 35-50 percent.

## Public Profile

Current issue:

- Profile pages use repeated contribution language.

Delete:

- "{name} contributes regulatory judgment..."
- "{name} has contributed to forum interpretation..."

Condense:

- Show name, role, contribution count, recent activity.

Expected reduction:

- 50-70 percent.

## About

Current issue:

- About page is prose-led.

Delete:

- Long mission headline.
- Empty investor/advisor explanation.

Condense:

- `About Geode`
- Team cards: `Name`, `Role`, `Contact`

Hide:

- Full bios.
- Investor note until populated.

Expected reduction:

- 50-65 percent.

## Trust

Current issue:

- Trust content is important, but the first view should be a security posture summary, not a document page.

Delete:

- Hero paragraph explaining why the page exists.
- Full row text on first load.

Condense:

- Trust cards to: `Encryption`, `Access`, `Logs`, `Infrastructure`, `Retention`, `Deletion`
- Status values: `In place`, `Planned`, `Available`, `On request`

Hide:

- Detailed privacy and security text behind expandable rows.

Primary action:

- `Contact security`

Expected reduction:

- 55-70 percent.

## Pricing

Current issue:

- Pricing reads like a sales page. The requested standard calls for less marketing language.

Delete:

- "Pricing begins with the operating problem."
- "Geode is sold for teams..."
- "Bring Geode to the regulatory work that cannot wait."

Condense:

- `Enterprise`
- `Custom scope`
- `Manager workflows`
- `Source-backed intelligence`

Primary action:

- `Contact sales`

Expected reduction:

- 65-80 percent.

## Manager Dashboard

Current issue:

- The dashboard has useful metrics, but too many panels include sentence-level explanation.

Delete:

- Board item body text such as "Official source status", "Blocked work", "Search the corpus", "Recent checks".
- Quality guidance paragraph.
- Layer reason text from default view.

Condense:

- Board items to icon, title, count, status.
- Readiness panel to three rows: `Corpus`, `Relationships`, `Next decision`.

Hide:

- Quality detail behind `Quality`.
- Layer reason behind expandable layer row.

Primary action:

- `Review queue`

Expected reduction:

- 50-65 percent.

## Manager Sources

Current issue:

- Sources should behave like an operations board. The page currently exposes next-step sentences, markers, download gates, probes, and calendar copy all at once.

Delete:

- Local intro block.
- Repeated "none" values where empty state can be visual.

Condense:

- Source table columns to: `Source`, `Layer`, `Status`, `Local`, `Observed`, `Action`.
- `nextStep` to a short action chip.

Hide:

- Download gate details.
- Source probe controls.
- Calendar entries.

Primary action:

- `Check sources`

Expected reduction:

- 45-60 percent.

## Manager Review Queue

Current issue:

- The queue should prioritize blocked items and the next repair action. It currently includes repair path explanation and a process flow.

Delete:

- Local intro block.
- Repair path teaching text.
- Flow labels if they do not change by item.

Condense:

- Queue item to: `ID`, `Status`, `Age`, `Owner`, `Source`, `Action`.

Hide:

- Official source confirmation.
- Reason text.
- Repair progress.
- Blocker detail.

Primary action:

- `Open item`

Expected reduction:

- 50-70 percent.

## Manager Explorer

Current issue:

- This screen is close to a search-first surface, but terrain cards contain explanatory text.

Delete:

- Local intro block.
- Terrain descriptions like "Definitions, duties, programs, and penalties."

Condense:

- Terrain cards to source labels and counts.

Hide:

- Layer descriptions until hover or drawer.

Primary action:

- Search.

Expected reduction:

- 45-60 percent.

## Manager Relationships

Current issue:

- Relationship pages explain why graph work is delayed. That is project documentation, not a dashboard.

Delete:

- "Why graph work stays later"
- "Use structured relationship panels first"
- Any paragraph explaining the graph boundary on first load.

Condense:

- Show metrics: `Total`, `CCR coverage`, `Missing evidence`, `Graph`.
- Crosswalk cards: `File`, `Relationships`, `Missing`, `Low confidence`, `Status`.

Hide:

- Graph boundary explanation.
- Improvement rationale.

Primary action:

- `Open relationship panel`

Expected reduction:

- 60-75 percent.

## Manager Timeline

Current issue:

- Timeline has a useful shape but includes educational panels below the event list.

Delete:

- Local intro block.
- Rulemaking and law-change teaching panels.
- Executive order caution text from default view.

Condense:

- Timeline event to: `Date`, `Type`, `Status`, `Open`.

Hide:

- Event body.
- OCR cautions unless the selected record needs it.

Primary action:

- Filter timeline.

Expected reduction:

- 50-70 percent.

## Manager Compliance Paths

Current issue:

- Strong task surface, but side copy and requirement strip repeat source-backed language.

Delete:

- "Start with an activity. Return source-backed steps."
- "Source-backed language only" repeated under every category.

Condense:

- Sidebar to checklist chips: `Requirements`, `Citations`, `Links`, `Flags`.

Hide:

- Output requirements behind tooltip.

Primary action:

- `Build path`

Expected reduction:

- 45-60 percent.

## Manager Ask

Current issue:

- Similar to Query. The screen should be almost entirely input-first.

Delete:

- Local intro block.
- Answer requirements paragraph.

Condense:

- Sidebar to chips: `Citations`, `Related`, `Freshness`.

Primary action:

- `Ask`

Expected reduction:

- 50-65 percent.

## Manager Publish

Current issue:

- Publish should show go/no-go state. It currently includes checklist panels plus explanatory recommendations.

Delete:

- "Can Geode publish or not?"
- Full recommendation paragraph from default view.

Condense:

- Top state: `Ready` or `Blocked`
- Checks: `Secrets`, `Downloads`, `Dashboard`, `Git`

Hide:

- Download closeout details.
- Trust controls.
- Pipeline details.
- Quality details.

Primary action:

- `Check release`

Expected reduction:

- 50-65 percent.

## Manager Improvements

Current issue:

- This screen reads like a completion report.

Delete:

- "All 35 recommended improvements are completed and audited."
- Per-item "Audit" and "Further attention" text from default view.

Condense:

- Show categories with counts: `Completed`, `Open`, `Deferred`.

Hide:

- Completed detail behind category drawer.

Primary action:

- `Review open attention`

Expected reduction:

- 65-80 percent.

## Manager Admin

Current issue:

- Admin has real actions, but the intro and registry detail add visual weight.

Delete:

- "Create, revoke, and review manager access."
- "Send this privately..." after invite creation can become `Copy invite`.

Condense:

- Account rows to: `Name`, `Email`, `Role`, `Status`, `Last active`, `Revoke`.

Hide:

- Access reasons.
- Activity history until opened.

Primary action:

- `Create manager`

Expected reduction:

- 35-50 percent.

## Manager Verify

Current issue:

- Verification can stay simple, but helper text should be minimal.

Condense:

- Title to `Manager access`
- Button to `Verify`

Hide:

- Any invite explanation until error state.

Expected reduction:

- 30-45 percent.

## App Dashboard

Current issue:

- This route overlaps with the manager dashboard and should not maintain separate explanatory copy.

Recommendation:

- Either redirect to the manager dashboard or use the same compact dashboard components.

Expected reduction:

- 40-60 percent by consolidation.

## App Requirements

Current issue:

- The page explains candidate versus validated signals before the user needs it.

Delete:

- Intro paragraph about rule units and candidate signals.
- Empty-state guidance sentence.

Condense:

- Header to: `Requirements`
- Status chip: `Validated` or `Candidate`

Hide:

- Source type explanation.
- Requirement evidence until item expansion.

Primary action:

- Search/filter requirements.

Expected reduction:

- 45-60 percent.

## App Impact

Current issue:

- The page explains the MVP and legal-review boundary in the intro. That belongs behind a boundary note.

Delete:

- Deterministic MVP explanation.
- "It is a review tool, not a legal..." from the default view.

Condense:

- Profile summary to three chips: `Industry`, `Jurisdiction`, `Operations`.

Hide:

- Source summary sentence on each result.

Primary action:

- `Review source`

Expected reduction:

- 45-60 percent.

## App Explore

Current issue:

- This screen is a source reader plus evidence side panel. It should not have a verbose intro.

Delete:

- "Read source text beside relationships and evidence."
- "No requirement signals were found. This does not mean no obligation exists."

Condense:

- Empty states to `No relationships` and `No requirements`.

Hide:

- Relationship evidence.
- Requirement evidence.
- Document outline on small screens.

Primary action:

- Search/select a source.

Expected reduction:

- 35-55 percent outside source text.

## App Compliance Paths

Current issue:

- This duplicates manager compliance ideas with more explanatory text.

Delete:

- Intro paragraph.
- Empty state paragraph.

Condense:

- Profile summary to chips.
- Path step to: `Order`, `Citation`, `Action`, `Status`.

Hide:

- Step description until expanded.

Expected reduction:

- 45-60 percent.

## App Relationships

Current issue:

- This is one of the highest-value pruning targets. It is currently too close to a project decision memo.

Delete:

- "Measure crosswalk coverage before building a visual graph."
- "Why graph work stays later."
- "Use structured relationship panels first."
- Paragraphs explaining sources and relationship counts.

Condense:

- Top metrics only.
- Crosswalk rows with counts.

Hide:

- Graph boundary.
- Next action explanations.

Expected reduction:

- 65-80 percent.

## App Review

Current issue:

- The page explains review mechanics before presenting the queue.

Delete:

- Intro paragraph about original source sentence, extraction, quality issues, and outcomes.
- "Work the queue..." can be shortened.

Condense:

- Header to: `Rule-unit review`
- Metrics: `Untouched`, `Decision-aware`, `Logged`

Hide:

- Review reason.
- Source sentence.
- Suggested outcomes.
- Rationale field until a user opens a row.

Primary action:

- `Review`

Expected reduction:

- 50-70 percent.

## App Review Packets

Current issue:

- Packet cards expose instruction, source sentence, context, and identifiers at once.

Delete:

- Intro paragraph.
- "Showing X packets" when filter count is already visible.

Condense:

- Packet card to: `Priority`, `Status`, `Review ID`, `Citation`, `Change ready`.

Hide:

- Reviewer instruction.
- Source sentence.
- Source context.

Primary action:

- `Open packet`

Expected reduction:

- 50-70 percent.

## App Reviewer Operations

Current issue:

- This page reads like an operations registry document.

Delete:

- "Prepare reviewer slots and operating instructions."
- SOP path from first view.
- Paragraph under next action.

Condense:

- Metrics: `Roles`, `Unassigned`, `SOP`
- Assignment cards: `Role`, `Reviewer`, `Status`

Hide:

- Operating instructions.
- SOP path.

Primary action:

- `Assign reviewer`

Expected reduction:

- 55-70 percent.

## App Reliance Policy

Current issue:

- Policy content is important but should be layered.

Delete:

- "Define when Geode outputs can support real-world decisions."
- "These limits travel with review outputs."

Condense:

- Top metrics: `Policy`, `Version`, `Approval levels`
- Boundary cards: `Level`, `Boundary`, `Status`

Hide:

- Role descriptions.
- Criteria descriptions.
- Boundary paragraphs.

Primary action:

- `Review policy`

Expected reduction:

- 50-65 percent.

## App Updates

Current issue:

- The page mixes freshness status, ledger summary, event descriptions, and log paths.

Delete:

- "Track source-backed corpus updates before full text diff."
- Full ledger next-action sentence from default view.

Condense:

- Metrics: `Ledger`, `Diff`, `Timeline`, `Logs`
- Events: `Date`, `Layer`, `Type`, `Status`

Hide:

- Event descriptions.
- Log paths.

Primary action:

- `View update`

Expected reduction:

- 50-65 percent.

## App System

Current issue:

- This is the densest dashboard. It currently reads like a readiness report.

Delete:

- "See what is complete, what is queued, and what needs people."
- "How much of the corpus is anchored to preserved source material."
- "Items that still need people or outside refresh."
- Boundary paragraphs from first view.
- Evidence path paragraphs from control cards.

Condense:

- Top state: `Local use`, `Reliance`, `Open work`, `Source score`
- Cards should show status, count, and action only.

Hide:

- Source evidence explanation.
- Repair next actions.
- Production boundary.
- Control details.
- Queued work reasons.
- Freshness details.

Primary action:

- `Open work queue`

Expected reduction:

- 65-80 percent.

## App Settings

Current issue:

- The app settings route is mostly migration explanation.

Delete:

- "Product settings remain connected to the existing workspace controls."
- "This route reserves..."
- "The existing settings page remains available during route migration."

Recommendation:

- Replace with actual settings or redirect to the existing settings page.

Expected reduction:

- 80-100 percent on this route.

## Legacy `apps/web` Surface

If `apps/web` is still part of any product path, it needs the same pruning. If it is no longer active, the best text reduction is to archive it or clearly mark it as legacy.

### Legacy Home

Delete:

- "The foundation of the regulatory market."
- "Regulation is one of the largest opaque markets in the economy."
- Pillar descriptions.
- "The regulatory economy is here. Geode makes it legible."

Condense:

- Home to metrics plus `Inspect corpus`.

Expected reduction:

- 70-85 percent.

### Legacy Search

Delete:

- "Search official law separately from discussion."
- "Results preserve the boundary..."

Condense:

- Keep search input, filters, result list.

Expected reduction:

- 45-60 percent.

### Legacy Agency, Community, Docket, Notification, Issue, Timeline, Review, Profile

Common cuts:

- Remove lede paragraphs.
- Keep object title, counts, status, filters, and primary action.
- Move summaries behind row expansion.

Expected reduction:

- 50-70 percent.

### Legacy Tokens

Recommendation:

- Keep as internal design documentation only.
- Remove from product navigation.

Expected user-facing reduction:

- 100 percent if hidden from users.

## Component-Level Rules To Apply

### Shared Page Header

Current:

- Route label
- Title
- Description
- Local page intro below

Target:

- Title
- One action
- Optional 3-5 word status chip

Rule:

- A screen cannot have both a shared page description and a local intro unless the local intro contains a live warning.

### Cards

Current:

- Label
- Sentence
- Status

Target:

- Label
- Count or status
- Optional icon

Rule:

- Card body text is hidden by default unless the card is a document preview.

### Tables And Lists

Current:

- Rows include reason, source confirmation, next step, owner, age, and prose.

Target:

- Rows show 4-6 fields maximum.
- Details open in drawer.

Rule:

- If a row has more than one sentence, it becomes expandable.

### Empty States

Current:

- Empty states explain what happened and what to do.

Target:

- `No matches`
- One button

Rule:

- Empty state copy max: 5 words plus one action.

### Warnings

Current:

- Warnings are written as full paragraphs.

Target:

- `Freshness warning`
- `Needs source`
- `Review only`
- `Blocked`

Rule:

- Explanation appears only on click.

## Suggested Implementation Plan For Approval

### Phase 1 - Fast Global Reduction

Goal:

- Remove the biggest repeated text without redesigning screens.

Work:

- Remove shared page descriptions from product chrome or local intros from screens.
- Shorten all route descriptions to status chips.
- Remove public page marketing paragraphs.
- Shorten empty states.

Expected result:

- 30-45 percent visible text reduction.

Risk:

- Low. Mostly copy removal.

### Phase 2 - Dashboard Compression

Goal:

- Make dashboards feel like intelligence tools instead of reports.

Work:

- Convert manager and app dashboard card bodies into counts, chips, and status labels.
- Collapse quality, source, repair, relationship, and system details.
- Make rows expandable.

Expected result:

- 50-65 percent reduction on operations screens.

Risk:

- Medium. Requires small layout changes.

### Phase 3 - Query And Review Progressive Disclosure

Goal:

- Keep deep evidence available without making every answer or queue item heavy.

Work:

- Default query answers to compact mode.
- Collapse source boundary, lens guide, missing facts, number workbench, and references.
- Collapse review packet instructions, source context, review reason, and evidence.

Expected result:

- 40-70 percent reduction on the highest-density screens.

Risk:

- Medium. Needs careful QA to ensure legal source detail remains easy to find.

### Phase 4 - Legacy Surface Decision

Goal:

- Avoid maintaining two verbose app experiences.

Work:

- Confirm whether `apps/web` is live.
- If not live, remove from product path or mark internal.
- If live, apply the same reduction rules.

Expected result:

- Major reduction in product confusion.

Risk:

- Low if not live. Medium if still used.

## Authorization Recommendation

I recommend approving Phase 1 first. It gives the largest immediate improvement with the least risk. The single most important rule to authorize is:

> Remove every local page intro when the shared product header already names the screen and shows the action.

That one decision will make Geode feel materially more focused before deeper layout work begins.
