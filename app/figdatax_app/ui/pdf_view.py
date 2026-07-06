"""PDF document tab: page navigator, detected figures/tables, and data mentions.

Emits ``send_figure_to_canvas(bgr, label)`` when the user chooses to digitize a
detected figure, and ``jump_requested`` is handled internally to show the page a
mention lives on. Heavy work (rendering, detection, scanning) runs in a worker thread
so the UI stays responsive.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QProgressBar,
                               QPushButton, QScrollArea, QSplitter, QTabWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..data_mentions import Mention, rank, scan_pages
from ..pdf_document import FigureRef, PdfDocument, TableRef, pdf_available


def _bgr_to_pixmap(bgr: np.ndarray) -> QPixmap:
    import cv2
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QPixmap.fromImage(QImage(rgb.tobytes(), w, h, 3 * w, QImage.Format_RGB888).copy())


class _AnalyzeWorker(QThread):
    """Detect figures + tables per page and scan all text, off the UI thread."""
    progress = Signal(int, int)                 # done, total
    done = Signal(object, object, object)       # figures, tables, mentions
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        try:
            doc = PdfDocument(self.path)
            figs: List[FigureRef] = []
            tables: List[TableRef] = []
            for i in range(doc.n_pages):
                figs.extend(doc.detect_figures(i))
                try:
                    tables.extend(doc.detect_tables(i))
                except Exception:
                    pass
                self.progress.emit(i + 1, doc.n_pages)
            mentions = rank(scan_pages(doc.all_text()))
            doc.close()
            self.done.emit(figs, tables, mentions)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class PdfView(QWidget):
    send_figure_to_canvas = Signal(object, str)   # (bgr ndarray, label)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: Optional[PdfDocument] = None
        self.figures: List[FigureRef] = []
        self.tables: List[TableRef] = []
        self.mentions: List[Mention] = []
        self._worker: Optional[_AnalyzeWorker] = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        # left: page image
        self.page_label = QLabel("打开一个 PDF 开始 / Open a PDF to begin")
        self.page_label.setAlignment(Qt.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.page_label)

        nav = QWidget()
        nav_l = QVBoxLayout(nav)
        row = QHBoxLayout()
        self.page_combo = QComboBox()
        self.page_combo.currentIndexChanged.connect(self._show_page)
        row.addWidget(QLabel("页 / Page"))
        row.addWidget(self.page_combo, 1)
        nav_l.addLayout(row)
        nav_l.addWidget(scroll, 1)
        split.addWidget(nav)

        # right: tabs of figures / tables / mentions
        tabs = QTabWidget()

        self.fig_list = QListWidget()
        self.fig_list.itemDoubleClicked.connect(self._digitize_selected_figure)
        fig_panel = QWidget(); fig_l = QVBoxLayout(fig_panel)
        fig_l.addWidget(QLabel("双击图形送入数字化画布 / Double-click a figure to digitize"))
        fig_l.addWidget(self.fig_list, 1)
        send_btn = QPushButton("送入数字化 / Send to digitizer")
        send_btn.clicked.connect(self._digitize_selected_figure)
        fig_l.addWidget(send_btn)
        tabs.addTab(fig_panel, "图形 / Figures")

        self.table_list = QListWidget()
        self.table_list.currentRowChanged.connect(self._show_table_preview)
        self.table_preview = QTableWidget(0, 0)
        tbl_panel = QWidget(); tbl_l = QVBoxLayout(tbl_panel)
        tbl_l.addWidget(self.table_list)
        tbl_l.addWidget(QLabel("预览 / Preview"))
        tbl_l.addWidget(self.table_preview, 1)
        tabs.addTab(tbl_panel, "表格 / Tables")

        self.mention_list = QListWidget()
        self.mention_list.itemClicked.connect(self._jump_to_mention)
        men_panel = QWidget(); men_l = QVBoxLayout(men_panel)
        men_l.addWidget(QLabel("点击线索跳转到所在页 / Click a clue to jump to its page"))
        men_l.addWidget(self.mention_list, 1)
        tabs.addTab(men_panel, "数据线索 / Data mentions")

        split.addWidget(tabs)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

    # ── loading ──
    def open_pdf(self, path: str):
        if not pdf_available():
            QMessageBox.critical(self, "PDF", "pypdfium2 / pdfplumber not installed.")
            return
        if self.doc:
            self.doc.close()
        self.doc = PdfDocument(path)
        self.page_combo.blockSignals(True)
        self.page_combo.clear()
        self.page_combo.addItems([f"{i + 1} / {self.doc.n_pages}"
                                  for i in range(self.doc.n_pages)])
        self.page_combo.blockSignals(False)
        self.page_combo.setCurrentIndex(0)
        self._show_page(0)
        self._analyze(path)

    def _analyze(self, path: str):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.fig_list.clear(); self.table_list.clear(); self.mention_list.clear()
        self._worker = _AnalyzeWorker(path)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_analyzed)
        self._worker.failed.connect(lambda m: (self.progress.setVisible(False),
                                               QMessageBox.warning(self, "PDF", m)))
        self._worker.start()

    def _on_progress(self, done, total):
        self.progress.setRange(0, total)
        self.progress.setValue(done)

    def _on_analyzed(self, figures, tables, mentions):
        self.progress.setVisible(False)
        self.figures, self.tables, self.mentions = figures, tables, mentions
        for i, f in enumerate(figures):
            w = f.bbox[2] - f.bbox[0]; h = f.bbox[3] - f.bbox[1]
            QListWidgetItem(f"p{f.page_index + 1}  ·  {w}×{h}px  ·  fig {i + 1}",
                            self.fig_list)
        for t in tables:
            QListWidgetItem(f"p{t.page_index + 1}  ·  {t.shape[0]}×{t.shape[1]}",
                            self.table_list)
        for m in mentions:
            QListWidgetItem(f"p{m.page_label}  [{m.category}]  {m.match_text}",
                            self.mention_list)
        self.window().statusBar().showMessage(
            f"PDF analyzed: {len(figures)} figures, {len(tables)} tables, "
            f"{len(mentions)} data mentions")

    # ── page display ──
    def _show_page(self, index: int):
        if not self.doc or index < 0:
            return
        bgr = self.doc.render_page(index)
        self.page_label.setPixmap(_bgr_to_pixmap(bgr))
        self.page_label.setFixedSize(bgr.shape[1], bgr.shape[0])

    # ── figures ──
    def _digitize_selected_figure(self, *_):
        row = self.fig_list.currentRow()
        if row < 0 or row >= len(self.figures):
            return
        fig = self.figures[row]
        crop = self.doc.crop_figure(fig)
        label = f"{self.doc.path.split('/')[-1]} p{fig.page_index + 1} figure {row + 1}"
        self.send_figure_to_canvas.emit(crop, label)

    # ── tables ──
    def _show_table_preview(self, row: int):
        if row < 0 or row >= len(self.tables):
            return
        t = self.tables[row]
        nrows, ncols = t.shape
        self.table_preview.setRowCount(nrows)
        self.table_preview.setColumnCount(ncols)
        for r, rowvals in enumerate(t.rows):
            for c, val in enumerate(rowvals):
                self.table_preview.setItem(r, c, QTableWidgetItem(val))

    # ── mentions ──
    def _jump_to_mention(self, item: QListWidgetItem):
        row = self.mention_list.row(item)
        if 0 <= row < len(self.mentions):
            self.page_combo.setCurrentIndex(self.mentions[row].page_index)
