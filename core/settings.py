"""Persistent, version-tolerant application settings for MediaAnvil."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from typing import Any


PRODUCT_NAME = "MediaAnvil"
DEFAULT_SETTINGS: dict[str, Any] = {
    "default_output_location": "source",
    "default_output_directory": "",
    "default_save_mode": "save_as",
    "default_mp3_bitrate": 192,
    "default_aac_bitrate": 192,
    "default_keep_sample_rate": True,
    "default_keep_channels": True,
    "default_preserve_metadata": True,
    "default_image_quality": 90,
    "default_webp_quality": 90,
    "default_keep_image_size": True,
    "subtitle_final_duration": 5.0,
    "auto_load_same_name_lyrics": True,
    "prefer_embedded_mp3_lyrics": False,
    "default_volume": 80,
    "remember_last_page": False,
    "last_page": "preview",
    "include_subfolders": False,
    "language": "zh_CN",
}

_CHOICES: dict[str, tuple[Any, ...]] = {
    "default_output_location": ("source", "custom"),
    "default_save_mode": ("save_as", "overwrite"),
    "default_mp3_bitrate": (128, 192, 256, 320),
    "default_aac_bitrate": (96, 128, 192, 256),
    "language": ("zh_CN", "en_US"),
}
_RANGES: dict[str, tuple[float, float]] = {
    "default_image_quality": (1, 100),
    "default_webp_quality": (1, 100),
    "default_volume": (0, 100),
    "subtitle_final_duration": (0.1, 3600.0),
}
_last_load_warning: str | None = None
_current_settings: dict[str, Any] | None = None


def settings_path(appdata_directory: str | Path | None = None) -> Path:
    """Return ``%APPDATA%\\MediaAnvil\\settings.json`` (or a test override)."""
    if appdata_directory is None:
        appdata_directory = os.environ.get("APPDATA")
    base = Path(appdata_directory) if appdata_directory else Path.home() / "AppData" / "Roaming"
    return base / PRODUCT_NAME / "settings.json"


def default_settings() -> dict[str, Any]:
    return deepcopy(DEFAULT_SETTINGS)


def _normalise(data: object) -> dict[str, Any]:
    result = default_settings()
    if not isinstance(data, dict):
        return result
    for key, default in DEFAULT_SETTINGS.items():
        value = data.get(key, default)
        if key in _CHOICES:
            if value in _CHOICES[key]:
                result[key] = value
            continue
        if key in _RANGES:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                low, high = _RANGES[key]
                result[key] = max(low, min(high, value))
            continue
        if isinstance(default, bool):
            if isinstance(value, bool):
                result[key] = value
        elif isinstance(default, str):
            if isinstance(value, str):
                result[key] = value
        elif isinstance(default, (int, float)):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                result[key] = value
    return result


def load_settings(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load settings, merging known keys over safe defaults.

    Corrupt or unreadable files are ignored and surfaced through
    :func:`last_load_warning`; startup can therefore continue normally.
    """
    global _current_settings, _last_load_warning
    target = Path(config_path) if config_path is not None else settings_path()
    _last_load_warning = None
    try:
        raw = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raw = {}
        _last_load_warning = f"设置文件无法读取，已恢复默认设置：{exc}"
    _current_settings = _normalise(raw)
    return deepcopy(_current_settings)


def last_load_warning() -> str | None:
    return _last_load_warning


def save_settings(settings: dict[str, Any] | None = None, config_path: str | Path | None = None) -> Path:
    """Persist known settings atomically as UTF-8 JSON."""
    global _current_settings
    values = _normalise(settings if settings is not None else (_current_settings or {}))
    target = Path(config_path) if config_path is not None else settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=target.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    _current_settings = deepcopy(values)
    return target


def get_setting(key: str, default: Any = None) -> Any:
    global _current_settings
    if _current_settings is None:
        load_settings()
    return deepcopy((_current_settings or {}).get(key, default))


def set_setting(key: str, value: Any) -> Any:
    global _current_settings
    if _current_settings is None:
        load_settings()
    values = dict(_current_settings or default_settings())
    values[key] = value
    _current_settings = _normalise(values)
    return deepcopy(_current_settings.get(key))


def reset_settings(config_path: str | Path | None = None) -> dict[str, Any]:
    values = default_settings()
    save_settings(values, config_path)
    return values


__all__ = [
    "DEFAULT_SETTINGS",
    "PRODUCT_NAME",
    "default_settings",
    "get_setting",
    "last_load_warning",
    "load_settings",
    "reset_settings",
    "save_settings",
    "set_setting",
    "settings_path",
]
