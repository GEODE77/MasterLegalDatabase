# Completion Report Language Delta

Generated: 2026-07-01T21:54:36.362516+00:00

This note tightens ambiguous language in `docs/GEODE_COMPLETION_REPORT.md`.

| Term | Use Instead | Owner | Threshold | Next Action |
| --- | --- | --- | --- | --- |
| production ready | system controls present | Project owner | All local control checks pass | Keep external reliance separate from system readiness. |
| complete | locally generated and gate-checked | Project owner | Required artifact exists and current gate passes | State remaining human, legal, or source-refresh work nearby. |
| verified | source-backed or locally validated | Data reviewer | Evidence path, hash, or validation output exists | Avoid using verified for unaudited UI or external-source state. |
| ready for reliance | ready for internal review | Legal reviewer | Named reviewer approval exists | Reserve reliance language for explicit legal reviewer authorization. |
| coverage complete | coverage measured | Corpus maintainer | Inventory and gap queue exist | Keep uncovered items in a closure plan until source-backed. |

## Required Rewrite Rule

Any future completion report should separate three ideas:

1. Built: the code or artifact exists.
2. Validated: a command, hash, or gate checked it.
3. Authorized: a named owner approved its use.

Geode can be built and locally validated without being externally authorized.
