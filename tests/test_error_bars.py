"""Error-bar extraction returns data-unit low/high with y_high >= y_low."""

import cv2
import numpy as np

from scripts.figdatax import extract_error_bars, calibrate_axes


def test_symmetric_error_bar():
    # Synthetic: plot area 40..360 in y maps to data 0..100 (top=100).
    img = np.full((400, 400, 3), 255, np.uint8)
    left, right, top, bottom = 60, 340, 40, 360
    cx = 200
    cy = 200            # marker center
    # draw vertical black whisker from cy-40 to cy+40
    cv2.line(img, (cx, cy - 40), (cx, cy + 40), (0, 0, 0), 2)
    cv2.circle(img, (cx, cy), 6, (0, 0, 255), -1)

    cal = calibrate_axes((left, top, right, bottom), (0, 1), (0, 100))
    res = extract_error_bars(img, [(cx, cy)], cal, error_color_hsv=(0, 0, 0),
                             search_radius=60)
    r = res[0]
    assert r["y_high"] >= r["y"] >= r["y_low"]
    # whisker spans +-40 px of 320px over 100 units => ~12.5 units each side
    assert abs((r["y_high"] - r["y"]) - 12.5) < 3
    assert abs((r["y"] - r["y_low"]) - 12.5) < 3
