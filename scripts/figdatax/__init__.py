"""FigDataX — High-Precision Scientific Figure Data Extraction.

Public API (import via ``from scripts.figdatax import ...``):

  Calibration   AxisCalibration, calibrate_axes_multipoint, calibrate_axes
  Color / I/O   pick_color, hsv_of_bgr, bgr_of_hsv, detect_data_colors
  Geometry      auto_detect_plot_area, detect_axes_hough, remove_grid,
                generate_grid_overlay, split_panels
  Extraction    extract_by_color_adaptive, extract_by_color, auto_extract_bars,
                auto_extract_scatter, extract_error_bars, extract_polar,
                trace_curve, interpolate_curve
  Same-color    detect_markers_morphological, cluster_markers_by_x,
                assign_series_with_crossover
  Chart types   extract_boxplot, extract_pie, extract_heatmap
  Validation    create_validation_plot, render_validation
  PDF figures   PdfDocument, FigureRef, pdf_available, scan_figures
  Export        export_figures
  Errors        FigDataXError, InputError, CalibrationError, DetectionError

PDF figure ingestion needs the optional pypdfium2 package (lazy-loaded);
everything else runs with cv2+numpy(+pandas), matplotlib/scipy also lazy.
"""

from __future__ import annotations

__version__ = "1.0.0"

from .core import (FigDataXError, InputError, CalibrationError, DetectionError,
                   auto_detect_plot_area, detect_axes_hough, remove_grid,
                   generate_grid_overlay, split_panels,
                   pick_color, hsv_of_bgr, bgr_of_hsv)
from .calibrate import (AxisCalibration, calibrate_axes_multipoint, calibrate_axes)
from .extract import (extract_by_color_adaptive, extract_by_color, detect_data_colors,
                      auto_extract_bars, auto_extract_scatter, extract_error_bars,
                      extract_polar, trace_curve, interpolate_curve)
from .morph import (detect_markers_morphological, cluster_markers_by_x,
                    assign_series_with_crossover)
from .charts import extract_boxplot, extract_pie, extract_heatmap
from .validate import create_validation_plot, render_validation
from .pdf import PdfDocument, FigureRef, PageText, pdf_available, scan_figures
from .export import export_figures

__all__ = [
    "__version__",
    "FigDataXError", "InputError", "CalibrationError", "DetectionError",
    "auto_detect_plot_area", "detect_axes_hough", "remove_grid",
    "generate_grid_overlay", "split_panels",
    "pick_color", "hsv_of_bgr", "bgr_of_hsv",
    "AxisCalibration", "calibrate_axes_multipoint", "calibrate_axes",
    "extract_by_color_adaptive", "extract_by_color", "detect_data_colors",
    "auto_extract_bars", "auto_extract_scatter", "extract_error_bars",
    "extract_polar", "trace_curve", "interpolate_curve",
    "detect_markers_morphological", "cluster_markers_by_x",
    "assign_series_with_crossover",
    "extract_boxplot", "extract_pie", "extract_heatmap",
    "create_validation_plot", "render_validation",
    "PdfDocument", "FigureRef", "PageText", "pdf_available", "scan_figures",
    "export_figures",
]
