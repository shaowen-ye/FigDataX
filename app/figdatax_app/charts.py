"""Headless wrappers for the engine's box/pie/heatmap extractors.

Each returns a (columns, rows) table plus the raw engine result, so the GUI can show a
table and the Excel exporter can write it without knowing chart specifics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from . import engine_bridge as eng


@dataclass
class ChartResult:
    kind: str                    # "box" | "pie" | "heatmap"
    columns: List[str]
    rows: List[list]
    raw: object = None
    meta: dict = field(default_factory=dict)


def extract_box(image_bgr, plot_bbox, calibration, box_color_hsv,
                median_color_hsv=None, color_distance=40) -> ChartResult:
    boxes = eng.extract_boxplot(image_bgr, plot_bbox, calibration,
                                box_color_hsv=box_color_hsv,
                                median_color_hsv=median_color_hsv,
                                color_distance=color_distance)
    cols = ["x_center", "whisker_low", "q1", "median", "q3", "whisker_high"]
    rows = [[round(b.get(c, float("nan")), 6) for c in cols] for b in boxes]
    return ChartResult("box", cols, rows, raw=boxes)


def extract_pie(image_bgr, center=None, radius=None) -> ChartResult:
    wedges = eng.extract_pie(image_bgr, center=center, radius=radius)
    cols = ["hex", "start_deg", "end_deg", "fraction", "percent"]
    rows = [[w["hex"], round(w["start_deg"], 2), round(w["end_deg"], 2),
             round(w["fraction"], 4), round(w["fraction"] * 100, 2)] for w in wedges]
    return ChartResult("pie", cols, rows, raw=wedges)


def extract_heatmap(image_bgr, plot_bbox, grid_shape, colorbar_bbox, colorbar_range,
                    orientation="vertical") -> ChartResult:
    result = eng.extract_heatmap(image_bgr, plot_bbox, grid_shape, colorbar_bbox,
                                 colorbar_range, colorbar_orientation=orientation)
    matrix = result[0] if isinstance(result, tuple) else result
    matrix = np.asarray(matrix, dtype=float)
    cols = [f"c{j}" for j in range(matrix.shape[1])]
    rows = [[round(float(v), 6) for v in row] for row in matrix]
    return ChartResult("heatmap", cols, rows, raw=matrix,
                       meta={"grid_shape": tuple(matrix.shape)})
