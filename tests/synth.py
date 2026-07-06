"""Synthetic chart generators with recorded ground truth.

Each generator draws a chart with matplotlib and records the EXACT pixel geometry
of the data using the axes ``transData`` transform, so tests can assert extraction
accuracy against a known truth (not a re-measurement of the same image).

Coordinate convention: matplotlib display origin is bottom-left; image (cv2/PNG)
origin is top-left, so ``image_y = height_px - display_y``.
"""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


def _save(fig, path):
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    w, h = canvas.get_width_height()
    fig.savefig(path, dpi=fig.dpi)
    return w, h


def _to_px(ax, h, dx, dy):
    xd, yd = ax.transData.transform((dx, dy))
    return xd, h - yd


def _axes_bbox_px(ax, h):
    bb = ax.get_window_extent()
    left, right = bb.x0, bb.x1
    top, bottom = h - bb.y1, h - bb.y0
    return int(round(left)), int(round(top)), int(round(right)), int(round(bottom))


def make_scatter(path, dpi=150):
    """Red-circle scatter of y = 2x, x in 0..10. Returns ground truth dict."""
    fig = Figure(figsize=(6, 4), dpi=dpi)
    ax = fig.add_subplot(111)
    xs = list(range(0, 11, 2))
    ys = [2.0 * x for x in xs]
    ax.scatter(xs, ys, c="red", s=80, zorder=5)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 25)
    ax.grid(True)
    w, h = _save(fig, path)
    pts = [(x, y, *_to_px(ax, h, x, y)) for x, y in zip(xs, ys)]
    ticks_x = [(v, _to_px(ax, h, v, 0)[0]) for v in [0, 2, 4, 6, 8, 10]]
    ticks_y = [(v, _to_px(ax, h, 0, v)[1]) for v in [0, 5, 10, 15, 20, 25]]
    return {
        "path": path, "w": w, "h": h,
        "points": pts,  # (data_x, data_y, px, py)
        "ticks_x": ticks_x, "ticks_y": ticks_y,
        "plot_bbox": _axes_bbox_px(ax, h),
        "color_hsv": (0, 255, 255),  # pure red
        "x_range": (0, 10), "y_range": (0, 25),
    }


def make_line(path, dpi=150):
    """Blue sine curve y = 25 + 20 sin(x/5), x in 0..50."""
    fig = Figure(figsize=(6, 4), dpi=dpi)
    ax = fig.add_subplot(111)
    xs = np.linspace(0, 50, 400)
    ys = 25 + 20 * np.sin(xs / 5.0)
    ax.plot(xs, ys, color="blue", linewidth=2)
    ax.set_xlim(0, 50)
    ax.set_ylim(0, 50)
    w, h = _save(fig, path)
    sample = [(float(x), float(25 + 20 * np.sin(x / 5.0))) for x in np.linspace(2, 48, 20)]
    return {
        "path": path, "w": w, "h": h,
        "truth_fn": lambda x: 25 + 20 * np.sin(x / 5.0),
        "sample": sample,
        "plot_bbox": _axes_bbox_px(ax, h),
        "color_hsv": (120, 255, 255),  # pure blue
        "x_range": (0, 50), "y_range": (0, 50),
    }


def make_bars(path, kind="simple", dpi=150):
    """Bar chart. kind: 'simple' | 'grouped' | 'stacked'. Records exact heights."""
    fig = Figure(figsize=(6, 4), dpi=dpi)
    ax = fig.add_subplot(111)
    cats = np.arange(4)
    if kind == "simple":
        vals = [10.0, 25.0, 40.0, 15.0]
        ax.bar(cats, vals, color="green")
        truth = {"green": vals}
        colors = {"green": (60, 255, 128)}
        ax.set_ylim(0, 50)
    elif kind == "grouped":
        a = [10.0, 20.0, 30.0, 25.0]
        b = [15.0, 12.0, 18.0, 35.0]
        ax.bar(cats - 0.2, a, width=0.4, color="red")
        ax.bar(cats + 0.2, b, width=0.4, color="blue")
        truth = {"red": a, "blue": b}
        colors = {"red": (0, 255, 255), "blue": (120, 255, 255)}
        ax.set_ylim(0, 50)
    else:  # stacked
        a = [10.0, 20.0, 15.0, 25.0]
        b = [12.0, 8.0, 18.0, 10.0]
        ax.bar(cats, a, color="red")
        ax.bar(cats, b, bottom=a, color="blue")
        truth = {"red": a, "blue": b}
        colors = {"red": (0, 255, 255), "blue": (120, 255, 255)}
        ax.set_ylim(0, 60)
    w, h = _save(fig, path)
    return {
        "path": path, "w": w, "h": h, "kind": kind,
        "truth": truth, "colors": colors,
        "plot_bbox": _axes_bbox_px(ax, h),
        "y_range": (ax.get_ylim()[0], ax.get_ylim()[1]),
    }


def make_log_scatter(path, dpi=150):
    """Semi-log-y scatter: y = 10^(x/3), x in 1..9."""
    fig = Figure(figsize=(6, 4), dpi=dpi)
    ax = fig.add_subplot(111)
    xs = list(range(1, 10))
    ys = [10 ** (x / 3.0) for x in xs]
    ax.scatter(xs, ys, c="red", s=70, zorder=5)
    ax.set_yscale("log")
    ax.set_xlim(0, 10)
    ax.set_ylim(1, 1000)
    w, h = _save(fig, path)
    pts = [(x, y, *_to_px(ax, h, x, y)) for x, y in zip(xs, ys)]
    ticks_x = [(v, _to_px(ax, h, v, 1)[0]) for v in [0, 2, 4, 6, 8, 10]]
    ticks_y = [(v, _to_px(ax, h, 0, v)[1]) for v in [1, 10, 100, 1000]]
    return {
        "path": path, "w": w, "h": h, "points": pts,
        "ticks_x": ticks_x, "ticks_y": ticks_y,
        "plot_bbox": _axes_bbox_px(ax, h),
        "color_hsv": (0, 255, 255),
    }


def make_boxplot(path, dpi=150):
    """Single filled box plot; records the drawn Q1/Q3/median/whisker data values."""
    fig = Figure(figsize=(5, 4), dpi=dpi)
    ax = fig.add_subplot(111)
    rng = np.random.default_rng(0)
    data = rng.normal(50, 12, 400)
    bp = ax.boxplot(data, patch_artist=True, widths=0.5, whis=1.5)
    bp["boxes"][0].set_facecolor("#e07070")  # distinct fill
    for med in bp["medians"]:
        med.set_color("black"); med.set_linewidth(2)
    ax.set_ylim(0, 100)
    w, h = _save(fig, path)

    box_path = bp["boxes"][0].get_path().vertices
    ys_box = sorted({round(v[1], 6) for v in box_path})
    q1, q3 = ys_box[0], ys_box[-1]
    median = bp["medians"][0].get_ydata()[0]
    caps = bp["caps"]
    wl = min(caps[0].get_ydata()[0], caps[1].get_ydata()[0])
    wh = max(caps[0].get_ydata()[0], caps[1].get_ydata()[0])
    return {
        "path": path, "w": w, "h": h,
        "plot_bbox": _axes_bbox_px(ax, h),
        "box_color_hsv": None,  # filled with #e07070; test computes from pixel
        "truth": {"q1": float(q1), "q3": float(q3), "median": float(median),
                  "whisker_low": float(wl), "whisker_high": float(wh)},
        "y_range": (0, 100),
    }


def make_pie(path, dpi=150):
    """Pie with known fractions and distinct colors."""
    fig = Figure(figsize=(5, 5), dpi=dpi)
    ax = fig.add_subplot(111)
    fracs = [0.4, 0.3, 0.2, 0.1]
    colors = ["#e01010", "#10a010", "#1010e0", "#e0a010"]
    ax.pie(fracs, colors=colors, startangle=0, counterclock=True)
    ax.set_aspect("equal")
    w, h = _save(fig, path)
    return {"path": path, "w": w, "h": h, "fractions": sorted(fracs, reverse=True)}


def make_heatmap(path, dpi=150):
    """imshow heatmap + vertical colorbar; records the matrix and colorbar geometry."""
    fig = Figure(figsize=(6, 5), dpi=dpi)
    ax = fig.add_subplot(111)
    rng = np.random.default_rng(1)
    mat = rng.uniform(0, 100, (5, 6))
    im = ax.imshow(mat, cmap="viridis", vmin=0, vmax=100, aspect="auto")
    cbar = fig.colorbar(im, ax=ax)
    w, h = _save(fig, path)
    grid_bbox = _axes_bbox_px(ax, h)
    cb_bbox = _axes_bbox_px(cbar.ax, h)
    return {
        "path": path, "w": w, "h": h,
        "matrix": mat, "grid_shape": mat.shape,
        "plot_bbox": grid_bbox,
        "colorbar_bbox": cb_bbox,
        "colorbar_range": (0, 100),
    }


def make_composite_2x2(path, dpi=150):
    """2x2 grid of colored panels for split_panels testing."""
    fig = Figure(figsize=(6, 5), dpi=dpi)
    axes = fig.subplots(2, 2)
    for a in axes.flat:
        a.plot([0, 1], [0, 1])
    fig.subplots_adjust(wspace=0.4, hspace=0.4)
    w, h = _save(fig, path)
    return {"path": path, "w": w, "h": h}
