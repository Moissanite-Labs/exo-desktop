# Exo Desktop

A macOS window for the existing Exo web client. The core, provider login and approval rules remain in Exo.

The [macOS alpha follow-up plan](ALPHA-PLAN.md) tracks packaging, interface state and native controls, with acceptance criteria and current limits.

The [upstream harness study](UPSTREAM-STUDY.md) records concrete patterns from Codex, Hermes, Pi, OpenCode, T3 Code, Command Code, DeepSeek Harness, Oh My Pi and UniiChat, with source revisions and reuse limits.

## Local alpha install

Needs macOS 13 or later, Xcode command line tools (`swiftc` and `codesign`), and `uv` on PATH. From the repository root:

```sh
clients/desktop/macos/test-launcher.sh
clients/desktop/macos/install-local-alpha.sh
open "$HOME/Applications/Exo Desktop Alpha.app"
```

The installer runs `uv sync --frozen --extra tui --extra mcp` in this checkout, builds and ad hoc signs the app, then installs it in `~/Applications`. Keep the checkout in place: its `.venv` and repo-relative web assets are the runtime. Reinstall after updating sources. An existing alpha app is preserved with a timestamp and process number in its `.previous` backup name. Signing errors fail the build/install.

The alpha bundles a launcher which uses this checkout's Python environment. It sets `EXO_HOME` to `~/Library/Application Support/Exo Desktop Alpha/runtime`, works in the sibling `workspace` folder, and requests an available local port. It does not replace `~/.local/bin/exo` or read the normal `~/.exo` configuration. First launch creates its own Exo identity and configuration. CLI providers are found through `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and the system PATH. Existing CLI logins remain managed by those CLIs. The alpha clears `ANTHROPIC_API_KEY` for its child process so Claude CLI can use its existing subscription login; it does not copy credentials into the app.

For local acceptance, launch from Finder, confirm the first-run page loads, select an available provider, send a short prompt, and check the reply. Paste using Command-V, open an external HTTPS link, then quit and reopen. Check that its own data persists, that the normal Exo data is untouched, and that quitting closes its web listener. These real provider/UI checks are separate from the launcher smoke tests.

## Attach to an existing core

To share an existing core's sessions and memory, install with its exact runtime, plugins, data home, seat and Unix socket. Replace these example paths with the existing core's settings:

```sh
clients/desktop/macos/install-local-alpha.sh \
  --attach-socket "$HOME/.exo/run/agent-canary.sock" \
  --exo /path/to/canary-environment/bin/exo \
  --plugins /path/to/canary-checkout/plugins \
  --exo-home "$HOME/.exo" \
  --seat canary
```

Attached installation skips `uv sync` and uses the supplied executable and web assets. It requires the selected socket and runtime to exist. It passes an explicit socket to `exo web`, which disables automatic core startup. If that core is unavailable, Retry reconnects to the same socket. It never starts a replacement core. The bundled launcher rejects every command except `web`, and the app hides Stop Core. Quit and Reload stop only the app's own web process. The existing core keeps running.

The attached app shares the selected core's real data. Removing the app does not remove that data. Do not follow the isolated alpha data-removal instructions for an attached installation. The normal alpha installer with no flags switches back to isolated mode.

Test wrapper generation without accessing live data:

```sh
python3 clients/desktop/macos/Tests/test_attach_launcher.py
```

For a runtime checkout with compatible web code that needs the replay fix in this branch, create a separate plugin copy, then pass that output as `--plugins`:

```sh
python3 clients/desktop/macos/prepare-web-overlay.py \
  --plugins /path/to/existing-checkout/plugins \
  --output /path/to/new-desktop-plugins
```

This copies the selected plugins and replaces `exo-command`'s `server.py` and `service.py`, plus the `reasoning.py` HTTP edge.

It leaves the running core and original runtime files untouched. Use it only when those two original files match this branch's base version.

Fresh page event streams use the recent event cache. Saved transcripts still come from the core. Replay waits for the browser to consume each event so a large history cannot fill the web process's output buffer and freeze the app.

Add `--with-model-picker` to also install the searchable chat and Providers pickers. This option checks the supported asset versions and patches chat without replacing runtime-specific commands. Names, providers and full routes can be searched, including punctuation-free queries such as `gpt6`. Use the arrow keys and Enter to select, or Escape to cancel. Typing alone does not change the model.

This option also copies the `reasoning.js` dependency used by Providers. The overlay does not upgrade the core. Reasoning controls return an upgrade response when the selected core lacks that capability.

Add `--with-approval-shortcuts` to show the approval keyboard path and highlight the focused card. Press Ctrl+F to focus the first approval, then use its shown keys. Always and deny require Enter. This option checks the original approval script and stylesheet before copying the updated assets. It can be combined with `--with-model-picker`.

For separate agent GitHub credentials, see [per-seat GitHub authentication](../../docs/GITHUB-AUTH.md). It needs a core version containing that feature. Updating this web overlay alone does not enable it in an older core.

## Generic shell build

```sh
clients/desktop/macos/build-macos-app.sh
open clients/desktop/macos/build/ExoDesktop.app
```

This shell uses external `exo`. `EXO_DESKTOP_EXO` overrides discovery; otherwise a bundled launcher is preferred, then PATH and standard local install locations. `EXO_DESKTOP_PORT` overrides the default port 7342. The generic shell starts in the user's home directory and preserves the usual Exo data configuration. Environment overrides must be passed when starting the executable directly, or through `open --env` on macOS versions supporting it.

## Native controls

The app menu has About Exo, showing the app version, build and the source commit stamped at build time (`ExoSourceCommit` in Info.plist, `unknown` outside a git checkout). The View menu has Zoom In (Command-+), Zoom Out (Command--) and Actual Size (Command-0), applied to the web view. The Edit menu has a Find submenu: Find… (Command-F) opens a native find bar, Find Next (Command-G), Find Previous (Shift-Command-G), Use Selection for Find (Command-E); Enter finds next, Escape closes the bar. The Window menu has Minimize, Zoom Window and Close. The status bar at the bottom of the window shows Starting, Connecting, Ready or Failed; Ready appears only after the page finishes loading, and Connecting first verifies the printed origin actually answers HTTP (a token-free request for the page shell, fragment stripped) — a printed URL alone is never shown as healthy. Startup failure keeps the existing Retry/Quit alert.

The app icon is `Exo` in Info.plist. The source artwork is `macos/Assets/ExoIcon-1024.png`, regenerated with `python3 macos/make-icon-source.py` (standard library only, so it runs on Linux too); the build script converts it to `Exo.icns` with `sips` + `iconutil` on macOS (`macos/make-icon.sh` also runs standalone) and warns instead of failing when those tools are absent.

## Lifecycle and security

The shell waits for a complete local page URL line, keeps its fragment token in memory, and continuously drains both process pipes without displaying their contents. Startup completion fires once; a later server exit presents Retry/Quit. Reload Page restarts the web server. Closing the window quits the app and stops its web server with bounded SIGINT, SIGTERM and SIGKILL stages (about four seconds maximum); the background core remains running. Stop Core first stops the web server, then stops the core so the web feed cannot restart it. Reload Page starts again.

The web view uses an ephemeral store. In-app navigation stays on the launched server's exact scheme/host/port. Other HTTP/HTTPS links open in the default browser after removing their fragment; other external schemes are blocked. The launcher never logs the page URL or process output. Run the bundled `Contents/Resources/exo-alpha` launcher in a terminal for diagnostics, keeping its output private because Exo prints a local access token.

## Remove the alpha

These steps apply to an isolated installation only. For an attached installation, quit and remove the app and its backups. Leave the selected core and data home in place.

Quit the isolated app. To stop its alpha core left running, run:

```sh
"$HOME/Applications/Exo Desktop Alpha.app/Contents/Resources/exo-alpha" stop
```

Then remove `~/Applications/Exo Desktop Alpha.app` and its optional `.previous.*` backups. To erase alpha sessions, identity and configuration, also remove `~/Library/Application Support/Exo Desktop Alpha`. This is permanent. Keep any workspace files you need before deleting that folder. Normal `~/.exo` data and CLI provider logins are separate.

This is a local source alpha with ad hoc signing. It has no notarization, automatic updater or portable bundled Python runtime. macOS distribution and Windows/Linux clients remain separate work.
