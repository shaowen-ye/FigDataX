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
from .models import CalibPoint, ExtractionSession  # noqa: E402
from .pipeline import extract_series  # noqa: E402
from .export_xlsx import export_session  # noqa: E402
from .project import load_project, save_project  # noqa: E402
from .ui.main_window import MainWindow  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(__file__), "assets", "sample", "sample_scatter.png")

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


def main() -> int:
    app = QApplication.instance() or QApplication([])

    win = MainWindow()
    win.canvas.load_image(SAMPLE)
    assert win.canvas.session.image_path == SAMPLE

    n = check_pipeline()
    check_point_editing(win)
    check_project_roundtrip(win)

    win._dirty = False  # avoid the unsaved-changes prompt in headless close
    print(f"SMOKE OK — engine {eng.engine_version}, {n} extracted points")
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
