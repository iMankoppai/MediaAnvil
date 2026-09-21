"""Windows filename validation used by generated output names."""

from __future__ import annotations

import re


INVALID_FILENAME_CHARACTERS = frozenset('<>:"/\\|?*')
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
_WHITESPACE = re.compile(r"\s+")


def is_windows_reserved_name(filename: str) -> bool:
    """Return true for device names such as CON, NUL.txt and COM1."""
    stem = filename.rstrip(" .").split(".", 1)[0]
    return stem.upper() in WINDOWS_RESERVED_NAMES


def sanitize_windows_stem(value: str, *, replacement: str = " ") -> str:
    """Return a safe filename stem while preserving readable Unicode text."""
    cleaned = "".join(
        replacement if character in INVALID_FILENAME_CHARACTERS or ord(character) < 32 else character
        for character in value
    )
    cleaned = _WHITESPACE.sub(" ", cleaned).strip().rstrip(" .")
    if is_windows_reserved_name(cleaned):
        cleaned += "_"
    return cleaned


def validate_windows_filename(filename: str) -> None:
    """Raise ValueError when a Windows filename component is unsafe."""
    if not filename or filename in {".", ".."}:
        raise ValueError("文件名不能为空。")
    if any(character in INVALID_FILENAME_CHARACTERS or ord(character) < 32 for character in filename):
        raise ValueError("文件名包含 Windows 不允许的字符。")
    if filename.endswith((" ", ".")):
        raise ValueError("Windows 文件名不能以空格或句点结尾。")
    if is_windows_reserved_name(filename):
        raise ValueError("文件名是 Windows 保留名称（例如 CON、NUL、COM1）。")
    if len(filename) > 255:
        raise ValueError("文件名过长（最多 255 个字符）。")


__all__ = [
    "INVALID_FILENAME_CHARACTERS",
    "WINDOWS_RESERVED_NAMES",
    "is_windows_reserved_name",
    "sanitize_windows_stem",
    "validate_windows_filename",
]
