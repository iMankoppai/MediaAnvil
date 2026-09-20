"""Inspect MP3 audio details and export embedded lyrics or cover art."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError


class Mp3ExportError(ValueError):
    """Raised when MP3 information or embedded content cannot be read."""


@dataclass(frozen=True)
class Mp3AudioInfo:
    duration_seconds: float
    bitrate_kbps: int
    sample_rate_hz: int
    channels: int
    file_size_bytes: int
    id3_version: str
    tag_count: int
    lyrics_count: int
    cover_count: int


@dataclass(frozen=True)
class EmbeddedLyrics:
    text: str
    extension: str
    frame_count: int


@dataclass(frozen=True)
class EmbeddedCover:
    data: bytes
    extension: str
    frame_count: int


_LRC_TIMESTAMP = re.compile(r"^\[\d+:\d{2}(?:\.\d{1,3})?\]", re.MULTILINE)


def _load_mp3(path: str | Path) -> tuple[Path, object, object | None]:
    mp3_path = Path(path)
    if mp3_path.suffix.lower() != ".mp3":
        raise Mp3ExportError("请选择扩展名为 .mp3 的歌曲文件。")
    if not mp3_path.is_file():
        raise Mp3ExportError("MP3 文件不存在或无法访问。")
    try:
        from mutagen import MutagenError
        from mutagen.id3 import ID3, ID3NoHeaderError
        from mutagen.mp3 import HeaderNotFoundError, MP3
    except ImportError as exc:
        raise Mp3ExportError("缺少 Mutagen 组件，请重新安装或重新打包软件。") from exc
    try:
        audio = MP3(mp3_path)
        try:
            tags = ID3(mp3_path, translate=False)
        except ID3NoHeaderError:
            tags = None
    except (HeaderNotFoundError, MutagenError, OSError) as exc:
        raise Mp3ExportError("所选文件不是有效的 MP3，或音频数据已经损坏。") from exc
    return mp3_path, audio, tags


def inspect_mp3(path: str | Path) -> Mp3AudioInfo:
    """Return stable audio properties and a compact tag inventory."""
    mp3_path, audio, tags = _load_mp3(path)
    info = audio.info
    version = "无 ID3 标签"
    tag_count = lyrics_count = cover_count = 0
    if tags is not None:
        version = f"ID3v2.{tags.version[1]}"
        tag_count = len(tags.values())
        lyrics_count = len(tags.getall("USLT")) + len(tags.getall("SYLT"))
        cover_count = len(tags.getall("APIC"))
    return Mp3AudioInfo(
        duration_seconds=float(info.length),
        bitrate_kbps=round(info.bitrate / 1000),
        sample_rate_hz=int(info.sample_rate),
        channels=int(info.channels),
        file_size_bytes=mp3_path.stat().st_size,
        id3_version=version,
        tag_count=tag_count,
        lyrics_count=lyrics_count,
        cover_count=cover_count,
    )


def read_embedded_lyrics(path: str | Path) -> EmbeddedLyrics:
    """Select the preferred lyrics frame and choose LRC or TXT by content."""
    _mp3_path, _audio, tags = _load_mp3(path)
    if tags is None:
        raise Mp3ExportError("当前 MP3 没有内嵌歌词。")
    uslt = tags.getall("USLT")
    sylt = tags.getall("SYLT")
    frame_count = len(uslt) + len(sylt)
    preferred = next((frame for frame in uslt if frame.desc == "Sub2LRC"), uslt[0] if uslt else None)
    if preferred is not None:
        text = preferred.text
        extension = ".lrc" if _LRC_TIMESTAMP.search(text) else ".txt"
        return EmbeddedLyrics(text, extension, frame_count)
    if sylt:
        lines = []
        for text, milliseconds in sylt[0].text:
            total_centiseconds = (milliseconds + 5) // 10
            minutes, remainder = divmod(total_centiseconds, 6000)
            seconds, centiseconds = divmod(remainder, 100)
            lines.append(f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}]{text}")
        return EmbeddedLyrics("\n".join(lines) + "\n", ".lrc", frame_count)
    raise Mp3ExportError("当前 MP3 没有内嵌歌词。")


def read_embedded_cover(path: str | Path) -> EmbeddedCover:
    """Select the front cover and identify JPEG/PNG from the image bytes."""
    from io import BytesIO

    _mp3_path, _audio, tags = _load_mp3(path)
    if tags is None:
        raise Mp3ExportError("当前 MP3 没有内嵌封面。")
    covers = tags.getall("APIC")
    if not covers:
        raise Mp3ExportError("当前 MP3 没有内嵌封面。")
    preferred = next((frame for frame in covers if frame.type == 3), covers[0])
    try:
        with Image.open(BytesIO(preferred.data)) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise Mp3ExportError("内嵌封面数据已损坏，无法导出。") from exc
    extensions = {"JPEG": ".jpg", "PNG": ".png"}
    if image_format not in extensions:
        raise Mp3ExportError("当前内嵌封面不是可导出的 JPG 或 PNG 图片。")
    return EmbeddedCover(preferred.data, extensions[image_format], len(covers))


def unique_export_path(directory: str | Path, stem: str, extension: str) -> Path:
    """Choose a non-existing export name without overwriting user files."""
    output_dir = Path(directory)
    if not output_dir.is_dir():
        raise Mp3ExportError("导出目录不存在或无法访问。")
    candidate = output_dir / f"{stem}{extension}"
    index = 1
    while candidate.exists():
        candidate = output_dir / f"{stem}_{index}{extension}"
        index += 1
    return candidate


def export_embedded_lyrics(path: str | Path, directory: str | Path) -> tuple[Path, int]:
    mp3_path = Path(path)
    lyrics = read_embedded_lyrics(mp3_path)
    destination = unique_export_path(directory, mp3_path.stem, lyrics.extension)
    try:
        destination.write_text(lyrics.text, encoding="utf-8-sig", newline="\n")
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise Mp3ExportError(f"无法导出歌词：{exc}") from exc
    return destination, lyrics.frame_count


def export_embedded_cover(path: str | Path, directory: str | Path) -> tuple[Path, int]:
    mp3_path = Path(path)
    cover = read_embedded_cover(mp3_path)
    destination = unique_export_path(directory, mp3_path.stem, cover.extension)
    try:
        destination.write_bytes(cover.data)
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise Mp3ExportError(f"无法导出封面：{exc}") from exc
    return destination, cover.frame_count
