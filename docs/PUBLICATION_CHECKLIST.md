# Publication Checklist

Use this checklist before making a Geode branch public-facing by merging it into GitHub `main`, changing repository visibility, or pointing users to the corpus.

## 1. Git State

- [ ] Working tree is clean.
- [ ] Branch is pushed to GitHub.
- [ ] Pull request is opened against `main`.
- [ ] Pull request title follows the Project Geode phase format.
- [ ] The branch includes only work intended for public release.
- [ ] Temporary stashes, rebase folders, and local-only recovery files are gone.

## 2. Source Boundaries

- [ ] No files in `_RAW_ARCHIVE/` were manually edited.
- [ ] Any manually supplied official source went through manual source intake.
- [ ] No unofficial replacement source was used for a blocked official download.
- [ ] All source URLs are official Colorado government sources or approved providers.
- [ ] Any blocked source remains listed in `_CONTROL_PLANE/BLOCKED_DOWNLOAD_QUEUE.json`.

## 3. Secrets And Private Data

- [ ] No API keys, tokens, passwords, cookies, or local credentials are committed.
- [ ] No personal reviewer contact data is committed unless intentionally approved.
- [ ] No local machine paths are exposed where a project-relative path would work.
- [ ] Sample, export, and API-response data does not contain private user information.

## 4. Large Files

- [ ] Files over 50 MB are identified before merge.
- [ ] Files near or over GitHub's hard limit are not committed to normal Git.
- [ ] The project owner has approved whether large generated files stay in Git, move to Git LFS, or move to external storage.
- [ ] Any large-file warning from GitHub is recorded in the pull request notes.

Known large files from the July 2 checkpoint push:

- `03_Legislation/_documents/bill_documents.jsonl`
- `_CONTROL_PLANE/SOURCE_TO_OUTPUT_ACCURACY_RECORDS.jsonl`
- `02_Regulations_CCR/_meta/ccr_rules_meta.jsonl`

## 5. Validation

- [ ] Focused tests for any conflict area pass.
- [ ] Full test suite is run when practical.
- [ ] Control-plane JSON files parse successfully.
- [ ] Layer indexes and manifest files are present.
- [ ] Freshness reports clearly separate local freshness from live official refresh.

Minimum validation before publishing a checkpoint branch:

```bash
pytest tests/test_ccr_scraper.py -q
python -m json.tool _CONTROL_PLANE/NEXT_DOWNLOAD_DASHBOARD.json
python -m json.tool _CONTROL_PLANE/DOWNLOAD_SAFETY_CHECKPOINT.json
```

## 6. Legal And Reliance Boundary

- [ ] Publication notes say Geode is not legal advice.
- [ ] Publication notes say local usability is not external reliance readiness.
- [ ] Human review status is disclosed if review packets remain pending.
- [ ] Named reviewer assignments are complete before any external reliance claim.
- [ ] Any unresolved source-repair items are disclosed.

## 7. Merge Decision

- [ ] Project owner approves merge to `main`.
- [ ] Project owner approves repository visibility before switching private to public.
- [ ] Pull request description includes what changed, key files, how to verify, and known issues.
- [ ] After merge, GitHub `main` is checked to confirm the expected files are visible.

## Publication Boundary

Passing this checklist means the branch is ready for a public GitHub workflow. It does not certify the legal accuracy of the corpus, approve legal advice, or replace human review.
