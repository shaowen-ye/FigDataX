"""FigDataX core utilities — image I/O, color helpers, and geometry detection.

This module depends ONLY on cv2 + numpy so it can be imported and used on any
Python that has OpenCV installed, without pulling in scipy or matplotlib.

Conventions used throughout FigDataX (the #1 source of mistakes):
  * OpenCV images are **BGR**, not RGB.
  * OpenCV HSV hue is in **[0, 179]** (degrees / 2), not [0, 360]. S, V are [0, 255].
  * Pixels are indexed ``img[y, x]`` (row first). Pixel y increases *downward*, so
    data-space y is inverted relative to pixel-space y.
  * ``cv2.imread`` returns ``None`` (does not raise) on a bad path — always checked.
"""

from __future__ import annotations

import importlib
import logging
import os
from typing import Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger("figdatax")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

ImageLike = Union[str, "os.PathLike[str]", np.ndarray]


# ───────────────────────────────────────────────────────────────────
#  Error hierarchy
# ───────────────────────────────────────────────────────────────────

class FigDataXError(Exception):
    """Base class for all FigDataX-raised errors."""


class InputError(FigDataXError):
    """Invalid image, path, or argument supplied by the caller."""


class CalibrationError(FigDataXError):
    """Axis calibration could not be fitted (bad points, log of <= 0, etc.)."""


class DetectionError(FigDataXError):
    """A detector could not find the requested structure in the image."""


def _require(module_name: str, feature: str):
    """Import an optional heavy dependency, with an actionable error message."""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise FigDataXError(
            f"{feature} requires the '{module_name}' package, which is not "
            f"installed. Bootstrap the skill environment with "
            f"`bash scripts/setup.sh` and run FigDataX with "
            f"`<skill_dir>/.venv/bin/python`."
        ) from None


# ───────────────────────────────────────────────────────────────────
#  Image loading / normalization
# ───────────────────────────────────────────────────────────────────

def _load_bgr(img_or_path: ImageLike) -> np.ndarray:
    """Load/normalize an image to a contiguous 8-bit **BGR** ndarray.

    Accepts a file path or an existing ndarray. Handles grayscale, RGBA/BGRA,
    and 16-bit inputs so downstream ``cv2.cvtColor(..., BGR2HSV)`` never crashes.

    Raises:
        InputError: path cannot be read, or the array has an unsupported shape.
    """
    if isinstance(img_or_path, np.ndarray):
        img = img_or_path
    else:
        path = os.fspath(img_or_path)
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise InputError(f"Could not read image (path invalid or unsupported): {path}")

    if img.dtype != np.uint8:
        # 16-bit (or float) → scale to 8-bit.
        if np.issubdtype(img.dtype, np.integer):
            maxv = float(np.iinfo(img.dtype).max) or 255.0
            img = (img.astype(np.float64) / maxv * 255.0).round().astype(np.uint8)
        else:
            fmax = float(np.nanmax(img)) if img.size else 1.0
            scale = 255.0 / fmax if fmax > 0 else 255.0
            img = (np.nan_to_num(img) * scale).clip(0, 255).astype(np.uint8)

    if img.ndim == 2:  # grayscale
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    if img.ndim == 3:
        ch = img.shape[2]
        if ch == 3:
            return np.ascontiguousarray(img)
        if ch == 4:  # BGRA → composite over white, drop alpha
            bgr = img[:, :, :3].astype(np.float64)
            alpha = img[:, :, 3:4].astype(np.float64) / 255.0
            white = np.full_like(bgr, 255.0)
            comp = bgr * alpha + white * (1.0 - alpha)
            return np.ascontiguousarray(comp.round().astype(np.uint8))
        if ch == 1:
            return cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR)

    raise InputError(f"Unsupported image shape {img.shape}; expected 2-D or 3-D (1/3/4 channels).")


# ───────────────────────────────────────────────────────────────────
#  Color helpers
# ───────────────────────────────────────────────────────────────────

def hsv_of_bgr(bgr: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Convert a single ``(B, G, R)`` triple to OpenCV HSV (H in [0, 179])."""
    px = np.uint8([[list(bgr)]])
    h, s, v = cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0][0]
    return int(h), int(s), int(v)


def bgr_of_hsv(hsv: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Convert a single OpenCV ``(H, S, V)`` triple to ``(B, G, R)``."""
    px = np.uint8([[list(hsv)]])
    b, g, r = cv2.cvtColor(px, cv2.COLOR_HSV2BGR)[0][0]
    return int(b), int(g), int(r)


def pick_color(img_or_path: ImageLike, x: int, y: int, radius: int = 2) -> dict:
    """Sample the color at pixel ``(x, y)`` — the reliable way to get a target HSV.

    Returns the **median** color in a small window (robust to anti-aliasing) as a
    dict with ``hsv``, ``bgr`` and ``hex`` (``#RRGGBB``) keys. Use the ``hsv`` value
    as ``target_hsv`` for the color-based extractors instead of guessing.

    Raises:
        InputError: the coordinate is outside the image.
    """
    img = _load_bgr(img_or_path)
    h, w = img.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        raise InputError(f"pick_color: ({x}, {y}) outside image of size {w}x{h}")

    x0, x1 = max(0, x - radius), min(w, x + radius + 1)
    y0, y1 = max(0, y - radius), min(h, y + radius + 1)
    patch = img[y0:y1, x0:x1].reshape(-1, 3)
    med_bgr = np.median(patch, axis=0).round().astype(int)
    b, g, r = int(med_bgr[0]), int(med_bgr[1]), int(med_bgr[2])
    hsv = hsv_of_bgr((b, g, r))
    return {"hsv": hsv, "bgr": (b, g, r), "hex": f"#{r:02x}{g:02x}{b:02x}"}


def _hsv_distance(hsv_img: np.ndarray, target_hsv: Tuple[int, int, int]) -> np.ndarray:
    """Per-pixel Euclidean color distance in HSV space (hue treated as circular).

    Hue difference is scaled ×2 so it is comparable to S/V on a 0-255 footing.
    ``hsv_img`` may be a full ``HxWx3`` image or an ``Nx3`` array of pixels.
    """
    hsv = hsv_img.astype(np.float64)
    h_t, s_t, v_t = target_hsv
    h = hsv[..., 0]
    h_diff = np.minimum(np.abs(h - h_t), 180.0 - np.abs(h - h_t)) * 2.0
    s_diff = hsv[..., 1] - s_t
    v_diff = hsv[..., 2] - v_t
    return np.sqrt(h_diff ** 2 + s_diff ** 2 + v_diff ** 2)


# ───────────────────────────────────────────────────────────────────
#  Plot-area / axis detection (Hough)
# ───────────────────────────────────────────────────────────────────

def _iter_hough_segments(lines):
    """Yield (x1, y1, x2, y2) from HoughLinesP output regardless of OpenCV version.

    OpenCV <5 returns shape ``(N, 1, 4)``; OpenCV >=5 returns ``(N, 4)``. Reshaping
    to ``(-1, 4)`` normalizes both. This is the fix for the crash on cv2 4.13/5.0.
    """
    if lines is None:
        return
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        yield int(x1), int(y1), int(x2), int(y2)


def _cluster_lines(positions, threshold: int = 15):
    """Cluster nearby 1-D line positions and return sorted cluster centers."""
    if not positions:
        return []
    positions = sorted(positions)
    clusters = [[positions[0]]]
    for p in positions[1:]:
        if p - clusters[-1][-1] < threshold:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return [float(np.mean(c)) for c in clusters]


def auto_detect_plot_area(img_or_path: ImageLike) -> Optional[Tuple[int, int, int, int]]:
    """Detect the plot-area bounding box via Hough line detection.

    Finds the outermost strong horizontal and vertical lines forming the axes
    frame. Returns ``(left, top, right, bottom)`` in pixels, or ``None`` if a
    plausible frame could not be found (caller should fall back to a manual bbox).
    """
    img = _load_bgr(img_or_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    h, w = gray.shape
    min_line_len = int(min(h, w) * 0.3)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=min_line_len, maxLineGap=10)

    horizontals, verticals = [], []
    for x1, y1, x2, y2 in _iter_hough_segments(lines):
        angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if angle < 5 or angle > 175:      # horizontal
            horizontals.append(min(y1, y2))
        elif 85 < angle < 95:             # vertical
            verticals.append(min(x1, x2))

    if len(horizontals) < 2 or len(verticals) < 2:
        logger.debug("auto_detect_plot_area: too few axis lines (h=%d, v=%d)",
                     len(horizontals), len(verticals))
        return None

    h_clusters = _cluster_lines(horizontals, threshold=15)
    v_clusters = _cluster_lines(verticals, threshold=15)
    if len(h_clusters) < 2 or len(v_clusters) < 2:
        return None

    top, bottom = int(h_clusters[0]), int(h_clusters[-1])
    left, right = int(v_clusters[0]), int(v_clusters[-1])

    if right - left < w * 0.2 or bottom - top < h * 0.2:
        logger.debug("auto_detect_plot_area: detected frame too small, rejecting")
        return None

    return (left, top, right, bottom)


def detect_axes_hough(img_or_path: ImageLike) -> Optional[dict]:
    """Return axis line segments and plot bbox derived from the detected frame."""
    bbox = auto_detect_plot_area(img_or_path)
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    return {
        "x_axis": (left, bottom, right, bottom),
        "y_axis": (left, top, left, bottom),
        "plot_bbox": bbox,
    }


# ───────────────────────────────────────────────────────────────────
#  Grid removal
# ───────────────────────────────────────────────────────────────────

def remove_grid(img_or_path: ImageLike, method: str = "adaptive",
                grid_color_hsv: Optional[Tuple[int, int, int]] = None) -> np.ndarray:
    """Remove grid lines to improve color-based detection.

    Methods:
        ``"hough"``   detect straight grid lines and inpaint them.
        ``"color"``   inpaint thin runs matching ``grid_color_hsv``.
        ``"adaptive"`` Hough first, then color (if a color is given).

    Returns a cleaned BGR image (input is never mutated).
    """
    img = _load_bgr(img_or_path)
    result = img.copy()

    if method in ("hough", "adaptive"):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 30, 100, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60,
                                minLineLength=50, maxLineGap=5)
        mask = np.zeros(gray.shape, dtype=np.uint8)
        drew = False
        for x1, y1, x2, y2 in _iter_hough_segments(lines):
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if angle < 3 or angle > 177 or (87 < angle < 93):
                cv2.line(mask, (x1, y1), (x2, y2), 255, 2)
                drew = True
        if drew:
            result = cv2.inpaint(result, mask, 3, cv2.INPAINT_TELEA)
        elif method == "hough":
            return result

    if method in ("color", "adaptive") and grid_color_hsv is not None:
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
        h, s, v = grid_color_hsv
        lower = np.array([max(0, h - 10), 0, max(0, v - 30)])
        upper = np.array([min(179, h + 10), 60, min(255, v + 30)])
        grid_mask = cv2.inRange(hsv, lower, upper)
        kernel = np.ones((3, 3), np.uint8)
        thick = cv2.dilate(grid_mask, kernel, iterations=2)
        thin_lines = cv2.bitwise_and(
            grid_mask, cv2.bitwise_not(cv2.erode(thick, kernel, iterations=2)))
        result = cv2.inpaint(result, thin_lines, 3, cv2.INPAINT_TELEA)

    return result


# ───────────────────────────────────────────────────────────────────
#  Grid overlay for manual reading
# ───────────────────────────────────────────────────────────────────

def generate_grid_overlay(img_or_path: ImageLike, output_path: Optional[str] = None,
                          spacing: Tuple[int, int, int] = (10, 50, 200),
                          plot_bbox: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
    """Draw a 3-level (fine/mid/major) coordinate grid for precise manual reading.

    ``spacing`` = ``(fine, mid, major)`` pixel steps. Fine (10px) grid gives ~±5px
    reading precision; mid (50px) and major (200px) carry coordinate labels.
    Saves to ``output_path`` (auto ``<stem>_grid.png`` when a path was given).
    Returns the overlay BGR image.
    """
    if isinstance(img_or_path, (str, os.PathLike)):
        img = _load_bgr(img_or_path)
        if output_path is None:
            base, _ = os.path.splitext(os.fspath(img_or_path))
            output_path = f"{base}_grid.png"
    else:
        img = _load_bgr(img_or_path)

    overlay = img.copy()
    h, w = overlay.shape[:2]
    fine, mid, major = spacing
    x0, y0, x1, y1 = plot_bbox if plot_bbox else (0, 0, w, h)

    for x in range(x0, x1 + 1, fine):
        cv2.line(overlay, (x, y0), (x, y1), (210, 210, 210), 1)
    for y in range(y0, y1 + 1, fine):
        cv2.line(overlay, (x0, y), (x1, y), (210, 210, 210), 1)

    for x in range(x0, x1 + 1, mid):
        cv2.line(overlay, (x, y0), (x, y1), (150, 150, 150), 1)
    for y in range(y0, y1 + 1, mid):
        cv2.line(overlay, (x0, y), (x1, y), (150, 150, 150), 1)
    for x in range(x0, x1 + 1, mid):
        cv2.putText(overlay, str(x), (x + 1, max(y0 - 3, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.25, (100, 100, 100), 1)
    for y in range(y0, y1 + 1, mid):
        cv2.putText(overlay, str(y), (max(x0 - 28, 2), y + 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.25, (100, 100, 100), 1)

    for x in range(0, w + 1, major):
        cv2.line(overlay, (x, 0), (x, h), (0, 0, 255), 1)
        cv2.putText(overlay, str(x), (x + 2, 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
    for y in range(0, h + 1, major):
        cv2.line(overlay, (0, y), (w, y), (0, 0, 255), 1)
        cv2.putText(overlay, str(y), (2, y + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

    if output_path:
        cv2.imwrite(output_path, overlay)
    return overlay


# ───────────────────────────────────────────────────────────────────
#  Multi-panel splitting
# ───────────────────────────────────────────────────────────────────

def _find_splits(signal, min_gap: int = 10, threshold: int = 240):
    """Find centers of bright gaps (panel gutters) in a 1-D mean-intensity signal."""
    above = np.asarray(signal) > threshold
    splits, in_gap, gap_start = [], False, 0
    for i, val in enumerate(above):
        if val and not in_gap:
            in_gap, gap_start = True, i
        elif not val and in_gap:
            if i - gap_start >= min_gap:
                splits.append((gap_start + i) // 2)
            in_gap = False
    return splits


def split_panels(img_or_path: ImageLike, layout: str = "auto") -> dict:
    """Split a multi-panel figure into labeled sub-images (``{"a": img, ...}``).

    ``layout`` is ``"RxC"`` (e.g. ``"2x2"``, ``"1x3"``) or ``"auto"`` to detect the
    grid from bright gutters between panels.
    """
    img = _load_bgr(img_or_path)
    h, w = img.shape[:2]
    labels = "abcdefghijklmnop"

    if layout == "auto":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        n_rows = len(_find_splits(np.mean(gray, axis=1), min_gap=10, threshold=240)) + 1
        n_cols = len(_find_splits(np.mean(gray, axis=0), min_gap=10, threshold=240)) + 1
        layout = f"{n_rows}x{n_cols}"

    rows, cols = map(int, layout.split("x"))
    panel_h, panel_w = h // rows, w // cols

    panels, idx = {}, 0
    for r in range(rows):
        for c in range(cols):
            y0 = r * panel_h
            y1 = (r + 1) * panel_h if r < rows - 1 else h
            x0 = c * panel_w
            x1 = (c + 1) * panel_w if c < cols - 1 else w
            panels[labels[idx]] = img[y0:y1, x0:x1].copy()
            idx += 1
    return panels
