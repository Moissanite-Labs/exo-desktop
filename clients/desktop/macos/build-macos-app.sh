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
MACOSX_DEPLOYMENT_TARGET=13.0 swiftc -O Sources/ExoDesktop/*.swift \
  -o build/ExoDesktop.app/Contents/MacOS/ExoDesktop \
  -framework AppKit -framework WebKit
cp Info.plist build/ExoDesktop.app/Contents/Info.plist
# Stamp the source commit the app was built from, for the About panel.
# Outside a git checkout the Info.plist placeholder ("unknown") stands.
if command -v git >/dev/null 2>&1 && commit=$(git rev-parse HEAD 2>/dev/null); then
  /usr/libexec/PlistBuddy -c "Set :ExoSourceCommit $commit" build/ExoDesktop.app/Contents/Info.plist
fi
# App icon: warns and continues on machines without sips/iconutil.
./make-icon.sh Assets/ExoIcon-1024.png build/ExoDesktop.app/Contents/Resources/Exo.icns
if command -v codesign >/dev/null 2>&1; then
  codesign --force --sign - build/ExoDesktop.app
fi
echo "Built build/ExoDesktop.app"
echo "Open it with: open build/ExoDesktop.app"
