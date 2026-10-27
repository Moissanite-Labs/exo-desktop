#!/bin/sh
# Build ExoDesktop.app on a Mac. Needs swiftc. Ad hoc signing only.
set -eu
cd "$(dirname "$0")"

if [ "$(uname)" != "Darwin" ]; then
  echo "build-macos-app.sh runs on macOS only." >&2
  exit 1
fi
if ! command -v swiftc >/dev/null 2>&1; then
  echo "swiftc was not found. Install Xcode command line tools first." >&2
  exit 1
fi

rm -rf build
mkdir -p build/ExoDesktop.app/Contents/MacOS
mkdir -p build/ExoDesktop.app/Contents/Resources
swiftc -O Sources/ExoDesktop/*.swift \
  -o build/ExoDesktop.app/Contents/MacOS/ExoDesktop \
  -framework AppKit -framework WebKit
cp Info.plist build/ExoDesktop.app/Contents/Info.plist
if command -v codesign >/dev/null 2>&1; then
  codesign --force --sign - build/ExoDesktop.app || true
fi
echo "Built build/ExoDesktop.app"
echo "Open it with: open build/ExoDesktop.app"
