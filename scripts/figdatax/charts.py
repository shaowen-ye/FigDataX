"""Box plot, pie chart, and heatmap extraction.

These close the chart types advertised in the skill description. Each returns
data-unit values with provenance-friendly structure.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

from .core import DetectionError, _hsv_distance, _load_bgr
from .calibrate import AxisCalibration


# ───────────────────────────────────────────────────────────────────
#  Box plots
# ───────────────────────────────────────────────────────────────────

def extract_boxplot(img_or_path, plot_bbox, converter: AxisCalibration,
                    box_color_hsv: Tuple[int, int, int] = None,
                    median_color_hsv: Tuple[int, int, int] = None,
                    color_distance=40, min_box_width=6):
    """Extract five-number summaries from a box plot with filled colored boxes.

    Detects each box rectangle (Q1 = lower edge, Q3 = upper edge), the median line
    inside it, and the whisker caps above/below. Provide ``box_color_hsv`` (the fill
    color; use :func:`pick_color`). ``median_color_hsv`` optionally isolates the
    median line color (else the median is the strongest horizontal line in the box).

    Returns a list (sorted by x) of dicts with data-unit
    ``{x_center, q1, q3, median, whisker_low, whisker_high}``.
    """
    if box_color_hsv is None:
        raise DetectionError("extract_boxplot needs box_color_hsv (fill color of the boxes).")
    img = _load_bgr(img_or_path)
    left, top, right, bottom = plot_bbox
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Mask the box fill within the plot area.
    dist = _hsv_distance(hsv, box_color_hsv)
    mask = np.zeros(dist.shape, np.uint8)
    mask[top:bottom, left:right] = (dist[top:bottom, left:right] < color_distance).astype(np.uint8) * 255
    # Vertical closing bridges the thin median line (and box edge) that otherwise
    # splits the fill into two contours; keep it narrow to not merge adjacent boxes.
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 9)))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    boxes = []
    for c in sorted(contours, key=lambda c: cv2.boundingRect(c)[0]):
        x, y, w, h = cv2.boundingRect(c)
        if w < min_box_width or h < 3:
            continue
        q3_py, q1_py = y, y + h  # image y grows downward: top edge = higher value = Q3

        # Median: strongest horizontal line in the box INTERIOR (exclude the box
        # edges, which are also dark and would otherwise win argmax).
        pad = max(2, int(h * 0.12))
        iy0, iy1 = y + pad, y + h - pad
        if iy1 <= iy0:
            iy0, iy1 = y, y + h
        strip = img[iy0:iy1, x:x + w]
        if median_color_hsv is not None:
            band = _hsv_distance(cv2.cvtColor(strip, cv2.COLOR_BGR2HSV), median_color_hsv)
            score = (band < color_distance).sum(axis=1)
        else:
            g = gray[iy0:iy1, x:x + w]
            score = (g < 100).sum(axis=1)
        med_py = iy0 + int(np.argmax(score)) if score.size and score.max() > 0 else y + h // 2

        # Whiskers: follow the thin vertical stem at the box center column up/down.
        cx = x + w // 2
        whisker_hi_py = _follow_stem(gray, cx, q3_py, -1, top)
        whisker_lo_py = _follow_stem(gray, cx, q1_py, +1, bottom)

        def val(py):
            return converter.pixel_to_data(cx, py)[1]

        boxes.append({
            "x_center": float(cx),
            "q1": val(q1_py), "q3": val(q3_py), "median": val(med_py),
            "whisker_low": val(whisker_lo_py), "whisker_high": val(whisker_hi_py),
        })
    return boxes


def _follow_stem(gray, cx, start_py, step, limit_py, max_gap=3):
    """Walk a thin dark vertical stem from ``start_py`` until it ends; return the cap y."""
    h = gray.shape[0]
    last, gap, y = start_py, 0, start_py + step
    while (step < 0 and y >= max(0, limit_py)) or (step > 0 and y < min(h, limit_py)):
        row = gray[y, max(0, cx - 2):cx + 3]
        if row.size and row.min() < 110:
            last, gap = y, 0
        else:
            gap += 1
            if gap > max_gap:
                break
        y += step
    return last


# ───────────────────────────────────────────────────────────────────
#  Pie charts
# ───────────────────────────────────────────────────────────────────

def extract_pie(img_or_path, center=None, radius=None, n_samples=1440,
                sat_min=40, val_min=40, boundary_distance=25, min_wedge_deg=3.0):
    """Extract wedge fractions from a pie chart by angular color segmentation.

    Locates the disc (Hough circle / largest contour if ``center``/``radius`` omitted),
    samples colors around a ring at 0.7·r, and splits into wedges at color-change
    boundaries. Angle convention: 0° = +x (east), counter-clockwise.

    Returns wedges sorted by ``start_deg``: dicts with
    ``{color_hsv, hex, start_deg, end_deg, fraction}``. ``fraction`` sums to ~1.0.
    """
    img = _load_bgr(img_or_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w = img.shape[:2]

    if center is None or radius is None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        circles = cv2.HoughCircles(cv2.medianBlur(gray, 5), cv2.HOUGH_GRADIENT, 1,
                                   minDist=min(h, w), param1=100, param2=30,
                                   minRadius=int(min(h, w) * 0.1),
                                   maxRadius=int(min(h, w) * 0.5))
        if circles is None:
            raise DetectionError("extract_pie: could not locate the pie disc; pass center and radius.")
        cx, cy, r = circles[0][0]
        center = (float(cx), float(cy))
        radius = float(r)
    cx, cy = center
    ring_r = radius * 0.7

    samples = []  # (theta_deg, hsv)
    for i in range(n_samples):
        theta = 360.0 * i / n_samples
        rad = np.radians(theta)
        px = int(round(cx + ring_r * np.cos(rad)))
        py = int(round(cy - ring_r * np.sin(rad)))
        if 0 <= px < w and 0 <= py < h:
            samples.append((theta, hsv[py, px].astype(float)))

    if len(samples) < n_samples * 0.5:
        raise DetectionError("extract_pie: ring sampling fell outside the image; check center/radius.")

    # Segment where consecutive ring colors jump.
    thetas = np.array([s[0] for s in samples])
    cols = np.array([s[1] for s in samples])
    boundaries = [0]
    for i in range(1, len(cols)):
        if float(_hsv_distance(cols[i:i + 1], tuple(cols[i - 1]))[0]) > boundary_distance:
            boundaries.append(i)
    boundaries.append(len(cols))

    wedges = []
    for b in range(len(boundaries) - 1):
        i0, i1 = boundaries[b], boundaries[b + 1]
        if i1 - i0 < 2:
            continue
        seg = cols[i0:i1]
        med = np.median(seg, axis=0)
        s, v = med[1], med[2]
        if s < sat_min and v < val_min:  # skip background/edges
            continue
        span = 360.0 * (i1 - i0) / len(cols)
        if span < min_wedge_deg:  # drop anti-aliased boundary slivers
            continue
        start = float(thetas[i0])
        end = float(thetas[i1 - 1])
        h_, s_, v_ = int(med[0]), int(med[1]), int(med[2])
        b_, g_, r_ = cv2.cvtColor(np.uint8([[[h_, s_, v_]]]), cv2.COLOR_HSV2BGR)[0][0]
        wedges.append({"color_hsv": (h_, s_, v_),
                       "hex": f"#{int(r_):02x}{int(g_):02x}{int(b_):02x}",
                       "start_deg": start, "end_deg": end,
                       "_span": span})

    # Merge adjacent wedges of the same color (wrap-around split), compute fractions.
    wedges = _merge_wrap_wedges(wedges, boundary_distance)
    total = sum(wd["_span"] for wd in wedges) or 360.0
    for wd in wedges:
        wd["fraction"] = wd.pop("_span") / total
    wedges.sort(key=lambda wd: wd["start_deg"])
    return wedges


def _merge_wrap_wedges(wedges, boundary_distance):
    if len(wedges) < 2:
        return wedges
    first, last = wedges[0], wedges[-1]
    if float(_hsv_distance(np.array([first["color_hsv"]], float),
                           last["color_hsv"])[0]) < boundary_distance:
        first["_span"] += last["_span"]
        first["start_deg"] = last["start_deg"]
        wedges = wedges[:-1]
    return wedges


# ───────────────────────────────────────────────────────────────────
#  Heatmaps
# ───────────────────────────────────────────────────────────────────

def extract_heatmap(img_or_path, plot_bbox, grid_shape, colorbar_bbox, colorbar_range,
                    colorbar_orientation="vertical", inset=0.2):
    """Extract a heatmap grid into a numeric matrix via colorbar calibration.

    Args:
        plot_bbox: (left, top, right, bottom) of the heatmap grid area.
        grid_shape: (n_rows, n_cols) of cells.
        colorbar_bbox: (left, top, right, bottom) of the colorbar strip (user-supplied;
            not auto-detected).
        colorbar_range: (value_at_low_end, value_at_high_end) of the colorbar.
        colorbar_orientation: "vertical" (top=high) or "horizontal" (right=high).
        inset: fraction of each cell trimmed on all sides before sampling (avoids borders).

    Returns:
        (matrix, dataframe-ready) — a float ndarray of shape ``grid_shape`` with the
        estimated value per cell, mapped through nearest-neighbor in CIELab space.
    """
    img = _load_bgr(img_or_path)
    left, top, right, bottom = plot_bbox
    n_rows, n_cols = grid_shape

    # Build colorbar LUT: sampled Lab colors ↔ values along the strip.
    cb_l, cb_t, cb_r, cb_b = colorbar_bbox
    strip = img[cb_t:cb_b, cb_l:cb_r]
    lab_strip = cv2.cvtColor(strip, cv2.COLOR_BGR2Lab).astype(np.float32)
    lo_val, hi_val = colorbar_range

    if colorbar_orientation == "vertical":
        line = lab_strip.mean(axis=1)          # (H,3), index 0 = top
        n = line.shape[0]
        vals = np.linspace(hi_val, lo_val, n)  # top = high
    else:
        line = lab_strip.mean(axis=0)          # (W,3), index 0 = left
        n = line.shape[0]
        vals = np.linspace(lo_val, hi_val, n)  # right = high
    lut_lab = line                              # (n,3)

    cell_h = (bottom - top) / n_rows
    cell_w = (right - left) / n_cols
    matrix = np.zeros((n_rows, n_cols), dtype=float)

    for i in range(n_rows):
        for j in range(n_cols):
            y0 = int(top + (i + inset) * cell_h)
            y1 = int(top + (i + 1 - inset) * cell_h)
            x0 = int(left + (j + inset) * cell_w)
            x1 = int(left + (j + 1 - inset) * cell_w)
            patch = img[max(y0, top):max(y1, y0 + 1), max(x0, left):max(x1, x0 + 1)]
            if patch.size == 0:
                matrix[i, j] = np.nan
                continue
            lab = cv2.cvtColor(patch, cv2.COLOR_BGR2Lab).astype(np.float32)
            med = np.median(lab.reshape(-1, 3), axis=0)
            d = np.linalg.norm(lut_lab - med, axis=1)
            matrix[i, j] = float(vals[int(np.argmin(d))])

    return matrix
