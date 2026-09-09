# MediaAnvil Qt 1.0.0

**[简体中文 →](README-Qt.md)**

MediaAnvil uses a native Qt desktop interface with standard system window decorations. It does not use Tk/TkDND, a frameless window, custom title-bar dragging, or mouse-capture hooks.

## Start the application

Open `dist/MediaAnvilQt/MediaAnvilQt.exe`. Python is not required.

Keep the complete `MediaAnvilQt` folder, including `_internal`; do not copy the EXE by itself.

## Features and interface

All pages share a light-blue background, white rounded cards, and line icons. Conversion pages place selected files and options on the left, with result lists, image details, or complete subtitle text on the right. Narrow windows automatically switch to a vertical layout. Results can be saved as a copy, converted again, or opened in File Explorer. Settings supports immediate Chinese/English switching and keyboard control of toggles with Space. Tag Editor presents basic metadata, lyrics, and artwork side by side, with an expandable matching area for batch lyrics and artwork updates. See the [English User Guide](USER_GUIDE.en.md) for normal operation.

Audio Preview loads the selected file and provides 30-second back, play/pause, and 30-second forward controls. Synchronized lyrics highlight and track the current line. Batch Rename supports selecting individual operations, filename search, CSV preview export, and undo. Search only filters visible rows and does not alter existing selections.

- Audio Preview: playback, pause, seeking, volume, and the Space shortcut; reads matching LRC/SRT/VTT files and synchronized MP3 lyrics, centers the current line, and supports click-to-seek.
- Tag Editor: MP3, FLAC, M4A, OGG, and Opus; title, artist, album, LRC/SRT/VTT import, free rectangular artwork cropping, and lyrics/artwork export. WAV information is read-only.
- Same-directory lyrics and artwork matching with folder scanning, including double-extension names such as `song.wav.vtt` and `song.wav.png`. Ambiguous candidates are left unselected until the user chooses one.
- Lyrics / Subtitles: conversion between LRC, SRT, and VTT, configurable final-line duration, and text result preview.
- Audio Converter: MP3, WAV, FLAC, M4A/AAC, and OGG, with bitrate/quality, sample-rate, channel, and metadata-preservation settings.
- Image Converter: JPG, PNG, WebP, and BMP, with quality settings, transparency handling, and image preview.
- Batch Rename: generates a preview from metadata, shows conflicts, executes selected items, and can undo the most recent batch.
- Files and folders can be dropped onto the current page. Window movement remains responsive during background scanning, conversion, and metadata operations. The content area is temporarily disabled while a task owns its inputs and is restored on completion.

Save As is the default. Conversion outputs avoid existing files automatically, while metadata writes require an explicit choice before overwriting. Batch Rename processes only renameable preview items and never overwrites a file that occupies an original name during undo.

Media processing modules are located in `sub2lrc/` and `core/`; interface code is in `mediaanvil_qt/`. Settings are stored in `%APPDATA%/MediaAnvilQt/settings.json`.

## Run from source and build

Use an official Windows build of Python rather than MSYS2 Python:

```powershell
.build-venv-windows\Scripts\python.exe -m pip install -r requirements-qt.txt
.\tools\download_icu.ps1
.build-venv-windows\Scripts\python.exe main_qt.py
.\build-qt.ps1
```

`build-qt.ps1` uses the project's `.build-venv-windows` environment, isolates the DLL search path, and packages the required Qt DLLs and FFmpeg/FFplay without accepting same-named dependencies from unrelated software. After building, it audits DLL sources, launches the frozen EXE, performs a real audio conversion, and checks FFplay. A failure in any step prevents the build from being reported as successful.

Run the Qt integration tests with:

```powershell
.build-venv-windows\Scripts\python.exe -m unittest discover -s tests -p test_qt_rewrite.py -v
```

## Verification scope

Integration tests cover event-loop responsiveness, conversion, source-file preservation, metadata Save As, rename and undo behavior, lyrics seeking, settings, and cropping. Automated tests cannot prove that native title-bar movement is visually stable on every user system; verify the final Qt build by dragging its window on a real desktop.

## Third-party components

Qt/PySide6/Shiboken 6.11.2 is distributed as separate dynamic libraries. The ICU 78.3 runtime required by Qt is downloaded through `tools/download_icu.ps1`; its license is in `licenses/ICU-LICENSE.txt`. Qt/PySide open-source license information is provided in `licenses/qt/`. Source and build information:

- https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=6.11.2
- https://code.qt.io/cgit/qt/qtbase.git/tree/?h=v6.11.2
- https://doc.qt.io/qtforpython-6/building_from_source/index.html

Qt/PySide licensing does not change the copyright ownership of other project code. Third-party libraries may be replaced independently when ABI-compatible; retain all distributed license notices. See `THIRD_PARTY_NOTICES.md` for FFmpeg/FFplay details.
