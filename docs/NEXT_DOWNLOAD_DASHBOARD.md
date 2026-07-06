# Next Download Dashboard

This guide points to the control-plane file that tells the next agent where to resume source download work:

`_CONTROL_PLANE/NEXT_DOWNLOAD_DASHBOARD.json`

## Current Recommendation

The next major download should be the LegiScan live refresh for the legislation layer, but only after the project owner authorizes the safety gate.

The safety gate exists because the repository is currently on detached HEAD with many uncommitted generated files from the July 2 refresh. Starting another large refresh before accepting or committing that state would make it harder to tell which files belong to which run.

## Current Blockers

1. LegiScan live refresh needs `LEGISCAN_API_KEY`.
2. EO-2019-007 needs a valid official PDF from the Governor's Office, State Archives, or another approved official transfer.

## Operating Rule

Before any broad download, read:

1. `_CONTROL_PLANE/DOWNLOAD_SAFETY_CHECKPOINT.json`
2. `_CONTROL_PLANE/NEXT_DOWNLOAD_DASHBOARD.json`
3. `_CONTROL_PLANE/BLOCKED_DOWNLOAD_QUEUE.json`
4. `_CONTROL_PLANE/FRESHNESS_VERIFICATION_QUEUE.json`

Then ask the project owner to approve the specific next run.
