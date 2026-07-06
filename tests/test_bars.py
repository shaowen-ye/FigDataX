"""Bar chart extraction: simple, grouped, stacked."""

import pytest

from scripts.figdatax import auto_extract_bars, calibrate_axes
import synth


def _y_cal(gt):
    return calibrate_axes(gt["plot_bbox"], (0, 1), gt["y_range"])


def test_simple_bars(artifacts):
    gt = synth.make_bars(str(artifacts / "b.png"), kind="simple")
    res = auto_extract_bars(gt["path"], gt["plot_bbox"], converter=_y_cal(gt),
                            colors_hsv=gt["colors"])
    got = sorted(res["green"])
    truth = sorted(gt["truth"]["green"])
    for g, t in zip(got, truth):
        assert abs(g - t) < 0.5  # 1% of the 50-unit range


def test_grouped_bars(artifacts):
    gt = synth.make_bars(str(artifacts / "b.png"), kind="grouped")
    res = auto_extract_bars(gt["path"], gt["plot_bbox"], converter=_y_cal(gt),
                            colors_hsv=gt["colors"])
    for name in ("red", "blue"):
        got = sorted(res[name])
        truth = sorted(gt["truth"][name])
        assert len(got) == len(truth)
        for g, t in zip(got, truth):
            assert abs(g - t) < 0.6


def test_stacked_bars(artifacts):
    gt = synth.make_bars(str(artifacts / "b.png"), kind="stacked")
    res = auto_extract_bars(gt["path"], gt["plot_bbox"], converter=_y_cal(gt),
                            colors_hsv=gt["colors"], stacked=True)
    # red is the bottom segment; its height should match truth
    red_vals = sorted(seg["value"] for seg in res["red"])
    truth = sorted(gt["truth"]["red"])
    for g, t in zip(red_vals, truth):
        assert abs(g - t) < 1.2  # 2% of the 60-unit range
