"""QApplication bootstrap."""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("FigDataX Desktop")
    window = MainWindow()
    window.show()
    # Headless launch check: FIGDATAX_SELFTEST_QUIT=1 starts the event loop and quits
    # immediately, so packaging can be verified without a display or user.
    if os.environ.get("FIGDATAX_SELFTEST_QUIT"):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
