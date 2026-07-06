"""One regression test per audited bug, named by bug number."""

import warnings

import cv2
import numpy as np
import pytest

from scripts.figdatax import (auto_detect_plot_area, remove_grid,
                              extract_by_color_adaptive, calibrate_axes_multipoint,
                              CalibrationError)
from scripts.figdatax.core import _load_bgr
import synth


def test_bug01_houghlinesp_shape(artifacts):
    """HoughLinesP output must be handled on OpenCV >=5 (shape (N,4))."""
    gt = synth.make_scatter(str(artifacts / "s.png"))
    # Must not raise "cannot unpack non-iterable numpy.int32"
    bbox = auto_detect_plot_area(gt["path"])
    assert bbox is not None
    cleaned = remove_grid(gt["path"], method="hough")
    assert cleaned.shape == _load_bgr(gt["path"]).shape


def test_bug02_lazy_imports_core_without_scipy():
    """Core color extraction must not require scipy/matplotlib at import time."""
    import importlib
    mod = importlib.import_module("scripts.figdatax.core")
    # core module must not have imported scipy/matplotlib
    assert "scipy" not in dir(mod)


def test_bug03_log_guard():
    with pytest.raises(CalibrationError):
        calibrate_axes_multipoint([0, 10], [0, 100], [10, 0], [1, 10], x_log=True)


def test_bug04_small_magnitude_not_rounded():
    cal = calibrate_axes_multipoint([0, 100], [1e-6, 3e-6], [100, 0], [0, 1])
    dx, _ = cal.pixel_to_data(50, 50)
    assert dx != 0.0  # old round(,4) would have made this 0.0


def test_bug07_rgba_input_no_crash():
    rgba = np.zeros((60, 60, 4), np.uint8)
    rgba[..., 3] = 255
    rgba[20:40, 20:40] = (0, 0, 255, 255)  # opaque red square
    # would previously crash cvtColor(BGR2HSV) on a 4-channel array
    res = extract_by_color_adaptive(rgba, (0, 255, 255), color_distance=40)
    assert isinstance(res, list)


def test_bug07_grayscale_input_no_crash():
    gray = np.full((40, 40), 128, np.uint8)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = extract_by_color_adaptive(gray, (0, 255, 255))
    assert res == []


def test_bug06_zero_detection_returns_empty_with_warning():
    img = np.full((50, 50, 3), 255, np.uint8)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        res = extract_by_color_adaptive(img, (0, 255, 255))
    assert res == []
    assert len(w) >= 1
