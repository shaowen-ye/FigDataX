"""Interactive digitizer canvas — the core WebPlotDigitizer-style UX.

A QGraphicsView whose scene units equal image pixels, so every overlay position is
directly an image pixel coordinate the engine understands. Supports zoom/pan, placing
axis-calibration points (with value entry), an eyedropper color pick, running color
extraction, and a live pixel→data readout.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QGraphicsScene, QGraphicsView, QInputDialog,
                               QGraphicsPixmapItem)

from .. import engine_bridge as eng
from ..models import CalibPoint, ExtractionSession
from ..pipeline import extract_series
from .canvas_items import calib_marker, data_marker


class Mode(Enum):
    PAN = auto()
    CALIBRATE_X = auto()
    CALIBRATE_Y = auto()
    EYEDROPPER = auto()


def bgr_to_pixmap(bgr: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    img = QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(img.copy())


class DigitizerCanvas(QGraphicsView):
    status = Signal(str)                 # live readout / hints
    color_picked = Signal(tuple)         # (H, S, V)
    calibration_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self.session = ExtractionSession()
        self.mode = Mode.PAN
        self._bgr: Optional[np.ndarray] = None
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.target_hsv: Optional[tuple] = None

    # ── image ──
    def load_image(self, path: str):
        self._bgr = cv2.imread(path)
        if self._bgr is None:
            raise FileNotFoundError(path)
        self.session = ExtractionSession(image_path=path)
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(bgr_to_pixmap(self._bgr))
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        # seed auto-detected plot area
        try:
            self.session.plot_bbox = eng.auto_detect_plot_area(path)
        except Exception:
            self.session.plot_bbox = None
        self.status.emit(f"Loaded {path} ({self._bgr.shape[1]}x{self._bgr.shape[0]})")

    # ── zoom / pan ──
    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    # ── interaction ──
    def set_mode(self, mode: Mode):
        self.mode = mode
        self.setDragMode(QGraphicsView.ScrollHandDrag if mode == Mode.PAN
                         else QGraphicsView.NoDrag)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self._bgr is None:
            return
        p = self.mapToScene(event.position().toPoint())
        px, py = p.x(), p.y()
        if self.session.calibration.is_ready():
            try:
                axis = eng.calibrate_axes_multipoint(
                    [c.px for c in self.session.calibration.x_points],
                    [c.value for c in self.session.calibration.x_points],
                    [c.px for c in self.session.calibration.y_points],
                    [c.value for c in self.session.calibration.y_points])
                dx, dy = axis.pixel_to_data(px, py)
                self.status.emit(f"pixel ({px:.0f}, {py:.0f})  →  data ({dx:.4g}, {dy:.4g})")
                return
            except Exception:
                pass
        self.status.emit(f"pixel ({px:.0f}, {py:.0f})")

    def mousePressEvent(self, event):
        if self._bgr is None or self.mode == Mode.PAN:
            return super().mousePressEvent(event)
        p = self.mapToScene(event.position().toPoint())
        px, py = p.x(), p.y()

        if self.mode in (Mode.CALIBRATE_X, Mode.CALIBRATE_Y):
            axis = "x" if self.mode == Mode.CALIBRATE_X else "y"
            coord = px if axis == "x" else py
            val, ok = QInputDialog.getDouble(
                self, f"{axis.upper()}-axis value",
                f"Data value at this {axis}-axis tick:", decimals=6)
            if ok:
                cp = CalibPoint(coord, val)
                (self.session.calibration.x_points if axis == "x"
                 else self.session.calibration.y_points).append(cp)
                self._scene.addItem(calib_marker(px, py, axis))
                self.calibration_changed.emit()
                self.status.emit(f"Added {axis}-calibration point ({coord:.0f} → {val})")
        elif self.mode == Mode.EYEDROPPER:
            info = eng.pick_color(self._bgr, int(px), int(py))
            self.target_hsv = info["hsv"]
            self.color_picked.emit(info["hsv"])
            self.status.emit(f"Picked color HSV {info['hsv']} {info['hex']}")

    # ── extraction ──
    def run_extraction(self, color_distance=30):
        if self._bgr is None:
            raise RuntimeError("No image loaded.")
        if not self.session.calibration.is_ready():
            raise RuntimeError("Need at least 2 calibration points per axis.")
        if self.target_hsv is None:
            raise RuntimeError("Pick a target color first (eyedropper).")
        series = extract_series(self.session, self.target_hsv, color_distance)
        for p in series.points:
            self._scene.addItem(data_marker(p.px, p.py))
        self.status.emit(f"Extracted {len(series.points)} points.")
        return series
