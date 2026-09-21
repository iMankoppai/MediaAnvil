"""Cooperative cancellation primitives shared by UI and worker code."""

from __future__ import annotations

from threading import Event, Lock
from typing import Any


class TaskCancelled(Exception):
    """Raised when the user asks a background task to stop."""


class CancellationToken:
    """Thread-safe cancellation flag with optional child-process tracking."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._process: Any | None = None

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise TaskCancelled("任务已取消")

    def cancel(self) -> None:
        self._event.set()
        with self._lock:
            process = self._process
        if process is not None:
            try:
                process.terminate()
            except (OSError, ProcessLookupError):
                pass

    def register_process(self, process: Any) -> None:
        with self._lock:
            self._process = process
        if process is not None and self.cancelled:
            try:
                process.terminate()
            except (OSError, ProcessLookupError):
                pass

    def unregister_process(self, process: Any) -> None:
        with self._lock:
            if self._process is process:
                self._process = None


__all__ = ["CancellationToken", "TaskCancelled"]
