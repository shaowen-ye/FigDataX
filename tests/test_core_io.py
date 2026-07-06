"""Core I/O and geometry: input normalization, plot-area detection, panels, colors."""

import cv2
import numpy as np
import pytest

from scripts.figdatax import (auto_detect_plot_area, split_panels, pick_color,
                              generate_grid_overlay, InputError)
from scripts.figdatax.core import _load_bgr
import synth


def test_load_grayscale():
    gray = np.full((50, 60), 128, np.uint8)
    out = _load_bgr(gray)
    assert out.shape == (50, 60, 3)


def test_load_rgba_composites_over_white():
    rgba = np.zeros((10, 10, 4), np.uint8)
    rgba[..., 3] = 0  # fully transparent
    out = _load_bgr(rgba)
    assert out.shape == (10, 10, 3)
    assert (out == 255).all()  # transparent → white


def test_load_16bit():
    img16 = np.full((8, 8, 3), 65535, np.uint16)
    out = _load_bgr(img16)
    assert out.dtype == np.uint8 and out.max() == 255


def test_load_bad_path_raises():
    with pytest.raises(InputError):
        _load_bgr("/nonexistent/xyz.png")


def test_pick_color_red():
    img = np.full((20, 20, 3), 255, np.uint8)
    img[8:12, 8:12] = (0, 0, 255)  # red BGR
    info = pick_color(img, 10, 10)
    assert info["hsv"][0] in (0, 179) or info["hsv"][0] < 5
    assert info["hsv"][1] > 200


def test_pick_color_out_of_bounds():
    with pytest.raises(InputError):
        pick_color(np.zeros((10, 10, 3), np.uint8), 99, 99)


def test_auto_detect_plot_area(artifacts):
    gt = synth.make_scatter(str(artifacts / "s.png"))
    bbox = auto_detect_plot_area(gt["path"])
    assert bbox is not None
    left, top, right, bottom = bbox
    tl, tt, tr, tb = gt["plot_bbox"]
    # within ~15px of the true axes frame
    assert abs(left - tl) < 15 and abs(right - tr) < 15
    assert abs(top - tt) < 15 and abs(bottom - tb) < 15


def test_split_panels_2x2(artifacts):
    gt = synth.make_composite_2x2(str(artifacts / "c.png"))
    panels = split_panels(gt["path"], layout="2x2")
    assert set(panels) == {"a", "b", "c", "d"}
    for p in panels.values():
        assert p.size > 0


def test_generate_grid_overlay(artifacts):
    gt = synth.make_scatter(str(artifacts / "s.png"))
    out = str(artifacts / "grid.png")
    generate_grid_overlay(gt["path"], out)
    import os
    assert os.path.getsize(out) > 0
