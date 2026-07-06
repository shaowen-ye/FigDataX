"""Bridge to the FigDataX extraction engine.

Puts the repo root on sys.path and re-exports the engine API the app uses. Works
whether the engine is the current package (``scripts/figdatax/``) or a future
frozen/bundled copy. Keeps the app decoupled from the engine's on-disk layout.
"""

from __future__ import annotations

import os
import sys


def _repo_root() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller/py2app bundle
        return os.path.dirname(sys.executable)
    # app/figdatax_app/engine_bridge.py → repo root is two levels up from app/
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


REPO_ROOT = _repo_root()
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.figdatax import (  # noqa: E402
    auto_detect_plot_area, calibrate_axes_multipoint, AxisCalibration,
    extract_by_color_adaptive, auto_extract_scatter, detect_data_colors,
    pick_color, hsv_of_bgr, create_validation_plot, __version__ as engine_version,
)

__all__ = [
    "auto_detect_plot_area", "calibrate_axes_multipoint", "AxisCalibration",
    "extract_by_color_adaptive", "auto_extract_scatter", "detect_data_colors",
    "pick_color", "hsv_of_bgr", "create_validation_plot", "engine_version",
    "REPO_ROOT",
]
