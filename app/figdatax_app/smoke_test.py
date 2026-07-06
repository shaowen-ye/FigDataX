"""Headless end-to-end smoke test (run with QT_QPA_PLATFORM=offscreen).

Proves the app's image → calibrate → extract → export path works without a display,
and that the Qt widgets instantiate. Exit code 0 = pass.
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
from .ui.main_window import MainWindow  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(__file__), "assets", "sample", "sample_scatter.png")


def main() -> int:
    app = QApplication.instance() or QApplication([])

    # 1. Widgets instantiate and the sample loads into the canvas.
    win = MainWindow()
    win.canvas.load_image(SAMPLE)
    assert win.canvas.session.image_path == SAMPLE

    # 2. Headless calibrate + extract + export.
    session = ExtractionSession(image_path=SAMPLE)
    session.calibration.x_points = [CalibPoint(90, 0), CalibPoint(590, 10)]
    session.calibration.y_points = [CalibPoint(380, 0), CalibPoint(40, 25)]
    series = extract_series(session, (0, 255, 255), color_distance=40)
    assert len(series.points) >= 8, f"expected >=8 points, got {len(series.points)}"

    max_err = max(abs(p.data_y - 2 * p.data_x) for p in series.points)
    assert max_err < 0.5, f"y≈2x expected, max error {max_err:.3f}"

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out.xlsx")
        export_session(session, out)
        assert os.path.getsize(out) > 0

    print(f"SMOKE OK — engine {eng.engine_version}, "
          f"{len(series.points)} points, max |y-2x| = {max_err:.3f}")
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
