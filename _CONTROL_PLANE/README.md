# Project Geode Control Plane

The control plane contains the small, AI-readable files that describe corpus
schema, sources, agencies, freshness, timelines, manifests, and update history.

Current operational handoff files:

- `QUALITY_STATUS.json` is the first-read quality map for the corpus. It shows each layer's
  current status, open review limits, and next quality actions.
- `DOWNLOAD_SAFETY_CHECKPOINT.json` records the safety state before the next major source download.
- `NEXT_DOWNLOAD_DASHBOARD.json` identifies the next recommended download area and current blockers.
- `../docs/PUBLICATION_CHECKLIST.md` must be completed before public-facing GitHub publication.
