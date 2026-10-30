# Exo desktop continuity

The [2026-10-28 decision](https://github.com/Moissanite-Labs/exo/discussions/746) makes Exo the shared implementation home. [Exo PR #747](https://github.com/Moissanite-Labs/exo/pull/747) landed that policy.

The authority is [canonical Exo's workflow document](https://github.com/Moissanite-Labs/exo/blob/main/docs/REPOSITORY-WORKFLOW.md). This file covers fork operations, not a second feature policy.

Native shell and packaging work belongs under `clients/desktop`. Fork maintenance exceptions are this file, the local `AGENTS.md` pointer, the sync workflow, `scripts/sync_upstream.py` and its tests. Shared runtime and web work has one canonical Exo PR.

Temporary alpha carries must name their canonical owner, PR, exact source version and reconciliation step. Existing paired PRs transition with their authors. Retain review evidence and unique native work. Do not overwrite another author's branch or close their work without coordination and verified downstream integration.

A parent branch, repository main and an installed runtime are different states. Before a packaged build, record the tested native/fork SHA and canonical Exo SHA. Verify the intended merged features by content and behavior, and list any temporary alpha carries. A fork PR merge does not install its code.

Fork-only native work can be proposed upstream from current Exo main with only the reviewed native changes. A PR from fork main carries all fork history and cannot promise desktop files only.

This fork publishes no wheel. A wheel built from this checkout has the same distribution name and version as canonical Exo's (`exo` 0.2.0) and packages only `src/exo` and `clients/tui/exo_tui`, so it is deliberately not distinguishable from one built there. `pyproject.toml` is shared with canonical Exo, so a fork marker would be a shared change made there first. The desktop app is built from `clients/desktop`, not from the wheel.

## Prepare a draft sync

The helper uses a new private Git directory and the reserved `automation/exo-upstream-sync` branch. It makes normal merges, preserves history and creates or reuses an owned draft PR targeting fork main. It never pushes main, force-pushes, executes fetched code or tests, merges a PR, installs an app or restarts a core.

Unexpected branch commits or a non-draft or unmarked PR require maintainer review. Markers are coordination guards, not cryptographic ownership. Conflicts go back to the source owners, without automatic runtime fixes.

GitHub does not lock PR state and main together with a Git push. Either can change between a check and a write. Review the current base, combined tree and verification results before a maintainer merges the draft.

The workflow checks out fixed main, serializes runs and requires `EXO_SYNC_TOKEN`. Scheduled runs are disabled unless `EXO_SYNC_ENABLED` is `true`. Enable that repository variable only after the owner supplies the credential and verifies Actions. Manual dispatch remains available and reports a missing credential clearly.

Until credentials are configured and an Actions run succeeds, use the helper manually with an already authorized host `gh` identity. Python 3, Git and GitHub CLI are required:

```sh
python3 scripts/sync_upstream.py --manual --work-dir ../exo-desktop-sync-review-20261028
```

The work directory must not exist and is left for inspection. The operator's checkout is untouched. Repeated runs use new local directories and reuse the reserved remote branch and draft PR. If canonical main is included or the merged tree has no change, no PR is created.

Authentication, fetch, merge conflict, merge failure, base drift, push and PR failures are distinct. `--report-failures` files stage-specific issues in this fork, deduplicated by a stable marker without daily comment spam. Reporting errors remain failures. Missing credentials may prevent issue reporting too.

## Credential requirements

An owner supplies `EXO_SYNC_TOKEN` through Actions secrets. The workflow creates no credential. It must read `Moissanite-Labs/exo`, read and write desktop contents and workflow files, and write desktop PRs and failure issues. Both repositories are public after the transfer. The write credential is still required.

Use an approved GitHub App token or personal access token with the required repository access, organization authorization and permissions. Permissions can cover all selected repositories: the script's one-way access pattern is not a token sandbox.

[App installation tokens expire after one hour](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app). This workflow does not mint or refresh them.

A stored installation token alone is not a lasting schedule credential. An approved App setup must provide a fresh token per run, or the owner supplies and maintains a suitable personal token.

`GITHUB_TOKEN` is not a substitute for the required workflow-file writes. The workflow uses masked secret inputs and environment variables. It never puts tokens in Git URLs or command-line arguments, or changes host authentication and Git configuration.

GitHub documents [Actions token scope](https://docs.github.com/en/actions/concepts/security/github_token), [reference permissions including workflow updates](https://docs.github.com/en/rest/git/refs), and [PR permissions](https://docs.github.com/en/rest/pulls/pulls).

A suitable App token or personal token avoids relying on the default token's workflow-trigger restrictions. This does not promise Actions availability or passing CI.
