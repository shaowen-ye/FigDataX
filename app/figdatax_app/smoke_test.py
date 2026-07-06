"""Headless end-to-end smoke test (run with QT_QPA_PLATFORM=offscreen).

Covers the app skeleton plus Phase 1: image → calibrate → extract → export,
manual point add/move/delete on the canvas, and .fdx project save/load round-trip.
Exit code 0 = pass.
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from . import engine_bridge as eng  # noqa: E402
from .data_mentions import rank, scan_pages  # noqa: E402
from .models import CalibPoint, ExtractionSession  # noqa: E402
from .pdf_document import PdfDocument, pdf_available  # noqa: E402
from .pipeline import extract_series  # noqa: E402
from .export_xlsx import export_session, export_workbook  # noqa: E402
from .project import load_project, save_project  # noqa: E402
from .ui.main_window import MainWindow  # noqa: E402

ASSETS = os.path.join(os.path.dirname(__file__), "assets", "sample")
SAMPLE = os.path.join(ASSETS, "sample_scatter.png")
SAMPLE_PDF = os.path.join(ASSETS, "sample_paper.pdf")

CAL_X = [CalibPoint(90, 0, scene_x=90, scene_y=380),
         CalibPoint(590, 10, scene_x=590, scene_y=380)]
CAL_Y = [CalibPoint(380, 0, scene_x=90, scene_y=380),
         CalibPoint(40, 25, scene_x=90, scene_y=40)]


def check_pipeline() -> int:
    """Headless calibrate + extract + export (no widgets)."""
    session = ExtractionSession(image_path=SAMPLE)
    session.calibration.x_points = list(CAL_X)
    session.calibration.y_points = list(CAL_Y)
    series = extract_series(session, (0, 255, 255), color_distance=40)
    assert len(series.points) >= 8, f"expected >=8 points, got {len(series.points)}"
    max_err = max(abs(p.data_y - 2 * p.data_x) for p in series.points)
    assert max_err < 0.5, f"y≈2x expected, max error {max_err:.3f}"

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out.xlsx")
        export_session(session, out)
        assert os.path.getsize(out) > 0
    print(f"  pipeline OK — {len(series.points)} points, max |y-2x| = {max_err:.3f}")
    return len(series.points)


def check_point_editing(win: MainWindow):
    """Phase 1: manual add / drag-update / delete, synced with the results table."""
    canvas = win.canvas
    canvas.load_image(SAMPLE)
    canvas.session.calibration.x_points = list(CAL_X)
    canvas.session.calibration.y_points = list(CAL_Y)
    canvas.target_hsv = (0, 255, 255)
    series = canvas.run_extraction(color_distance=40)
    n0 = len(series.points)
    assert win.results.rowCount() == n0, "results table out of sync after extraction"

    # add a manual point at a known pixel: x=340 → data (5, ...)
    pt = canvas.add_manual_point(340, 240)
    assert pt is not None and pt.manual
    assert canvas.session.total_points() == n0 + 1
    assert win.results.rowCount() == n0 + 1, "table missed manual point"

    # simulate a drag: move the marker item; itemChange must update the model
    item = canvas._point_items[-1]
    old_dx = item.point.data_x
    item.setPos(item.pos().x() + 50, item.pos().y())
    assert abs(item.point.px - 390) < 1e-6, "drag did not update pixel coords"
    assert item.point.data_x > old_dx, "drag did not recompute data coords"

    # delete it via selection
    item.setSelected(True)
    deleted = canvas.delete_selected_points()
    assert deleted == 1 and canvas.session.total_points() == n0
    assert win.results.rowCount() == n0, "table out of sync after delete"
    print(f"  point editing OK — add/drag/delete on {n0}+1 points")
    return n0


def check_project_roundtrip(win: MainWindow):
    """Phase 1: .fdx save → load restores image, calibration, points, color."""
    canvas = win.canvas
    n_before = canvas.session.total_points()
    shape_before = canvas.image_bgr.shape
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "demo.fdx")
        saved = save_project(path, canvas.session, image_bgr=canvas.image_bgr,
                             target_hsv=canvas.target_hsv)
        session2, bgr2, hsv2 = load_project(saved)
        assert bgr2 is not None and bgr2.shape == shape_before, "embedded image lost"
        assert session2.total_points() == n_before, "points lost in round-trip"
        assert len(session2.calibration.x_points) == 2
        assert session2.calibration.x_points[1].value == 10
        assert hsv2 == (0, 255, 255), "target color lost"

        # loading into the canvas restores overlays and table
        canvas.load_bgr(bgr2, session2)
        canvas.target_hsv = hsv2
        win._refresh_results()
        assert len(canvas._point_items) == n_before, "markers not restored"
        assert win.results.rowCount() == n_before, "table not restored"
    print(f"  project round-trip OK — {n_before} points, image {shape_before[1]}x{shape_before[0]}")


def check_pdf_pipeline(win: MainWindow):
    """Phase 2: figure detection → digitize crop, table extraction, data mentions,
    and multi-sheet workbook export."""
    if not pdf_available():
        print("  pdf pipeline SKIPPED (pypdfium2/pdfplumber missing)")
        return
    doc = PdfDocument(SAMPLE_PDF)
    assert doc.n_pages == 1

    figs = doc.detect_figures(0)
    assert figs, "no embedded figure detected in sample PDF"
    crop = doc.crop_figure(figs[0])
    assert crop.ndim == 3 and crop.shape[0] > 80 and crop.shape[1] > 80

    tables = doc.detect_tables(0)
    assert tables and tables[0].shape == (4, 4), f"expected a 4×4 table, got {tables}"
    assert tables[0].rows[0][0].lower() == "site"

    mentions = rank(scan_pages(doc.all_text()))
    cats = {m.category for m in mentions}
    for needed in ("mean±sd", "n=", "p-value", "table-ref", "figure-ref"):
        assert needed in cats, f"data-mention scanner missed {needed}: {cats}"
    meansd = next(m for m in mentions if m.category == "mean±sd")
    assert meansd.match_text == "4.2 +/- 0.8", f"bad mean±sd span: {meansd.match_text!r}"

    # feed the detected figure into the canvas (as the GUI would)
    win._digitize_pdf_figure(crop, "sample_paper.pdf p1 figure 1")
    assert win.canvas.image_bgr is not None
    assert win.canvas.session.source_label.startswith("sample_paper.pdf")

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "doc.xlsx")
        export_workbook(out, sessions=[], tables=tables, mentions=mentions,
                        source_name=SAMPLE_PDF)
        assert os.path.getsize(out) > 0
    doc.close()
    print(f"  pdf pipeline OK — 1 figure, table {tables[0].shape}, "
          f"{len(mentions)} mentions")


def check_ai_layer():
    """AI provider layer with the offline FakeProvider: figure→calibration suggestion,
    frac→pixel mapping, applying confirmed ticks, and mention summarization."""
    from .ai.assist import frac_to_pixel, suggest_calibration, summarize_mentions
    from .ai.providers import ClaudeCliProvider, CodexCliProvider, FakeProvider
    from .models import ExtractionSession
    import cv2

    fake = FakeProvider(response=(
        '{"chart_type":"scatter",'
        '"x_ticks":[{"value":0,"frac":0.0},{"value":10,"frac":1.0}],'
        '"y_ticks":[{"value":0,"frac":0.0},{"value":25,"frac":1.0}],'
        '"series_colors":["#00ffff"],"notes":"clean"}'))
    img = cv2.imread(SAMPLE)
    sug = suggest_calibration(fake, img, plot_bbox=(90, 40, 590, 380))
    assert sug.chart_type == "scatter" and len(sug.x_ticks) == 2
    px = frac_to_pixel(sug.x_ticks[1], (90, 40, 590, 380))
    assert abs(px - 590) < 1e-6, f"frac→pixel wrong: {px}"

    # apply confirmed ticks to a canvas session
    from PySide6.QtWidgets import QApplication  # noqa: F401 (app already exists)
    from .ui.canvas import DigitizerCanvas
    canvas = DigitizerCanvas()
    canvas.load_bgr(img, ExtractionSession(image_path=SAMPLE))
    confirmed = [("x", t.value, t) for t in sug.x_ticks] + \
                [("y", t.value, t) for t in sug.y_ticks]
    n = canvas.apply_calibration_ticks(confirmed, (90, 40, 590, 380))
    assert n == 4 and canvas.session.calibration.is_ready(), "AI ticks not applied"

    class M:
        def __init__(s, p, c, t, sent):
            s.page_label, s.category, s.match_text, s.sentence = p, c, t, sent
    summary = summarize_mentions(FakeProvider(response="- p1: CPUE 4.2±0.8"),
                                 [M(1, "mean±sd", "4.2 +/- 0.8", "…")])
    assert "4.2" in summary
    print(f"  ai layer OK — providers(claude={ClaudeCliProvider.available()}, "
          f"codex={CodexCliProvider.available()}), 4 AI ticks applied")


def check_special_charts():
    """Phase-3 chart wrappers: pie fractions on a synthetic pie, and box/heatmap
    wrappers return the right table shape (values checked in the engine's own suite)."""
    import math
    import cv2
    import numpy as np
    from .charts import extract_pie, extract_heatmap
    from .export_xlsx import export_chart_result

    img = np.full((300, 300, 3), 255, np.uint8)
    cx, cy, r = 150, 150, 100

    def wedge(a0, a1, color):
        pts = [(cx, cy)]
        for a in np.linspace(a0, a1, 60):
            pts.append((int(cx + r * math.cos(math.radians(a))),
                        int(cy - r * math.sin(math.radians(a)))))
        cv2.fillPoly(img, [np.array(pts, np.int32)], color)

    wedge(0, 180, (0, 0, 255)); wedge(180, 288, (0, 255, 0)); wedge(288, 360, (255, 0, 0))
    pie = extract_pie(img, center=(cx, cy), radius=r)
    assert pie.kind == "pie" and len(pie.rows) == 3, f"pie rows: {pie.rows}"
    fracs = sorted(row[3] for row in pie.rows)
    assert abs(fracs[-1] - 0.5) < 0.05, f"largest wedge ≈0.5, got {fracs[-1]}"

    # heatmap wrapper shape on a simple vertical gradient grid + colorbar
    hm = np.zeros((100, 120, 3), np.uint8)
    for j in range(120):
        hm[:, j] = (0, 0, int(255 * j / 119))
    cbar = np.zeros((100, 10, 3), np.uint8)
    for i in range(100):
        cbar[i, :] = (0, 0, int(255 * (99 - i) / 99))
    canvas = np.full((120, 160, 3), 255, np.uint8)
    canvas[10:110, 10:130] = hm
    canvas[10:110, 140:150] = cbar
    res = extract_heatmap(canvas, (10, 10, 130, 110), (4, 4), (140, 10, 150, 110), (0, 1))
    assert res.kind == "heatmap" and res.meta["grid_shape"] == (4, 4), res.meta

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "pie.xlsx")
        export_chart_result(pie, out, "smoke")
        assert os.path.getsize(out) > 0
    print(f"  special charts OK — pie {len(pie.rows)} wedges, heatmap {res.meta['grid_shape']}")


def main() -> int:
    app = QApplication.instance() or QApplication([])

    win = MainWindow()
    win.canvas.load_image(SAMPLE)
    assert win.canvas.session.image_path == SAMPLE

    n = check_pipeline()
    check_point_editing(win)
    check_project_roundtrip(win)
    win._dirty = False   # headless: avoid the modal unsaved-changes prompt in _digitize
    check_pdf_pipeline(win)
    check_ai_layer()
    check_special_charts()

    win._dirty = False   # and again before close
    print(f"SMOKE OK — engine {eng.engine_version}, {n} extracted points")
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
