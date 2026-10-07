"""Cooperative cancellation and task-history primitives shared by UI workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Event, Lock
from typing import Any
from uuid import uuid4

from .persistence import read_json, write_json


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
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    task_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def failures(self) -> tuple[TaskRecord, ...]:
        return tuple(record for record in self.records if record.failed)

    @property
    def succeeded(self) -> tuple[TaskRecord, ...]:
        return tuple(record for record in self.records if record.state == "已完成")

    @property
    def retryable(self) -> tuple[TaskRecord, ...]:
        return tuple(record for record in self.records if record.state in {"失败", "已取消", "已中断"})


def save_task_histories(path: Path, histories: tuple[TaskHistory, ...] | list[TaskHistory]) -> None:
    write_json(path, {"version": 1, "tasks": [
        {"kind": task.kind, "parameters": task.parameters, "created_at": task.created_at,
         "task_id": task.task_id, "records": [
             {"source": str(r.source), "state": r.state, "message": r.message,
              "output": str(r.output) if r.output else None} for r in task.records]}
        for task in histories[-20:]]})


def load_task_histories(path: Path) -> list[TaskHistory]:
    raw = read_json(path, {})
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("tasks"), list):
        return []
    histories = []
    for value in raw["tasks"][-20:]:
        try:
            if not isinstance(value["parameters"], dict) or not isinstance(value["records"], list):
                continue
            records = []
            for r in value["records"]:
                if not isinstance(r["source"], str) or not isinstance(r["state"], str):
                    raise ValueError("Invalid task record")
                state = "已中断" if r["state"] in {"等待", "处理中"} else r["state"]
                records.append(TaskRecord(Path(r["source"]), state, str(r.get("message", "")),
                                          Path(r["output"]) if r.get("output") else None))
            histories.append(TaskHistory(str(value["kind"]), tuple(records), value["parameters"],
                                         str(value["created_at"]), str(value["task_id"])))
        except (KeyError, TypeError, ValueError):
            continue
    return histories


__all__ = ["CancellationToken", "TaskCancelled", "TaskRecord", "TaskHistory", "save_task_histories", "load_task_histories"]
