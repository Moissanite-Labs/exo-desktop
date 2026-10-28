# Desktop repository work routing

Read [CONTINUITY.md](CONTINUITY.md) before opening or changing a PR. It points to Exo's canonical workflow and documents this fork's sync process.

Native desktop shell, packaging and sync tooling belong here. Shared core and web changes are implemented once in `aska-digital/exo`, then consumed through reviewed sync PRs. Preserve existing author work and unique native files during the transition.

The sync helper prepares drafts. It does not merge or install them. An active canary, credentials and permission settings remain outside repository-sync work.
