"""Cooperative cancellation and task-history primitives shared by UI workers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class TaskRecord:
    """One item in a recent batch task, kept locally only for retry actions."""

    source: Path
    state: str
    message: str = ""
    output: Path | None = None

    @property
    def failed(self) -> bool:
        return self.state == "失败"


@dataclass(frozen=True)
class TaskHistory:
    kind: str
    records: tuple[TaskRecord, ...] = ()

    @property
    def failures(self) -> tuple[TaskRecord, ...]:
        return tuple(record for record in self.records if record.failed)

    @property
    def succeeded(self) -> tuple[TaskRecord, ...]:
        return tuple(record for record in self.records if not record.failed)


__all__ = ["CancellationToken", "TaskCancelled", "TaskRecord", "TaskHistory"]
