#!/bin/sh
# Convert the 1024x1024 icon source PNG into a macOS .icns file.
# Usage: make-icon.sh <source-png> <output.icns>
# macOS only (needs sips + iconutil). On any other machine, or when the
# tools are missing, it warns and exits 0 so the app build still succeeds
# with the generic icon instead of failing on artwork.
set -eu
png=${1:-Assets/ExoIcon-1024.png}
out=${2:-build/Exo.icns}
if [ "$(uname)" != "Darwin" ] || ! command -v sips >/dev/null 2>&1 || ! command -v iconutil >/dev/null 2>&1; then
  echo "Warning: app icon not generated (needs macOS with sips + iconutil)." >&2
  exit 0
fi
if [ ! -f "$png" ]; then
  echo "Warning: icon source $png not found; skipping icon." >&2
  exit 0
fi
iconset=$(mktemp -d)/Exo.iconset
mkdir -p "$iconset"
for spec in "16:icon_16x16" "32:icon_16x16@2x" "32:icon_32x32" "64:icon_32x32@2x" \
            "128:icon_128x128" "256:icon_128x128@2x" "256:icon_256x256" "512:icon_256x256@2x" \
            "512:icon_512x512" "1024:icon_512x512@2x"; do
  size=${spec%%:*}
  name=${spec#*:}
  sips -z "$size" "$size" "$png" --out "$iconset/$name.png" >/dev/null
done
mkdir -p "$(dirname "$out")"
iconutil -c icns "$iconset" -o "$out"
echo "Wrote $out"
