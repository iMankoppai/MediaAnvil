"""Qt worker thread and cancellable progress/checkpoint reporting."""
from __future__ import annotations
from PySide6.QtCore import Signal, QThread


class TaskReporter:
    """Callable progress reporter exposed to background jobs."""
    def __init__(self, signal, token, checkpoint=None):
        self._signal = signal; self._token = token; self._checkpoint = checkpoint
    @property
    def cancelled(self): return self._token.cancelled
    def __call__(self, percent, text=''):
        self.raise_if_cancelled(); self._signal.emit(float(percent), str(text))
    def raise_if_cancelled(self): self._token.raise_if_cancelled()
    def register_process(self, process): self._token.register_process(process)
    def unregister_process(self, process): self._token.unregister_process(process)
    def checkpoint(self, record):
        if self._checkpoint is not None:self._checkpoint.emit(record)


class Worker(QThread):
    result = Signal(object)
    error = Signal(str)
    cancelled = Signal()
    progress = Signal(float, str)
    checkpoint = Signal(object)
    def __init__(self, work, parent=None):
        from core.tasks import CancellationToken
        super().__init__(parent); self.work = work; self.token = CancellationToken()
    def request_cancel(self): self.token.cancel()
    def run(self):
        from core.tasks import TaskCancelled
        try: self.result.emit(self.work(TaskReporter(self.progress, self.token, self.checkpoint)))
        except TaskCancelled: self.cancelled.emit()
        except Exception as exc: self.error.emit(str(exc))

