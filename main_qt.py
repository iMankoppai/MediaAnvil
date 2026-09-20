from __future__ import annotations

import os
from pathlib import Path
import sys


# The Qt wheel used by this project resolves ICU at load time. Place the
# project-owned runtime directory on PATH before importing any PySide module.
# Updating PATH is deliberate here: ``os.add_dll_directory`` changes Windows'
# loader policy and prevents PySide from finding its own companion DLLs.
if os.name == "nt":
    _runtime_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    _icu_directory = _runtime_root if hasattr(sys, "_MEIPASS") else _runtime_root / "vendor" / "icu"
    if _icu_directory.is_dir():
        os.environ["PATH"] = str(_icu_directory) + os.pathsep + os.environ.get("PATH", "")
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller keeps PySide extension modules one directory below the
        # application runtime. Preload Qt's dependency chain by absolute path
        # so ordinary Explorer launches do not depend on PATH search order.
        import ctypes

        _pyside_directory = _runtime_root / "PySide6"
        for _library in ("icudt78.dll", "icuuc.dll", "Qt6Core.dll"):
            _candidate = _pyside_directory / _library
            if _candidate.is_file():
                ctypes.WinDLL(str(_candidate))

from mediaanvil_qt.app import main

if __name__ == '__main__':
    raise SystemExit(main())
