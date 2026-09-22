"""Local, privacy-preserving task log for MediaAnvil.

Only operational facts are recorded: the task kind, how many inputs were
handled, how many succeeded and why the rest failed. Media content, file
names, lyrics text and tags are never written, and nothing is ever uploaded.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .settings import PRODUCT_NAME

LOG_DIRECTORY_NAME = "logs"
LOG_FILE_NAME = "tasks.log"
MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 5


def log_directory(appdata_directory: str | Path | None = None) -> Path:
    """Return ``%APPDATA%\\MediaAnvilQt\\logs`` (or a test override)."""
    if appdata_directory is None:
        appdata_directory = os.environ.get("APPDATA")
    base = Path(appdata_directory) if appdata_directory else Path.home() / "AppData" / "Roaming"
    return base / f"{PRODUCT_NAME}Qt" / LOG_DIRECTORY_NAME


def _rotate(directory: Path, maximum: int, backups: int) -> Path:
    target = directory / LOG_FILE_NAME
    try:
        if target.stat().st_size < maximum:
            return target
    except OSError:
        return target
    # Keep ``backups`` files in total: the active log plus numbered history.
    (directory / f"{LOG_FILE_NAME}.{backups - 1}").unlink(missing_ok=True)
    for index in range(backups - 2, 0, -1):
        older = directory / f"{LOG_FILE_NAME}.{index}"
        if older.is_file():
            os.replace(older, directory / f"{LOG_FILE_NAME}.{index + 1}")
    os.replace(target, directory / f"{LOG_FILE_NAME}.1")
    return target


def record_task(kind: str, inputs: int, succeeded: int, failures: tuple[str, ...] = (),
                directory: str | Path | None = None, maximum: int = MAX_BYTES,
                backups: int = BACKUP_COUNT) -> Path | None:
    """Append one JSON line describing a finished task.

    Returns the log path, or ``None`` when logging was not possible. Logging
    must never break a media task, so every error is swallowed.
    """
    try:
        target_directory = Path(directory) if directory is not None else log_directory()
        target_directory.mkdir(parents=True, exist_ok=True)
        target = _rotate(target_directory, maximum, backups)
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "task": str(kind),
            "inputs": int(inputs),
            "succeeded": int(succeeded),
            "failed": int(len(failures)),
            "reasons": [str(reason)[:300] for reason in failures][:10],
        }
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return target
    except OSError:
        return None


def read_entries(directory: str | Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Read the most recent log entries, newest last (for tests and support)."""
    target_directory = Path(directory) if directory is not None else log_directory()
    target = target_directory / LOG_FILE_NAME
    if not target.is_file():
        return []
    entries: list[dict[str, Any]] = []
    try:
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return entries[-limit:]


__all__ = [
    "BACKUP_COUNT",
    "LOG_DIRECTORY_NAME",
    "LOG_FILE_NAME",
    "MAX_BYTES",
    "log_directory",
    "read_entries",
    "record_task",
]
