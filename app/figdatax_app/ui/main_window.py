"""Three-pane main window: document/project sidebar · digitizer canvas · results + export.

Phase 1 (this file): full project lifecycle — New/Open/Save/Save As .fdx with recent
files and dirty tracking — plus manual point editing synced to the results table.
PDF ingestion panels are stubbed for Phase 2.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QLabel, QListWidget,
                               QMainWindow, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QToolBar, QVBoxLayout,
                               QWidget)

from .. import __app_version__
from .. import engine_bridge as eng
from ..export_xlsx import export_session, export_workbook
from ..pdf_document import pdf_available
from ..project import SUFFIX, ProjectError, load_project, save_project
from .canvas import DigitizerCanvas, Mode
from .pdf_view import PdfView

MAX_RECENT = 8


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1200, 800)

        self.settings = QSettings("FigDataX", "Desktop")
        self.project_path: str | None = None
        self._dirty = False

        self.canvas = DigitizerCanvas()
        self._build_center()
        self._build_sidebar()
        self._build_results_dock()
        self._build_toolbar()
        self._build_menu()

        self.canvas.status.connect(self.statusBar().showMessage)
        self.canvas.color_picked.connect(self._on_color_picked)
        self.canvas.points_changed.connect(self._refresh_results)
        self.canvas.points_changed.connect(self._mark_dirty)
        self.canvas.calibration_changed.connect(self._mark_dirty)
        self._update_title()

    # ── window state ──
    def _update_title(self):
        name = os.path.basename(self.project_path) if self.project_path else "未命名 / Untitled"
        star = " *" if self._dirty else ""
        self.setWindowTitle(f"{name}{star} — FigDataX Desktop {__app_version__} "
                            f"(engine {eng.engine_version})")

    def _mark_dirty(self, *_):
        self._dirty = True
        self._update_title()

    def _clear_dirty(self):
        self._dirty = False
        self._update_title()

    def closeEvent(self, event):
        if self._maybe_save():
            event.accept()
        else:
            event.ignore()

    def _maybe_save(self) -> bool:
        """Returns True when it is OK to proceed (saved / discarded / not dirty)."""
        if not self._dirty:
            return True
        ret = QMessageBox.question(
            self, "未保存的更改 / Unsaved changes",
            "项目有未保存的更改。保存吗？\nThe project has unsaved changes. Save?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if ret == QMessageBox.Save:
            return self._save_project()
        return ret == QMessageBox.Discard

    # ── layout ──
    def _build_center(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self.canvas, "提取工作台 / Workspace")
        self.pdf_view = PdfView()
        self.pdf_view.send_figure_to_canvas.connect(self._digitize_pdf_figure)
        self.tabs.addTab(self.pdf_view, "文档 / Document")
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
        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(["Series", "X", "Y", "conf"])
        self.results.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.results)
        del_btn = QPushButton("删除选中点 / Delete selected")
        del_btn.clicked.connect(self._delete_table_selection)
        layout.addWidget(del_btn)
        export_btn = QPushButton("导出 Excel / Export Excel")
        export_btn.clicked.connect(self._export)
        layout.addWidget(export_btn)
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._row_points: list = []   # row index → DataPoint (identity)

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
        tb.addAction("加点 / Add point", lambda: self.canvas.set_mode(Mode.ADD_POINT))
        tb.addAction("编辑点 / Edit points", lambda: self.canvas.set_mode(Mode.EDIT))
        tb.addSeparator()
        tb.addAction("提取 / Extract", self._extract)

    def _build_menu(self):
        m_file = self.menuBar().addMenu("文件 / File")

        def act(text, slot, shortcut=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            m_file.addAction(a)
            return a

        act("新建项目 / New Project", self._new_project, "Ctrl+N")
        act("打开项目… / Open Project…", self._open_project_dialog, "Ctrl+O")
        self.recent_menu = m_file.addMenu("最近项目 / Recent")
        m_file.addSeparator()
        act("打开图片… / Open Image…", self._open_image, "Ctrl+I")
        act("打开 PDF… / Open PDF…", self._open_pdf, "Ctrl+P")
        m_file.addSeparator()
        act("保存项目 / Save", self._save_project, "Ctrl+S")
        act("项目另存为… / Save As…", self._save_project_as, "Ctrl+Shift+S")
        m_file.addSeparator()
        act("导出 Excel… / Export Excel…", self._export, "Ctrl+E")
        act("导出整篇文档… / Export Document…", self._export_document, "Ctrl+Shift+E")
        m_file.addSeparator()
        act("退出 / Quit", self.close, "Ctrl+Q")
        self._rebuild_recent_menu()

        m_edit = self.menuBar().addMenu("编辑 / Edit")
        a_del = QAction("删除选中点 / Delete selected points", self)
        a_del.triggered.connect(self.canvas.delete_selected_points)
        m_edit.addAction(a_del)

        m_charts = self.menuBar().addMenu("图表 / Charts")
        a_box = QAction("箱线图提取 / Box plot…", self)
        a_box.triggered.connect(self._extract_box)
        m_charts.addAction(a_box)
        a_pie = QAction("饼图提取 / Pie chart…", self)
        a_pie.triggered.connect(self._extract_pie)
        m_charts.addAction(a_pie)
        a_heat = QAction("热图提取 / Heatmap…", self)
        a_heat.triggered.connect(self._extract_heatmap)
        m_charts.addAction(a_heat)

        m_ai = self.menuBar().addMenu("AI")
        a_cfg = QAction("AI 设置… / AI Settings…", self)
        a_cfg.triggered.connect(self._ai_settings)
        m_ai.addAction(a_cfg)
        a_analyze = QAction("AI 分析图形（辅助校准）/ Analyze figure", self)
        a_analyze.triggered.connect(self._ai_analyze_figure)
        m_ai.addAction(a_analyze)
        a_sum = QAction("AI 汇总数据线索 / Summarize data mentions", self)
        a_sum.triggered.connect(self._ai_summarize_mentions)
        m_ai.addAction(a_sum)

    # ── recent files ──
    def _recent(self) -> list:
        return [p for p in self.settings.value("recentProjects", [], type=list)
                if isinstance(p, str)]

    def _push_recent(self, path: str):
        rec = [p for p in self._recent() if p != path]
        rec.insert(0, path)
        self.settings.setValue("recentProjects", rec[:MAX_RECENT])
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self):
        self.recent_menu.clear()
        for p in self._recent():
            a = QAction(os.path.basename(p), self)
            a.setToolTip(p)
            a.triggered.connect(lambda _=False, path=p: self._open_project(path))
            self.recent_menu.addAction(a)
        self.recent_menu.setEnabled(bool(self._recent()))

    # ── project lifecycle ──
    def _new_project(self):
        if not self._maybe_save():
            return
        self.canvas.reset()
        self.project_path = None
        self._refresh_results()
        self._clear_dirty()

    def _open_project_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", f"FigDataX project (*{SUFFIX})")
        if path:
            self._open_project(path)

    def _open_project(self, path: str):
        if not self._maybe_save():
            return
        try:
            session, bgr, target_hsv = load_project(path)
        except ProjectError as exc:
            QMessageBox.critical(self, "Open project", str(exc))
            return
        if bgr is None:
            QMessageBox.warning(
                self, "Open project",
                "项目未包含内嵌图像，且原图路径不存在。\n"
                "No embedded image and the original image path is gone.")
            return
        self.canvas.load_bgr(bgr, session)
        self.canvas.target_hsv = target_hsv
        self.project_path = path
        self._push_recent(path)
        self._refresh_results()
        self._clear_dirty()
        self.statusBar().showMessage(f"Opened {path}")

    def _save_project(self) -> bool:
        if self.project_path is None:
            return self._save_project_as()
        return self._write_project(self.project_path)

    def _save_project_as(self) -> bool:
        default = self.project_path or ""
        if not default and self.canvas.session.image_path:
            default = os.path.splitext(self.canvas.session.image_path)[0] + SUFFIX
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project", default, f"FigDataX project (*{SUFFIX})")
        if not path:
            return False
        return self._write_project(path)

    def _write_project(self, path: str) -> bool:
        try:
            saved = save_project(path, self.canvas.session,
                                 image_bgr=self.canvas.image_bgr,
                                 target_hsv=self.canvas.target_hsv)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save project", str(exc))
            return False
        self.project_path = saved
        self._push_recent(saved)
        self._clear_dirty()
        self.statusBar().showMessage(f"Saved {saved}")
        return True

    # ── actions ──
    def _on_color_picked(self, hsv):
        self.statusBar().showMessage(f"Target color HSV {hsv}")
        self._mark_dirty()

    def _open_image(self):
        if not self._maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open figure image", "", "Images (*.png *.jpg *.jpeg *.tif *.bmp)")
        if path:
            try:
                self.canvas.load_image(path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Error", str(exc))
                return
            self.project_path = None
            self._refresh_results()
            self._clear_dirty()

    def _open_pdf(self):
        if not pdf_available():
            QMessageBox.critical(
                self, "PDF",
                "PDF support needs pypdfium2 + pdfplumber. Reinstall the app venv "
                "(bash app/run_dev.sh) — they are in app/requirements.txt.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF (*.pdf)")
        if not path:
            return
        self.tabs.setCurrentWidget(self.pdf_view)
        self.pdf_view.open_pdf(path)

    def _digitize_pdf_figure(self, bgr, label: str):
        """A figure detected in the PDF was sent to the digitizer canvas."""
        if not self._maybe_save():
            return
        from ..models import ExtractionSession
        session = ExtractionSession(source_label=label)
        self.canvas.load_bgr(bgr, session)
        try:
            self.canvas.session.plot_bbox = eng.auto_detect_plot_area(bgr)
        except Exception:
            self.canvas.session.plot_bbox = None
        self.project_path = None
        self.tabs.setCurrentWidget(self.canvas)
        self._refresh_results()
        self._clear_dirty()
        self.statusBar().showMessage(f"Loaded figure from {label} — calibrate to begin.")

    def _export_document(self):
        """Export everything found in the current PDF (tables + data mentions) plus the
        current digitized figure, to a multi-sheet workbook."""
        pv = self.pdf_view
        if not (pv.tables or pv.mentions or self.canvas.session.total_points()):
            QMessageBox.information(self, "Export", "Open and analyze a PDF first, or extract a figure.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export document workbook", "",
                                              "Excel (*.xlsx)")
        if not path:
            return
        sessions = [self.canvas.session] if self.canvas.session.total_points() else []
        src = pv.doc.path if pv.doc else (self.canvas.session.image_path or "")
        export_workbook(path, sessions=sessions, tables=pv.tables,
                        mentions=pv.mentions, source_name=src)
        self.statusBar().showMessage(f"Exported document workbook {path}")

    def _extract(self):
        try:
            self.canvas.run_extraction()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Extraction", str(exc))

    def _refresh_results(self):
        session = self.canvas.session
        rows = [(s.name, p) for s in session.series for p in s.points]
        self.results.setRowCount(len(rows))
        self._row_points = [p for _, p in rows]
        for r, (name, p) in enumerate(rows):
            self.results.setItem(r, 0, QTableWidgetItem(name))
            self.results.setItem(r, 1, QTableWidgetItem(f"{p.data_x:.4g}"))
            self.results.setItem(r, 2, QTableWidgetItem(f"{p.data_y:.4g}"))
            conf = "手动/manual" if p.manual else f"{p.confidence:.2f}"
            self.results.setItem(r, 3, QTableWidgetItem(conf))

    def _delete_table_selection(self):
        rows = sorted({i.row() for i in self.results.selectedIndexes()}, reverse=True)
        if not rows:
            self.statusBar().showMessage("No rows selected.")
            return
        doomed = {id(self._row_points[r]) for r in rows if r < len(self._row_points)}
        for s in self.canvas.session.series:
            s.points = [p for p in s.points if id(p) not in doomed]
        # rebuild canvas markers + table
        for it in list(self.canvas._point_items):
            self.canvas._scene.removeItem(it)
        self.canvas._point_items = []
        for s in self.canvas.session.series:
            for p in s.points:
                self.canvas._add_point_item(p)
        self.canvas.points_changed.emit()

    # ── special charts (box / pie / heatmap) ──
    def _need_image(self) -> bool:
        if self.canvas.image_bgr is None:
            QMessageBox.information(self, "Charts", "先打开一张图 / open a figure first.")
            return False
        return True

    def _show_chart_result(self, result, source: str):
        from ..export_xlsx import export_chart_result
        from .chart_dialogs import ChartResultDialog
        dlg = ChartResultDialog(result, self)
        if dlg.exec():
            path, _ = QFileDialog.getSaveFileName(self, "Export chart result", "",
                                                  "Excel (*.xlsx)")
            if path:
                export_chart_result(result, path, source)
                self.statusBar().showMessage(f"Exported {path}")

    def _extract_box(self):
        if not self._need_image():
            return
        if not self.canvas.session.calibration.is_ready():
            QMessageBox.information(self, "Box plot",
                                    "需要 Y 轴校准 / calibrate the Y axis first.")
            return
        from ..charts import extract_box
        from ..pipeline import build_calibration
        from .chart_dialogs import BoxParamsDialog
        dlg = BoxParamsDialog(default_hsv=self.canvas.target_hsv, parent=self)
        if not dlg.exec():
            return
        try:
            box_hsv, median_hsv = dlg.values()
            if box_hsv is None:
                box_hsv = self.canvas.target_hsv
            if box_hsv is None:
                raise ValueError("Provide a box color (or pick one with the eyedropper).")
            cal = build_calibration(self.canvas.session.calibration)
            result = extract_box(self.canvas.image_bgr, self.canvas.session.plot_bbox,
                                 cal, box_hsv, median_hsv)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Box plot", str(exc))
            return
        self._show_chart_result(result, self._chart_source())

    def _extract_pie(self):
        if not self._need_image():
            return
        from ..charts import extract_pie
        from .chart_dialogs import PieParamsDialog
        dlg = PieParamsDialog(self)
        if not dlg.exec():
            return
        try:
            center, radius = dlg.values()
            result = extract_pie(self.canvas.image_bgr, center=center, radius=radius)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pie chart", str(exc))
            return
        self._show_chart_result(result, self._chart_source())

    def _extract_heatmap(self):
        if not self._need_image():
            return
        from ..charts import extract_heatmap
        from .chart_dialogs import HeatmapParamsDialog
        dlg = HeatmapParamsDialog(plot_bbox=self.canvas.session.plot_bbox, parent=self)
        if not dlg.exec():
            return
        try:
            bbox, grid, cbar, crange = dlg.values()
            result = extract_heatmap(self.canvas.image_bgr, bbox, grid, cbar, crange)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Heatmap", str(exc))
            return
        self._show_chart_result(result, self._chart_source())

    def _chart_source(self) -> str:
        return (self.canvas.session.source_label or self.canvas.session.image_path
                or self.project_path or "")

    # ── AI assists ──
    def _ai_settings(self):
        from .ai_dialog import AISettingsDialog
        AISettingsDialog(self.settings, self).exec()

    def _ai_provider(self):
        from ..ai import config as aicfg
        cfg = aicfg.load_config(self.settings)
        if not aicfg.provider_available(cfg):
            QMessageBox.warning(
                self, "AI", "所选 AI 提供方不可用（CLI 未安装或未登录）。\n"
                            "Selected AI provider is unavailable — check AI Settings.")
            return None
        return aicfg.build_provider(cfg)

    def _ai_analyze_figure(self):
        if self.canvas.image_bgr is None:
            QMessageBox.information(self, "AI", "先打开一张图 / open a figure first.")
            return
        provider = self._ai_provider()
        if provider is None:
            return
        from ..ai.assist import suggest_calibration
        from .ai_dialog import CalibrationReviewDialog
        bbox = self.canvas.session.plot_bbox
        self.statusBar().showMessage("AI 分析图形中… / analyzing figure…")

        def work():
            return suggest_calibration(provider, self.canvas.image_bgr, bbox)

        def done(sug):
            self.statusBar().clearMessage()
            if sug is None:
                return
            if sug.is_empty():
                QMessageBox.information(self, "AI",
                                       "AI 未能读出刻度 / no ticks read. " + (sug.notes or ""))
                return
            if not bbox:
                QMessageBox.information(
                    self, "AI", "需要先确定绘图区（自动或手动）以映射刻度位置。\n"
                                "A plot area is required to place ticks.")
                return
            dlg = CalibrationReviewDialog(sug, bbox, self)
            if dlg.exec():
                n = self.canvas.apply_calibration_ticks(dlg.confirmed(), bbox)
                self.statusBar().showMessage(f"应用了 {n} 个 AI 校准点 / applied {n} ticks")

        self._run_async(work, done, "AI figure analysis")

    def _ai_summarize_mentions(self):
        mentions = getattr(self.pdf_view, "mentions", [])
        if not mentions:
            QMessageBox.information(self, "AI", "先打开并分析一个 PDF / analyze a PDF first.")
            return
        provider = self._ai_provider()
        if provider is None:
            return
        from ..ai.assist import summarize_mentions
        self.statusBar().showMessage("AI 汇总中… / summarizing…")

        def work():
            return summarize_mentions(provider, mentions)

        def done(text):
            self.statusBar().clearMessage()
            if text is not None:
                dlg = QMessageBox(self)
                dlg.setWindowTitle("AI 数据线索汇总 / Data-mention summary")
                dlg.setText(text)
                dlg.setTextInteractionFlags(Qt.TextSelectableByMouse)
                dlg.exec()

        self._run_async(work, done, "AI summary")

    def _run_async(self, work, done, label: str):
        """Run ``work()`` in a thread; call ``done(result)`` on the UI thread. On error,
        show a message and call ``done(None)``."""
        from PySide6.QtCore import QThread, Signal

        class _W(QThread):
            ok = Signal(object)
            err = Signal(str)

            def run(self):
                try:
                    self.ok.emit(work())
                except Exception as exc:  # noqa: BLE001
                    self.err.emit(str(exc))

        w = _W(self)
        self._ai_worker = w   # keep a reference

        def on_err(msg):
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "AI", f"{label} failed:\n{msg}")
            done(None)

        w.ok.connect(done)
        w.err.connect(on_err)
        w.start()

    def _export(self):
        if not self.canvas.session.total_points():
            QMessageBox.information(self, "Export", "Nothing to export yet — extract first.")
            return
        default = ""
        base_src = self.project_path or self.canvas.session.image_path
        if base_src:
            default = os.path.splitext(base_src)[0] + "_figdatax.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", default,
                                              "Excel (*.xlsx)")
        if path:
            export_session(self.canvas.session, path)
            self.statusBar().showMessage(f"Exported {path}")
