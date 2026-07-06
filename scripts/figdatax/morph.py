"""Same-color multi-series detection via morphology + crossover-aware assignment.

For charts where every series is the same color (e.g. all black) and differs only
by marker shape or line style, color detection fails. Erosion removes thin
connecting lines and keeps thick markers; markers are then grouped by x-position
and assigned to series while tracking curve crossovers.
"""

from __future__ import annotations

from itertools import permutations
from typing import List, Optional

import cv2
import numpy as np

from .core import _load_bgr


def detect_markers_morphological(img_or_path, plot_bbox, legend_bbox=None,
                                 threshold=100, kernel_size=4, erode_iterations=1,
                                 area_range=(60, 300), aspect_range=(0.6, 1.5),
                                 max_dim=20):
    """Detect marker centers by eroding away thin lines and keeping thick blobs.

    Returns ``(cx, cy, area, bbox_w, bbox_h)`` per marker, sorted by x.
    Tune ``kernel_size`` up if line fragments survive, down if markers vanish.
    """
    img = _load_bgr(img_or_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, dark = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)

    x0, y0, x1, y1 = plot_bbox
    plot_mask = np.zeros_like(dark)
    plot_mask[y0:y1, x0:x1] = dark[y0:y1, x0:x1]
    if legend_bbox:
        lx0, ly0, lx1, ly1 = legend_bbox
        plot_mask[ly0:ly1, lx0:lx1] = 0

    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    eroded = cv2.erode(plot_mask, kernel, iterations=erode_iterations)
    dilated = cv2.dilate(eroded, kernel, iterations=erode_iterations)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area, max_area = area_range
    min_aspect, max_aspect = aspect_range

    markers = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        if bw > max_dim or bh > max_dim:
            continue
        aspect = bw / bh if bh > 0 else 0
        if aspect < min_aspect or aspect > max_aspect:
            continue
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        markers.append((M["m10"] / M["m00"], M["m01"] / M["m00"], area, bw, bh))
    markers.sort(key=lambda m: m[0])
    return markers


def cluster_markers_by_x(markers, tolerance=25):
    """Group markers into x-position clusters; within each group sort top→bottom."""
    if not markers:
        return []
    ordered = sorted(markers, key=lambda m: m[0])
    groups = [[ordered[0]]]
    for m in ordered[1:]:
        if m[0] - groups[-1][-1][0] < tolerance:
            groups[-1].append(m)
        else:
            groups.append([m])
    for g in groups:
        g.sort(key=lambda m: m[1])
    return groups


def _best_assignment(group_ys, pred_y, n_series):
    """Permutation of markers→series minimizing total |Δy| from *predicted* positions.

    ``pred_y[s]`` is the extrapolated (trajectory-predicted) y for series ``s`` — using
    predictions rather than last positions lets curves cross instead of bouncing apart.
    Uses scipy's Hungarian algorithm when available, else brute-force permutations.
    """
    valid = [i for i in range(n_series) if pred_y[i] is not None]
    try:
        from scipy.optimize import linear_sum_assignment
        cost = np.zeros((n_series, n_series))
        for s in range(n_series):
            for m in range(n_series):
                cost[s, m] = abs(group_ys[m] - pred_y[s]) if pred_y[s] is not None else 0.0
        _, col = linear_sum_assignment(cost)
        return list(col)  # assignment[series] = marker index
    except ImportError:
        if n_series > 8:
            raise
        best, best_cost = None, float("inf")
        for perm in permutations(range(n_series)):
            c = sum(abs(group_ys[perm[i]] - pred_y[i]) for i in valid)
            if c < best_cost:
                best, best_cost = perm, c
        return list(best)


def assign_series_with_crossover(groups, n_series, series_names=None,
                                 initial_order="top_to_bottom"):
    """Assign per-x-group markers to series, tracking curve crossovers.

    Returns ``{series_name: [(cx, cy) | None, ...]}``. Missing markers (overlaps)
    become ``None``. Requires ``n_series <= 8`` without scipy.
    """
    if series_names is None:
        series_names = [f"Series_{i + 1}" for i in range(n_series)]
    result = {name: [] for name in series_names}
    prev_y: Optional[List[Optional[float]]] = None
    vel: Optional[List[float]] = None  # per-series velocity for trajectory prediction

    for group in groups:
        n_found = len(group)

        if n_found == n_series:
            if prev_y is None:
                order = range(n_series) if initial_order == "top_to_bottom" else range(n_series - 1, -1, -1)
                assignment = list(order)
            else:
                # Predict next position from the last velocity (enables crossovers).
                pred = [prev_y[s] + (vel[s] if vel else 0.0) if prev_y[s] is not None else None
                        for s in range(n_series)]
                assignment = _best_assignment([m[1] for m in group], pred, n_series)
            new_y = [group[assignment[s]][1] for s in range(n_series)]
            if prev_y is not None:
                vel = [new_y[s] - prev_y[s] for s in range(n_series)]
            for s in range(n_series):
                m = group[assignment[s]]
                result[series_names[s]].append((m[0], m[1]))
            prev_y = new_y

        elif n_found < n_series:
            if prev_y is not None and n_found > 0:
                assigned = set()
                for m in group:
                    cands = [(abs(m[1] - prev_y[i]), i) for i in range(n_series)
                             if i not in assigned and prev_y[i] is not None]
                    if cands:
                        _, idx = min(cands)
                        assigned.add(idx)
                        result[series_names[idx]].append((m[0], m[1]))
                        prev_y[idx] = m[1]
                for i in range(n_series):
                    if i not in assigned:
                        result[series_names[i]].append(None)
            else:
                for i in range(n_found):
                    result[series_names[i]].append((group[i][0], group[i][1]))
                for i in range(n_found, n_series):
                    result[series_names[i]].append(None)
                prev_y = prev_y or [None] * n_series
                for i in range(n_found):
                    prev_y[i] = group[i][1]

        else:  # more markers than series: keep the n largest by area
            trimmed = sorted(sorted(group, key=lambda m: m[2], reverse=True)[:n_series],
                             key=lambda m: m[1])
            sub = assign_series_with_crossover([trimmed], n_series, series_names, initial_order)
            for name in series_names:
                result[name].extend(sub[name])
            prev_y = [m[1] for m in trimmed]

    return result
