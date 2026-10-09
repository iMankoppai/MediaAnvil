"""File-dialog categories, remembered directories and filters."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QStandardPaths


_DIALOG_SETTING_KEYS = {
    'audio': 'last_audio_directory',
    'image': 'last_image_directory',
    'subtitle': 'last_subtitle_directory',
    'output': 'last_output_directory',
}
_DIALOG_STANDARD_LOCATIONS = {
    'audio': QStandardPaths.StandardLocation.MusicLocation,
    'image': QStandardPaths.StandardLocation.PicturesLocation,
    'subtitle': QStandardPaths.StandardLocation.DocumentsLocation,
    'output': QStandardPaths.StandardLocation.DocumentsLocation,
}


_DIALOG_FILTER_KEYS = {
    'audio': 'last_audio_filter',
    'image': 'last_image_filter',
    'subtitle': 'last_subtitle_filter',
    'output': 'last_output_filter',
}


def dialog_category(value):
    """Return the persisted directory category for a page or file-list kind."""
    return 'audio' if value in ('audio', 'rename', 'editor', 'preview') else value if value in _DIALOG_SETTING_KEYS else 'output'


def dialog_initial_directory(widget, category):
    """Choose a stable file-dialog start directory instead of the process cwd."""
    category = dialog_category(category)
    app = widget.window()
    saved = getattr(app, 'settings', {}).get(_DIALOG_SETTING_KEYS[category], '')
    if saved and Path(saved).is_dir():
        return str(Path(saved))
    fallback = QStandardPaths.writableLocation(_DIALOG_STANDARD_LOCATIONS[category])
    return fallback if fallback and Path(fallback).is_dir() else str(Path.home())


def remember_dialog_selection(widget, category, selection):
    """Remember the parent directory of a successful dialog selection."""
    if not selection:
        return
    category = dialog_category(category)
    selected = Path(selection)
    directory = selected if selected.is_dir() else selected.parent
    if directory.is_dir():
        app = widget.window()
        settings = getattr(app, 'settings', None)
        if settings is not None:
            settings[_DIALOG_SETTING_KEYS[category]] = str(directory.resolve())


def dialog_filters(widget, category, filters):
    """Order file-dialog filters so the last used one is offered first.

    Windows shows the first entry of the filter list, and Qt's convenience
    dialog API cannot select an index, so remembering means reordering.
    """
    category = dialog_category(category)
    available = [value for value in filters if value]
    if len(available) < 2:
        return ';;'.join(available)
    saved = getattr(widget.window(), 'settings', {}).get(_DIALOG_FILTER_KEYS[category], '')
    if saved in available:
        available.insert(0, available.pop(available.index(saved)))
    return ';;'.join(available)


def remember_dialog_filter(widget, category, chosen):
    """Persist which filter the user actually used."""
    if not chosen:
        return
    category = dialog_category(category)
    settings = getattr(widget.window(), 'settings', None)
    if settings is not None:
        settings[_DIALOG_FILTER_KEYS[category]] = str(chosen)

