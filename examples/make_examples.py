#!/usr/bin/env python3
"""Generate the committed example fixtures used for the quick end-to-end demo/test.

Run with the skill venv:
    .venv/bin/python examples/make_examples.py

Produces (in this directory):
    scatter_demo.png            a scatter chart with a red series (y = 2x)
    scatter_demo_calib.json     multi-point axis calibration for it
    scatter_demo_expected.csv   the extracted data, for regression comparison
"""

import json
import os
import sys

import cv2
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skill root → scripts.figdatax

from scripts.figdatax import calibrate_axes_multipoint, extract_by_color_adaptive  # noqa: E402


def build():
    W, H = 640, 440
    img = np.full((H, W, 3), 255, np.uint8)
    left, right, top, bottom = 90, 590, 40, 380
    # light gridlines
    for gx in range(left, right + 1, (right - left) // 10):
        cv2.line(img, (gx, top), (gx, bottom), (220, 220, 220), 1)
    for gy in range(top, bottom + 1, (bottom - top) // 5):
        cv2.line(img, (left, gy), (right, gy), (220, 220, 220), 1)
    cv2.rectangle(img, (left, top), (right, bottom), (0, 0, 0), 2)

    xs = list(range(0, 11, 1))
    ys = [2.0 * x for x in xs]
    for x, y in zip(xs, ys):
        px = int(left + x / 10.0 * (right - left))
        py = int(bottom - y / 25.0 * (bottom - top))
        cv2.circle(img, (px, py), 6, (0, 0, 255), -1)  # red BGR

    cv2.imwrite(os.path.join(HERE, "scatter_demo.png"), img)

    calib = {
        "x": [[left, 0], [int(left + 0.5 * (right - left)), 5], [right, 10]],
        "y": [[bottom, 0], [int(bottom - 0.6 * (bottom - top)), 15], [top, 25]],
        "x_log": False, "y_log": False,
    }
    with open(os.path.join(HERE, "scatter_demo_calib.json"), "w") as fh:
        json.dump(calib, fh, indent=2)

    cal = calibrate_axes_multipoint(
        [p[0] for p in calib["x"]], [p[1] for p in calib["x"]],
        [p[0] for p in calib["y"]], [p[1] for p in calib["y"]])
    det = extract_by_color_adaptive(img, (0, 255, 255), color_distance=40, subpixel=True)
    rows = [(*cal.pixel_to_data(cx, cy), round(area, 1), round(conf, 3))
            for cx, cy, area, conf in det]
    df = pd.DataFrame(rows, columns=["X", "Y", "Area", "Confidence"]).round({"X": 3, "Y": 3})
    df.to_csv(os.path.join(HERE, "scatter_demo_expected.csv"), index=False)
    print(f"Wrote scatter_demo.png ({len(det)} points), calib JSON, expected CSV")
    print(df.to_string(index=False))


if __name__ == "__main__":
    build()
