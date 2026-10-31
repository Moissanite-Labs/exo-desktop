# Desktop repository work routing

Read [CONTINUITY.md](CONTINUITY.md) before opening or changing a PR. It points to Exo's canonical workflow and documents this fork's sync process.

Native desktop shell, packaging and sync tooling belong here. Shared core, plugins and web UI are implemented once in `Moissanite-Labs/exo`. Do not open a matching desktop implementation PR for shared code. Desktop receives merged upstream changes through reviewed sync PRs. Preserve existing author work and unique native files during the transition.

`Moissanite-Labs/exo-cli` currently contains a fork snapshot. Its extraction is proposed, not complete. Until a reviewed migration changes ownership, shared changes stay in `Moissanite-Labs/exo`. Preserve existing terminal PR ownership and link related work across repositories.

The sync helper prepares drafts. It does not merge or install them. An active canary, credentials and permission settings remain outside repository-sync work.
