# Geode Commons UI And Community Implementation Plan

## High-Level Summary

Geode Commons should be the public, collaborative interface on top of Project
Geode. The product goal is simple: people should be able to gather around the
actual legal objects in the database - statutes, regulations, bills, rulemaking
notices, agencies, executive orders, session laws, AG opinions, and review
documents - and build shared understanding without weakening the integrity of
the underlying legal corpus.

The recommended product shape is:

> A legal research interface plus a civic discussion layer, where every
> community contribution is anchored to a source-backed Geode entity or an exact
> passage of legal text.

The experience should feel familiar to people who understand Reddit, Stack
Overflow, annotation tools, and civic deliberation platforms, but the incentives
must be different. The system should not reward outrage, hot takes, or
free-floating argument. It should reward source-backed explanations, useful
questions, lived experience, precise corrections, and cross-corpus discoveries.

The first version should not try to be a full legal advice app. It should be a
structured public workspace for:

- Asking what a law or regulation says.
- Explaining legal text in plain English.
- Connecting statutes, regulations, bills, agencies, and timelines.
- Capturing real-world compliance burden and ambiguity.
- Flagging data quality issues in the Geode corpus.
- Proposing reforms or duplication reviews.
- Letting experts, agency staff, business owners, researchers, advocates, and
  citizens work from the same source material.

The most important implementation decision is that community content must live
outside the canonical corpus. The existing Geode files remain the source of
truth. The Commons layer stores discussions, annotations, votes, trust signals,
moderation records, and correction proposals in a separate application database.
Only reviewed, schema-valid, source-faithful corrections may flow back into the
canonical corpus through the existing writer, validation, snapshot, crosswalk,
timeline, and update-log machinery.

## Product Principles

1. Source first
   Every discussion starts from a Geode entity, citation, source URL, passage,
   crosswalk, timeline event, agency, or docket. Free-form posts are allowed
   only when they are clearly marked as general discussion.

2. Separate law from commentary
   Official source text, Geode extracted metadata, AI summaries, community
   answers, annotations, and personal experiences must be visually and
   structurally distinct.

3. Build trust through contribution type
   A user should not have one generic karma number. Trust should be earned in
   dimensions: citation accuracy, helpful explanations, data review, moderation
   judgment, and constructive participation.

4. Prefer structured participation over generic posting
   The user should choose a post type: question, explanation, impact story,
   data issue, overlap report, reform idea, agency note, or case example. This
   gives the database useful structure and helps moderation.

5. Anchor comments to text when precision matters
   Users should be able to highlight a sentence, paragraph, section, or
   regulation part and start a discussion or annotation on that exact text.

6. Do not turn popularity into authority
   Upvotes should not make a legal claim true. The interface should distinguish
   "helpful," "well sourced," "needs citation," "lived experience," and
   "potentially misleading."

7. Make AI useful but bounded
   AI may summarize, route, cite, detect duplicates, suggest related entities,
   and prepare review drafts. It must not present generated interpretations as
   legal authority, and it must preserve the Geode extraction principles.

8. Community corrections go through review
   User-submitted data fixes should become correction proposals, not direct
   corpus edits. Promotion into the corpus requires validation, review, and an
   auditable update path.

## Existing Codebase Fit

Project Geode is currently an ingestion, normalization, validation, and storage
backend. It has no web stack yet. That is an advantage: the Commons layer can be
added cleanly without rewiring the current pipeline.

Important existing boundaries:

- `geode/schemas/models.py` defines strict Pydantic models for canonical corpus
  records, crosswalks, timeline events, layer indexes, update logs, quarantine
  records, and validation results.
- `geode/utils/file_io.py` already provides streaming JSONL helpers, atomic
  writes, snapshotting, and raw-archive write protection.
- `geode/pipeline/writer.py` writes validated records through the canonical
  contract: content, metadata, index, crosswalks, timeline, manifest, and update
  log.
- `_CONTROL_PLANE/MASTER_MANIFEST.json` is the corpus entry point for AI and
  future API indexing.
- `_CROSSWALKS/` is already the relationship engine for statute-to-regulation,
  bill-to-statute, agency-to-statute, rulemaking-to-regulation, and amendment
  history.
- `geode/extractors/citation_extractor.py` can be reused to detect CRS, CCR,
  CFR, and USC references in user posts and annotations.
- `geode/validation/checks.py` and `geode/validation/integrity.py` already
  embody the "validate before write" posture.

The web interface should therefore be implemented as an additive layer:

```text
Canonical Geode Corpus
  - Markdown
  - JSONL metadata
  - control plane
  - crosswalks
  - timeline
  - raw archive

Derived Read Index
  - searchable entity records
  - text chunks
  - citation aliases
  - relationship graph
  - source hashes

Commons Application Layer
  - users
  - communities
  - follows
  - threads
  - posts
  - comments
  - annotations
  - reactions
  - trust events
  - moderation
  - correction proposals

Web UI
  - browse/search law
  - entity pages
  - discussion feeds
  - passage annotations
  - review queues
  - dashboards
```

## Recommended Architecture

### 1. Keep The File Corpus As Source Of Truth

The current file architecture should remain authoritative. The website should
not mutate `01_Statutes_CRS/`, `02_Regulations_CCR/`, `_CROSSWALKS/`,
`_CONTROL_PLANE/`, or `_RAW_ARCHIVE/` during normal user activity.

The website should read from a derived index that is rebuilt from the corpus.
This avoids slow request-time parsing of Markdown and JSONL, and it prevents
application bugs from corrupting canonical data.

Recommended derived index database:

- Local development: SQLite is acceptable for quick prototypes.
- Production: PostgreSQL.
- Optional retrieval: PostgreSQL full-text search first; pgvector can be added
  later for semantic retrieval.
- Optional external search: Typesense, Meilisearch, or OpenSearch can be added
  if legal search needs more specialized ranking.

### 2. Add A Corpus Indexer

Add a new command that reads the Geode file corpus and populates the web read
model:

```powershell
python -m geode.web.index --rebuild
python -m geode.web.index --incremental
```

The indexer should read in the same AI retrieval order:

1. `_CONTROL_PLANE/MASTER_MANIFEST.json`
2. layer `_index.jsonl` files
3. specific Markdown or JSONL content
4. `_meta/*.jsonl` sidecars
5. `_CROSSWALKS/*.jsonl`
6. `_CONTROL_PLANE/MASTER_TIMELINE_INDEX.jsonl`

Indexer output should include:

- `corpus_entities`
- `entity_aliases`
- `entity_text_chunks`
- `entity_relations`
- `timeline_events`
- `source_versions`
- `index_runs`

Each indexed entity should retain:

- Geode entity ID.
- Entity type.
- Layer.
- Citation.
- Title.
- Source URL.
- Source path.
- Markdown or JSONL path.
- Metadata path.
- SHA-256 hash.
- Confidence.
- Subject tags.
- Industry tags.
- Agency code where available.
- Publication year or effective date where available.
- Indexed-at timestamp.

The indexer must be idempotent. Rebuilding from the same corpus should produce
the same logical records.

### 3. Add A Commons Domain Package

Recommended Python package layout:

```text
geode/
  commons/
    __init__.py
    models.py
    permissions.py
    reactions.py
    reputation.py
    moderation.py
    annotations.py
    correction_workflow.py
    citation_linker.py
    services.py
    repositories.py
  web/
    __init__.py
    app.py
    config.py
    db.py
    index.py
    auth.py
    routes/
      entities.py
      search.py
      communities.py
      threads.py
      annotations.py
      corrections.py
      moderation.py
      users.py
```

Recommended frontend layout:

```text
apps/
  web/
    package.json
    next.config.ts
    src/
      app/
      components/
      features/
        entity/
        search/
        commons/
        annotations/
        moderation/
        review/
      lib/
      styles/
```

This keeps the current Python package focused on corpus logic while allowing a
modern frontend to grow independently.

### 4. Use FastAPI For The Application API

The Python side already uses Pydantic. FastAPI fits that model well and keeps
schema validation consistent.

Suggested new dependencies:

```toml
fastapi
uvicorn
sqlalchemy
alembic
psycopg[binary]
pydantic-settings
python-jose or authlib
passlib or external auth provider
```

For local development, use SQLite with SQLAlchemy. For production, use
PostgreSQL and migrations via Alembic.

### 5. Use Next.js For The Web UI

The frontend should be a real app, not a landing page. The first screen should
be a usable dashboard with search, live topics, followed entities, active
dockets, unresolved data issues, and recent legal changes.

Recommended stack:

- Next.js with TypeScript.
- Server-rendered entity pages for shareable legal objects.
- Client-side panels for discussion, annotation, and voting.
- Accessible, restrained UI components.
- No marketing-style hero as the primary product screen.

## Core Data Model

### Corpus Read Model

These records are derived from the file corpus. They can be deleted and rebuilt.

#### `corpus_entities`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | App database primary key |
| `geode_id` | text unique | `CRS-25-7-109`, `5_CCR_1001-9`, etc. |
| `entity_type` | text | Matches Geode entity type |
| `layer` | text | One of the seven canonical layers |
| `citation` | text nullable | Human citation |
| `title` | text | Display title |
| `summary` | text nullable | Extracted summary if available |
| `source_url` | text | Official or authorized source |
| `source_path` | text nullable | Raw source path if present |
| `content_path` | text | Canonical Markdown or JSONL path |
| `meta_path` | text nullable | Metadata sidecar path |
| `sha256` | text | Hash of indexed source content |
| `confidence` | numeric | Geode confidence |
| `subject_tags` | text array | From ontology |
| `industry_tags` | text array | From ontology |
| `agency_code` | text nullable | Agency anchor |
| `effective_date` | date nullable | Where known |
| `publication_year` | integer nullable | Where known |
| `status` | text nullable | Active, repealed, signed, etc. |
| `indexed_at` | timestamptz | Current index timestamp |

#### `entity_aliases`

Aliases power citation search and URL resolution.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `entity_geode_id` | text FK | Target entity |
| `alias` | text | `25-7-109`, `C.R.S. 25-7-109`, etc. |
| `alias_type` | text | citation, slug, source-id, legacy-id |
| `normalized_alias` | text | Lowercase, punctuation-normalized |

#### `entity_text_chunks`

Chunks power search, passage anchors, and AI retrieval.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `entity_geode_id` | text FK | Parent entity |
| `chunk_index` | integer | Stable ordering within entity |
| `heading_path` | text array | Title, article, part, section |
| `text` | text | Exact source-derived text |
| `start_char` | integer nullable | Offset in normalized text |
| `end_char` | integer nullable | Offset in normalized text |
| `sha256` | text | Chunk hash |
| `citation_scope` | text nullable | Section or part citation |
| `embedding` | vector nullable | Optional later |

#### `entity_relations`

Derived from `_CROSSWALKS/` and explicit reference fields.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `source_geode_id` | text | Source entity |
| `source_type` | text | Source entity type |
| `target_geode_id` | text | Target entity |
| `target_type` | text | Target entity type |
| `relationship` | text | Controlled relationship |
| `confidence` | numeric | Relationship confidence |
| `source_evidence` | text nullable | Evidence from crosswalk |
| `crosswalk_file` | text nullable | Origin file |

### Commons Write Model

These records are user or system generated. They are not canonical legal
authority.

#### `users`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `display_name` | text | Public display |
| `handle` | text unique | Stable username |
| `email_hash` | text | Avoid exposing email |
| `created_at` | timestamptz | Audit |
| `status` | text | active, limited, suspended, deleted |
| `home_region` | text nullable | Optional |
| `bio` | text nullable | Public |

#### `user_credentials`

Credentials are public or private trust markers.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `user_id` | UUID FK | User |
| `credential_type` | text | attorney, agency_staff, researcher, business_owner, legislator_staff, data_reviewer |
| `display_label` | text | Public label |
| `verification_status` | text | self_claimed, verified, rejected, expired |
| `verified_by` | UUID nullable | Reviewer |
| `verified_at` | timestamptz nullable | Audit |
| `expires_at` | timestamptz nullable | For official roles |

#### `communities`

Communities are topic spaces, similar to subreddits, but tied to the ontology.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `slug` | text unique | `air-quality`, `child-care`, `manufacturing` |
| `name` | text | Display name |
| `description` | text | Scope |
| `community_type` | text | subject, industry, agency, docket, custom |
| `ontology_tag` | text nullable | Links to `ONTOLOGY.json` tag |
| `agency_code` | text nullable | Agency community |
| `created_by` | UUID nullable | Null for generated communities |
| `created_at` | timestamptz | Audit |
| `posting_policy` | jsonb | Required post types, citation rules |

#### `entity_follows`

Users can follow entities, agencies, communities, tags, or dockets.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `user_id` | UUID FK | User |
| `target_type` | text | entity, community, agency, tag, docket |
| `target_id` | text | Geode ID or app ID |
| `created_at` | timestamptz | Audit |
| `notification_level` | text | none, digest, all |

#### `threads`

Threads are the primary discussion object.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `title` | text | User title |
| `thread_type` | text | question, explanation, impact_story, data_issue, overlap_report, reform_idea, agency_note, case_example |
| `body` | text | Markdown or rich text |
| `author_id` | UUID FK | User |
| `primary_entity_id` | text nullable | Geode entity ID |
| `community_id` | UUID nullable | Community |
| `status` | text | open, answered, archived, locked, removed |
| `created_at` | timestamptz | Audit |
| `updated_at` | timestamptz | Audit |
| `resolved_at` | timestamptz nullable | For questions/data issues |
| `accepted_post_id` | UUID nullable | For Q&A |
| `ai_summary` | text nullable | Clearly labeled generated summary |
| `quality_score` | numeric | Derived ranking |

#### `thread_entity_links`

Threads may be linked to many legal objects.

| Field | Type | Notes |
| --- | --- | --- |
| `thread_id` | UUID FK | Thread |
| `entity_geode_id` | text | Geode entity |
| `link_type` | text | primary, cited, related, user_added, ai_suggested |
| `confidence` | numeric | For AI-extracted links |
| `created_at` | timestamptz | Audit |

#### `posts`

Posts include thread bodies, answers, comments, moderator notes, and agency
responses. A `parent_post_id` creates nesting when needed.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `thread_id` | UUID FK | Thread |
| `author_id` | UUID FK | User |
| `parent_post_id` | UUID nullable | Reply nesting |
| `post_kind` | text | thread_body, answer, comment, moderator_note, agency_response |
| `body` | text | Markdown or rich text |
| `status` | text | visible, edited, removed, deleted, locked |
| `created_at` | timestamptz | Audit |
| `updated_at` | timestamptz | Audit |
| `source_required` | boolean | True for legal claims |
| `contains_ai_assist` | boolean | Transparency |

#### `post_claims`

Claims let the system distinguish legal claims from general discussion.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `post_id` | UUID FK | Post |
| `claim_text` | text | Extracted sentence or user-marked claim |
| `claim_type` | text | legal_claim, lived_experience, policy_opinion, data_claim |
| `support_status` | text | supported, unsupported, contradicted, needs_review |
| `created_by` | text | user, ai, moderator |

#### `source_citations`

Every source-backed claim can cite entities, passages, or URLs.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `post_id` | UUID FK | Post |
| `claim_id` | UUID nullable | Optional claim link |
| `entity_geode_id` | text nullable | Geode entity |
| `citation_text` | text | As written |
| `source_url` | text nullable | External source |
| `text_anchor_id` | UUID nullable | Passage anchor |
| `confidence` | numeric | Extracted or manual confidence |
| `created_by` | text | user, ai, moderator |

#### `text_anchors`

Text anchors attach posts and annotations to exact source passages.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `entity_geode_id` | text | Geode entity |
| `entity_sha256` | text | Version hash at time of anchor |
| `chunk_id` | UUID nullable | Indexed chunk |
| `selector_type` | text | quote, position, heading, section |
| `exact_text` | text | Selected text |
| `prefix_text` | text nullable | Re-anchoring aid |
| `suffix_text` | text nullable | Re-anchoring aid |
| `start_char` | integer nullable | Position selector |
| `end_char` | integer nullable | Position selector |
| `created_at` | timestamptz | Audit |
| `anchor_status` | text | active, stale, orphaned, reanchored |

Anchoring should use both text quote and position selectors. If a statute or
regulation is reindexed and offsets change, the system can re-anchor by exact
quote plus prefix and suffix. If that fails, the annotation becomes stale or
orphaned and appears in a review queue.

#### `annotations`

Annotations are passage-level discussions.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `anchor_id` | UUID FK | Text anchor |
| `author_id` | UUID FK | User |
| `annotation_type` | text | question, note, exception, definition, ambiguity, data_issue |
| `body` | text | Annotation text |
| `visibility` | text | public, private_group, moderator_only |
| `thread_id` | UUID nullable | Optional promoted discussion |
| `status` | text | visible, resolved, removed |
| `created_at` | timestamptz | Audit |

#### `reactions`

Reactions replace generic upvotes.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `user_id` | UUID FK | User |
| `target_type` | text | thread, post, annotation, correction |
| `target_id` | UUID | Target |
| `reaction_type` | text | helpful, well_sourced, needs_citation, lived_experience, misleading, duplicate, off_topic |
| `weight` | integer | Usually 1; higher only for trusted review actions |
| `created_at` | timestamptz | Audit |

#### `trust_events`

Trust is event-sourced so score formulas can change.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `user_id` | UUID FK | User earning or losing trust |
| `event_type` | text | accepted_answer, source_verified, correction_accepted, misleading_removed, moderation_reversal |
| `dimension` | text | citation_accuracy, explanation_helpfulness, data_review, conduct, moderation |
| `points` | integer | Positive or negative |
| `source_target_type` | text | post, annotation, correction, moderation_case |
| `source_target_id` | UUID | Origin |
| `created_at` | timestamptz | Audit |

#### `moderation_reports`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `reporter_id` | UUID nullable | Null for automated reports |
| `target_type` | text | thread, post, annotation, user |
| `target_id` | UUID | Target |
| `reason` | text | misinformation, harassment, spam, legal_advice, off_topic, privacy |
| `details` | text nullable | Reporter text |
| `status` | text | open, reviewing, resolved, dismissed |
| `created_at` | timestamptz | Audit |
| `resolved_by` | UUID nullable | Moderator |
| `resolved_at` | timestamptz nullable | Audit |

#### `correction_proposals`

This is the bridge from community to corpus.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `proposal_type` | text | metadata_fix, citation_fix, crosswalk_fix, summary_fix, tag_fix, source_url_fix |
| `target_entity_id` | text | Geode entity |
| `target_layer` | text | Canonical layer |
| `field_path` | text nullable | JSON path or content scope |
| `current_value` | jsonb nullable | Existing data |
| `proposed_value` | jsonb | Proposed data |
| `source_evidence` | text | Must cite source passage or URL |
| `submitted_by` | UUID FK | User |
| `status` | text | open, needs_evidence, accepted, rejected, applied |
| `review_notes` | text nullable | Reviewer note |
| `created_at` | timestamptz | Audit |
| `reviewed_by` | UUID nullable | Reviewer |
| `reviewed_at` | timestamptz nullable | Audit |
| `applied_update_log_id` | text nullable | Link to `UPDATE_LOG.jsonl` event |

No correction proposal should directly write to corpus files. Accepted
proposals should generate a controlled patch, run Pydantic validation, update
snapshots and logs through existing code paths, and then trigger reindexing.

## User Experience

### Main Navigation

Primary app areas:

- Search
- Communities
- Dockets
- Agencies
- Timeline
- Questions
- Data Issues
- Review
- Profile

The homepage should be the working dashboard:

- Global search input.
- Recent legal changes.
- Active rulemaking notices.
- Open questions with high activity.
- Data issues needing review.
- Trending topics by subject and industry.
- Followed agencies, communities, and citations.
- Recently accepted corrections.

### Entity Page

The entity page is the core screen.

Recommended layout:

```text
Top bar:
  Citation, title, entity type, status, confidence, follow button

Left rail:
  In-document outline
  Related entities
  Agency
  Timeline

Center:
  Plain-English summary
  Official source-backed text
  Source metadata
  Crosswalks
  Timeline events

Right rail:
  Discussions
  Passage annotations
  Ask question
  Report data issue
  Related community posts
```

Tabs:

- Text
- Summary
- Crosswalks
- Timeline
- Discussions
- Annotations
- Data

The "Text" view must preserve hierarchy:

- CRS: Title, Article, Part, Section.
- CCR: Department, agency, rule, part, section.
- Bills: session, bill, sections, affected CRS.
- Rulemaking: notice type, hearing, affected CCR rule.

### Discussion Creation Flow

When a user starts a post, the app should ask:

1. What are you trying to do?
   - Ask a question.
   - Explain this.
   - Share real-world impact.
   - Flag a data problem.
   - Report overlap or duplication.
   - Suggest reform.
   - Add agency note.
   - Add case example.

2. What legal object is this about?
   - Pre-filled if started from an entity page or selection.
   - Citation extractor suggests additional entities.

3. Does this include a legal claim?
   - If yes, source citation is required or the post is marked "needs citation."

4. Which community should see it?
   - Auto-suggest from subject tags, industry tags, agency, and entity type.

This structure should happen before posting, not after moderation.

### Communities

Communities should be partly generated from Geode's ontology and partly user
created.

Generated communities:

- `air-quality`
- `child-care`
- `occupational-licensing`
- `manufacturing`
- `energy`
- `housing`
- `water`
- `public-health`
- agency-specific communities like `cdphe-aqcc`

Community pages should show:

- Description and scope.
- Relevant Geode entities.
- Active questions.
- Recent annotations.
- Rulemaking deadlines.
- Top accepted explanations.
- Data issues.
- Related agencies.

Communities should have local rules, post flair, and moderators, but they
should not own the canonical law. They organize discussion around it.

### Annotation Experience

Users should be able to:

- Highlight a passage.
- Add an annotation.
- Choose annotation type.
- Link the annotation to a thread.
- Mark an annotation as public, private group, or moderator only.
- Resolve an annotation when answered.

Annotation types:

- Question
- Explanation
- Exception
- Definition
- Ambiguity
- Data issue
- Cross-reference
- Enforcement note
- Compliance burden

### Q&A Experience

Questions should have an accepted answer model, but accepted does not mean
legally authoritative. It means the asker or reviewer found the answer useful.

Answers should display:

- Author role and verification status.
- Cited legal objects.
- Cited passages.
- Community trust reactions.
- "Not legal advice" boundary.
- AI-generated summary only when clearly labeled.

### Data Issue Experience

Data issues are special. They should open a correction workflow.

Examples:

- Missing enabling statute.
- Broken source URL.
- Wrong effective date.
- Bad agency mapping.
- Incorrect crosswalk.
- Incomplete summary.
- Extraction omitted exception.
- Duplicate entity.

Data issues should show:

- Affected Geode ID.
- Current field or passage.
- Proposed correction.
- Source evidence.
- Review status.
- Linked correction proposal.
- Applied update-log event if accepted.

## API Design

### Search And Entity APIs

```http
GET /api/search?q=air+permit&type=law
GET /api/search?q=small+business&type=discussions
GET /api/entities/{geode_id}
GET /api/entities/{geode_id}/text
GET /api/entities/{geode_id}/relations
GET /api/entities/{geode_id}/timeline
GET /api/entities/{geode_id}/threads
GET /api/entities/{geode_id}/annotations
GET /api/entities/{geode_id}/data-issues
```

### Community APIs

```http
GET /api/communities
GET /api/communities/{slug}
GET /api/communities/{slug}/threads
POST /api/communities/{slug}/threads
POST /api/follows
DELETE /api/follows/{id}
```

### Thread And Post APIs

```http
GET /api/threads/{thread_id}
POST /api/threads
POST /api/threads/{thread_id}/posts
PATCH /api/posts/{post_id}
POST /api/reactions
DELETE /api/reactions/{reaction_id}
POST /api/posts/{post_id}/citations
```

### Annotation APIs

```http
POST /api/text-anchors
POST /api/annotations
GET /api/annotations/{annotation_id}
PATCH /api/annotations/{annotation_id}
POST /api/annotations/{annotation_id}/promote-to-thread
```

### Correction APIs

```http
POST /api/correction-proposals
GET /api/correction-proposals
GET /api/correction-proposals/{proposal_id}
POST /api/correction-proposals/{proposal_id}/review
POST /api/correction-proposals/{proposal_id}/apply
```

### Moderation APIs

```http
POST /api/reports
GET /api/moderation/queue
POST /api/moderation/actions
GET /api/moderation/audit-log
```

## AI Integration

AI should be implemented as a service layer, not embedded directly in route
handlers.

Recommended modules:

```text
geode/commons/ai/
  summarizer.py
  citation_suggester.py
  duplicate_detector.py
  moderation_assistant.py
  correction_drafter.py
  retrieval.py
  prompts.py
```

AI functions:

1. Entity-aware search answer
   Given a user query, retrieve relevant entities, crosswalks, timeline events,
   and discussions. Return cited passages and uncertainty.

2. Thread summarization
   Summarize long threads into neutral bullets, preserving disagreement and
   source citations.

3. Citation extraction
   Reuse deterministic regex first. Use LLM only to suggest missed references
   for review.

4. Duplicate detection
   When a user drafts a question, suggest existing threads and annotations.

5. Claim support check
   Detect legal claims lacking citations. Mark them as `needs_citation`.

6. Correction proposal drafting
   Convert a data issue into a structured proposal, but do not apply it.

7. Moderation assistance
   Flag likely spam, harassment, legal advice risk, misinformation, or privacy
   issues. Human moderators make final decisions.

AI prompts must include the Geode extraction principles:

- Source fidelity.
- Completeness over brevity.
- Exception preservation.
- Citation completeness.
- No interpretation.
- Atomicity.
- Temporal precision.
- Entity clarity.

AI outputs should store:

- Model name.
- Prompt version.
- Retrieval context IDs.
- Source citations used.
- Confidence.
- Human review status where relevant.

## Trust And Reputation

Do not implement one global karma score. Use dimensions:

- `citation_accuracy`
- `explanation_helpfulness`
- `data_review`
- `civic_conduct`
- `moderation_judgment`

Example privileges:

| Requirement | Privilege |
| --- | --- |
| Account created | Post questions and comments |
| Email verified | Follow entities and communities |
| 10 helpful points | Add public annotations |
| 25 citation accuracy | Mark posts as well sourced |
| 50 data review | Review low-risk data issues |
| 100 data review plus approval | Approve correction proposals |
| Verified agency staff | Add agency notes |
| Moderator appointment | Remove posts and lock threads |

Ranking should use trust and source quality more than raw engagement.

Possible thread ranking:

```text
quality_score =
  helpful_reactions * 1.0
  + well_sourced_reactions * 2.0
  + accepted_answer_bonus
  + verified_expert_bonus
  + data_issue_resolution_bonus
  - needs_citation_penalty
  - misleading_penalty
  - unresolved_report_penalty
```

Trending should be split:

- Popular discussions.
- Important unresolved data issues.
- Active rulemaking deadlines.
- Recently changed legal objects.
- High-consensus reform ideas.

This prevents the interface from becoming purely engagement driven.

## Moderation Model

Moderation should combine platform rules, community rules, and legal-domain
rules.

Global rules:

- No harassment.
- No spam.
- No impersonation.
- No doxxing or private personal information.
- No unsupported legal claims presented as authority.
- No paid legal solicitation unless explicitly allowed by policy.
- No alteration or misquotation of legal text.

Community rules:

- Topic scope.
- Required post types.
- Citation requirement level.
- Moderator team.

Legal-domain safety rules:

- The interface may explain source text but should not create attorney-client
  relationships.
- Agency staff notes should be labeled and should not be presented as binding
  unless the agency source says so.
- AI outputs must be labeled.
- Community summaries must not replace official text.

Moderation queues:

- New user posts with legal claims and no citation.
- High-impact posts marked misleading.
- Data corrections requiring review.
- Orphaned annotations after corpus updates.
- Agency identity verification.
- Repeated reaction abuse.

## Correction Workflow

This workflow protects the Geode Laws.

1. User flags a data issue
   The issue is anchored to an entity, field, passage, crosswalk, or timeline
   event.

2. System extracts and validates references
   Use `geode.extractors.citation_extractor` and known entity IDs.

3. User supplies source evidence
   Evidence must be a source passage, official URL, or authorized provider URL.

4. A `correction_proposal` is created
   It contains current value, proposed value, target field, source evidence,
   and proposer.

5. Review queue evaluates proposal
   Reviewers can request evidence, reject, accept, or mark as duplicate.

6. Accepted proposal generates a controlled patch
   The patch should target canonical metadata, crosswalk, timeline, or summary
   records. It should never touch `_RAW_ARCHIVE/`.

7. Existing validation runs
   Use Pydantic validation, layer validation, and integrity checks.

8. Existing writer/snapshot/update-log semantics apply
   The update should create snapshots where needed and append an update-log
   event.

9. Reindex the affected entity
   The app updates read models and marks the proposal `applied`.

10. Notify participants
    The data issue thread shows the applied update-log event.

## Search And Retrieval

Search should have two clear modes:

1. Law search
   Searches official source-backed Geode records.

2. Community search
   Searches discussions, annotations, and accepted explanations.

A combined result page can show both, but the sections must be visually
separate.

Law search ranking should combine:

- Citation exact match.
- Entity title match.
- Source text match.
- Tag match.
- Agency match.
- Crosswalk relevance.
- Effective date/status.
- Confidence.

Community search ranking should combine:

- Entity match.
- Thread type.
- Accepted answer.
- Well-sourced reactions.
- Author trust dimension.
- Recency.
- Report status.

The search result should expose why something matched:

- Citation matched.
- Text matched.
- Related by crosswalk.
- Agency matched.
- Tagged by industry.
- Discussed in followed community.

## Frontend Design Direction

The visual design should feel like a serious civic tool:

- Dense but not cramped.
- Fast to scan.
- Minimal ornament.
- Clear source hierarchy.
- Strong typography for legal text.
- Visible confidence and status indicators.
- Good keyboard navigation.
- High contrast.
- Mobile usable, especially for reading and replying.

Avoid:

- Marketing hero as first screen.
- Decorative gradients as the core identity.
- Cards nested inside cards.
- Generic social feed without legal anchors.
- Treating AI output as primary law.

Primary components:

- Entity header.
- Citation badge.
- Source status bar.
- Confidence indicator.
- Crosswalk graph strip.
- Timeline rail.
- Discussion composer.
- Post type selector.
- Citation picker.
- Text selection annotation popover.
- Reaction bar.
- Moderator review row.
- Correction proposal diff.

## URL Design

Stable URLs matter because legal discussion needs citation-like durability.

Recommended routes:

```text
/                                  Dashboard
/search                            Search law and discussions
/law/{geode_id}                    Entity page
/law/{geode_id}/text               Text-focused view
/law/{geode_id}/timeline           Timeline view
/law/{geode_id}/discussions        Threads for entity
/law/{geode_id}/annotations        Passage annotations
/c/{community_slug}                Community
/q/{thread_id}/{slug}              Thread or question
/a/{annotation_id}                 Annotation permalink
/dockets                           Rulemaking dashboard
/agencies/{agency_code}            Agency page
/issues                            Data issues
/review                            Reviewer workspace
/mod                               Moderator workspace
```

## Implementation Phases

### Phase 0: Product Specification And Architecture

Deliverables:

- This document.
- Route map.
- Initial wireframes.
- Data model approval.
- Decision on FastAPI plus Next.js or alternative stack.
- Decision on local SQLite vs immediate PostgreSQL.

### Phase 1: Corpus Read API

Goal: Serve the existing corpus without social features.

Build:

- `geode.web.index` command.
- SQLAlchemy models for corpus read model.
- FastAPI app skeleton.
- Entity resolver.
- Search endpoint.
- Entity endpoint.
- Crosswalk endpoint.
- Timeline endpoint.

Tests:

- Indexer idempotency.
- Entity lookup by Geode ID and citation alias.
- Crosswalk loading.
- Timeline loading.
- API contract tests.

### Phase 2: Read-Only Web UI

Goal: Make Geode browsable.

Build:

- Next.js app shell.
- Dashboard.
- Search page.
- Entity page.
- Crosswalk display.
- Timeline display.
- Agency page.
- Responsive layout.

Tests:

- Playwright desktop and mobile.
- Accessibility checks.
- Entity page renders from fixture corpus.
- Search returns expected sample entities.

### Phase 3: Social MVP

Goal: Let people discuss legal objects.

Build:

- Auth.
- User profiles.
- Communities.
- Follows.
- Threads.
- Posts.
- Post type selector.
- Entity-linked composer.
- Basic reactions.

Tests:

- User can create entity-anchored question.
- Citation extraction links entities.
- Community feed filters by entity/tag.
- Permission tests.

### Phase 4: Passage Annotation

Goal: Let people gather around exact text.

Build:

- Text selection in entity pages.
- `text_anchors`.
- `annotations`.
- Annotation right rail.
- Annotation permalink.
- Re-anchoring job after reindex.

Tests:

- Exact quote anchor creation.
- Offset anchor creation.
- Re-anchor after text chunk offset changes.
- Orphan queue when anchor cannot be resolved.

### Phase 5: Data Issues And Review Queues

Goal: Convert useful community work into safe corpus improvements.

Build:

- Data issue thread type.
- Correction proposal model.
- Reviewer queue.
- Proposal diff view.
- Validation dry-run endpoint.
- Apply workflow guarded by permissions.
- Update-log linking.

Tests:

- Proposal requires source evidence.
- Invalid target field is rejected.
- Accepted proposal cannot bypass validation.
- `_RAW_ARCHIVE/` write attempts remain blocked.
- Applied proposal triggers reindex.

### Phase 6: Trust, Moderation, And Safety

Goal: Make the community resilient.

Build:

- Trust event engine.
- Privilege checks.
- Moderator reports.
- Report queue.
- Post guidance before submission.
- Rate limits.
- Audit log.
- User credential verification.

Tests:

- New users cannot spam links.
- Legal claims without citations are flagged.
- Misleading reports affect visibility until review.
- Moderator actions are audited.
- Reputation cannot be trivially gamed by reaction rings.

### Phase 7: AI-Assisted Commons

Goal: Make the system easier to use without blurring authority.

Build:

- Retrieval service.
- Thread summarizer.
- Citation suggester.
- Duplicate detector.
- Claim support checker.
- Correction drafter.
- AI disclosure UI.

Tests:

- AI answer includes source IDs.
- AI summary preserves dissent and uncertainty.
- Unsupported legal claims are flagged.
- Prompt includes Geode extraction principles.
- AI output is not stored as canonical law.

### Phase 8: Civic Deliberation Mode

Goal: Support large-scale policy discussion.

Build:

- Short statement prompts.
- Agree/disagree/pass voting.
- Opinion clusters.
- Consensus statements.
- Divisive statements.
- Exportable reports for policymakers.

Use cases:

- Which licensing requirements create the most burden?
- Where do regulations duplicate statute?
- Which permitting processes are confusing?
- What reforms have broad support across stakeholder groups?

## Testing Strategy

### Backend

- Pydantic model tests for all Commons records.
- SQL migration tests.
- API contract tests.
- Permission matrix tests.
- Citation extraction tests on user text.
- Correction workflow tests.
- Validation integration tests with existing Geode checks.
- Indexer idempotency tests.

### Frontend

- Component tests for entity header, composer, annotation rail, reactions, and
  correction diff.
- Playwright tests for dashboard, search, entity page, thread creation, and
  annotation creation.
- Mobile viewport tests.
- Accessibility checks for keyboard navigation and screen readers.

### Moderation And Abuse

- Spam posting.
- Unsupported legal claims.
- Fake agency identity.
- Harassment.
- Reaction-ring trust manipulation.
- Citation stuffing.
- AI hallucinated citation.
- Data issue with fabricated evidence.

### Data Integrity

- Community actions do not modify corpus files.
- Correction proposals cannot target `_RAW_ARCHIVE/`.
- Accepted corrections require schema validation.
- Applied corrections create snapshots where existing files are overwritten.
- Reindex updates the app database after corpus changes.

## Operational Model

Recommended services:

```text
web-ui             Next.js app
api                FastAPI app
worker             background jobs for indexing, AI, email, moderation
postgres           application database
redis              optional queue/cache/rate limit store
object-storage     optional attachments and exports
```

Background jobs:

- Corpus reindex.
- Incremental affected-entity reindex.
- Annotation re-anchoring.
- AI summarization.
- Duplicate detection.
- Digest emails.
- Moderation scans.
- Trust recalculation.

Observability:

- Structured logs.
- Request IDs.
- Audit logs for moderation and corrections.
- Index run reports.
- AI prompt/output metadata.
- Validation failure dashboards.

## Security And Privacy

Requirements:

- Passwordless email or OAuth login.
- Verified role workflow for attorneys, agency staff, and reviewers.
- Rate limits on posting, reactions, and reports.
- Private groups for closed review or research cohorts.
- Strict separation of public profile data and private auth data.
- Audit logs for moderation and correction actions.
- Attachment scanning if uploads are allowed.
- Clear terms for public comments and reuse.

Privacy-sensitive design choices:

- Impact stories may involve businesses or individuals. Provide guidance to
  avoid private identifying details.
- Agency staff should be able to participate with verified labels, but the app
  must clarify whether a statement is official, personal, or informational.
- Legal advice boundaries should be visible near Q&A and AI-generated content.

## First MVP Recommendation

The best MVP is not full Reddit. It is:

1. Read-only legal entity browser.
2. Entity-anchored questions and explanations.
3. Basic communities generated from ontology tags.
4. Passage annotations.
5. Data issue workflow.
6. Human review queue for corrections.

This MVP proves the essential loop:

```text
Find legal object
  -> ask or explain
  -> cite exact source text
  -> discuss with community
  -> identify data issue
  -> review correction
  -> improve corpus
  -> reindex and notify
```

## Key Technical Risks

1. Treating discussion as authority
   Mitigation: strict visual separation, labels, trust dimensions, source
   citations, and AI disclosure.

2. User content corrupting corpus data
   Mitigation: separate database, correction proposals, validation gates, and
   existing writer/snapshot/update-log flow.

3. Legal text annotations becoming stale
   Mitigation: text quote plus position anchors, entity hashes, re-anchoring
   jobs, orphan review queue.

4. Search confusion
   Mitigation: separate law search and community search, with combined results
   clearly labeled.

5. Moderation load
   Mitigation: post guidance, structured post types, claim detection, trust
   gates, and review queues.

6. Reputation gaming
   Mitigation: dimensioned trust, audit trails, reaction weighting, anomaly
   detection, and privilege review.

7. Overbuilding before corpus readiness
   Mitigation: start with read-only API and fixture corpus, then add social
   features incrementally.

## Open Decisions

- Use FastAPI plus Next.js, or a single full-stack framework.
- Use PostgreSQL immediately, or SQLite for prototype.
- Whether public posting requires account verification.
- Whether agency staff notes require official agency email verification.
- Whether user content should be public by default.
- Whether annotations can be private groups in MVP.
- Which AI provider and model policy should be allowed in production.
- Whether accepted correction proposals create pull requests, direct writes, or
  maintainer-reviewed patches.
- Whether community exports should be written as JSONL snapshots for AI use.

## Recommended Next Step

Create Phase 1 as a code milestone:

> Build the Geode read API and derived corpus index, without social writes.

That phase gives the web application a stable substrate. Once legal entities,
citations, crosswalks, and timeline events can be served quickly through an API,
the social layer can be added without guessing about the shape of the data.

