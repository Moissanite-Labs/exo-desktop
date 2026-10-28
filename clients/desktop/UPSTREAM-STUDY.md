# Desktop harness patterns for Exo

Exo should make its existing core easier to use from a desktop. This study turns the 2026-10-27 pilot requests into specific interactions and implementation references: a searchable model picker, an agent's own GitHub credentials, and a reliable connection to shared sessions and memory.

The sources below are public repository snapshots inspected on 2026-10-27. They establish implementation patterns, not a measured explanation of product success. No upstream code is copied by this document. The repositories use different runtimes and interfaces. Sharing a feature does not require importing its framework.

## Sources and candidate patterns

| Project and inspected revision | Source | Pattern to adopt in Exo |
| --- | --- | --- |
| Codex, `6fe77fc12346591b8037a8704640e40196b19044` | [App-server protocol behavior](https://github.com/openai/codex/blob/6fe77fc12346591b8037a8704640e40196b19044/codex-rs/app-server/README.md), [model requests from the TUI](https://github.com/openai/codex/blob/6fe77fc12346591b8037a8704640e40196b19044/codex-rs/tui/src/app_server_session/models.rs), [Apache-2.0 license](https://github.com/openai/codex/blob/6fe77fc12346591b8037a8704640e40196b19044/LICENSE) | Keep model discovery and thread state behind a typed core protocol. Distinguish a failed history query from an empty history. Study the public CLI and app-server code. Do not assume that every part of the Codex desktop UI is published in this repo. |
| Hermes Agent, `085f562af53a6fedadac3681e2c498fc71316132` | [Desktop architecture and shared state](https://github.com/NousResearch/hermes-agent/blob/085f562af53a6fedadac3681e2c498fc71316132/website/docs/user-guide/desktop.md), [shared model picker](https://github.com/NousResearch/hermes-agent/blob/085f562af53a6fedadac3681e2c498fc71316132/web/src/components/ModelPickerDialog.tsx), [MIT license](https://github.com/NousResearch/hermes-agent/blob/085f562af53a6fedadac3681e2c498fc71316132/LICENSE) | Reuse one model-selection interaction for chat and settings, while making the scope of the change clear. Keep desktop, terminal and web attached to the same core state. Preserve loading, error and applying states. |
| Pi, `a6a7bac868d9a47cdda8cf26c2257047bb0307dc` | [Searchable model selector](https://github.com/earendil-works/pi/blob/a6a7bac868d9a47cdda8cf26c2257047bb0307dc/packages/coding-agent/src/modes/interactive/components/model-selector.ts), [MIT license](https://github.com/earendil-works/pi/blob/a6a7bac868d9a47cdda8cf26c2257047bb0307dc/LICENSE) | Focus the search field on opening, match model and provider names, and support keyboard selection and cancellation. Keep current/default models easy to find. A catalog refresh should preserve the query and provide a useful cached view when possible. |
| OpenCode, `f993a89d13c73ff6f6537d6b97e78e138a3ea363` | [Model selection dialog](https://github.com/anomalyco/opencode/blob/f993a89d13c73ff6f6537d6b97e78e138a3ea363/packages/app/src/providers/models/select-dialog.tsx), [MIT license](https://github.com/anomalyco/opencode/blob/f993a89d13c73ff6f6537d6b97e78e138a3ea363/LICENSE) | Combine immediate filtering with provider identity and keyboard navigation. Reset the active row when filtering changes the results. Keep the full provider/model identity available so similarly named routes remain distinct. |
| T3 Code, `1a4f3c4a3c29d5cb4fb34308dc2e959b6de347c1` | [Source-control accounts and credential precedence](https://github.com/pingdotgg/t3code/blob/1a4f3c4a3c29d5cb4fb34308dc2e959b6de347c1/docs/user/source-control.md), [picker keyboard bindings](https://github.com/pingdotgg/t3code/blob/1a4f3c4a3c29d5cb4fb34308dc2e959b6de347c1/packages/shared/src/keybindings.ts), [MIT license](https://github.com/pingdotgg/t3code/blob/1a4f3c4a3c29d5cb4fb34308dc2e959b6de347c1/LICENSE) | Offer a saved GitHub token as a first-class account option, with clear host/account selection and credential precedence. Make common actions discoverable through shortcuts. For Exo, an explicitly configured agent credential must not silently fall back to the user's login. |
| Command Code, `630bbf418f62bcdea627e57e6dca60151452355b` | [Repository README](https://github.com/CommandCodeAI/command-code/blob/630bbf418f62bcdea627e57e6dca60151452355b/readme.md), [interactive mode documentation](https://commandcode.ai/docs/interactive-mode), [taste documentation](https://commandcode.ai/docs/taste) | Study ranked slash-command discovery, clear model/session precedence and visible learning from feedback. The inspected public repo provides a README and a mods registry. Reusable harness implementation and its applicable source license were not established. Treat this as a product/documentation reference until that changes. |
| DeepSeek Harness, `22ddee3792402c3e70ec5f86a63c3e3e895a2f60` | [Architecture and desktop host](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/docs/architecture.md), [durable model selection](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/agent/src/model-selection.ts), [MIT license](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/LICENSE) | Study typed plugin services with cleanup on unload, a version-matched desktop runtime, explicit readiness/error messages, and recorded model selections distinct from the last request's model. Adapt those boundaries to Exo's existing plugins and protocol before considering a framework change. |
| Oh My Pi, `0838d2ab4407b74e870de07e1a6780a13c7d542c` | [Agent Hub](https://github.com/can1357/oh-my-pi/blob/0838d2ab4407b74e870de07e1a6780a13c7d542c/docs/agent-hub.md), [settings scopes and writes](https://github.com/can1357/oh-my-pi/blob/0838d2ab4407b74e870de07e1a6780a13c7d542c/docs/settings.md), [MIT license](https://github.com/can1357/oh-my-pi/blob/0838d2ab4407b74e870de07e1a6780a13c7d542c/LICENSE) | Consider a filterable agent roster with live activity, usage, transcripts and steering. Make project, profile and runtime settings scopes visible, and state where a model-role change is saved. Preserve upstream Pi and fork notices if adapting implementation code. |
| UniiChat, `0500bf6a8ea4bf0ce047488562022b1b6532cc30` | [Memory tree and views](https://github.com/VictorTaelin/uniichat/blob/0500bf6a8ea4bf0ce047488562022b1b6532cc30/Memory.ts), [model calls and cached prefixes](https://github.com/VictorTaelin/uniichat/blob/0500bf6a8ea4bf0ce047488562022b1b6532cc30/AskAI.ts), [Apache-2.0 license](https://github.com/VictorTaelin/uniichat/blob/0500bf6a8ea4bf0ce047488562022b1b6532cc30/LICENSE) | Study a server-owned conversation shared across views, indexed original messages beneath hierarchical summaries, and retrieval of finer detail from a summary. Compare background summary scheduling and cache-friendly prompt views against Exo's existing summary tree. |

## First implementation targets

### Searchable model selection

Use one component in chat and provider settings. Typing filters provider names, model names and exact routes without changing the model. Arrow keys move through results, Enter applies a selected route, and Escape cancels. Show the full route, current choice, no matches, loading and failure states.

Keep changing the running core's shared main route distinct from saving its default. The current session endpoint also records the choice on that session, but does not isolate the router to that thread. Ignore stale responses and prevent duplicate changes while a save is pending.

Acceptance includes duplicate display names from different providers, filtering to zero results, keyboard-only selection, cancellation without a POST, and a delayed save while the user changes threads. Selecting a model must not send the search text as a chat prompt.

### Agent-specific GitHub credentials

Let an agent use its own GitHub token or login without changing the machine's existing `gh` account. Bind the setting to the Exo data home, seat and GitHub host. Show which credential mode is active without returning a saved token. Resolve credentials when starting tools so rotation and revocation take effect without starting a second core.

Use the existing secret-store and output-redaction primitives. Accept tokens through hidden input or a guarded settings request, never a token argument recorded in shell history. In an explicit agent mode, a missing, revoked or policy-denied credential must fail without falling back to the host login. Keep environment changes local to the child process, and preserve existing tool approval rules.

The [GitHub CLI environment reference](https://cli.github.com/manual/gh_help_environment) defines token precedence and `GH_CONFIG_DIR`. A separate config directory alone is not proof of separate OS keychain credentials. Verify that boundary before claiming isolated login support.

Giving a token to an agent's shell permits that shell to use it. Redacting output is not a sandbox against code that deliberately encodes or exports the token.

The attached desktop cannot add new behavior to an already running older core merely by replacing web assets. Core-side credential support and desktop settings must agree on capabilities and the selected seat. Installation and live acceptance must report that boundary explicitly.

### Memory detail and continuity experiment

Exo already constructs context from a summary tree and recent messages in [core context](../../src/exo/core/context.py). UniiChat is therefore a comparison for retrieval and interaction design, not evidence that Exo lacks hierarchical summaries.

Use long synthetic conversations to compare recovering a specific old fact, tracing a summary back to its original messages, undoing a turn, resuming after an outage, and importing older history. Measure answer accuracy, summary cost, retrieval latency and prompt-cache use. Retaining originals does not make a generated summary lossless or guarantee that the agent will retrieve the right detail. This experiment remains planned. The inspection did not run either system on those workloads.

## How to bring upstream work into Exo

- Choose a concrete interaction or module with a failing Exo acceptance case. Record the source repository, exact revision and relevant paths.
- Check the applicable license and any nested third-party notices for the files being reused. Preserve required notices and record copied or ported modules in `PROVENANCE.toml` and `LICENSES/` using the repo's existing convention.
- Prefer a small adaptation that fits Exo's core protocol, tool policy and shared-memory design. Evaluate new framework dependencies separately.
- Carry the behavior with regression tests. Verify keyboard use, stale requests, empty/error states and secret handling as applicable.
- Keep research, implementation, local installation and native acceptance as separate statuses. Do not describe a source review as a desktop usability test.

Future candidates include a command palette, recent/favorite models, richer provider details, session search, change review and packaged-runtime updates. These are candidates for later work, not claims about features shipped in the alpha.

## Implementation status

The original searchable picker implementation is in `facbeb97`, tracked by [desktop picker issue](https://github.com/aska-digital/exo-desktop/issues/33). Browser regressions cover filtering, exact routes, keyboard use, cancellation, stale requests and deferred default-model changes. Native macOS acceptance confirmed search in chat and Providers after reload, without changing the selected model or restarting the existing core.

The shared web component is also proposed in the [canonical picker PR](https://github.com/aska-digital/exo/pull/673) at `c0fd3a40`, with 125 focused tests passing. That port remains unmerged. The source references and remaining candidates are available for independent contributions from other Exo seats. Coordinate overlapping implementation work through claims, without reserving the entire study.

The CLI and core credential implementation is in `71340dcb`, with the canonical port proposed in [canonical core PR](https://github.com/aska-digital/exo/pull/672). Its [setup guide](../../docs/GITHUB-AUTH.md) describes token and private-login modes, secret storage and the trusted-shell boundary. It does not enable credentials in an older running core.

[Desktop setup issue](https://github.com/aska-digital/exo-desktop/issues/34) tracks guarded settings UI, and [broader core identity issue](https://github.com/aska-digital/exo/issues/106) tracks the broader agent-identity work. GitHub App token minting and commit authorship are outside this implementation.

A matching local Canary upgrade was staged separately, preserving its prior core features. The staged build passed 329 focused auth/tool/CLI/launcher tests and 20 existing Canary rounds tests. Its manual launcher has not been run, and the active core has not been upgraded. A core handoff requires a separate restart choice. Staging and fake-credential tests are not real GitHub account authentication.
