#!/bin/sh
# Local source install, isolated from ~/.exo and global exo launchers.
set -eu
cd "$(dirname "$0")"
repo=$(cd ../../.. && pwd)
attached=false
socket= exo= plugins= exo_home= seat=
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || { echo 'Every install flag needs a value.' >&2; exit 64; }
  case "$1" in
    --attach-socket) attached=true; socket=$2 ;;
    --exo) exo=$2 ;;
    --plugins) plugins=$2 ;;
    --exo-home) exo_home=$2 ;;
    --seat) seat=$2 ;;
    *) echo "Unknown install flag: $1" >&2; exit 64 ;;
  esac
  shift 2
done
if [ "$attached" = true ]; then
  [ -n "$exo" ] && [ -x "$exo" ] && [ -S "$socket" ] && [ -n "$exo_home" ] && [ -n "$seat" ] && [ -f "$plugins/exo-command/exo_command/__init__.py" ] || {
    echo 'Attached mode needs an executable --exo, live --attach-socket, --exo-home, --seat and --plugins containing exo-command.' >&2; exit 64;
  }
else
  [ -z "$exo$plugins$exo_home$seat" ] || { echo 'Runtime flags require --attach-socket.' >&2; exit 64; }
  command -v uv >/dev/null 2>&1 || { echo 'Install uv first.' >&2; exit 1; }
  uv sync --project "$repo" --frozen --inexact --extra tui --extra mcp
  exo="$repo/.venv/bin/exo"
fi
./build-macos-app.sh
app='build/Exo Desktop Alpha.app'
mv build/ExoDesktop.app "$app"
plist="$app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleName Exo Desktop Alpha' "$plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.askaconsult.exo-desktop-alpha' "$plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 0.1.0-alpha' "$plist"
if [ "$attached" = true ]; then
  /usr/libexec/PlistBuddy -c 'Add :ExoAttachedCore bool true' "$plist"
  python3 make-launcher.py --output "$app/Contents/Resources/exo-alpha" --exo "$exo" --attach-socket "$socket" --plugins "$plugins" --exo-home "$exo_home" --seat "$seat"
else
  python3 make-launcher.py --output "$app/Contents/Resources/exo-alpha" --exo "$exo"
fi
# Scope UI choices to the selected runtime identity, without persisting its paths in preferences.
preference_scope=$(python3 - "$attached" "$exo_home" "$seat" "$socket" <<'PYSCOPE'
import hashlib, json, os, sys
mode, home, seat, socket = sys.argv[1:]
if mode == 'true':
    identity = ['attached', os.path.realpath(os.path.expanduser(home)), seat, os.path.realpath(os.path.expanduser(socket))]
else:
    identity = ['isolated', os.path.expanduser('~/Library/Application Support/Exo Desktop Alpha/runtime')]
print(hashlib.sha256(json.dumps(identity, separators=(',', ':')).encode()).hexdigest())
PYSCOPE
)
/usr/libexec/PlistBuddy -c "Add :ExoPreferenceScope string $preference_scope" "$plist"
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
