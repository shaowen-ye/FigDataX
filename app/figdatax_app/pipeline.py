"""Headless extraction pipeline — the engine glue, independent of any GUI.

Both the Qt workers and the smoke test call these functions, so the core logic is
testable without a display.
"""

from __future__ import annotations

from typing import List, Tuple

from . import engine_bridge as eng
from .models import Calibration, DataPoint, ExtractionSession, Series


def build_calibration(cal: Calibration) -> "eng.AxisCalibration":
    return eng.calibrate_axes_multipoint(
        pixel_points_x=[p.px for p in cal.x_points],
        data_values_x=[p.value for p in cal.x_points],
        pixel_points_y=[p.px for p in cal.y_points],
        data_values_y=[p.value for p in cal.y_points],
        x_log=cal.x_log, y_log=cal.y_log)


def extract_series(session: ExtractionSession, target_hsv, color_distance=30,
                   subpixel=True) -> Series:
    """Run color extraction for the session's active series and fill its points."""
    axis = build_calibration(session.calibration)
    det = eng.extract_by_color_adaptive(session.image_path, target_hsv,
                                        color_distance=color_distance,
                                        subpixel=subpixel, auto_widen=True)
    series = session.active_series()
    series.color_hsv = tuple(int(v) for v in target_hsv)
    series.points = []
    for cx, cy, _area, conf in det:
        dx, dy = axis.pixel_to_data(cx, cy)
        series.points.append(DataPoint(cx, cy, dx, dy, float(conf)))
    series.points.sort(key=lambda p: p.data_x)
    return series


def auto_bbox(image_path) -> Tuple[int, int, int, int] | None:
    return eng.auto_detect_plot_area(image_path)
