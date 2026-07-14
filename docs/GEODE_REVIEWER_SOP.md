# Geode Reviewer SOP

## Purpose

This SOP explains how review packets, review decisions, canonical apply, and external reliance should be handled.

## Non-Negotiable Boundaries

- Do not treat review packets as legal advice.
- Do not assign a reviewer without project-owner authorization.
- Do not change canonical rule units outside the guarded apply path.
- Do not externally rely on pending packets.
- Do not remove source citations or reliance boundaries from reviewed outputs.

## Reviewer Roles

### Data Reviewer

- Status: unassigned
- Assigned to: unassigned
- May log decisions: yes
- May apply canonical changes: no
- May approve external reliance: no

Responsibilities:

- Review packet source fidelity.
- Confirm extraction quality issues before logging a decision.
- Escalate unclear legal meaning instead of interpreting it.

Escalation path:

- corpus_maintainer
- legal_reviewer

### Corpus Maintainer

- Status: unassigned
- Assigned to: unassigned
- May log decisions: yes
- May apply canonical changes: yes
- May approve external reliance: no

Responsibilities:

- Apply only validated canonical changes.
- Confirm snapshot and guarded apply behavior before writing canonical files.
- Stop apply work when replacement records fail validation.

Escalation path:

- legal_reviewer

### Legal Reviewer

- Status: unassigned
- Assigned to: unassigned
- May log decisions: yes
- May apply canonical changes: no
- May approve external reliance: yes

Responsibilities:

- Approve or reject production reliance on reviewed outputs.
- Confirm that external guidance preserves citations and reliance boundaries.
- Escalate unresolved ambiguity before external use.

Escalation path:

- project_owner

## Operating Flow

1. Start with the review packet JSONL file to select a pending packet.
2. Confirm the source sentence and quality issue.
3. Use the backend review queue to log approve, revise, split, or quarantine decisions.
4. Rebuild the guarded apply proposal after decisions are logged.
5. Apply canonical changes only when replacements validate and authorization exists.
6. Seek legal reviewer approval before external reliance.

## Current Boundary

Reviewer slots are prepared but no real person is assigned until a project owner authorizes named reviewers.
