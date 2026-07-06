#!/usr/bin/env bash
#
# FigDataX skill environment bootstrap.
#
# Creates a skill-local virtual environment at <skill_root>/.venv and installs the
# runtime dependencies (opencv-python, numpy, pandas, matplotlib, scipy, openpyxl).
# Prefers `uv` for speed; falls back to `python3 -m venv` + pip.
#
# Usage:
#   bash scripts/setup.sh          # runtime deps only
#   bash scripts/setup.sh --dev    # runtime + test deps (pytest)
#
# Idempotent: re-running reuses the existing venv and re-syncs dependencies.
# On success prints the interpreter path and dependency versions.
# Exits non-zero if any required dependency fails to import (no silent degradation).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$SKILL_ROOT/.venv"

DEV=0
for arg in "$@"; do
    case "$arg" in
        --dev) DEV=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

if [ "$DEV" -eq 1 ]; then
    REQ_FILE="$SKILL_ROOT/requirements-dev.txt"
else
    REQ_FILE="$SKILL_ROOT/requirements.txt"
fi

# Locate uv (PATH, then the common user install location).
UV=""
if command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
elif [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
fi

echo "FigDataX setup"
echo "  skill root : $SKILL_ROOT"
echo "  venv       : $VENV"
echo "  requirements: $REQ_FILE"

if [ -n "$UV" ]; then
    echo "  installer  : uv ($UV)"
    [ -d "$VENV" ] || "$UV" venv "$VENV"
    "$UV" pip install --python "$VENV/bin/python" -r "$REQ_FILE"
else
    echo "  installer  : python3 -m venv + pip (uv not found)"
    [ -d "$VENV" ] || python3 -m venv "$VENV"
    "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
    "$VENV/bin/python" -m pip install -r "$REQ_FILE"
fi

# Verify required runtime dependencies import cleanly.
echo ""
echo "Verifying dependencies..."
"$VENV/bin/python" - <<'PY'
import sys
required = ["cv2", "numpy", "pandas", "matplotlib", "scipy", "openpyxl"]
missing = []
for name in required:
    try:
        mod = __import__(name)
        print(f"  OK  {name:12s} {getattr(mod, '__version__', '?')}")
    except Exception as exc:  # noqa: BLE001
        missing.append(name)
        print(f"  ERR {name:12s} {exc}")
if missing:
    print(f"\nMissing/broken: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)
print("\nAll runtime dependencies present.")
PY

echo ""
echo "Done. Use this interpreter for FigDataX:"
echo "  $VENV/bin/python"
