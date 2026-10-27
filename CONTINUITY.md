# Continuity between exo and exo-desktop

Exo is the core. Exo-desktop is a fork that adds a desktop client. This file states how the two stay in step, so drift is caught in hours, not in dozens of commits.

## The one rule, and its current exception

Exo-desktop edits only `clients/desktop`. It never edits `src/`, plugins, docs, or tests for the core. Upstream changes and desktop changes then touch different files, and a sync cannot conflict on content.

Exception, decided 2026-10-27 (issue #51): while the project is early, in stealth, with no external users, shipping speed comes first. The fork may edit core `src/`, plugins, docs, and tests when the desktop requires it. This exception is open-ended for now and covers the macOS alpha stack, audit fixes that touch core code, and core rework such as the gate change. As the project grows and external users start contributing to the repos, this setup will need to be more consolidated, with more structured rules, and the exception will be revisited and the setup adapted to whatever the circumstances require at that point.

## Sync

Sync the fork at the start of every work session. The daily workflow in `.github/workflows/sync-upstream.yml` also merges upstream main into fork main once a day. If that merge conflicts, the workflow opens an issue in this fork. A conflict is a signal to stop and merge by hand, not to force it.

A sync is one way only. It brings upstream into the fork. It does not send desktop work upstream.

## Sending desktop work upstream

Desktop work goes on a fork branch, then a pull request to fork main. When the desktop work is ready, open a cross-repo pull request from fork main to exo main, with the desktop files only. Do not carry the sync workflow into that pull request. The workflow is fork only, and its job condition already stops it running elsewhere.

## Issues

File desktop only issues in this fork. File core issues in exo. When a desktop issue depends on a core change, link the exo issue from the fork issue, and link back. Do not file the same issue in both repos.

While the exception above is in effect, core issues found through fork work may be filed in this fork, since that is where the work is happening. When the setup is consolidated later, those issues move to exo with links back, and the fork copies close.

## When the rule breaks

If the fork starts editing the core, this setup no longer works. That is the signal to stop using a fork and work in exo directly. The desktop client already lives in `clients/desktop`, so the move is a pull request, not a rewrite.
