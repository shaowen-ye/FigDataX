"""Validation overlay — original figure beside the reconstructed data.

matplotlib is imported lazily and used via ``Figure`` + ``FigureCanvasAgg`` (no
``pyplot`` global state), so this is safe to call from GUI worker threads.
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .core import _load_bgr, _require


def render_validation(original_img_path, data_points, xlabel="X", ylabel="Y",
                      title="FigDataX Validation Overlay", dpi=150) -> np.ndarray:
    """Render the side-by-side validation figure and return it as an RGB ndarray.

    ``data_points`` may be a list of ``(x, y)`` / list of bar values, or a dict of
    ``{series_name: points}``. Returns the composed image (H×W×3, RGB) — the GUI
    can display it directly without touching disk.
    """
    _require("matplotlib", "validation overlay")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    original_rgb = cv2.cvtColor(_load_bgr(original_img_path), cv2.COLOR_BGR2RGB)

    fig = Figure(figsize=(14, 6), dpi=dpi)
    canvas = FigureCanvasAgg(fig)
    ax0, ax1 = fig.subplots(1, 2)

    ax0.imshow(original_rgb)
    ax0.set_title("Original Figure")
    ax0.axis("off")

    has_label = False
    if isinstance(data_points, dict):
        for name, pts in data_points.items():
            if isinstance(pts, list) and pts:
                if isinstance(pts[0], (list, tuple)):
                    ax1.plot([p[0] for p in pts], [p[1] for p in pts], "o-",
                             label=name, markersize=4)
                else:
                    ax1.bar(range(len(pts)), pts, label=name, alpha=0.7)
                has_label = True
    elif isinstance(data_points, list) and data_points:
        if isinstance(data_points[0], (list, tuple)):
            ax1.plot([p[0] for p in data_points], [p[1] for p in data_points],
                     "o-", color="steelblue", markersize=4)
        else:
            ax1.bar(range(len(data_points)), data_points, color="steelblue", alpha=0.7)

    ax1.set_xlabel(xlabel)
    ax1.set_ylabel(ylabel)
    ax1.set_title(title)
    if has_label:
        ax1.legend()
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()

    canvas.draw()
    buf = np.asarray(canvas.buffer_rgba())
    return buf[:, :, :3].copy()


def create_validation_plot(original_img_path, data_points, output_path,
                           xlabel="X", ylabel="Y",
                           title="FigDataX Validation Overlay", dpi=150) -> str:
    """Render the validation overlay and save it to ``output_path``. Returns the path."""
    rgb = render_validation(original_img_path, data_points, xlabel, ylabel, title, dpi)
    cv2.imwrite(output_path, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return output_path
