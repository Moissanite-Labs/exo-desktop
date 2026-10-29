# Draft native and workspace integration, 2026-10-29

This is a reviewable composition of merged desktop work and pending canonical changes. It is not release-ready and does not update the official upstream sync pin or install an application.

## Source ownership and exact inputs

| Input | Exact source | State and reconciliation |
|---|---|---|
| Desktop base | `ace641c32eb8692b26a2839643fc99a8c445c45b` | Current desktop main when this composition began. Its latest common canonical main is `75d72a7f82ff5a533b110ae584b653b14a379ec4`. |
| Canonical main included by the pending branches | `b086d165e2fc2a84783994f6505d810fa58d9dd7` | Already merged in canonical Exo; awaiting a reviewed desktop sync. |
| Local growth and companion | `d911b390e989d1bbb33bc7c3fce3e2094f9ff5a9` | Temporary carry from [canonical PR #826](https://github.com/Moissanite-Labs/exo/pull/826). Shared core, API and web source remain owned there. Replace this carry with its merged canonical history before an official sync. |
| Native web preference consumer | `b275cfaa61cc8cc962d58b35c77a141bb4e99ceb` | Temporary carry from [canonical PR #933](https://github.com/Moissanite-Labs/exo/pull/933). Production source equals `a81f2f0fa127fbcde73d3a739af575d6c04cfced`; the successor fixes a held-request test fixture. Replace with merged canonical history before an official sync. |
| Native preference bridge | `6a836f1e8693f9698c27f521649475ce8d24ba4b` | Desktop-owned successor to [PR #49](https://github.com/Moissanite-Labs/exo-desktop/pull/49); the original author branch is preserved. Native code, installer and fixture acceptance only. |
| Native confirmations | `8c832adb02fca2e28dcde90a35d37d9e63fa90af` | Desktop-owned continuation of [PR #96](https://github.com/Moissanite-Labs/exo-desktop/pull/96), preserving its history. Includes Return/Escape cancellation and refusal when a pending sheet's page changes. |

The existing overlay version checks, sync helper targets and installed-runtime state are unchanged. Before an official sync, refresh canonical main after #826 and #933 merge, compare the resulting shared source with this tested composition, reconcile any delta, and independently review the exact resulting tree. A draft integration PR does not authorize an installation.

## Integration decisions

The shared web implementation is consumed from canonical Exo rather than separately developed in desktop. Native source stays under `clients/desktop`. The local conflict resolutions preserve the existing desktop model-picker generation cleanup, companion detach/state synchronization and native read-position guards together. The canonical minimum-positive session-list validation is retained. Fixture module lists include the companion, native preferences and desktop picker dependencies.

The native preference bridge retains an ephemeral WebKit store and available-port launch. It accepts only allowlisted UI fields from the connected main frame, scopes stored choices to the configured runtime identity and excludes tokens, credentials, drafts and transcript content. An explicit URL view remains intentional; ordinary token-only launch links can restore the native saved view.

## Acceptance and limits

`LOCAL-ACCEPTANCE.md` records the reproducible commands. The native harness compiles the actual production delegate and invokes its HTTP verification and document-start preference injection path. It runs the actual web assets and API against a fixture core, in a real WKWebView with a temporary home, isolated preference suite and nonpersistent browser storage.

It verifies Appearance, route, selected thread, layout, transcript reading fraction and companion Full/Off choices through a same-process page reload and a second process on a different loopback port. The companion's pending egg and banked growth display use synthetic fixture values; these checks do not establish ledger verification. Core cryptographic growth checks remain separate.

Native confirmation acceptance operates real sheet buttons and dispatches Return and Escape only to the disposable sheet. It also checks wrong-origin/subframe/restart refusal and that Continue becomes false after the presenting context changes. VoiceOver acceptance remains unperformed. No live core, provider credentials, model call, installed app or active user settings were used.
