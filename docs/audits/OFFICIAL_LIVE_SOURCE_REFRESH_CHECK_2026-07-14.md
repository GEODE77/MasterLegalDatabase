# Official Live Source Refresh Check

Generated: 2026-07-14T16:06Z

## Summary

The official live source refresh check was run, but it did not close as a full
source refresh. The run updated the built-in source watcher and confirmed live
source signals where the current tooling can safely check them. It did not run
broad downloads, rewrite the legal corpus, or certify external reliance.

Overall result: WARN

Closeout result: FAIL

## Commands Run

- `python -m geode.pipeline.source_update_watcher --root . --live-probes --write --json`
- Direct read-only source checks for CRS, LegiScan, eDocket, Rulemaking Search, and eCFR OSHA.
- `python -m geode.pipeline.download_closeout --root . --json`

## Watcher Results

The built-in watcher wrote:

- `_CONTROL_PLANE/SOURCE_UPDATE_WATCHER_DASHBOARD.json`
- `_CONTROL_PLANE/SOURCE_UPDATE_DOWNLOAD_QUEUE.json`
- `docs/audits/SOURCE_UPDATE_WATCHER_DASHBOARD_2026-07-06.md`

Watcher status: `warn`

Watcher counts:

- Sources watched: 10
- New data items: 0
- Manual review items: 6
- Needs live check items: 3
- No-change items: 1

Observed markers from the watcher:

| Source | Local marker | Live observed marker | Watcher status |
| --- | --- | --- | --- |
| CCR | 2026-07-08 | 2026-06-29 | manual review needed |
| Colorado Register | 2026-07-08 | 2026-07-10 | manual review needed |
| Executive Orders | 2026-07-07 | 2026-06-16 | manual review needed |
| COPRRR | 2026-07-08 | 2025-10-15 | manual review needed |
| AG Opinions | 2026-07-08 | 2026-01-01 | no change detected |

The watcher still routes CRS, CCR, LegiScan, Colorado Register, Executive Orders,
and COPRRR to manual review because the current freshness queue says official
refresh action is still required.

## Direct Source Checks

Additional direct checks were run for sources not fully covered by the watcher.

| Source | Result |
| --- | --- |
| CRS | Reachable. The old CRS URL redirects to the current Colorado General Assembly CRS page. |
| LegiScan | Public page is visible through browser/web access and shows Colorado 2026 regular session data; terminal `curl` received a Cloudflare 403. |
| eDocket | Terminal header check returned 404 on the registered endpoint. This source still needs browser or connector review. |
| Rulemaking Search | Public page is visible through browser/web access; terminal `curl` received CloudFront 403. |
| eCFR OSHA | Terminal header check redirected to an unblock page. This source still needs browser/API-safe review before treating it as refreshed. |

## Closeout Result

The download closeout checklist returned `fail`.

Closeout details:

- Secret scan: pass.
- Pending downloads/freshness: warn, because 7 known future freshness items remain.
- Next-download dashboard: fail, because `_CONTROL_PLANE/NEXT_DOWNLOAD_DASHBOARD.json` is dated 2026-07-07, not 2026-07-14.
- Git pushed/clean: fail, because the working tree has uncommitted changes.

## Boundary

This run completes the live source check pass for the currently available tools.
It does not complete an official source refresh, because several sources still
require manual review, guarded connector runs, or browser-style verification.
It does not change the external reliance status of Geode.

## Recommended Next Actions

1. Update the next-download dashboard for the current date and selected next action.
2. Decide whether to run guarded downloads for Colorado Register and LegiScan.
3. Verify eDocket, Rulemaking Search, and eCFR OSHA using browser-safe workflows.
4. Rerun source quality and closeout after the selected guarded refreshes are complete.
