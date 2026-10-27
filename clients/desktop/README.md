# Exo Desktop

A macOS app window for Exo. It shows the web client that already exists. It does not replace the core, the memory, or the approval gate.

## What it is

Exo Desktop is a thin shell. It starts `exo web`, then shows that page in a native macOS window. The agent, its memory, and its approvals stay exactly where they already are.

## What it is not

It is not a new agent. It is not a new protocol. It is not a native rewrite of the chat view. Approvals still happen in the web client, with the same exact text rule.

## How it works

The app finds `exo` on PATH, or at the path in `EXO_DESKTOP_EXO`. It runs `exo web --port 7342 --no-open` unless `EXO_DESKTOP_PORT` sets another port.

`exo web` already handles the core. If a core is running, it joins it. If none is running, it starts one in the background. The desktop app does not start a second core.

The app reads one page address from `exo web` output. It loads that address in a WebKit view. It never prints that address, never writes it to disk, and never puts it in an argument list.

Closing the window quits the app. Quitting stops the web server first, waits up to five seconds, then forces it if needed. The core keeps running either way. The Exo menu has a Stop Core item. It runs `exo stop`.

The startup timeout only applies before the page address is found. Once the page loads, the timeout does not touch the server.

## Security rules

The page address carries a token in its fragment. A fragment is never sent to a server. The app keeps the token in memory only.

The web view uses a non-persistent store. Closing the app clears it. Navigation stays on loopback. A link to any other host opens in the default browser, with the fragment removed.

If `exo web` exits, the app shows the failure and quits. It does not dump process output into the alert.

## Build on a Mac

Run this from `clients/desktop`:

```sh
macos/build-macos-app.sh
```

This needs `swiftc` and a Mac. It builds `macos/build/ExoDesktop.app`. It signs the app ad hoc only. A signed and notarized release is separate work.

## Run

Open `macos/build/ExoDesktop.app`. `exo` must be installed and on PATH first. Run `exo web` in a terminal if the app reports a startup failure. That terminal output is the diagnostic.

## Still to do

- A signed and notarized release build.
- An update path for the app itself.
- A menu bar mode, so closing the window can keep the app running with visible UI.
- Native approval cards, instead of the web client view.
- Windows and Linux shells, if the shell approach is kept.

None of these change the core. Each one is a client change.
