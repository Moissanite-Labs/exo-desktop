# Local native and web acceptance

This branch tests desktop integration with pending shared changes. It does not update an official sync pin, release an app or change an installed runtime.

## Inputs

| Source | Commit |
|---|---|
| Desktop main | `ace641c32eb8692b26a2839643fc99a8c445c45b` |
| Native preferences | `5838a68ea0b40813b16be37e6aee82268602f747` |
| Native confirmations | `923860a6a8dd1dd0f1ff530b0562c929e84d4350` |
| Web preferences | `1103f530ea8e1acd58caf817addfddccc299a591` |
| Cached-provider retry | `d32b6d2f624cd1a562c3ec2919afbc53b4535bb8` |
| Shared combination | `9ade86146a973b0ceacf5ad3608918f61915fe69` |
| Certificate lock repair | `568b903fc45984052b888636ef53647c2a10a38f` |
| Companion | `d911b390e989d1bbb33bc7c3fce3e2094f9ff5a9` |

## Reproduce on a Mac graphical session

Use an existing test Python environment with the repository dependencies:

```sh
EXO_BUS_URL=http://127.0.0.1:9 python clients/desktop/macos/Tests/test_native_workspace_acceptance.py
python3 clients/desktop/macos/Tests/test_native_dialog_acceptance.py
python3 clients/desktop/macos/Tests/test_native_preferences_acceptance.py
python3 clients/desktop/macos/Tests/test_native_preference_context.py
```

The harness compiles the actual app controller and uses its HTTP verification and page-start preference injection. It serves the real web assets and API against a fixture core in WKWebView. Homes and preference stores are disposable. No app is installed and no live core, provider or model is used.

## Evidence

The complete exo-command suite passed **495 tests in 153.90 seconds** on `d58166bc47e1eb479fe151203a52b7b575b5e30f`. Consuming the canonical combination history preserved the full production and test subtrees. The one obsolete desktop picker expectation now checks the new cached retry and successful recovery.

Focused checks passed 36 tests. Actual WKWebView checks cover early Off before bootstrap, an initial list error, an older thread outside the list and a live event during the saved snapshot read. They also verify reload and relaunch on another local port. Return and Escape cancel the native dialog. Changed page context refuses Continue.

The native context test uses embedded app metadata. The intended context enables restoration. A changed home, explicit executable override or missing bundled launcher refuses it. A PATH fixture verifies that launcher generation fixes the executable before a later launch from another directory.

The companion's growth values are synthetic. Ledger verification and VoiceOver acceptance remain separate. Successful fixture teardown can still emit pending `WebServer._client` task warnings.

The lock selects certifi 2026.10.23. Tests use the existing Python environment with certifi 2026.7.22, so TLS bundle validation is separate. No active environment was updated.
