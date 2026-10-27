#!/bin/sh
# Local source install, isolated from ~/.exo and global exo launchers.
set -eu
cd "$(dirname "$0")"
repo=$(cd ../../.. && pwd)
attached=false
packaged=false
package_overlay=false
socket= exo= plugins= exo_home= seat= python_home= site_packages=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --packaged) packaged=true; shift ;;
    --package-overlay) package_overlay=true; shift ;;
    --python-home) [ "$#" -ge 2 ] || { echo 'Every install flag needs a value.' >&2; exit 64; }; python_home=$2; shift 2 ;;
    --site-packages) [ "$#" -ge 2 ] || { echo 'Every install flag needs a value.' >&2; exit 64; }; site_packages=$2; shift 2 ;;
    --attach-socket) [ "$#" -ge 2 ] || { echo 'Every install flag needs a value.' >&2; exit 64; }; attached=true; socket=$2; shift 2 ;;
    --exo) [ "$#" -ge 2 ] || { echo 'Every install flag needs a value.' >&2; exit 64; }; exo=$2; shift 2 ;;
    --plugins) [ "$#" -ge 2 ] || { echo 'Every install flag needs a value.' >&2; exit 64; }; plugins=$2; shift 2 ;;
    --exo-home) [ "$#" -ge 2 ] || { echo 'Every install flag needs a value.' >&2; exit 64; }; exo_home=$2; shift 2 ;;
    --seat) [ "$#" -ge 2 ] || { echo 'Every install flag needs a value.' >&2; exit 64; }; seat=$2; shift 2 ;;
    *) echo "Unknown install flag: $1" >&2; exit 64 ;;
  esac
done
if [ "$packaged" = true ] && [ "$attached" = true ]; then
  echo '--packaged is for isolated installs; attached installs use --package-overlay for the overlay only.' >&2; exit 64;
fi
if [ "$package_overlay" = true ] && [ "$attached" != true ]; then
  echo '--package-overlay needs --attach-socket.' >&2; exit 64;
fi
if [ "$attached" = true ]; then
  # With --package-overlay the overlay comes from this repo, so --plugins
  # is not needed; without it, --plugins must contain exo-command.
  if [ "$package_overlay" = true ]; then
    [ -n "$exo" ] && [ -x "$exo" ] && [ -S "$socket" ] && [ -n "$exo_home" ] && [ -n "$seat" ] || {
      echo 'Attached mode needs an executable --exo, live --attach-socket, --exo-home and --seat.' >&2; exit 64;
    }
  else
    [ -n "$exo" ] && [ -x "$exo" ] && [ -S "$socket" ] && [ -n "$exo_home" ] && [ -n "$seat" ] && [ -f "$plugins/exo-command/exo_command/__init__.py" ] || {
      echo 'Attached mode needs an executable --exo, live --attach-socket, --exo-home, --seat and --plugins containing exo-command.' >&2; exit 64;
    }
  fi
else
  [ -z "$exo$plugins$exo_home$seat" ] || { echo 'Runtime flags require --attach-socket.' >&2; exit 64; }
  if [ "$packaged" = true ]; then
    # Packaged isolated install: the checkout is a build-time input only.
    # A staging sync supplies third-party deps; the bundle itself carries
    # the sources, plugins and pinned Python, so the app keeps working
    # after the checkout moves. --python-home must be a pinned
    # python-build-standalone tree for the target Mac.
    [ -n "$python_home" ] || { echo 'Packaged install needs --python-home.' >&2; exit 64; }
    command -v uv >/dev/null 2>&1 || { echo 'Install uv first.' >&2; exit 1; }
    uv sync --project "$repo" --frozen --inexact --extra tui --extra mcp
    [ -n "$site_packages" ] || site_packages=$(ls -d "$repo"/.venv/lib/python*/site-packages 2>/dev/null | head -n 1)
    exo="$repo/.venv/bin/exo"
  else
    command -v uv >/dev/null 2>&1 || { echo 'Install uv first.' >&2; exit 1; }
    uv sync --project "$repo" --frozen --inexact --extra tui --extra mcp
    exo="$repo/.venv/bin/exo"
  fi
fi
if [ "$packaged" = true ]; then
  set -- --with-packaged-runtime --python-home "$python_home"
  [ -n "$site_packages" ] && set -- "$@" --site-packages "$site_packages"
  ./build-macos-app.sh "$@"
else
  ./build-macos-app.sh
fi
app='build/Exo Desktop Alpha.app'
mv build/ExoDesktop.app "$app"
plist="$app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleName Exo Desktop Alpha' "$plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.askaconsult.exo-desktop-alpha' "$plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 0.1.0-alpha' "$plist"
if [ "$attached" = true ]; then
  /usr/libexec/PlistBuddy -c 'Add :ExoAttachedCore bool true' "$plist"
  if [ "$package_overlay" = true ]; then
    # Versioned overlay inside the app's own Application Support folder,
    # not an external path: the selected exo executable is still used,
    # only the plugin copy moves under app-owned, versioned storage.
    # A stale overlay from an older app version fails at launch (exit 72)
    # instead of silently serving old web assets.
    overlay_version="0.1.0-alpha+$(git -C "$repo" rev-parse HEAD 2>/dev/null || echo unknown)"
    overlay_dir="$HOME/Library/Application Support/Exo Desktop Alpha/overlay/$overlay_version"
    python3 package-runtime.py --repo "$repo" --overlay-only --overlay-output "$overlay_dir" --version 0.1.0-alpha
    python3 make-launcher.py --output "$app/Contents/Resources/exo-alpha" --exo "$exo" --attach-socket "$socket" --overlay-dir "$overlay_dir" --overlay-version "$overlay_version" --exo-home "$exo_home" --seat "$seat"
  else
    python3 make-launcher.py --output "$app/Contents/Resources/exo-alpha" --exo "$exo" --attach-socket "$socket" --plugins "$plugins" --exo-home "$exo_home" --seat "$seat"
  fi
elif [ "$packaged" = true ]; then
  python3 make-launcher.py --output "$app/Contents/Resources/exo-alpha" --packaged
else
  python3 make-launcher.py --output "$app/Contents/Resources/exo-alpha" --exo "$exo"
fi
codesign --force --sign - "$app"
codesign --verify --strict "$app"
mkdir -p "$HOME/Applications"
dest="$HOME/Applications/Exo Desktop Alpha.app"
if [ -e "$dest" ]; then
  old="$dest.previous.$(date +%Y%m%d%H%M%S).$$"
  mv "$dest" "$old"
fi
cp -R "$app" "$dest"
echo "Installed $dest"
echo 'Launch with: open "$HOME/Applications/Exo Desktop Alpha.app"'
