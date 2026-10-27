#!/bin/sh
# Local source install, isolated from ~/.exo and global exo launchers.
set -eu
cd "$(dirname "$0")"
repo=$(cd ../../.. && pwd)
command -v uv >/dev/null 2>&1 || { echo 'Install uv first.' >&2; exit 1; }
# Editable install retains repo-relative exo-command assets; keep this checkout.
uv sync --project "$repo" --frozen --inexact --extra tui --extra mcp
./build-macos-app.sh
app='build/Exo Desktop Alpha.app'
mv build/ExoDesktop.app "$app"
plist="$app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleName Exo Desktop Alpha' "$plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.askaconsult.exo-desktop-alpha' "$plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 0.1.0-alpha' "$plist"
# Quote the source path as a shell literal, including spaces and apostrophes.
python3 - "$repo" "$app/Contents/Resources/exo-alpha" <<'PY'
import pathlib, shlex, sys
repo, target = sys.argv[1:]
pathlib.Path(target).write_text('''#!/bin/sh
set -eu
export PYTHONUNBUFFERED=1
export EXO_DESKTOP_PORT=0
unset ANTHROPIC_API_KEY EXO_SEAT EXO_PLUGIN_DIRS EXO_PRINCIPAL EXO_STORE EXO_COMMAND_SOCKET EXO_COMMAND_URL EXO_COMMAND_TOKEN EXO_COMMAND_TOKEN_FILE EXO_TOKEN EXO_KEYS_FILE EXO_PRINCIPAL_STORE EXO_COMMAND_PRINCIPAL_STORE EXO_COMMAND_HOST
export EXO_COMMAND_HOST=127.0.0.1
export EXO_HOME="$HOME/Library/Application Support/Exo Desktop Alpha/runtime"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
mkdir -p "$EXO_HOME" "$HOME/Library/Application Support/Exo Desktop Alpha/workspace"
cd "$HOME/Library/Application Support/Exo Desktop Alpha/workspace"
exec ''' + shlex.quote(repo + '/.venv/bin/exo') + ' "$@"\n')
PY
chmod 755 "$app/Contents/Resources/exo-alpha"
codesign --force --sign - "$app"
codesign --verify --strict "$app"
mkdir -p "$HOME/Applications"
dest="$HOME/Applications/Exo Desktop Alpha.app"
if [ -e "$dest" ]; then
  old="$dest.previous"
  [ ! -e "$old" ] || { echo "Remove $old before replacing this alpha." >&2; exit 1; }
  mv "$dest" "$old"
fi
cp -R "$app" "$dest"
echo "Installed $dest"
echo 'Launch with: open "$HOME/Applications/Exo Desktop Alpha.app"'
