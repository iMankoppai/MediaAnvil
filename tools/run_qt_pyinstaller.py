"""Run PyInstaller with an explicit, project-owned DLL search path."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _runtime_paths() -> list[Path]:
    python_base = Path(sys.base_prefix)
    pyside = Path(__import__("PySide6").__file__).resolve().parent
    system_root = Path(os.environ["SystemRoot"])
    return [
        ROOT / "vendor" / "icu",
        pyside,
        Path(sys.executable).resolve().parent,
        python_base,
        python_base / "DLLs",
        system_root / "System32",
        system_root,
    ]


def main() -> int:
    paths = [str(path) for path in _runtime_paths() if path.is_dir()]
    os.environ["PATH"] = os.pathsep.join(paths)
    from PyInstaller.__main__ import run

    run(sys.argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
