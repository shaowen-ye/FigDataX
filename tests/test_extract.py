"""Color extraction accuracy, subpixel, and 0-detection warning behavior."""

import warnings

import numpy as np
import pytest

from scripts.figdatax import (extract_by_color_adaptive, auto_extract_scatter,
                              calibrate_axes_multipoint, detect_data_colors)
import synth


def test_scatter_accuracy(artifacts):
    gt = synth.make_scatter(str(artifacts / "s.png"))
    cal = calibrate_axes_multipoint(
        [t[1] for t in gt["ticks_x"]], [t[0] for t in gt["ticks_x"]],
        [t[1] for t in gt["ticks_y"]], [t[0] for t in gt["ticks_y"]])
    det = extract_by_color_adaptive(gt["path"], gt["color_hsv"],
                                    color_distance=40, subpixel=True)
    assert len(det) == len(gt["points"])
    got = sorted(cal.pixel_to_data(cx, cy) for cx, cy, _, _ in det)
    truth = sorted((p[0], p[1]) for p in gt["points"])
    max_err = max(abs(g[1] - t[1]) for g, t in zip(got, truth))
    assert max_err < 0.25  # < 1% of the 25-unit y range


def test_auto_extract_scatter_with_converter(artifacts):
    gt = synth.make_scatter(str(artifacts / "s.png"))
    cal = calibrate_axes_multipoint(
        [t[1] for t in gt["ticks_x"]], [t[0] for t in gt["ticks_x"]],
        [t[1] for t in gt["ticks_y"]], [t[0] for t in gt["ticks_y"]])
    pts = auto_extract_scatter(gt["path"], gt["plot_bbox"],
                               target_hsv=gt["color_hsv"], converter=cal)
    assert len(pts) == len(gt["points"])


def test_zero_detection_warns(artifacts):
    gt = synth.make_scatter(str(artifacts / "s.png"))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # green target on a red-only chart → 0 detections
        res = extract_by_color_adaptive(gt["path"], (60, 255, 255), color_distance=15)
    assert res == []
    assert any("0 points" in str(x.message) for x in w)


def test_auto_widen_recovers(artifacts):
    gt = synth.make_scatter(str(artifacts / "s.png"))
    # slightly-off red target that misses at distance 15 but recovers when widened
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = extract_by_color_adaptive(gt["path"], (0, 200, 200),
                                        color_distance=15, auto_widen=True)
    assert len(res) == len(gt["points"])


def test_detect_data_colors_deterministic(artifacts):
    gt = synth.make_scatter(str(artifacts / "s.png"))
    c1 = detect_data_colors(gt["path"], gt["plot_bbox"])
    c2 = detect_data_colors(gt["path"], gt["plot_bbox"])
    assert c1 == c2
    assert any(name == "red" for name, _ in c1)
