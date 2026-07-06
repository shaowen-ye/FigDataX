"""Qt worker plumbing — run engine calls off the UI thread.

QRunnable + signals so the GUI never blocks on OpenCV/extraction work.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    started = Signal()
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class CallableWorker(QRunnable):
    """Run ``fn(*args, **kwargs)`` on the thread pool and emit its result/error."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        self.signals.started.emit()
        try:
            out = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(out)
        finally:
            self.signals.finished.emit()
