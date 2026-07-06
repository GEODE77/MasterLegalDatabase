# Next Download Dashboard

This guide points to the control-plane file that tells the next agent where to resume source download work:

`_CONTROL_PLANE/NEXT_DOWNLOAD_DASHBOARD.json`

## Current Recommendation

The LegiScan live refresh is complete. The next broad source issue remains EO-2019-007, which needs a valid official PDF from the Governor's Office or State Archives.

For LegiScan specifically, use the focused modern repair queue before starting the large legacy archive recovery project:

`_CONTROL_PLANE/MODERN_LEGISCAN_REPAIR_QUEUE.json`

Track repair progress here:

`_CONTROL_PLANE/LEGISCAN_REPAIR_PROGRESS_DASHBOARD.json`

After an official replacement file is verified, repair one queue item with:

```powershell
python -m geode.pipeline.legiscan_repair_intake `
  --root . `
  --queue-id <queue_id> `
  --source-file <verified_official_file> `
  --official-source-url <official_leg_colorado_url> `
  --reviewer-name <reviewer_name> `
  --custody-note <custody_note>
```

The July 2 checkpoint has been committed on `codex/july-2-corpus-checkpoint` and pushed to GitHub. Before treating it as public-facing, complete `docs/PUBLICATION_CHECKLIST.md`, then merge the branch into GitHub `main`.

## Current Blockers

1. EO-2019-007 needs a valid official PDF from the Governor's Office, State Archives, or another approved official transfer.
2. The modern LegiScan repair queue has 41 official-source gaps that need targeted review.

## Operating Rule

Before any broad download, read:

1. `_CONTROL_PLANE/DOWNLOAD_SAFETY_CHECKPOINT.json`
2. `_CONTROL_PLANE/NEXT_DOWNLOAD_DASHBOARD.json`
3. `_CONTROL_PLANE/BLOCKED_DOWNLOAD_QUEUE.json`
4. `_CONTROL_PLANE/FRESHNESS_VERIFICATION_QUEUE.json`
5. `_CONTROL_PLANE/MODERN_LEGISCAN_REPAIR_QUEUE.json`
6. `_CONTROL_PLANE/LEGISCAN_REPAIR_PROGRESS_DASHBOARD.json`
7. `docs/PUBLICATION_CHECKLIST.md`

Then ask the project owner to approve the specific next run.
