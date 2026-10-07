"""Small atomic JSON stores for local recovery data."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time


def replace_file(source: Path, destination: Path) -> None:
    """Keep atomic replacement while tolerating brief Windows sharing locks."""
    for attempt in range(5):
        try:
            os.replace(source,destination);return
        except PermissionError as exc:
            if getattr(exc,'winerror',None) not in (5,32,33) or attempt==4:raise
            time.sleep(.025*2**attempt)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + "-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        replace_file(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
