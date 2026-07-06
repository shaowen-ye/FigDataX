"""Axis calibration — the single most important step for extraction accuracy.

Maps pixel coordinates to data coordinates via a least-squares linear fit on the
transformed axis (linear / log10 / reciprocal). Provides the forward transform
(pixel → data), the **inverse** (data → pixel, needed to draw data-space grids in
the GUI), quality metrics (RMSE, absolute and as % of axis span), and JSON
serialization so calibrations round-trip through project files.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

import numpy as np

from .core import CalibrationError


def _fwd_transform(values: np.ndarray, log: bool, transform: Optional[str], axis: str) -> np.ndarray:
    """Apply data → fit-space transform, validating the domain."""
    if log:
        if np.any(values <= 0):
            raise CalibrationError(
                f"{axis}-axis is log scale but tick values include non-positive "
                f"numbers {values.tolist()}; log10 is undefined there.")
        return np.log10(values)
    if transform == "reciprocal":
        if np.any(values == 0):
            raise CalibrationError(
                f"{axis}-axis uses reciprocal transform but a tick value is 0.")
        return 1.0 / values
    return values


class AxisCalibration:
    """Bidirectional pixel↔data mapping with fit-quality metrics.

    Callable: ``cal(px, py) -> (data_x, data_y)`` (backward compatible with the
    old closure API, including ``.x_rmse`` / ``.y_rmse`` / ``.x_coeffs`` / ``.y_coeffs``).
    """

    def __init__(self, x_coeffs, y_coeffs, x_log=False, y_log=False,
                 x_transform=None, y_transform=None,
                 x_rmse=0.0, y_rmse=0.0, x_span=1.0, y_span=1.0):
        self.x_coeffs = np.asarray(x_coeffs, dtype=float)
        self.y_coeffs = np.asarray(y_coeffs, dtype=float)
        self.x_log = bool(x_log)
        self.y_log = bool(y_log)
        self.x_transform = x_transform
        self.y_transform = y_transform
        self.x_rmse = float(x_rmse)
        self.y_rmse = float(y_rmse)
        self._x_span = float(x_span) or 1.0
        self._y_span = float(y_span) or 1.0

    # ── fit-quality as a fraction of axis span (the useful number) ──
    @property
    def x_rmse_pct(self) -> float:
        return 100.0 * self.x_rmse / abs(self._x_span)

    @property
    def y_rmse_pct(self) -> float:
        return 100.0 * self.y_rmse / abs(self._y_span)

    @staticmethod
    def _inv_axis(fit_val, log, transform):
        if log:
            return 10.0 ** fit_val
        if transform == "reciprocal":
            return np.inf if fit_val == 0 else 1.0 / fit_val
        return fit_val

    @staticmethod
    def _fwd_axis(data_val, log, transform):
        if log:
            return np.log10(data_val)
        if transform == "reciprocal":
            return 1.0 / data_val
        return data_val

    def pixel_to_data(self, px, py) -> Tuple[float, float]:
        """Convert a pixel coordinate to a data coordinate (no rounding)."""
        raw_x = np.polyval(self.x_coeffs, px)
        raw_y = np.polyval(self.y_coeffs, py)
        dx = self._inv_axis(raw_x, self.x_log, self.x_transform)
        dy = self._inv_axis(raw_y, self.y_log, self.y_transform)
        return float(dx), float(dy)

    def data_to_pixel(self, dx, dy) -> Tuple[float, float]:
        """Inverse transform: data coordinate → pixel coordinate.

        Requires non-degenerate calibration slopes. Used to draw data-space grids
        and to re-project edited data points back onto the image.
        """
        fx = self._fwd_axis(dx, self.x_log, self.x_transform)
        fy = self._fwd_axis(dy, self.y_log, self.y_transform)
        if self.x_coeffs[0] == 0 or self.y_coeffs[0] == 0:
            raise CalibrationError("Degenerate calibration (zero slope); cannot invert.")
        px = (fx - self.x_coeffs[1]) / self.x_coeffs[0]
        py = (fy - self.y_coeffs[1]) / self.y_coeffs[0]
        return float(px), float(py)

    def __call__(self, px, py) -> Tuple[float, float]:
        return self.pixel_to_data(px, py)

    def to_dict(self) -> dict:
        return {
            "x_coeffs": self.x_coeffs.tolist(),
            "y_coeffs": self.y_coeffs.tolist(),
            "x_log": self.x_log, "y_log": self.y_log,
            "x_transform": self.x_transform, "y_transform": self.y_transform,
            "x_rmse": self.x_rmse, "y_rmse": self.y_rmse,
            "x_span": self._x_span, "y_span": self._y_span,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AxisCalibration":
        return cls(d["x_coeffs"], d["y_coeffs"], d.get("x_log", False),
                   d.get("y_log", False), d.get("x_transform"), d.get("y_transform"),
                   d.get("x_rmse", 0.0), d.get("y_rmse", 0.0),
                   d.get("x_span", 1.0), d.get("y_span", 1.0))

    def __repr__(self) -> str:
        return (f"AxisCalibration(x_rmse={self.x_rmse:.4g} ({self.x_rmse_pct:.2f}%), "
                f"y_rmse={self.y_rmse:.4g} ({self.y_rmse_pct:.2f}%))")


def calibrate_axes_multipoint(pixel_points_x: Sequence[float], data_values_x: Sequence[float],
                              pixel_points_y: Sequence[float], data_values_y: Sequence[float],
                              x_log: bool = False, y_log: bool = False,
                              x_transform: Optional[str] = None,
                              y_transform: Optional[str] = None) -> AxisCalibration:
    """Fit a bidirectional pixel↔data calibration from N reference ticks per axis.

    Using 3+ ticks per axis (rather than just min/max) averages out reading error
    and corrects mild perspective/scan distortion.

    Args:
        pixel_points_x / data_values_x: paired x-axis tick pixels ↔ data values.
        pixel_points_y / data_values_y: paired y-axis tick pixels ↔ data values.
        x_log / y_log: axis is base-10 log scale (tick values must be > 0).
        x_transform / y_transform: ``"reciprocal"`` for 1/x axes.

    Returns:
        AxisCalibration.

    Raises:
        CalibrationError: mismatched/insufficient points, or invalid log/reciprocal domain.
    """
    px = np.asarray(pixel_points_x, dtype=float)
    dx = np.asarray(data_values_x, dtype=float)
    py = np.asarray(pixel_points_y, dtype=float)
    dy = np.asarray(data_values_y, dtype=float)

    if px.size != dx.size or py.size != dy.size:
        raise CalibrationError("pixel/data point counts must match on each axis.")
    if px.size < 2 or py.size < 2:
        raise CalibrationError("Need at least 2 calibration points per axis.")

    dx_fit = _fwd_transform(dx, x_log, x_transform, "x")
    dy_fit = _fwd_transform(dy, y_log, y_transform, "y")

    x_coeffs = np.polyfit(px, dx_fit, 1)
    y_coeffs = np.polyfit(py, dy_fit, 1)

    x_res = dx_fit - np.polyval(x_coeffs, px)
    y_res = dy_fit - np.polyval(y_coeffs, py)
    x_rmse = float(np.sqrt(np.mean(x_res ** 2)))
    y_rmse = float(np.sqrt(np.mean(y_res ** 2)))
    x_span = float(np.ptp(dx_fit)) or 1.0
    y_span = float(np.ptp(dy_fit)) or 1.0

    return AxisCalibration(x_coeffs, y_coeffs, x_log, y_log, x_transform, y_transform,
                           x_rmse, y_rmse, x_span, y_span)


def calibrate_axes(plot_bbox: Tuple[int, int, int, int],
                   x_range: Tuple[float, float], y_range: Tuple[float, float],
                   x_log: bool = False, y_log: bool = False) -> AxisCalibration:
    """Simple 2-point calibration from the plot bbox corners and axis ranges.

    Note image y is inverted: the bbox top maps to ``y_max``, the bottom to ``y_min``.
    For best accuracy prefer :func:`calibrate_axes_multipoint` with real tick marks.
    """
    left, top, right, bottom = plot_bbox
    return calibrate_axes_multipoint(
        pixel_points_x=[left, right], data_values_x=[x_range[0], x_range[1]],
        pixel_points_y=[top, bottom], data_values_y=[y_range[1], y_range[0]],
        x_log=x_log, y_log=y_log)
