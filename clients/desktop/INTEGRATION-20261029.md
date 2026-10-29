# Desktop integration review, 2026-10-29

This branch combines native confirmations and saved display choices with pending Exo web changes. It is for integration review and is not release-ready. It does not change the official sync pin or install an app.

## Sources

| Input | Exact source | Review and next step |
|---|---|---|
| Desktop base | `ace641c32eb8692b26a2839643fc99a8c445c45b` | Desktop main at the start of this review. Its latest common canonical main is `75d72a7f82ff5a533b110ae584b653b14a379ec4`. |
| Canonical main included by the pending branches | `b086d165e2fc2a84783994f6505d810fa58d9dd7` | Merged in canonical Exo. Awaiting a reviewed desktop sync. |
| Growth and companion | `d911b390e989d1bbb33bc7c3fce3e2094f9ff5a9` | Pending [canonical review](https://github.com/Moissanite-Labs/exo/pull/826). Shared core, API and web source belong there. |
| Native web preference consumer | `1103f530ea8e1acd58caf817addfddccc299a591` | Pending [canonical review](https://github.com/Moissanite-Labs/exo/pull/933). Failed reads preserve saved intent. Exact lookup restores an older thread outside the bounded list. Confirmed 404 clears it. |
| Cached provider-list retry | `d32b6d2f624cd1a562c3ec2919afbc53b4535bb8` | Pending [canonical review](https://github.com/Moissanite-Labs/exo/pull/932). The existing desktop search picker keeps one retry button for a cached transport failure and none for an authority refusal. |
| Native preference bridge | `5838a68ea0b40813b16be37e6aee82268602f747` | [Desktop review](https://github.com/Moissanite-Labs/exo-desktop/pull/98). The [original restoration proposal](https://github.com/Moissanite-Labs/exo-desktop/pull/49) and its author branch remain intact. |
| Native confirmations | `923860a6a8dd1dd0f1ff530b0562c929e84d4350` | [Desktop review](https://github.com/Moissanite-Labs/exo-desktop/pull/96). Preserves the source history and adds Return/Escape cancellation and refusal after the presenting page changes. |

The shared changes above are temporary copies for review. An official sync requires their merged canonical history, a comparison with this tested branch and independent review of the resulting tree. Existing overlay version checks and installed runtimes are unchanged.

## Composition

Shared web source comes from canonical Exo. Native code stays under `clients/desktop`. The merge keeps the desktop model picker, companion cleanup and reading-position guards together. The provider fix changes only the cached-error path and does not save a model default. The new missing-thread handler also resets companion selection. This combination hook requires comparison with canonical source during the official sync.

The browser keeps page data in memory and the server chooses an available local port. Native storage accepts only the listed display fields from the connected main frame. Saved choices belong to the configured runtime identity. Tokens, credentials, drafts and transcript content do not enter that copy.

A changed user home, explicit runtime override or missing bundled launcher disables native restoration. Bare executable names are resolved through PATH during launcher generation and saved as absolute paths. An explicit URL view takes priority over the saved view.

## Acceptance

`LOCAL-ACCEPTANCE.md` records the commands and test results. The native harness compiles the actual app controller and uses its HTTP check and page-start injection. It serves the real web assets and API against a fixture core in WKWebView, with a temporary home and an isolated preference store.

The checks cover Appearance, route, thread, layout, reading position and Full/Off companion mode through reload and relaunch on another local port. An initial session-list error preserves the saved thread and reading position. A later successful reload restores both. The fixture also checks early Off during startup, an older thread outside the listed prefix and a live event during the saved snapshot read.

Companion growth values are synthetic test data. These checks do not establish ledger verification. Native dialog checks operate real sheet buttons and send Return/Escape only to the temporary sheet. VoiceOver acceptance remains unperformed. No live core, credentials, model call or installed app was used.
