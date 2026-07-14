# Project Geode Control Plane

The control plane contains the small, AI-readable files that describe Geode's
backend knowledge layer: corpus schema, sources, agencies, freshness,
timelines, manifests, reliance boundaries, and update history.

The orchestration engine reads these files before retrieving legal text. They
are part of hard orchestration: code uses them to decide what exists, what is
fresh, what is trusted, and what must be disclosed as missing. Prompts may
summarize these rules for an LLM, but the control-plane files and validation
code are authoritative.

Current operational handoff files:

- `QUALITY_STATUS.json` is the first-read quality map for the corpus. It shows each layer's
  current status, open review limits, and next quality actions.
- `DOWNLOAD_SAFETY_CHECKPOINT.json` records the safety state before the next major source download.
- `NEXT_DOWNLOAD_DASHBOARD.json` identifies the next recommended download area and current blockers.
- `../docs/PUBLICATION_CHECKLIST.md` must be completed before public-facing GitHub publication.
