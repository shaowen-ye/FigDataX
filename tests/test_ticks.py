"""Tick auto-detection and series suggestion against synthetic ground truth."""

import os

from scripts.figdatax import detect_ticks, suggest_series
from tests import synth


def _match(detected, truth, tol=1.5):
    """Count truth ticks with a detected position within tol px."""
    if not detected:
        return 0, []
    matched, errs = 0, []
    for t in truth:
        nearest = min(detected, key=lambda p: abs(p - t))
        if abs(nearest - t) <= tol:
            matched += 1
            errs.append(abs(nearest - t))
    return matched, errs


def test_detect_ticks_linear(artifacts):
    gt = synth.make_scatter(os.path.join(artifacts, "scatter.png"))
    res = detect_ticks(gt["path"], gt["plot_bbox"])
    for ax in ("x", "y"):
        truth = [px for _v, px in gt[f"ticks_{ax}"]]
        assert res[ax] is not None, f"{ax}-axis ticks not detected"
        assert res[ax]["spacing_cv"] < 0.05, f"{ax} spacing_cv too high"
        matched, errs = _match(res[ax]["positions"], truth)
        assert matched >= 4, f"{ax}: only {matched}/{len(truth)} major ticks matched"
        assert max(errs) <= 1.5


def test_detect_ticks_log_recovers_majors(artifacts):
    # The log-y axis has many minor ticks; the detector must keep the (longer) majors.
    gt = synth.make_log_scatter(os.path.join(artifacts, "log.png"))
    res = detect_ticks(gt["path"], gt["plot_bbox"])
    truth_y = [px for _v, px in gt["ticks_y"]]
    assert res["y"] is not None
    assert res["y"]["spacing_cv"] < 0.05, "log-y majors should be evenly spaced"
    matched, _ = _match(res["y"]["positions"], truth_y)
    assert matched == len(truth_y), "all decade major ticks should be recovered"


def test_detect_ticks_tickless_returns_none(artifacts):
    import cv2
    import numpy as np
    p = os.path.join(artifacts, "rect.png")
    img = np.full((300, 400, 3), 255, np.uint8)
    cv2.rectangle(img, (60, 40), (360, 260), (0, 0, 0), 2)
    cv2.imwrite(p, img)
    res = detect_ticks(p, (60, 40, 360, 260))
    assert res["x"] is None and res["y"] is None


def test_suggest_series_markers(artifacts):
    gt = synth.make_scatter(os.path.join(artifacts, "scatter2.png"))
    series = suggest_series(gt["path"], gt["plot_bbox"])
    assert series, "expected at least one series"
    red = max(series, key=lambda s: s["pixel_fraction"])
    assert red["geometry"] in ("markers", "region")
    assert red["geometry"] != "line"


def test_suggest_series_line(artifacts):
    gt = synth.make_line(os.path.join(artifacts, "line.png"))
    series = suggest_series(gt["path"], gt["plot_bbox"])
    assert series, "expected a line series"
    assert any(s["geometry"] == "line" for s in series)
