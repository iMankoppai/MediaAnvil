"""Unified LRC, SRT and WebVTT parsing and rendering.

Every supported input is parsed into :class:`SubtitleCue` objects first.
Renderers only depend on that shared representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re


class SubtitleError(ValueError):
    """Raised when a subtitle/lyric file cannot be decoded or converted."""


@dataclass(frozen=True)
class SubtitleCue:
    start_seconds: float
    text: str
    end_seconds: float | None = None


Cue = SubtitleCue  # Backward-compatible public name.
SUPPORTED_FORMATS = ("lrc", "srt", "vtt")
_TIMING_LINE = re.compile(
    r"^\s*(?P<start>(?:\d{1,}:)?\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*"
    r"(?P<end>(?:\d{1,}:)?\d{1,2}:\d{2}[.,]\d{1,3})(?:\s+.*)?$"
)
_TAG = re.compile(r"<[^>]+>")
_LRC_TIMESTAMP = re.compile(r"\[(?P<time>\d+:\d{2}(?:\.\d{1,3})?)\]")
_LRC_METADATA = re.compile(r"^\s*\[(?:ar|ti|al|by|offset|length|re):.*?\]\s*$", re.I)
_AUDIO_EXTENSIONS = {
    ".aac", ".aiff", ".alac", ".ape", ".flac", ".m4a", ".mp3",
    ".ogg", ".opus", ".wav", ".wma",
}


def read_subtitle(path: str | Path) -> str:
    """Read text while avoiding mojibake for common Chinese encodings."""
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise SubtitleError("无法识别文件编码。请将文件保存为 UTF-8、UTF-16 或 GB18030。")


def _normalize_format(value: str) -> str:
    normalized = value.lower().lstrip(".")
    if normalized not in SUPPORTED_FORMATS:
        raise SubtitleError(f"不支持的格式：{value}。请选择 LRC、SRT 或 VTT。")
    return normalized


def detect_format(source: str | Path, content: str | None = None) -> str:
    """Detect a supported format from a filename, with a content fallback."""
    suffix = Path(source).suffix.lower().lstrip(".")
    if suffix in SUPPORTED_FORMATS:
        return suffix
    if content is not None:
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        if normalized.lstrip("\ufeff\n ").startswith("WEBVTT"):
            return "vtt"
        if _LRC_TIMESTAMP.search(normalized):
            return "lrc"
        if any(_TIMING_LINE.match(line) for line in normalized.split("\n")):
            return "srt"
    raise SubtitleError(f"无法识别文件格式：{Path(source).name}")


def _parse_timestamp(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
        elif len(parts) == 2:
            hours, minutes, seconds = 0, int(parts[0]), float(parts[1])
        else:
            raise ValueError
        if minutes < 0 or seconds < 0 or seconds >= 60:
            raise ValueError
    except ValueError as exc:
        raise SubtitleError(f"无效时间戳：{value}") from exc
    return hours * 3600 + minutes * 60 + seconds


def _clean_text(lines: list[str]) -> str:
    # Preserve the established VTT/SRT -> LRC behaviour exactly.
    pieces: list[str] = []
    for line in lines:
        line = _TAG.sub("", line).strip()
        if line and not line.startswith("NOTE"):
            pieces.append(line)
    return "\n".join(pieces)


def parse_timed_subtitle(content: str) -> list[SubtitleCue]:
    """Parse SRT or WebVTT content into the common cue representation."""
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues: list[SubtitleCue] = []
    index = 0
    while index < len(lines):
        match = _TIMING_LINE.match(lines[index])
        if not match:
            index += 1
            continue
        start = _parse_timestamp(match.group("start"))
        end = _parse_timestamp(match.group("end"))
        if end < start:
            raise SubtitleError("字幕结束时间不能早于开始时间。")
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1
        text = _clean_text(text_lines)
        if text:
            cues.append(SubtitleCue(start, text, end))
    if not cues:
        raise SubtitleError("没有找到有效字幕。请确认文件是标准 VTT 或 SRT 格式。")
    return cues


def parse_lrc(content: str) -> list[SubtitleCue]:
    """Parse LRC, grouping adjacent equal timestamps as one multiline cue."""
    cues: list[SubtitleCue] = []
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    for raw_line in normalized.split("\n"):
        if not raw_line or _LRC_METADATA.match(raw_line):
            continue
        matches = list(_LRC_TIMESTAMP.finditer(raw_line))
        if not matches:
            continue
        text = raw_line[matches[-1].end():]
        for match in matches:
            start = _parse_timestamp(match.group("time"))
            if cues and cues[-1].start_seconds == start and cues[-1].end_seconds is None:
                previous = cues[-1]
                cues[-1] = SubtitleCue(start, f"{previous.text}\n{text}", None)
            else:
                cues.append(SubtitleCue(start, text, None))
    if not cues:
        raise SubtitleError("没有找到有效歌词时间戳。请确认文件是标准 LRC 格式。")
    return cues


def parse_text(content: str, input_format: str) -> list[SubtitleCue]:
    input_format = _normalize_format(input_format)
    return parse_lrc(content) if input_format == "lrc" else parse_timed_subtitle(content)


def parse_subtitle(content: str) -> list[SubtitleCue]:
    """Backward-compatible parser for VTT/SRT content."""
    return parse_timed_subtitle(content)


def _rounded_units(seconds: float, multiplier: int) -> int:
    return int((Decimal(str(seconds)) * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _lrc_timestamp(seconds: float) -> str:
    centiseconds = _rounded_units(seconds, 100)
    minutes, remainder = divmod(centiseconds, 6000)
    secs, fraction = divmod(remainder, 100)
    return f"[{minutes:02d}:{secs:02d}.{fraction:02d}]"


def _subtitle_timestamp(seconds: float, separator: str) -> str:
    milliseconds = _rounded_units(seconds, 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, fraction = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{fraction:03d}"


def with_inferred_end_times(cues: list[SubtitleCue], final_duration: float = 5.0) -> list[SubtitleCue]:
    """Fill only missing ends, using the next start and a final fallback."""
    if final_duration <= 0:
        raise SubtitleError("最后一句持续时间必须大于 0 秒。")
    completed: list[SubtitleCue] = []
    for index, cue in enumerate(cues):
        end = cue.end_seconds
        if end is None:
            next_start = cues[index + 1].start_seconds if index + 1 < len(cues) else None
            end = next_start if next_start is not None and next_start > cue.start_seconds else cue.start_seconds + final_duration
        completed.append(SubtitleCue(cue.start_seconds, cue.text, end))
    return completed


def cues_to_lrc(cues: list[SubtitleCue]) -> str:
    """Render cues as LRC, retaining each original text line."""
    output: list[str] = []
    for cue in cues:
        timestamp = _lrc_timestamp(cue.start_seconds)
        output.extend(f"{timestamp}{line}" for line in (cue.text.splitlines() or [""]))
    return "\n".join(output) + "\n"


def cues_to_srt(cues: list[SubtitleCue], final_duration: float = 5.0) -> str:
    blocks: list[str] = []
    for index, cue in enumerate(with_inferred_end_times(cues, final_duration), 1):
        timing = f"{_subtitle_timestamp(cue.start_seconds, ',')} --> {_subtitle_timestamp(cue.end_seconds or 0, ',')}"
        blocks.append(f"{index}\n{timing}\n{cue.text}")
    return "\n\n".join(blocks) + "\n"


def cues_to_vtt(cues: list[SubtitleCue], final_duration: float = 5.0) -> str:
    blocks: list[str] = []
    for cue in with_inferred_end_times(cues, final_duration):
        timing = f"{_subtitle_timestamp(cue.start_seconds, '.')} --> {_subtitle_timestamp(cue.end_seconds or 0, '.')}"
        blocks.append(f"{timing}\n{cue.text}")
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def render_cues(cues: list[SubtitleCue], output_format: str, final_duration: float = 5.0) -> str:
    output_format = _normalize_format(output_format)
    if output_format == "lrc":
        return cues_to_lrc(cues)
    if output_format == "srt":
        return cues_to_srt(cues, final_duration)
    return cues_to_vtt(cues, final_duration)


def convert_content(content: str, input_format: str, output_format: str, final_duration: float = 5.0) -> str:
    return render_cues(parse_text(content, input_format), output_format, final_duration)


def convert_text(content: str) -> str:
    """Backward-compatible VTT/SRT -> LRC conversion."""
    return cues_to_lrc(parse_timed_subtitle(content))


def convert_file(
    source: str | Path,
    destination: str | Path,
    output_format: str | None = None,
    final_duration: float = 5.0,
    *,
    overwrite: bool = False,
) -> Path:
    """Auto-detect input, convert through cues, and write UTF-8 with BOM."""
    source_path = Path(source)
    destination_path = Path(destination)
    if source_path.resolve() == destination_path.resolve() and not overwrite:
        raise SubtitleError("输出文件不能覆盖输入文件。")
    content = read_subtitle(source_path)
    input_format = detect_format(source_path, content)
    chosen_output = _normalize_format(output_format or destination_path.suffix)
    converted = convert_content(content, input_format, chosen_output, final_duration)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(converted, encoding="utf-8-sig", newline="\n")
    return destination_path


def unique_output_path(directory: str | Path, source: str | Path, output_format: str = "lrc") -> Path:
    """Return a non-existing output path, never silently overwriting input."""
    output_format = _normalize_format(output_format)
    directory_path = Path(directory)
    source_path = Path(source)
    stem = source_path.stem
    possible_audio = Path(stem)
    if output_format == "lrc" and possible_audio.suffix.lower() in _AUDIO_EXTENSIONS:
        stem = possible_audio.stem
    candidate = directory_path / f"{stem}.{output_format}"
    suffix = 1
    source_absolute = source_path.resolve()
    while candidate.exists() or candidate.resolve() == source_absolute:
        candidate = directory_path / f"{stem}_{suffix}.{output_format}"
        suffix += 1
    return candidate
