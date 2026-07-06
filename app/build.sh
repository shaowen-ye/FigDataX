#!/usr/bin/env bash
#
# Build the unsigned FigDataX Desktop .app and .dmg on macOS (arm64).
#
#   bash app/build.sh
#
# Output: app/dist/FigDataX.app, app/dist/FigDataX-<ver>.dmg, app/dist/FigDataX-<ver>.app.zip
#
# The bundle is UNSIGNED. Users open it the first time with right-click → Open, or:
#   xattr -dr com.apple.quarantine /Applications/FigDataX.app
#
# NOTE: the engine (scripts/figdatax) must be reachable inside the bundle; setup.py
# includes it via the "scripts" package. Adjust if the repo layout changes.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
VER="$(cat VERSION)"

# Isolated build venv
UV=""
command -v uv >/dev/null 2>&1 && UV="$(command -v uv)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
BVENV=".venv-build"
if [ -n "$UV" ]; then
    [ -d "$BVENV" ] || "$UV" venv "$BVENV" --python 3.12
    "$UV" pip install --python "$BVENV/bin/python" -r requirements.txt py2app
else
    [ -d "$BVENV" ] || python3 -m venv "$BVENV"
    "$BVENV/bin/python" -m pip install -r requirements.txt py2app
fi

rm -rf build dist
"$BVENV/bin/python" setup.py py2app

# Optional: ad-hoc sign so it launches with fewer warnings (uncomment to enable)
# codesign --deep --force --sign - "dist/FigDataX.app"

# .dmg (create-dmg if available, else hdiutil)
if command -v create-dmg >/dev/null 2>&1; then
    create-dmg --volname "FigDataX" --app-drop-link 480 180 \
        "dist/FigDataX-$VER.dmg" "dist/FigDataX.app" || true
else
    hdiutil create -volname FigDataX -srcfolder "dist/FigDataX.app" -ov \
        -format UDZO "dist/FigDataX-$VER.dmg"
fi

# Also zip the .app as a lighter release asset
ditto -c -k --keepParent "dist/FigDataX.app" "dist/FigDataX-$VER.app.zip"

echo "Built: dist/FigDataX-$VER.dmg  and  dist/FigDataX-$VER.app.zip"
