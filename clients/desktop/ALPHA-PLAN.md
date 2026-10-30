# macOS alpha follow-up

The current alpha attaches to an existing Exo core and shares its saved sessions and memory. The next pass should make the desktop independent of development checkout paths, preserve interface state, and improve the native controls, in that order.

This plan records the 2026-10-27 alpha feedback and source review at `9be0eb22`. The feedback inspected source, the installed bundle and live HTTP endpoints. It did not exercise the GUI. Separate native acceptance confirmed saved threads, a model reply and responsive requests after the replay fix. The separate reported release-build startup race has not been reproduced.

## Pilot additions

- [Searchable model picker](https://github.com/aska-digital/exo-desktop/issues/33): implemented in `facbeb97` and verified in the native alpha. Chat and Providers share name/provider/route search with keyboard selection and cancellation.
- [Agent GitHub credentials](../../docs/GITHUB-AUTH.md): CLI and core support implemented in `71340dcb`. The running older Canary core still needs an upgrade before its shell tools can use this feature. [Desktop setup](https://github.com/aska-digital/exo-desktop/issues/34) remains planned. The broader identity work is [broader core identity issue](https://github.com/aska-digital/exo/issues/106).
- [Upstream study](UPSTREAM-STUDY.md): source references, licenses and concrete adoption patterns for the repositories supplied during the pilot. Research does not imply that all candidate features have shipped.

## 1. Package a stable desktop runtime

Status: planned. Tracked in the [GitHub issue](https://github.com/aska-digital/exo-desktop/issues/31).

The isolated installer uses its checkout's Python environment and assets. Attached mode uses the explicitly selected executable and plugins. The current local installation selects a Canary environment and a separate copied plugin overlay. Neither mode is a portable app bundle. Moving, removing or incompatibly updating those dependencies can break a later launch.

Acceptance:

- Install the web runtime and assets with the app, using a versioned runtime that does not import from a development checkout.
- Launch and use the app after the source checkout is moved out of reach.
- Preserve attachment to the selected socket, existing sessions and memory. Never start a replacement core when the socket is unavailable.
- Quit, reload and update only the desktop's owned processes and files. Keep the existing core's runtime and data intact.
- Record the runtime version and source commit in the build. Validate the result on Apple Silicon macOS with a real reply and quit/reopen checks.

Bundling Python needs a packaging and signing check. The existing ad hoc source install remains the documented alpha path until that acceptance passes.

## 2. Preserve interface state

Status: planned. Tracked in the [GitHub issue](https://github.com/aska-digital/exo-desktop/issues/30).

The web view uses a nonpersistent store. Reload starts a new web server, and the alpha requests an available port. Browser storage belongs to an origin, so a different port also prevents reuse of saved browser preferences. Enabling a persistent store alone will not resolve this.

Acceptance:

- Restore the selected thread, chat layout, Appearance (the `xc-appearance` choice), window size and position after quit/reopen and Reload Page. Appearance is listed because the web page keeps it in browser storage: the nonpersistent website data store drops it on quit, and the alpha's port 0 request gives each reload a new origin, so a Light or System choice returns to Dark today.
- Restore a useful position in an existing transcript where practical. Handle a removed thread by returning to the thread picker.
- Save only the interface preferences needed for restoration. Keep the page access token out of persisted preferences and diagnostic output.
- Keep saved conversations and memory in the core. Verify restoration across changing local ports without changing the selected core.

## 3. Add native controls and clear startup status

Status: implemented on `fix/desktop-native-controls-29` against this branch, pending a native macOS run (no Swift toolchain on the Linux machine that built it). Tracked in the [GitHub issue](https://github.com/aska-digital/exo-desktop/issues/29).

The shell currently provides a standard titled window, an Edit menu and Reload Page. It has no native toolbar, find or zoom commands, app icon, or About item. The version is present in Info.plist. Startup uses a plain text page followed by Retry/Quit on failure.

Acceptance:

- Add native find, zoom in/out/reset and discoverable menu shortcuts.
- Show clear starting, connecting, ready and failed states with the existing Retry/Quit behavior. Do not show a healthy connection solely because the web process has printed a URL.
- Add an app icon and an About panel showing the app version and source commit.
- Check keyboard navigation, editing, window resizing and startup failures in the native app.
- Preserve origin restrictions, private token handling and the attached mode's prohibition on Stop Core.

Treat the separate reported release-build startup race as an investigation item. Capture a reproducible case before describing it as a confirmed defect.

## Release boundary

The replay freeze is fixed in `9be0eb22` on the alpha branch. The three items above are planned work, not features delivered by that fix. Notarization, automatic updates and distribution beyond this local pilot remain later release work.

## Quit consent and remaining pause integration (#92)

The native quit path now defaults to Keep Open and explicitly says the shared core and active agent work remain running, including possible paid model calls. Quit and Keep Running preserves intentionally unattended sessions. Cancelling the quit returns without shutting down the web connection.

This is a partial repair. A native action that safely pauses the relevant active work without killing the shared core remains unimplemented; the shared session and authority boundary needs independent review. Users can keep the window open and cancel a turn in Chat. This change does not cancel other sessions or claim to stop provider-side work already submitted. Native dialog interaction remains manual acceptance.
