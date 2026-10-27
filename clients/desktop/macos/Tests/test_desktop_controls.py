"""Static checks for the native desktop controls (issue #29).

No Swift toolchain exists on this Linux machine, so these checks assert on
the Swift source, Info.plist, build scripts and icon asset instead of
compiling or running the app. A macOS build + native run is still required
and is listed as pending in the pull request.
"""
import struct
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / "Sources/ExoDesktop/main.swift").read_text()
plist = (root / "Info.plist").read_text()
build = (root / "build-macos-app.sh").read_text()
checks = []


def check(condition, label):
    checks.append(label)
    assert condition, label


# Find: menu, shortcuts, bar, keyboard handling.
for fragment in ('"Find…"', '"Find Next"', '"Find Previous"', '"Use Selection for Find"',
                 'keyEquivalent: "f"', 'keyEquivalent: "g"', 'keyEquivalent: "e"',
                 'keyEquivalentModifierMask = [.command, .shift]',
                 'window.find(', 'cancelOperation', 'insertNewline',
                 'JSONSerialization.data(withJSONObject'):
    check(fragment in main, f"find: {fragment}")
# Zoom: menu, shortcuts, pageZoom with bounds.
for fragment in ('"Zoom In"', '"Zoom Out"', '"Actual Size"',
                 'keyEquivalent: "+"', 'keyEquivalent: "-"', 'keyEquivalent: "0"',
                 'webView.pageZoom = min(3.0', 'webView.pageZoom = max(0.5',
                 'webView?.pageZoom = 1.0'):
    check(fragment in main, f"zoom: {fragment}")
# Startup states: four states, health verification before load, no healthy
# claim from a printed URL alone.
for fragment in ('"Starting Exo…"', '"Connecting to the Exo server…"', '"Ready"',
                 '"Failed"', 'verifyServer', 'didFinish navigation',
                 'didFailProvisionalNavigation'):
    check(fragment in main, f"status: {fragment}")
check('webView?.load(URLRequest(url: url))' in main, "load happens only after verification")
# About: standard panel, version + build + source commit from Info.plist.
for fragment in ('orderFrontStandardAboutPanel', 'CFBundleShortVersionString',
                 'CFBundleVersion', 'ExoSourceCommit', '"About Exo"'):
    check(fragment in main, f"about: {fragment}")
check('<key>ExoSourceCommit</key>' in plist, "plist: ExoSourceCommit key")
check('Set :ExoSourceCommit' in build, "build: stamps ExoSourceCommit")
# Icon: plist key, build wiring, 1024x1024 RGBA source PNG.
check('<key>CFBundleIconFile</key>' in plist, "plist: CFBundleIconFile key")
check('make-icon.sh' in build, "build: calls make-icon.sh")
png = root / "Assets" / "ExoIcon-1024.png"
data = png.read_bytes()
check(data[:8] == b"\x89PNG\r\n\x1a\n", "icon: PNG signature")
w, h, _depth, ctype = struct.unpack(">IIBB", data[16:26])
check((w, h) == (1024, 1024) and ctype == 6, "icon: 1024x1024 RGBA")
# Preserved guards: origin restriction, token handling, attached Stop Core.
check('url.scheme == origin?.scheme' in main, "guard: origin scheme/host/port check")
check('if !isAttached' in main and 'guard !isAttached else { return }' in main,
      "guard: Stop Core hidden and refused when attached")
check('fragment = nil' in main, "guard: health probe strips the fragment")
check('X-Exo-Token' not in main, "guard: no token header from the shell")
check('print(' not in main, "guard: shell prints nothing (no token leak path)")
# Layout: find bar, status bar and web view are laid out on resize.
for fragment in ('windowDidResize', 'layoutViews()', 'statusSpinner', 'findBar.isHidden'):
    check(fragment in main, f"layout: {fragment}")
print(f"PASS: {len(checks)} desktop-control checks")
sys.exit(0)
