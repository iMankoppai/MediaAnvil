"""Unified read/save workflow for all editable MP3 information."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cover import CoverEmbedError, embed_cover, read_cover
from .embedder import LyricsEmbedError, embed_lrc, read_lrc
from .metadata import MetadataError, read_mp3_metadata, update_mp3_metadata
from .mp3io import apply_to_mp3_copy
from .remover import TagRemovalError, remove_embedded_covers, remove_embedded_lyrics


class Mp3EditorError(ValueError):
    """Raised when a unified MP3 edit cannot be completed safely."""


@dataclass(frozen=True)
class Mp3EditorState:
    title: str
    artist: str
    album: str
    has_lyrics: bool
    lyrics: str
    has_cover: bool
    cover_data: bytes | None
    cover_mime: str | None


@dataclass(frozen=True)
class Mp3Edits:
    """Requested changes. None means unchanged; an empty string removes a basic tag."""

    title: str | None = None
    artist: str | None = None
    album: str | None = None
    lyrics_path: Path | None = None
    remove_lyrics: bool = False
    cover_path: Path | None = None
    remove_cover: bool = False

    def __post_init__(self) -> None:
        if self.lyrics_path is not None and self.remove_lyrics:
            raise ValueError("不能同时更换和移除歌词。")
        if self.cover_path is not None and self.remove_cover:
            raise ValueError("不能同时更换和移除封面。")


def _sylt_preview(frame: object) -> str:
    return "\n".join(text for text, _timestamp in frame.text)


def read_mp3_editor_state(path: str | Path) -> Mp3EditorState:
    """Read every value shown on the unified editor page."""
    mp3_path = Path(path)
    metadata = read_mp3_metadata(mp3_path)

    try:
        from mutagen import MutagenError
        from mutagen.id3 import ID3, ID3NoHeaderError
    except ImportError as exc:
        raise Mp3EditorError("缺少 Mutagen 组件，请重新安装或重新打包 MediaAnvil。") from exc

    lyrics = ""
    cover_data: bytes | None = None
    cover_mime: str | None = None
    try:
        tags = ID3(mp3_path, translate=False)
    except ID3NoHeaderError:
        tags = None
    except (MutagenError, OSError) as exc:
        raise Mp3EditorError(f"无法读取 MP3 标签：{exc}") from exc

    if tags is not None:
        unsynchronised = tags.getall("USLT")
        preferred = next((frame for frame in unsynchronised if frame.desc == "Sub2LRC"), None)
        if preferred is None and unsynchronised:
            preferred = unsynchronised[0]
        if preferred is not None:
            lyrics = preferred.text
        else:
            synchronised = tags.getall("SYLT")
            if synchronised:
                lyrics = _sylt_preview(synchronised[0])

        covers = tags.getall("APIC")
        cover = next((frame for frame in covers if frame.type == 3), covers[0] if covers else None)
        if cover is not None:
            cover_data = cover.data
            cover_mime = cover.mime

    return Mp3EditorState(
        title=metadata.title,
        artist=metadata.artist,
        album=metadata.album,
        has_lyrics=metadata.has_lyrics,
        lyrics=lyrics,
        has_cover=metadata.has_cover,
        cover_data=cover_data,
        cover_mime=cover_mime,
    )


def save_mp3_edits(
    source: str | Path,
    edits: Mp3Edits,
    destination: str | Path | None = None,
) -> Path:
    """Apply all requested changes as one atomic user-visible save operation."""
    source_path = Path(source)
    read_mp3_editor_state(source_path)

    expected_lyrics = read_lrc(edits.lyrics_path) if edits.lyrics_path is not None else None
    expected_cover = read_cover(edits.cover_path) if edits.cover_path is not None else None

    def edit(target: Path) -> None:
        if any(value is not None for value in (edits.title, edits.artist, edits.album)):
            update_mp3_metadata(target, edits.title, edits.artist, edits.album)

        if edits.remove_lyrics:
            remove_embedded_lyrics(target)
        elif edits.lyrics_path is not None:
            embed_lrc(target, edits.lyrics_path)

        if edits.remove_cover:
            remove_embedded_covers(target)
        elif edits.cover_path is not None:
            embed_cover(target, edits.cover_path)

        saved = read_mp3_editor_state(target)
        for requested, actual in (
            (edits.title, saved.title),
            (edits.artist, saved.artist),
            (edits.album, saved.album),
        ):
            if requested is not None and requested.strip() != actual:
                raise Mp3EditorError("保存后的基础信息校验失败，原文件未被修改。")
        if edits.remove_lyrics and saved.has_lyrics:
            raise Mp3EditorError("保存后的歌词移除校验失败，原文件未被修改。")
        if expected_lyrics is not None and saved.lyrics != expected_lyrics:
            raise Mp3EditorError("保存后的歌词校验失败，原文件未被修改。")
        if edits.remove_cover and saved.has_cover:
            raise Mp3EditorError("保存后的封面移除校验失败，原文件未被修改。")
        if expected_cover is not None and (
            saved.cover_data != expected_cover[0] or saved.cover_mime != expected_cover[1]
        ):
            raise Mp3EditorError("保存后的封面校验失败，原文件未被修改。")

    try:
        return apply_to_mp3_copy(source_path, destination, edit)
    except (
        OSError,
        ValueError,
        MetadataError,
        LyricsEmbedError,
        CoverEmbedError,
        TagRemovalError,
        Mp3EditorError,
    ) as exc:
        if isinstance(exc, Mp3EditorError):
            raise
        raise Mp3EditorError(f"保存 MP3 修改失败：{exc}") from exc
