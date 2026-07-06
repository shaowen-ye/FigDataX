"""Parameter dialogs for box / pie / heatmap extraction and a result viewer."""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel,
                               QLineEdit, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)


def _hsv_field(placeholder="H,S,V (blank = use eyedropper)") -> QLineEdit:
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    return e


def _parse_hsv(text: str) -> Optional[Tuple[int, int, int]]:
    text = text.strip()
    if not text:
        return None
    parts = [p for p in text.replace(",", " ").split() if p]
    if len(parts) != 3:
        raise ValueError("HSV needs three numbers: H,S,V")
    return tuple(int(float(p)) for p in parts)


class BoxParamsDialog(QDialog):
    def __init__(self, default_hsv=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("箱线图提取 / Box plot")
        form = QFormLayout(self)
        form.addRow(QLabel("需要已完成 Y 轴校准。\nRequires Y-axis calibration."))
        self.box_hsv = _hsv_field()
        if default_hsv:
            self.box_hsv.setText(",".join(map(str, default_hsv)))
        form.addRow("箱体颜色 / Box color HSV", self.box_hsv)
        self.median_hsv = _hsv_field("optional")
        form.addRow("中位线颜色 / Median HSV", self.median_hsv)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        form.addRow(box)

    def values(self):
        return _parse_hsv(self.box_hsv.text()), _parse_hsv(self.median_hsv.text())


class PieParamsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("饼图提取 / Pie chart")
        form = QFormLayout(self)
        form.addRow(QLabel("留空自动检测圆心/半径。\nBlank = auto-detect disc."))
        self.center = QLineEdit(); self.center.setPlaceholderText("cx,cy (optional)")
        form.addRow("圆心 / Center px", self.center)
        self.radius = QLineEdit(); self.radius.setPlaceholderText("r px (optional)")
        form.addRow("半径 / Radius px", self.radius)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        form.addRow(box)

    def values(self):
        c = self.center.text().strip()
        center = tuple(int(float(x)) for x in c.replace(",", " ").split()) if c else None
        r = self.radius.text().strip()
        radius = int(float(r)) if r else None
        return center, radius


class HeatmapParamsDialog(QDialog):
    def __init__(self, plot_bbox=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("热图提取 / Heatmap")
        form = QFormLayout(self)
        self.bbox = QLineEdit()
        if plot_bbox:
            self.bbox.setText(",".join(map(str, plot_bbox)))
        self.bbox.setPlaceholderText("left,top,right,bottom")
        form.addRow("网格区域 / Grid bbox", self.bbox)
        self.rows = QSpinBox(); self.rows.setRange(1, 500); self.rows.setValue(10)
        form.addRow("行数 / Rows", self.rows)
        self.cols = QSpinBox(); self.cols.setRange(1, 500); self.cols.setValue(10)
        form.addRow("列数 / Cols", self.cols)
        self.cbar = QLineEdit(); self.cbar.setPlaceholderText("left,top,right,bottom")
        form.addRow("色标区域 / Colorbar bbox", self.cbar)
        self.cbar_range = QLineEdit(); self.cbar_range.setPlaceholderText("low,high")
        form.addRow("色标范围 / Colorbar range", self.cbar_range)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        form.addRow(box)

    def values(self):
        def four(text):
            return tuple(int(float(x)) for x in text.replace(",", " ").split())
        bbox = four(self.bbox.text())
        cbar = four(self.cbar.text())
        lo, hi = [float(x) for x in self.cbar_range.text().replace(",", " ").split()]
        return bbox, (self.rows.value(), self.cols.value()), cbar, (lo, hi)


class ChartResultDialog(QDialog):
    """Show a ChartResult in a table with an Export button (handled by caller)."""

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle(f"{result.kind} 结果 / result")
        self.resize(560, 400)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"{result.kind}: {len(result.rows)} rows"))
        table = QTableWidget(len(result.rows), len(result.columns))
        table.setHorizontalHeaderLabels(result.columns)
        for r, row in enumerate(result.rows):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(str(val)))
        v.addWidget(table)
        box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        box.button(QDialogButtonBox.Save).setText("导出 Excel / Export")
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        v.addWidget(box)
