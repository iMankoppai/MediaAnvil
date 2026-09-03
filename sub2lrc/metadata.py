"""Read and edit basic MP3 ID3 metadata without touching audio data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .mp3io import apply_to_mp3_copy


class MetadataError(ValueError):
    """Raised when MP3 metadata cannot be read or safely written."""


@dataclass(frozen=True)
class Mp3Metadata:
    title: str = ""
    artist: str = ""
    album: str = ""
    has_cover: bool = False
    has_lyrics: bool = False


def _text_value(tags: object, frame_id: str) -> str:
    frames = tags.getall(frame_id)
    if not frames:
        return ""
    return " / ".join(str(value) for value in frames[0].text)


def read_mp3_metadata(path: str | Path) -> Mp3Metadata:
    """Read title, artist, album, and cover/lyrics presence from an MP3."""
    mp3_path = Path(path)
    if mp3_path.suffix.lower() != ".mp3":
        raise MetadataError("请选择扩展名为 .mp3 的歌曲文件。")
    if not mp3_path.is_file():
        raise MetadataError("MP3 文件不存在或无法访问。")

    try:
        from mutagen import MutagenError
        from mutagen.id3 import ID3, ID3NoHeaderError
        from mutagen.mp3 import HeaderNotFoundError, MP3
    except ImportError as exc:
        raise MetadataError("缺少 Mutagen 组件，请重新安装或重新打包 Sub2LRC。") from exc

    try:
        MP3(mp3_path)
        try:
            tags = ID3(mp3_path, translate=False)
        except ID3NoHeaderError:
            return Mp3Metadata()
    except (HeaderNotFoundError, MutagenError, OSError) as exc:
        raise MetadataError("所选文件不是有效的 MP3，或音频数据已经损坏。") from exc

    return Mp3Metadata(
        title=_text_value(tags, "TIT2"),
        artist=_text_value(tags, "TPE1"),
        album=_text_value(tags, "TALB"),
        has_cover=bool(tags.getall("APIC")),
        has_lyrics=bool(tags.getall("USLT") or tags.getall("SYLT")),
    )


def save_mp3_metadata(
    path: str | Path,
    title: str,
    artist: str,
    album: str,
    destination: str | Path | None = None,
) -> Path:
    """Save only TIT2, TPE1, and TALB, preserving every other tag and audio frame."""
    mp3_path = Path(path)
    # Validate before creating an output copy and provide the same clear errors as reading.
    read_mp3_metadata(mp3_path)
    values = {
        "TIT2": title.strip(),
        "TPE1": artist.strip(),
        "TALB": album.strip(),
    }

    try:
        from mutagen import MutagenError
        from mutagen.id3 import ID3, ID3NoHeaderError, TALB, TIT2, TPE1
    except ImportError as exc:
        raise MetadataError("缺少 Mutagen 组件，请重新安装或重新打包 Sub2LRC。") from exc

    frame_classes = {"TIT2": TIT2, "TPE1": TPE1, "TALB": TALB}

    def edit(target: Path) -> None:
        try:
            tags = ID3(target, translate=False)
            save_version = 4 if tags.version[1] == 4 else 3
            if save_version == 3:
                tags.update_to_v23()
        except ID3NoHeaderError:
            tags = ID3()
            save_version = 3

        for frame_id, value in values.items():
            tags.delall(frame_id)
            if value:
                tags.add(frame_classes[frame_id](encoding=3, text=[value]))
        tags.save(target, v2_version=save_version)

        saved = read_mp3_metadata(target)
        if (saved.title, saved.artist, saved.album) != (
            values["TIT2"],
            values["TPE1"],
            values["TALB"],
        ):
            raise MetadataError("写入后的基础标签校验失败，原文件未被修改。")

    try:
        return apply_to_mp3_copy(mp3_path, destination, edit)
    except (OSError, MutagenError, MetadataError, ValueError) as exc:
        if isinstance(exc, MetadataError):
            raise
        raise MetadataError(f"保存 MP3 标签失败：{exc}") from exc
