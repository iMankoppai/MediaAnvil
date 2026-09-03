"""Subtitle parsing and LRC conversion logic.

This module deliberately uses only Python's standard library so the program is
easy to run and maintain.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re


class SubtitleError(ValueError):
    """Raised when a file cannot be decoded or contains no subtitle cues."""


@dataclass(frozen=True)
class Cue:
    start_seconds: float
    text: str


_TIMING_LINE = re.compile(
    r"^\s*(?P<start>(?:\d{1,}:)?\d{1,2}:\d{2}[.,]\d{1,3})\s*-->"
)
_TAG = re.compile(r"<[^>]+>")
_LRC_TAG = re.compile(r"\[(?:\d+:\d{2}(?:\.\d{1,3})?|ar:|ti:|al:|by:|offset:)", re.I)
_AUDIO_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".alac",
    ".ape",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}


def read_subtitle(path: str | Path) -> str:
    """Read a subtitle file while avoiding mojibake for common Chinese encodings."""
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise SubtitleError("无法识别文件编码。请将字幕保存为 UTF-8、UTF-16 或 GB18030。")


def _parse_timestamp(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
        elif len(parts) == 2:
            hours, minutes, seconds = 0, int(parts[0]), float(parts[1])
        else:
            raise ValueError
    except ValueError as exc:
        raise SubtitleError(f"无效时间戳：{value}") from exc
    return hours * 3600 + minutes * 60 + seconds


def _clean_text(lines: list[str]) -> str:
    pieces: list[str] = []
    for line in lines:
        line = _TAG.sub("", line).strip()
        if line and not line.startswith("NOTE"):
            pieces.append(line)
    return "\n".join(pieces)


def parse_subtitle(content: str) -> list[Cue]:
    """Parse VTT or SRT content into timestamped text cues."""
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues: list[Cue] = []
    index = 0

    while index < len(lines):
        match = _TIMING_LINE.match(lines[index])
        if not match:
            index += 1
            continue

        start = _parse_timestamp(match.group("start"))
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1

        text = _clean_text(text_lines)
        if text:
            cues.append(Cue(start, text))

    if not cues:
        raise SubtitleError("没有找到有效字幕。请确认文件是标准 VTT 或 SRT 格式。")
    return cues


def _lrc_timestamp(seconds: float) -> str:
    # LRC commonly uses centiseconds. Decimal + ROUND_HALF_UP makes exact
    # millisecond ties predictable: 10.125 becomes 10.13, not 10.12.
    centiseconds = int(
        (Decimal(str(seconds)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    minutes, remainder = divmod(centiseconds, 6000)
    secs, fraction = divmod(remainder, 100)
    return f"[{minutes:02d}:{secs:02d}.{fraction:02d}]"


def cues_to_lrc(cues: list[Cue]) -> str:
    """Render cues as UTF-8 friendly LRC text."""
    output: list[str] = []
    for cue in cues:
        timestamp = _lrc_timestamp(cue.start_seconds)
        # LRC has no portable multi-line cue syntax. Repeating the timestamp
        # preserves every original subtitle line as a valid LRC lyric line.
        output.extend(f"{timestamp}{line}" for line in cue.text.splitlines())
    return "\n".join(output) + "\n"


def convert_text(content: str) -> str:
    return cues_to_lrc(parse_subtitle(content))


def convert_file(source: str | Path, destination: str | Path) -> Path:
    """Convert one subtitle and save it as UTF-8 with BOM for Windows apps."""
    source_path = Path(source)
    destination_path = Path(destination)
    lrc = convert_text(read_subtitle(source_path))
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(lrc, encoding="utf-8-sig", newline="\n")
    return destination_path


def unique_output_path(directory: str | Path, source: str | Path) -> Path:
    """Return a non-existing output path without overwriting user files."""
    directory_path = Path(directory)
    # "song.wav.vtt" should pair with "song.wav" as "song.lrc". Path.stem
    # first removes the subtitle suffix; remove one more suffix only when it is
    # a known audio extension. Plain "song.srt" remains "song.lrc".
    stem = Path(source).stem
    possible_audio = Path(stem)
    if possible_audio.suffix.lower() in _AUDIO_EXTENSIONS:
        stem = possible_audio.stem
    candidate = directory_path / f"{stem}.lrc"
    suffix = 1
    while candidate.exists():
        candidate = directory_path / f"{stem}_{suffix}.lrc"
        suffix += 1
    return candidate
