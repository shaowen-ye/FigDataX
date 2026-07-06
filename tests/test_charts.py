"""Box plot, pie, and heatmap extraction accuracy against synthetic ground truth."""

import cv2
import numpy as np
import pytest

from scripts.figdatax import (extract_boxplot, extract_pie, extract_heatmap,
                              calibrate_axes, pick_color)
import synth


def test_boxplot(artifacts):
    gt = synth.make_boxplot(str(artifacts / "box.png"))
    left, top, right, bottom = gt["plot_bbox"]
    cal = calibrate_axes(gt["plot_bbox"], (0, 1), gt["y_range"])
    # sample the box fill color from the box center
    img = cv2.imread(gt["path"])
    fill = pick_color(img, (left + right) // 2, (top + bottom) // 2)
    boxes = extract_boxplot(gt["path"], gt["plot_bbox"], cal,
                            box_color_hsv=fill["hsv"], color_distance=50)
    assert len(boxes) >= 1
    b = boxes[0]
    t = gt["truth"]
    span = gt["y_range"][1] - gt["y_range"][0]
    assert abs(b["q1"] - t["q1"]) < 0.03 * span
    assert abs(b["q3"] - t["q3"]) < 0.03 * span
    assert abs(b["median"] - t["median"]) < 0.03 * span


def test_pie(artifacts):
    gt = synth.make_pie(str(artifacts / "pie.png"))
    wedges = extract_pie(gt["path"])
    fracs = sorted((w["fraction"] for w in wedges), reverse=True)
    truth = gt["fractions"]
    assert len(fracs) == len(truth)
    for f, t in zip(fracs, truth):
        assert abs(f - t) < 0.02  # 2% (≈ 7° on a full circle)


def test_heatmap(artifacts):
    gt = synth.make_heatmap(str(artifacts / "hm.png"))
    matrix = extract_heatmap(gt["path"], gt["plot_bbox"], gt["grid_shape"],
                             gt["colorbar_bbox"], gt["colorbar_range"])
    assert matrix.shape == gt["grid_shape"]
    err = np.abs(matrix - gt["matrix"])
    # < 8% of the 0..100 colorbar range on median (viridis nearest-neighbor)
    assert np.median(err) < 8.0
