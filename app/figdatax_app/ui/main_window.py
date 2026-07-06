"""Three-pane main window: document/project sidebar · digitizer canvas · results + export.

This is the app skeleton: the image→calibrate→extract→export path is wired and
working; PDF ingestion, table extraction, and the data-mentions panel are stubbed
with honest "coming soon" placeholders for later phases.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QLabel, QListWidget,
                               QMainWindow, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QToolBar, QVBoxLayout,
                               QWidget)

from .. import __app_version__
from .. import engine_bridge as eng
from ..export_xlsx import export_session
from .canvas import DigitizerCanvas, Mode


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"FigDataX Desktop {__app_version__} "
                            f"(engine {eng.engine_version})")
        self.resize(1200, 800)

        self.canvas = DigitizerCanvas()
        self._build_center()
        self._build_sidebar()
        self._build_results_dock()
        self._build_toolbar()

        self.canvas.status.connect(self.statusBar().showMessage)
        self.canvas.color_picked.connect(
            lambda hsv: self.statusBar().showMessage(f"Target color HSV {hsv}"))

    # ── layout ──
    def _build_center(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self.canvas, "提取工作台 / Workspace")
        pdf_placeholder = QLabel("PDF 文档视图 — 后续阶段\n(PDF view — coming soon)")
        pdf_placeholder.setAlignment(Qt.AlignCenter)
        self.tabs.addTab(pdf_placeholder, "文档 / Document")
        self.setCentralWidget(self.tabs)

    def _build_sidebar(self):
        dock = QDockWidget("项目 / Project", self)
        self.sidebar = QListWidget()
        self.sidebar.addItem("图表 / Figures (coming soon)")
        self.sidebar.addItem("表格 / Tables (coming soon)")
        self.sidebar.addItem("数据线索 / Data mentions (coming soon)")
        dock.setWidget(self.sidebar)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _build_results_dock(self):
        dock = QDockWidget("结果 / Results", self)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.results = QTableWidget(0, 3)
        self.results.setHorizontalHeaderLabels(["X", "Y", "conf"])
        layout.addWidget(self.results)
        export_btn = QPushButton("导出 Excel / Export Excel")
        export_btn.clicked.connect(self._export)
        layout.addWidget(export_btn)
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        self.addToolBar(tb)
        tb.addAction("打开图片 / Open Image", self._open_image)
        tb.addAction("打开 PDF / Open PDF", self._open_pdf)
        tb.addSeparator()
        tb.addAction("平移 / Pan", lambda: self.canvas.set_mode(Mode.PAN))
        tb.addAction("校准X / Calib X", lambda: self.canvas.set_mode(Mode.CALIBRATE_X))
        tb.addAction("校准Y / Calib Y", lambda: self.canvas.set_mode(Mode.CALIBRATE_Y))
        tb.addAction("取色 / Eyedropper", lambda: self.canvas.set_mode(Mode.EYEDROPPER))
        tb.addSeparator()
        tb.addAction("提取 / Extract", self._extract)

    # ── actions ──
    def _open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open figure image", "", "Images (*.png *.jpg *.jpeg *.tif *.bmp)")
        if path:
            try:
                self.canvas.load_image(path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error", str(exc))

    def _open_pdf(self):
        QMessageBox.information(
            self, "Coming soon",
            "PDF ingestion (figure/table detection, data-mention location, Excel export) "
            "is planned for the next phase. For now, open a figure image.")

    def _extract(self):
        try:
            series = self.canvas.run_extraction()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Extraction", str(exc))
            return
        self.results.setRowCount(len(series.points))
        for r, p in enumerate(series.points):
            self.results.setItem(r, 0, QTableWidgetItem(f"{p.data_x:.4g}"))
            self.results.setItem(r, 1, QTableWidgetItem(f"{p.data_y:.4g}"))
            self.results.setItem(r, 2, QTableWidgetItem(f"{p.confidence:.2f}"))

    def _export(self):
        if not self.canvas.session.series:
            QMessageBox.information(self, "Export", "Nothing to export yet — extract first.")
            return
        default = ""
        if self.canvas.session.image_path:
            base, _ = os.path.splitext(self.canvas.session.image_path)
            default = base + "_figdatax.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", default,
                                              "Excel (*.xlsx)")
        if path:
            export_session(self.canvas.session, path)
            self.statusBar().showMessage(f"Exported {path}")
