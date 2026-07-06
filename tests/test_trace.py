"""Curve tracing and interpolation (require scipy)."""

import numpy as np
import pytest

pytest.importorskip("scipy")

from scripts.figdatax import trace_curve, interpolate_curve, calibrate_axes
import synth


def test_trace_sine(artifacts):
    gt = synth.make_line(str(artifacts / "l.png"))
    cal = calibrate_axes(gt["plot_bbox"], gt["x_range"], gt["y_range"])
    pts = trace_curve(gt["path"], gt["plot_bbox"], gt["color_hsv"],
                      converter=cal, n_samples=100)
    assert len(pts) > 50
    errs = [abs(y - gt["truth_fn"](x)) for x, y in pts if 3 < x < 47]
    assert np.median(errs) < 0.5  # 1% of the 50-unit y range


def test_interpolate_cubic():
    pts = interpolate_curve([(0, 0), (1, 1), (2, 4), (3, 9)], n_output=50)
    assert len(pts) == 50
    xs = [p[0] for p in pts]
    assert xs == sorted(xs)


def test_interpolate_duplicate_x_raises():
    from scripts.figdatax import DetectionError
    with pytest.raises(DetectionError):
        interpolate_curve([(0, 0), (0, 1), (2, 4)])
