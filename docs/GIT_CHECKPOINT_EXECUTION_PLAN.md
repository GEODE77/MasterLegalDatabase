# Git Checkpoint Execution Plan

This file explains how to turn the current safety checkpoint into a real git checkpoint.

## Current Situation

Git is not simply on a detached commit. It is paused in an interactive rebase of `main`.

Four older commits have already been replayed. Two remain:

1. `cd55c0a Finish CCR manifest URL canonicalization`
2. `a1c4684 Fix CCR manifest URL final serialization`

Git says the conflict in `tests/test_ccr_scraper.py` has been staged as resolved, so the next step is to continue the rebase.

## Recommended Path

1. Continue the paused rebase.
2. If Git stops again, resolve only the specific conflict it reports.
3. Once the rebase is complete, create a named branch from the resulting state.
4. Stage the July 2 refresh outputs, the source-control changes, and the new safety/dashboard files.
5. Commit that state with a Project Geode phase-style message.
6. Run validation before any new large download.

## Why This Order Matters

Committing the current state before finishing the rebase would mix three things:

1. Old CCR rebase work.
2. The July 2 corpus refresh.
3. The new safety dashboard files.

Finishing the rebase first gives the project a cleaner base before the broad checkpoint commit.

## Suggested Commit Message

`[Phase 1] Checkpoint July 2 corpus refresh and download controls`

## Boundary

Do not abort the rebase, reset the repository, or remove files unless the project owner explicitly approves that recovery path.
