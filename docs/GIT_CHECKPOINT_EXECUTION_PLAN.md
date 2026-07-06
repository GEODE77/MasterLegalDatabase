# Git Checkpoint Execution Plan

This file records how the safety checkpoint was turned into a real git checkpoint.

## Current Situation

The paused rebase was completed. The checkpoint work now lives on:

`codex/july-2-corpus-checkpoint`

The branch has been pushed to GitHub.

## Recommended Path

1. Open a pull request from `codex/july-2-corpus-checkpoint` to `main`.
2. Complete `docs/PUBLICATION_CHECKLIST.md`.
3. Review GitHub's large-file warnings.
4. Merge only after the project owner approves publication.
5. Run validation before any new large download.

## Why This Order Matters

The branch now separates the July 2 checkpoint from the next live download. This makes it easier to review and publish the existing corpus state before adding new source changes.

## Suggested Commit Message

`[Phase 1] Checkpoint July 2 corpus refresh and download controls`

## Boundary

Do not merge to public-facing `main` until the publication checklist is complete and the project owner approves the merge.
