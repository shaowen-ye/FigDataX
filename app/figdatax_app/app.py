"""QApplication bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("FigDataX Desktop")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
