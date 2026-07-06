"""Interactive digitizer canvas — the core WebPlotDigitizer-style UX.

A QGraphicsView whose scene units equal image pixels, so every overlay position is
directly an image pixel coordinate the engine understands. Supports zoom/pan, placing
axis-calibration points (with value entry), an eyedropper color pick, running color
extraction, manual point add/move/delete, and a live pixel→data readout.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QGraphicsPixmapItem, QGraphicsScene, QGraphicsView,
                               QInputDialog)

from .. import engine_bridge as eng
from ..models import CalibPoint, DataPoint, ExtractionSession
from ..pipeline import build_calibration, extract_series
from .canvas_items import DataMarkerItem, MarkerItem, calib_marker


class Mode(Enum):
    PAN = auto()
    CALIBRATE_X = auto()
    CALIBRATE_Y = auto()
    EYEDROPPER = auto()
    ADD_POINT = auto()
    EDIT = auto()          # select / drag / delete data points


def bgr_to_pixmap(bgr: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    img = QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(img.copy())


class DigitizerCanvas(QGraphicsView):
    status = Signal(str)                 # live readout / hints
    color_picked = Signal(tuple)         # (H, S, V)
    calibration_changed = Signal()
    points_changed = Signal()            # any edit to data points (add/move/delete/extract)

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
        self._point_items: List[DataMarkerItem] = []
        self._calib_items: List[MarkerItem] = []
        self.target_hsv: Optional[tuple] = None

    # ── image / session loading ──
    def load_image(self, path: str):
        bgr = cv2.imread(path)
        if bgr is None:
            raise FileNotFoundError(path)
        self.load_bgr(bgr, ExtractionSession(image_path=path))
        try:
            self.session.plot_bbox = eng.auto_detect_plot_area(bgr)
        except Exception:
            self.session.plot_bbox = None

    def load_bgr(self, bgr: np.ndarray, session: Optional[ExtractionSession] = None):
        """Show a BGR array (e.g. a PDF crop or project image) and adopt ``session``,
        restoring its calibration/data markers if it has any."""
        self._bgr = bgr
        self.session = session or ExtractionSession()
        self.target_hsv = None
        self._point_items = []
        self._calib_items = []
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(bgr_to_pixmap(bgr))
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._restore_overlays()
        label = self.session.source_label or self.session.image_path or "image"
        self.status.emit(f"Loaded {label} ({bgr.shape[1]}x{bgr.shape[0]})")

    def reset(self):
        """Clear image, session and overlays (File → New Project)."""
        self._bgr = None
        self._pixmap_item = None
        self._point_items = []
        self._calib_items = []
        self.session = ExtractionSession()
        self.target_hsv = None
        self._scene.clear()
        self.status.emit("New project")

    def _restore_overlays(self):
        cal = self.session.calibration
        for cp in cal.x_points:
            self._add_calib_item(cp, "x")
        for cp in cal.y_points:
            self._add_calib_item(cp, "y")
        for s in self.session.series:
            for p in s.points:
                self._add_point_item(p)

    @property
    def image_bgr(self) -> Optional[np.ndarray]:
        return self._bgr

    # ── zoom / pan ──
    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    # ── interaction ──
    def set_mode(self, mode: Mode):
        self.mode = mode
        if mode == Mode.PAN:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif mode == Mode.EDIT:
            self.setDragMode(QGraphicsView.RubberBandDrag)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
        hints = {
            Mode.PAN: "Pan: drag to move, wheel to zoom",
            Mode.CALIBRATE_X: "Click an X-axis tick, then enter its value",
            Mode.CALIBRATE_Y: "Click a Y-axis tick, then enter its value",
            Mode.EYEDROPPER: "Click a marker to pick the target color",
            Mode.ADD_POINT: "Click to add a data point (calibration required)",
            Mode.EDIT: "Drag points to move; select and press Delete to remove",
        }
        self.status.emit(hints[mode])

    def _axis(self):
        return build_calibration(self.session.calibration)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self._bgr is None:
            return
        p = self.mapToScene(event.position().toPoint())
        px, py = p.x(), p.y()
        if self.session.calibration.is_ready():
            try:
                dx, dy = self._axis().pixel_to_data(px, py)
                self.status.emit(f"pixel ({px:.0f}, {py:.0f})  →  data ({dx:.4g}, {dy:.4g})")
                return
            except Exception:
                pass
        self.status.emit(f"pixel ({px:.0f}, {py:.0f})")

    def mousePressEvent(self, event):
        if self._bgr is None or self.mode in (Mode.PAN, Mode.EDIT):
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
                cp = CalibPoint(coord, val, scene_x=px, scene_y=py)
                (self.session.calibration.x_points if axis == "x"
                 else self.session.calibration.y_points).append(cp)
                self._add_calib_item(cp, axis)
                self.calibration_changed.emit()
                self._recompute_data_coords()
                self.status.emit(f"Added {axis}-calibration point ({coord:.0f} → {val})")
        elif self.mode == Mode.EYEDROPPER:
            info = eng.pick_color(self._bgr, int(px), int(py))
            self.target_hsv = info["hsv"]
            self.color_picked.emit(info["hsv"])
            self.status.emit(f"Picked color HSV {info['hsv']} {info['hex']}")
        elif self.mode == Mode.ADD_POINT:
            self.add_manual_point(px, py)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.mode == Mode.EDIT:
            self.delete_selected_points()
        else:
            super().keyPressEvent(event)

    # ── point editing (Phase 1 MVP) ──
    def _add_calib_item(self, cp: CalibPoint, axis: str):
        # legacy projects (scene coords default 0,0): fall back to the axis coordinate
        sx = cp.scene_x or (cp.px if axis == "x" else 0.0)
        sy = cp.scene_y or (cp.px if axis == "y" else 0.0)
        item = calib_marker(sx, sy, axis)
        self._calib_items.append(item)
        self._scene.addItem(item)

    def _add_point_item(self, point: DataPoint):
        item = DataMarkerItem(point, on_moved=self._on_marker_moved)
        self._point_items.append(item)
        self._scene.addItem(item)
        return item

    def add_manual_point(self, px: float, py: float):
        if not self.session.calibration.is_ready():
            self.status.emit("Cannot add point: need 2+ calibration points per axis.")
            return None
        dx, dy = self._axis().pixel_to_data(px, py)
        point = DataPoint(px, py, dx, dy, confidence=1.0, manual=True)
        self.session.active_series().points.append(point)
        self._add_point_item(point)
        self.points_changed.emit()
        self.status.emit(f"Added point ({dx:.4g}, {dy:.4g})")
        return point

    def delete_selected_points(self):
        selected = [it for it in self._point_items if it.isSelected()]
        if not selected:
            self.status.emit("No points selected.")
            return 0
        doomed = {id(it.point) for it in selected}
        for s in self.session.series:
            s.points = [p for p in s.points if id(p) not in doomed]
        for it in selected:
            self._scene.removeItem(it)
            self._point_items.remove(it)
        self.points_changed.emit()
        self.status.emit(f"Deleted {len(selected)} point(s).")
        return len(selected)

    def _on_marker_moved(self, item: DataMarkerItem):
        if self.session.calibration.is_ready():
            try:
                dx, dy = self._axis().pixel_to_data(item.point.px, item.point.py)
                item.point.data_x, item.point.data_y = dx, dy
            except Exception:
                pass
        self.points_changed.emit()

    def _recompute_data_coords(self):
        """After calibration edits, refresh every point's data coordinates."""
        if not self.session.calibration.is_ready():
            return
        try:
            axis = self._axis()
        except Exception:
            return
        for s in self.session.series:
            for p in s.points:
                p.data_x, p.data_y = axis.pixel_to_data(p.px, p.py)
        if self.session.total_points():
            self.points_changed.emit()

    # ── extraction ──
    def run_extraction(self, color_distance=30):
        if self._bgr is None:
            raise RuntimeError("No image loaded.")
        if not self.session.calibration.is_ready():
            raise RuntimeError("Need at least 2 calibration points per axis.")
        if self.target_hsv is None:
            raise RuntimeError("Pick a target color first (eyedropper).")
        series = extract_series(self.session, self.target_hsv, color_distance,
                                bgr=self._bgr)
        # rebuild all data markers from the session
        for it in self._point_items:
            self._scene.removeItem(it)
        self._point_items = []
        for s in self.session.series:
            for p in s.points:
                self._add_point_item(p)
        self.points_changed.emit()
        self.status.emit(f"Extracted {len(series.points)} points.")
        return series
