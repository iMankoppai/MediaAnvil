"""Shared atomic output handling for MP3 tag operations."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable


def apply_to_mp3_copy(
    source: str | Path,
    destination: str | Path | None,
    edit: Callable[[Path], None],
) -> Path:
    """Edit a temporary copy, then atomically replace the chosen output path."""
    source_path = Path(source)
    target_path = source_path if destination is None else Path(destination)
    if target_path.suffix.lower() != ".mp3":
        raise ValueError("输出文件的扩展名必须是 .mp3。")
    if not target_path.parent.is_dir():
        raise ValueError("输出目录不存在或无法访问。")

    handle, temporary_name = tempfile.mkstemp(
        prefix=".sub2lrc-",
        suffix=".mp3",
        dir=target_path.parent,
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        shutil.copy2(source_path, temporary_path)
        edit(temporary_path)
        os.replace(temporary_path, target_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return target_path
