#!/bin/sh
# Build ExoDesktop.app on a Mac. Needs swiftc. Ad hoc signing only.
#
# Packaged runtime (issue #31): --with-packaged-runtime bundles a
# checkout-independent runtime into Contents/Resources/runtime (see
# package-runtime.py for the layout). The packaged app never reads the
# source checkout at launch. --dry-run prints the packaging plan without
# building; it runs on Linux too and is the checkout-free layout check.
set -eu
cd "$(dirname "$0")"

packaged=false
python_home=
site_packages=
version=0.1.0-alpha
commit=
dry_run=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --with-packaged-runtime) packaged=true ;;
    --python-home) [ "$#" -ge 2 ] || { echo '--python-home needs a value.' >&2; exit 64; }; python_home=$2; shift ;;
    --site-packages) [ "$#" -ge 2 ] || { echo '--site-packages needs a value.' >&2; exit 64; }; site_packages=$2; shift ;;
    --version) [ "$#" -ge 2 ] || { echo '--version needs a value.' >&2; exit 64; }; version=$2; shift ;;
    --commit) [ "$#" -ge 2 ] || { echo '--commit needs a value.' >&2; exit 64; }; commit=$2; shift ;;
    --dry-run) dry_run=true ;;
    *) echo "Unknown build flag: $1" >&2; exit 64 ;;
  esac
  shift
done

if [ "$dry_run" = true ]; then
  if [ -n "$commit" ]; then
    python3 package-runtime.py --dry-run --version "$version" --commit "$commit"
  else
    python3 package-runtime.py --dry-run --version "$version"
  fi
  echo "dry run: packaging plan only, no app built"
  exit 0
fi

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
if [ "$packaged" = true ]; then
  [ -n "$python_home" ] || { echo 'Packaged build needs --python-home (a pinned python-build-standalone tree).' >&2; exit 64; }
  set -- --output build/ExoDesktop.app/Contents/Resources \
    --python-home "$python_home" --version "$version"
  [ -n "$site_packages" ] && set -- "$@" --site-packages "$site_packages"
  [ -n "$commit" ] && set -- "$@" --commit "$commit"
  python3 package-runtime.py "$@"
  # Fail the build if the bundle layout is incomplete; a half-packaged
  # app must never ship and fail later at launch.
  resources=build/ExoDesktop.app/Contents/Resources/runtime
  [ -x "$resources/python/bin/python3" ] || { echo 'Packaged runtime is missing its Python interpreter.' >&2; exit 1; }
  [ -f "$resources/src/exo/cli.py" ] || { echo 'Packaged runtime is missing exo sources.' >&2; exit 1; }
  [ -f "$resources/plugins/exo-command/exo_command/__init__.py" ] || { echo 'Packaged runtime is missing its plugins.' >&2; exit 1; }
  [ -f "$resources/VERSION" ] || { echo 'Packaged runtime is missing VERSION.' >&2; exit 1; }
fi
if command -v codesign >/dev/null 2>&1; then
  codesign --force --sign - build/ExoDesktop.app
fi
echo "Built build/ExoDesktop.app"
echo "Open it with: open build/ExoDesktop.app"
