# Exo Desktop

A macOS window for the existing Exo web client. The core, provider login and approval rules remain in Exo.

## Local alpha install

Needs macOS 13 or later, Xcode command line tools (`swiftc` and `codesign`), and `uv` on PATH. From the repository root:

```sh
clients/desktop/macos/test-launcher.sh
clients/desktop/macos/install-local-alpha.sh
open "$HOME/Applications/Exo Desktop Alpha.app"
```

The installer runs `uv sync --frozen --extra tui --extra mcp` in this checkout, builds and ad hoc signs the app, then installs it in `~/Applications`. Keep the checkout in place: its `.venv` and repo-relative web assets are the runtime. Reinstall after updating sources. An existing alpha app is preserved as `Exo Desktop Alpha.app.previous`; remove that backup before another replacement. Signing errors fail the build/install.

The alpha bundles a launcher which uses this checkout's Python environment. It sets `EXO_HOME` to `~/Library/Application Support/Exo Desktop Alpha/runtime`, works in the sibling `workspace` folder, and requests an available local port. It does not replace `~/.local/bin/exo` or read the normal `~/.exo` configuration. First launch creates its own Exo identity and configuration. CLI providers are found through `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and the system PATH. Existing CLI logins remain managed by those CLIs. The alpha clears `ANTHROPIC_API_KEY` for its child process so Claude CLI can use its existing subscription login; it does not copy credentials into the app.

For local acceptance, launch from Finder, confirm the first-run page loads, select an available provider, send a short prompt, and check the reply. Paste using Command-V, open an external HTTPS link, then quit and reopen. Check that its own data persists, that the normal Exo data is untouched, and that quitting closes its web listener. These real provider/UI checks are separate from the launcher smoke tests.

## Generic shell build

```sh
clients/desktop/macos/build-macos-app.sh
open clients/desktop/macos/build/ExoDesktop.app
```

This shell uses external `exo`. `EXO_DESKTOP_EXO` overrides discovery; otherwise a bundled launcher is preferred, then PATH and standard local install locations. `EXO_DESKTOP_PORT` overrides the default port 7342. The generic shell starts in the user's home directory and preserves the usual Exo data configuration. Environment overrides must be passed when starting the executable directly, or through `open --env` on macOS versions supporting it.

## Lifecycle and security

The shell waits for a complete local page URL line, keeps its fragment token in memory, and continuously drains both process pipes without displaying their contents. Startup completion fires once; a later server exit presents Retry/Quit. Reload Page restarts the web server. Closing the window quits the app and stops its web server with bounded SIGINT, SIGTERM and SIGKILL stages (about four seconds maximum); the background core remains running. Stop Core first stops the web server, then stops the core so the web feed cannot restart it. Reload Page starts again.

The web view uses an ephemeral store. In-app navigation stays on the launched server's exact scheme/host/port. Other HTTP/HTTPS links open in the default browser after removing their fragment; other external schemes are blocked. The launcher never logs the page URL or process output. Run the bundled `Contents/Resources/exo-alpha` launcher in a terminal for diagnostics, keeping its output private because Exo prints a local access token.

## Remove the alpha

Quit the app. To stop an alpha core left running, run:

```sh
"$HOME/Applications/Exo Desktop Alpha.app/Contents/Resources/exo-alpha" stop
```

Then remove `~/Applications/Exo Desktop Alpha.app` and its optional `.previous` backup. To erase alpha sessions, identity and configuration, also remove `~/Library/Application Support/Exo Desktop Alpha`. This is permanent. Keep any workspace files you need before deleting that folder. Normal `~/.exo` data and CLI provider logins are separate.

This is a local source alpha with ad hoc signing. It has no notarization, automatic updater or portable bundled Python runtime. macOS distribution and Windows/Linux clients remain separate work.
