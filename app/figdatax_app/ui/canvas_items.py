"""Overlay items drawn on the digitizer canvas (scene units = image pixels)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem


class MarkerItem(QGraphicsEllipseItem):
    """A small filled circle marking a point at image pixel (px, py)."""

    def __init__(self, px, py, color: QColor, radius=5.0, label=""):
        super().__init__(QRectF(-radius, -radius, 2 * radius, 2 * radius))
        self.setPos(px, py)
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("black"), 1))
        self.setZValue(10)
        self.setToolTip(label)


def calib_marker(px, py, axis: str) -> MarkerItem:
    color = QColor("#1f77b4") if axis == "x" else QColor("#d62728")
    return MarkerItem(px, py, color, radius=6.0, label=f"{axis}-calibration")


def data_marker(px, py) -> MarkerItem:
    return MarkerItem(px, py, QColor("#2ca02c"), radius=4.0, label="data point")
