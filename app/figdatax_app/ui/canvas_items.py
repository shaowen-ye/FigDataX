"""Overlay items drawn on the digitizer canvas (scene units = image pixels)."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem

from ..models import DataPoint


class MarkerItem(QGraphicsEllipseItem):
    """A small filled circle marking a point at image pixel (px, py)."""

    def __init__(self, px, py, color: QColor, radius=5.0, label=""):
        super().__init__(QRectF(-radius, -radius, 2 * radius, 2 * radius))
        self.setPos(px, py)
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("black"), 1))
        self.setZValue(10)
        self.setToolTip(label)


class DataMarkerItem(MarkerItem):
    """A data-point marker bound to a :class:`DataPoint` — selectable and draggable.

    Dragging updates the bound point's pixel coordinates and calls ``on_moved`` so
    the canvas can recompute data coordinates and notify the results table.
    """

    def __init__(self, point: DataPoint,
                 on_moved: Optional[Callable[["DataMarkerItem"], None]] = None):
        color = QColor("#ff7f0e") if point.manual else QColor("#2ca02c")
        label = "manual point" if point.manual else "data point"
        super().__init__(point.px, point.py, color, radius=4.5, label=label)
        self.point = point
        self._on_moved = on_moved
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            self.setPen(QPen(QColor("#e6194b") if value else QColor("black"),
                             2 if value else 1))
        elif change == QGraphicsItem.ItemScenePositionHasChanged:
            self.point.px = self.pos().x()
            self.point.py = self.pos().y()
            self.point.manual = True
            if self._on_moved is not None:
                self._on_moved(self)
        return super().itemChange(change, value)


def calib_marker(px, py, axis: str) -> MarkerItem:
    color = QColor("#1f77b4") if axis == "x" else QColor("#d62728")
    return MarkerItem(px, py, color, radius=6.0, label=f"{axis}-calibration")
