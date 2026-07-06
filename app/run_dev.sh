#!/usr/bin/env bash
#
# Bootstrap the app's virtual environment and launch FigDataX Desktop from source.
#
#   bash app/run_dev.sh            # create app/.venv, install deps, run the GUI
#   bash app/run_dev.sh --smoke    # headless smoke test (no window), for CI/dev
#
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$APP_DIR/.venv"

UV=""
command -v uv >/dev/null 2>&1 && UV="$(command -v uv)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"

if [ -n "$UV" ]; then
    [ -d "$VENV" ] || "$UV" venv "$VENV"
    "$UV" pip install --python "$VENV/bin/python" -r "$APP_DIR/requirements.txt"
else
    [ -d "$VENV" ] || python3 -m venv "$VENV"
    "$VENV/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
fi

cd "$APP_DIR"
if [ "${1:-}" = "--smoke" ]; then
    QT_QPA_PLATFORM=offscreen "$VENV/bin/python" -m figdatax_app.smoke_test
else
    "$VENV/bin/python" -m figdatax_app
fi
