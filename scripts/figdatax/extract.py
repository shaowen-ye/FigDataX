"""Data-point extraction — color detection, scatter/bar/error-bar/polar, curve tracing.

Color extractors need only cv2+numpy. Curve tracing / interpolation import scipy
lazily so the rest of the module works without it.
"""

from __future__ import annotations

import warnings
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .core import (DetectionError, _hsv_distance, _load_bgr, _require, logger)
from .calibrate import AxisCalibration, calibrate_axes


def _hsv_scalar_distance(a, b) -> float:
    """Euclidean distance between two (H, S, V) triples, hue circular and ×2-scaled."""
    dh = min(abs(a[0] - b[0]), 180 - abs(a[0] - b[0])) * 2
    return (dh ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


# ───────────────────────────────────────────────────────────────────
#  Color-based centroid extraction
# ───────────────────────────────────────────────────────────────────

def _subpixel_refine(hsv, cx_init, cy_init, target_hsv, radius=5):
    """Gaussian-weighted sub-pixel centroid refinement (Engauge-style)."""
    h, w = hsv.shape[:2]
    x0, x1 = max(0, int(cx_init) - radius), min(w, int(cx_init) + radius + 1)
    y0, y1 = max(0, int(cy_init) - radius), min(h, int(cy_init) + radius + 1)
    region = hsv[y0:y1, x0:x1]
    dist = _hsv_distance(region, target_hsv)
    weights = np.exp(-dist ** 2 / (2 * 30.0 ** 2))
    total = float(np.sum(weights))
    if total < 1e-10:
        return cx_init, cy_init
    yy, xx = np.mgrid[y0:y1, x0:x1]
    return float(np.sum(xx * weights) / total), float(np.sum(yy * weights) / total)


def _merge_nearby(detections, distance):
    """Area-weighted merge of detections whose centers are within ``distance`` px."""
    if not detections:
        return detections
    merged, used = [], set()
    for i, (cx1, cy1, a1, conf1) in enumerate(detections):
        if i in used:
            continue
        gx, gy, ga, gconf = [cx1 * a1], [cy1 * a1], [a1], [conf1]
        for j in range(i + 1, len(detections)):
            if j in used:
                continue
            cx2, cy2, a2, conf2 = detections[j]
            if np.hypot(cx1 - cx2, cy1 - cy2) < distance:
                gx.append(cx2 * a2); gy.append(cy2 * a2)
                ga.append(a2); gconf.append(conf2); used.add(j)
        total_a = sum(ga) or 1.0
        merged.append((sum(gx) / total_a, sum(gy) / total_a, sum(ga), max(gconf)))
    return merged


def extract_by_color_adaptive(img_or_path, target_hsv, color_distance=25,
                              min_area=8, merge_distance=5, subpixel=False,
                              auto_widen=False):
    """Detect data-point centroids by HSV color distance.

    Args:
        target_hsv: target color; get it reliably with :func:`pick_color`, don't guess.
        color_distance: max Euclidean HSV distance (hue scaled ×2; range ~0-360).
        min_area: minimum blob area in pixels.
        merge_distance: merge detections closer than this (px); 0 disables.
        subpixel: Gaussian-weighted sub-pixel refinement.
        auto_widen: if nothing is found, retry with a widened threshold (up to 80).

    Returns:
        list of ``(cx, cy, area, confidence)`` sorted by x. Empty list if nothing
        matched — a warning names the nearest dominant color to help you fix the target.
    """
    img = _load_bgr(img_or_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    dist = _hsv_distance(hsv, target_hsv)

    thresholds = [color_distance]
    if auto_widen:
        thresholds += [t for t in (color_distance * 1.5, color_distance * 2.5, 80.0)
                       if t > color_distance]

    detections = []
    used_threshold = color_distance
    for thr in thresholds:
        mask = (dist < thr).astype(np.uint8) * 255
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue
            M = cv2.moments(c)
            if M["m00"] == 0:
                continue
            cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
            if subpixel:
                cx, cy = _subpixel_refine(hsv, cx, cy, target_hsv)
            single = np.zeros(mask.shape, np.uint8)
            cv2.drawContours(single, [c], -1, 255, -1)
            mean_dist = float(np.mean(dist[single > 0]))
            conf = max(0.0, 1.0 - mean_dist / thr)
            detections.append((float(cx), float(cy), float(area), float(conf)))
        used_threshold = thr
        if detections:
            break

    if not detections:
        _warn_no_detections(img, hsv, target_hsv, used_threshold)
        return []

    if used_threshold != color_distance:
        warnings.warn(f"extract_by_color_adaptive: no points at color_distance="
                      f"{color_distance}; auto-widened to {used_threshold:.0f}.")
    if merge_distance > 0:
        detections = _merge_nearby(detections, merge_distance)
    detections.sort(key=lambda d: d[0])
    return detections


def _warn_no_detections(img, hsv, target_hsv, threshold):
    """Emit an actionable warning naming the nearest dominant color to the target."""
    try:
        h, w = img.shape[:2]
        colors = detect_data_colors(img, (0, 0, w, h), n_clusters=4)
    except Exception:  # noqa: BLE001
        colors = []
    if colors:
        nearest = min(colors, key=lambda c: float(_hsv_distance(np.array([[c[1]]]), target_hsv)[0, 0]))
        d = float(_hsv_distance(np.array([[nearest[1]]]), target_hsv)[0, 0])
        warnings.warn(
            f"extract_by_color_adaptive: 0 points for target HSV {tuple(target_hsv)} "
            f"at color_distance={threshold:.0f}. Nearest dominant color is "
            f"{nearest[0]} HSV {nearest[1]} (distance {d:.0f}). Use pick_color() on a "
            f"marker to get the exact HSV, or raise color_distance / pass auto_widen=True.")
    else:
        warnings.warn(
            f"extract_by_color_adaptive: 0 points for target HSV {tuple(target_hsv)}. "
            f"Verify the marker color with pick_color() and check the plot area.")


def extract_by_color(img_or_path, target_hsv, tolerance=15, min_area=10):
    """Legacy simple color extraction → list of ``(cx, cy)``."""
    res = extract_by_color_adaptive(img_or_path, target_hsv,
                                    color_distance=tolerance * 3, min_area=min_area)
    return [(cx, cy) for cx, cy, _, _ in res]


# ───────────────────────────────────────────────────────────────────
#  Auto color detection (K-means, deterministic)
# ───────────────────────────────────────────────────────────────────

_HUE_NAMES = [
    (0, "red"), (15, "orange"), (25, "yellow"), (45, "green"), (75, "cyan"),
    (100, "blue"), (130, "purple"), (150, "magenta"), (170, "red"),
]


def _hue_name(h, s, v):
    if v < 40:
        return "black"
    if s < 30:
        return "white" if v > 200 else "gray"
    return min(_HUE_NAMES, key=lambda hn: min(abs(h - hn[0]), 180 - abs(h - hn[0])))[1]


def detect_data_colors(img_or_path, plot_bbox, n_clusters=4,
                       min_saturation=30, min_value=30, seed=42):
    """Auto-detect dominant data colors in the plot area via K-means (deterministic).

    Filters near-background pixels (low saturation = white/gray, or very dark),
    then clusters the rest. Returns a list of ``(name, (H, S, V))`` sorted by
    prevalence; ``name`` is a hue label ("red", "blue", ...).

    Background removal is by *saturation* (white/gray have low S), not a high-value
    cutoff — bright saturated markers (e.g. pure red, V=255) are real data.
    """
    img = _load_bgr(img_or_path)
    left, top, right, bottom = plot_bbox
    region = cv2.cvtColor(img[top:bottom, left:right], cv2.COLOR_BGR2HSV)
    pixels = region.reshape(-1, 3).astype(np.float32)

    mask = (pixels[:, 1] > min_saturation) & (pixels[:, 2] > min_value)
    fg = pixels[mask]
    if len(fg) < n_clusters * 10:
        return []

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    cv2.setRNGSeed(int(seed))
    _, labels, centers = cv2.kmeans(fg, n_clusters, None, criteria, 10, cv2.KMEANS_PP_CENTERS)
    _, counts = np.unique(labels, return_counts=True)

    results = []
    for idx in np.argsort(-counts):
        h, s, v = (int(round(c)) for c in centers[idx])
        results.append((_hue_name(h, s, v), (h, s, v)))
    return results


def suggest_series(img_or_path, plot_bbox, n_clusters: int = 6,
                   min_fraction: float = 0.002, color_distance: float = 30.0) -> list:
    """Suggest ready-to-use data series from a chart's colors and their geometry.

    Wraps :func:`detect_data_colors`, then for each color measures how it is laid out
    (connected-component analysis inside the plot area) so the caller can hand the
    ``hsv`` straight to the color extractors without any eyedropper step, and knows
    whether it is markers, a line, or a filled region. The legend name↔color mapping
    is left to the caller's vision (that is a semantic, not geometric, judgment).

    Returns dicts sorted by prevalence::

        [{"name": "red", "hsv": [3, 212, 231], "pixel_fraction": 0.031,
          "n_components": 11, "geometry": "markers"}]   # markers | line | region

    Heuristics: many small compact blobs → "markers"; one/two long thin components →
    "line"; otherwise → "region" (bars/areas/pie wedges).
    """
    img = _load_bgr(img_or_path)
    left, top, right, bottom = (int(v) for v in plot_bbox)
    area = max(1, (right - left) * (bottom - top))
    hsv_full = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # K-means often splits one visual color into several near-identical clusters;
    # merge clusters whose HSV are within this distance so each real series appears once.
    merged_colors = []
    for name, hsv in detect_data_colors(img, plot_bbox, n_clusters=n_clusters):
        if any(_hsv_scalar_distance(hsv, k) < 18 for _n, k in merged_colors):
            continue
        merged_colors.append((name, hsv))

    out = []
    for name, hsv in merged_colors:
        dist = _hsv_distance(hsv_full, hsv)
        mask = np.zeros(img.shape[:2], np.uint8)
        mask[top:bottom, left:right] = (
            dist[top:bottom, left:right] < color_distance).astype(np.uint8)
        frac = float(mask.sum()) / area
        if frac < min_fraction:
            continue
        n_lbl, _lbls, stats, _cent = cv2.connectedComponentsWithStats(mask, connectivity=8)
        comps = [stats[i] for i in range(1, n_lbl) if stats[i, cv2.CC_STAT_AREA] >= 4]
        n_comp = len(comps)
        # Fill ratio = component area / its bounding-box area. Markers and filled
        # regions fill most of their box (~0.5-1.0); a thin winding line fills little.
        fills = [st[cv2.CC_STAT_AREA] / max(1, st[cv2.CC_STAT_WIDTH] * st[cv2.CC_STAT_HEIGHT])
                 for st in comps]
        # Largest component's span across the plot width (a line stretches across it).
        span = (max((st[cv2.CC_STAT_WIDTH] for st in comps), default=0)
                / max(1, right - left))
        med_fill = float(np.median(fills)) if fills else 0.0
        # Median component size relative to the plot area: markers are small dots,
        # bars/regions are large blocks.
        rel_size = float(np.median([st[cv2.CC_STAT_AREA] for st in comps]) / area) \
            if comps else 0.0
        geometry = "region"
        if n_comp >= 4 and med_fill >= 0.4 and rel_size < 0.005:
            geometry = "markers"
        elif n_comp <= 3 and med_fill < 0.3 and span > 0.4:
            geometry = "line"
        out.append({"name": name, "hsv": [int(v) for v in hsv],
                    "pixel_fraction": round(frac, 4), "n_components": n_comp,
                    "geometry": geometry})
    return out


# ───────────────────────────────────────────────────────────────────
#  Bar chart extraction
# ───────────────────────────────────────────────────────────────────

def auto_extract_bars(img_or_path, plot_bbox, y_range=None, colors_hsv=None,
                      converter: Optional[AxisCalibration] = None,
                      group_detection=False, stacked=False, min_bar_width=3):
    """Extract bar heights per color series.

    Calibrate y either with ``converter`` (an :class:`AxisCalibration`, preferred)
    or a simple ``y_range=(y_min, y_max)`` mapped linearly over the plot bbox.
    Returns ``{series_name: [values]}`` (or list of segment dicts when ``stacked``).
    """
    img = _load_bgr(img_or_path)
    if colors_hsv is None:
        raise DetectionError("auto_extract_bars requires colors_hsv={name: (H,S,V)}.")
    if converter is None:
        if y_range is None:
            raise DetectionError("Provide either converter or y_range.")
        converter = calibrate_axes(plot_bbox, (0.0, 1.0), y_range)

    left, top, right, bottom = plot_bbox
    region = img[top:bottom, left:right]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    plot_h, plot_w = bottom - top, right - left
    min_bar_area = plot_h * plot_w * 0.001

    def y_value(py_abs):
        return converter.pixel_to_data(0, py_abs)[1]

    results: Dict[str, list] = {}
    for name, (h, s, v) in colors_hsv.items():
        lower = np.array([max(0, h - 15), max(0, s - 60), max(0, v - 60)])
        upper = np.array([min(179, h + 15), min(255, s + 60), min(255, v + 60)])
        mask = cv2.inRange(hsv, lower, upper)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bars = []
        for c in sorted(contours, key=lambda c: cv2.boundingRect(c)[0]):
            x, y, w, bh = cv2.boundingRect(c)
            if cv2.contourArea(c) < min_bar_area or w < min_bar_width or bh < 3:
                continue
            top_abs = top + y
            bottom_abs = top + y + bh
            if stacked:
                top_val = y_value(top_abs)
                bottom_val = y_value(bottom_abs)
                bars.append({
                    "x_center": left + x + w / 2.0,
                    "value": abs(top_val - bottom_val),
                    "cumulative_top": top_val,
                })
            else:
                # Bar top pixel → data value (baseline handled by calibration).
                bars.append(y_value(top_abs))
        results[name] = bars
    return results


# ───────────────────────────────────────────────────────────────────
#  Scatter extraction
# ───────────────────────────────────────────────────────────────────

def auto_extract_scatter(img_or_path, plot_bbox, x_range=None, y_range=None,
                         target_hsv=(120, 200, 200), marker_size_range=(3, 30),
                         x_log=False, y_log=False, subpixel=True,
                         converter: Optional[AxisCalibration] = None):
    """Extract scatter points → list of ``(x_data, y_data, marker_area)``.

    Provide ``converter`` (preferred) or ``x_range``/``y_range`` for bbox calibration.
    """
    img = _load_bgr(img_or_path)
    left, top, right, bottom = plot_bbox
    if converter is None:
        if x_range is None or y_range is None:
            raise DetectionError("Provide either converter or both x_range and y_range.")
        converter = calibrate_axes(plot_bbox, x_range, y_range, x_log, y_log)

    detections = extract_by_color_adaptive(
        img, target_hsv, color_distance=30,
        min_area=marker_size_range[0] ** 2 * 0.5,
        merge_distance=marker_size_range[0], subpixel=subpixel)

    points = []
    for cx, cy, area, _ in detections:
        if left <= cx <= right and top <= cy <= bottom:
            dx, dy = converter.pixel_to_data(cx, cy)
            points.append((dx, dy, area))
    return points


# ───────────────────────────────────────────────────────────────────
#  Error bars
# ───────────────────────────────────────────────────────────────────

def extract_error_bars(img_or_path, centroids, converter: AxisCalibration,
                        error_color_hsv=(0, 0, 0), search_radius=20,
                        marker_clearance=4, col_window=2):
    """Extract error-bar whiskers above/below each data-point centroid.

    Scans up and down from each centroid (skipping ``marker_clearance`` px so the
    marker body itself is not read as the whisker) for contiguous runs matching
    ``error_color_hsv``. Returns dicts ``{"x","y","y_low","y_high"}`` in DATA units,
    with ``y_high >= y_low`` guaranteed.
    """
    img = _load_bgr(img_or_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h_img, w_img = img.shape[:2]

    def matches(y, x):
        if not (0 <= y < h_img and 0 <= x < w_img):
            return False
        d = float(_hsv_distance(hsv[y:y + 1, x:x + 1], error_color_hsv)[0, 0])
        return d < 60

    def col_matches(y, cx):
        return any(matches(y, cx + dx) for dx in range(-col_window, col_window + 1))

    def scan(cyi, cxi, step, max_gap):
        """Walk outward from the centroid; return the farthest whisker pixel.

        Gap-tolerant so the marker body itself (which is wider than the clearance)
        does not stop the scan before the whisker is reached.
        """
        far, gap = cyi, 0
        y = cyi + step * marker_clearance
        while 0 <= y < h_img and abs(y - cyi) <= search_radius:
            if col_matches(y, cxi):
                far, gap = y, 0
            else:
                gap += 1
                if gap > max_gap and far != cyi:
                    break
            y += step
        return far

    # gap tolerance spans the marker radius so the scan can cross the marker body
    max_gap = max(marker_clearance, 10)

    results = []
    for cx, cy in centroids:
        cxi, cyi = int(round(cx)), int(round(cy))
        top_py = scan(cyi, cxi, -1, max_gap)
        bot_py = scan(cyi, cxi, +1, max_gap)

        _, y_mean = converter.pixel_to_data(cx, cy)
        _, y_a = converter.pixel_to_data(cx, top_py)
        _, y_b = converter.pixel_to_data(cx, bot_py)
        dx, _ = converter.pixel_to_data(cx, cy)
        results.append({"x": dx, "y": y_mean,
                        "y_low": min(y_a, y_b), "y_high": max(y_a, y_b)})
    return results


# ───────────────────────────────────────────────────────────────────
#  Polar
# ───────────────────────────────────────────────────────────────────

def extract_polar(img_or_path, center, r_range, theta_range=(0, 360),
                  target_hsv=(120, 200, 200), n_angles=360, color_distance=40):
    """Extract a polar curve.

    ``center=(cx, cy)`` pixel origin; ``r_range=(r_min_data, r_max_data, r_max_px)``.
    Angle convention: 0° = +x (east), counter-clockwise; image-y inversion handled.
    Returns list of ``(r_data, theta_deg)``.
    """
    img = _load_bgr(img_or_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cx, cy = center
    r_min_d, r_max_d, r_max_px = r_range
    h_img, w_img = img.shape[:2]

    results = []
    for i in range(n_angles):
        theta = theta_range[0] + i * (theta_range[1] - theta_range[0]) / n_angles
        rad = np.radians(theta)
        best_r, best_dist = None, float("inf")
        for r_px in range(1, int(r_max_px)):
            px = int(round(cx + r_px * np.cos(rad)))
            py = int(round(cy - r_px * np.sin(rad)))
            if 0 <= px < w_img and 0 <= py < h_img:
                d = float(_hsv_distance(hsv[py:py + 1, px:px + 1], target_hsv)[0, 0])
                if d < color_distance and d < best_dist:
                    best_dist = d
                    best_r = r_min_d + (r_px / r_max_px) * (r_max_d - r_min_d)
        if best_r is not None:
            results.append((float(best_r), float(theta)))
    return results


# ───────────────────────────────────────────────────────────────────
#  Curve tracing (lazy scipy)
# ───────────────────────────────────────────────────────────────────

def trace_curve(img_or_path, plot_bbox, target_hsv, x_range=None, y_range=None,
                n_samples=200, spline_smoothing=0.01, color_distance=30,
                subpixel=True, x_log=False, y_log=False,
                converter: Optional[AxisCalibration] = None):
    """Trace a continuous colored curve by column scan + cubic-spline resample.

    Returns evenly x-spaced ``(x_data, y_data)`` points. Requires scipy.
    """
    interp = _require("scipy.interpolate", "trace_curve")
    signal = _require("scipy.signal", "trace_curve")
    CubicSpline = interp.CubicSpline

    img = _load_bgr(img_or_path)
    left, top, right, bottom = plot_bbox
    if converter is None:
        if x_range is None or y_range is None:
            raise DetectionError("Provide either converter or both x_range and y_range.")
        converter = calibrate_axes(plot_bbox, x_range, y_range, x_log, y_log)

    region = cv2.cvtColor(img[top:bottom, left:right], cv2.COLOR_BGR2HSV)
    region_w = right - left

    cols, rows = [], []
    for col in range(region_w):
        dist = _hsv_distance(region[:, col, :], target_hsv)
        matching = np.where(dist < color_distance)[0]
        if matching.size == 0:
            continue
        if subpixel:
            w = np.exp(-dist[matching] ** 2 / (2 * 5.0 ** 2))
            cy = float(np.sum(matching * w) / np.sum(w)) if np.sum(w) > 0 else float(np.mean(matching))
        else:
            cy = float(np.mean(matching))
        cols.append(col); rows.append(cy)

    if len(cols) < 4:
        return []
    cols = np.array(cols, float); rows = np.array(rows, float)

    # Collapse duplicate columns (mean row) before spline fit.
    uniq, inv = np.unique(cols, return_inverse=True)
    if uniq.size != cols.size:
        rows = np.array([rows[inv == k].mean() for k in range(uniq.size)])
        cols = uniq

    # Median-filter outlier rejection (guarded for short sequences).
    if len(rows) >= 7:
        window = min(11, len(rows) // 3)
        window = max(3, window + (1 - window % 2))  # nearest odd >= 3
        smoothed = signal.medfilt(rows, kernel_size=window)
        resid = np.abs(rows - smoothed)
        keep = resid < (np.median(resid) * 3 + 1)
        cols, rows = cols[keep], rows[keep]
    if len(cols) < 4:
        return []

    cs = CubicSpline(cols, rows, extrapolate=False)
    sample_cols = np.linspace(cols[0], cols[-1], n_samples)
    sample_rows = cs(sample_cols)

    result = []
    for c, r in zip(sample_cols, sample_rows):
        if np.isnan(r):
            continue
        dx, dy = converter.pixel_to_data(left + c, top + r)
        result.append((dx, dy))
    return result


def interpolate_curve(sparse_points: Sequence[Tuple[float, float]],
                      n_output=200, method="cubic_spline"):
    """Densify sparse ``(x, y)`` points via interpolation. Requires scipy.

    ``method``: ``"cubic_spline"`` (smooth) or ``"pchip"`` (monotone, no overshoot).
    """
    interp = _require("scipy.interpolate", "interpolate_curve")
    pts = sorted(sparse_points, key=lambda p: p[0])
    xs = np.array([p[0] for p in pts], float)
    ys = np.array([p[1] for p in pts], float)
    if xs.size < 2:
        raise DetectionError("interpolate_curve needs at least 2 points.")
    if np.any(np.diff(xs) == 0):
        raise DetectionError("interpolate_curve: duplicate x values are not allowed.")

    if method == "cubic_spline":
        fn = interp.CubicSpline(xs, ys)
    elif method == "pchip":
        fn = interp.PchipInterpolator(xs, ys)
    else:
        raise ValueError(f"Unknown method: {method}")

    x_dense = np.linspace(xs[0], xs[-1], n_output)
    return list(zip(x_dense.tolist(), fn(x_dense).tolist()))
