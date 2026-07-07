"""FigDataX — High-Precision Scientific Figure Data Extraction.

Public API (import via ``from scripts.figdatax import ...``):

  Calibration   AxisCalibration, calibrate_axes_multipoint, calibrate_axes
  Color / I/O   pick_color, hsv_of_bgr, bgr_of_hsv, detect_data_colors
  Geometry      auto_detect_plot_area, detect_axes_hough, remove_grid,
                generate_grid_overlay, split_panels, detect_ticks,
                draw_geometry_overlay, suggest_series
  Extraction    extract_by_color_adaptive, extract_by_color, auto_extract_bars,
                auto_extract_scatter, extract_error_bars, extract_polar,
                trace_curve, interpolate_curve
  Same-color    detect_markers_morphological, cluster_markers_by_x,
                assign_series_with_crossover
  Chart types   extract_boxplot, extract_pie, extract_heatmap
  Validation    create_validation_plot, render_validation
  Export        export_figures
  Errors        FigDataXError, InputError, CalibrationError, DetectionError

Input is always a figure image (PNG/JPG/…) the user provides — crop/screenshot it
from the paper however you like. Core needs only cv2+numpy(+pandas);
matplotlib/scipy are lazy.
"""

from __future__ import annotations

__version__ = "2.0.0"

from .core import (FigDataXError, InputError, CalibrationError, DetectionError,
                   auto_detect_plot_area, detect_axes_hough, remove_grid,
                   generate_grid_overlay, split_panels, detect_ticks,
                   draw_geometry_overlay, pick_color, hsv_of_bgr, bgr_of_hsv)
from .calibrate import (AxisCalibration, calibrate_axes_multipoint, calibrate_axes)
from .extract import (extract_by_color_adaptive, extract_by_color, detect_data_colors,
                      suggest_series, auto_extract_bars, auto_extract_scatter,
                      extract_error_bars, extract_polar, trace_curve, interpolate_curve)
from .morph import (detect_markers_morphological, cluster_markers_by_x,
                    assign_series_with_crossover)
from .charts import extract_boxplot, extract_pie, extract_heatmap
from .validate import create_validation_plot, render_validation
from .export import export_figures

__all__ = [
    "__version__",
    "FigDataXError", "InputError", "CalibrationError", "DetectionError",
    "auto_detect_plot_area", "detect_axes_hough", "remove_grid",
    "generate_grid_overlay", "split_panels", "detect_ticks", "draw_geometry_overlay",
    "pick_color", "hsv_of_bgr", "bgr_of_hsv",
    "AxisCalibration", "calibrate_axes_multipoint", "calibrate_axes",
    "extract_by_color_adaptive", "extract_by_color", "detect_data_colors",
    "suggest_series", "auto_extract_bars", "auto_extract_scatter", "extract_error_bars",
    "extract_polar", "trace_curve", "interpolate_curve",
    "detect_markers_morphological", "cluster_markers_by_x",
    "assign_series_with_crossover",
    "extract_boxplot", "extract_pie", "extract_heatmap",
    "create_validation_plot", "render_validation",
    "export_figures",
]
