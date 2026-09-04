"""Unified metadata API with format-specific Mutagen adapters."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import tempfile
from typing import Callable, Protocol

from .cover import read_cover
from .editor import Mp3Edits, read_mp3_editor_state, save_mp3_edits
from .embedder import read_lrc
from .mp3_exporter import inspect_mp3


class AudioMetadataError(ValueError):
    """Raised when audio metadata cannot be read or safely saved."""


@dataclass(frozen=True)
class AudioFileInfo:
    format_label: str
    duration_seconds: float
    bitrate_kbps: int
    sample_rate_hz: int
    channels: int
    file_size_bytes: int
    tag_count: int


@dataclass(frozen=True)
class AudioMetadata:
    title: str
    artist: str
    album: str
    has_lyrics: bool
    lyrics: str
    has_cover: bool
    cover_data: bytes | None
    cover_mime: str | None
    lyrics_count: int
    cover_count: int
    writable: bool
    info: AudioFileInfo


@dataclass(frozen=True)
class AudioMetadataChanges:
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    lyrics_path: Path | None = None
    remove_lyrics: bool = False
    cover_path: Path | None = None
    remove_cover: bool = False


class MetadataAdapter(Protocol):
    writable: bool
    def read(self, path: Path) -> AudioMetadata: ...
    def write(self, source: Path, changes: AudioMetadataChanges, destination: Path | None) -> Path: ...


def _value(tags: object | None, key: str) -> str:
    if not tags:
        return ""
    value = tags.get(key)
    if not value:
        return ""
    if isinstance(value, list):
        return " / ".join(str(item) for item in value)
    return str(value)


def _generic_info(path: Path, audio: object, label: str, tag_count: int) -> AudioFileInfo:
    info = audio.info
    duration = float(getattr(info, "length", 0) or 0)
    bitrate = int(getattr(info, "bitrate", 0) or 0)
    if not bitrate and duration:
        bitrate = round(path.stat().st_size * 8 / duration)
    return AudioFileInfo(
        label, duration, round(bitrate / 1000), int(getattr(info, "sample_rate", 0) or 0),
        int(getattr(info, "channels", 0) or 0), path.stat().st_size, tag_count,
    )


def _atomic_copy(source: Path, destination: Path | None, edit: Callable[[Path], None]) -> Path:
    target = source if destination is None else destination
    if target.suffix.lower() != source.suffix.lower():
        raise AudioMetadataError("另存文件必须保持与源音频相同的扩展名。")
    if not target.parent.is_dir():
        raise AudioMetadataError("输出目录不存在或无法访问。")
    handle, name = tempfile.mkstemp(prefix=".sub2lrc-", suffix=source.suffix, dir=target.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        shutil.copy2(source, temporary)
        edit(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


class Mp3Adapter:
    writable = True

    def read(self, path: Path) -> AudioMetadata:
        state = read_mp3_editor_state(path)
        detail = inspect_mp3(path)
        info = AudioFileInfo(
            "MP3", detail.duration_seconds, detail.bitrate_kbps, detail.sample_rate_hz,
            detail.channels, detail.file_size_bytes, detail.tag_count,
        )
        return AudioMetadata(
            state.title, state.artist, state.album, state.has_lyrics, state.lyrics,
            state.has_cover, state.cover_data, state.cover_mime, detail.lyrics_count,
            detail.cover_count, True, info,
        )

    def write(self, source: Path, changes: AudioMetadataChanges, destination: Path | None) -> Path:
        edits = Mp3Edits(
            title=changes.title, artist=changes.artist, album=changes.album,
            lyrics_path=changes.lyrics_path, remove_lyrics=changes.remove_lyrics,
            cover_path=changes.cover_path, remove_cover=changes.remove_cover,
        )
        return save_mp3_edits(source, edits, destination)


class FlacAdapter:
    writable = True

    def read(self, path: Path) -> AudioMetadata:
        from mutagen.flac import FLAC
        audio = FLAC(path)
        tags = audio.tags
        lyrics = _value(tags, "lyrics") or _value(tags, "unsyncedlyrics")
        pictures = audio.pictures
        cover = next((item for item in pictures if item.type == 3), pictures[0] if pictures else None)
        return AudioMetadata(
            _value(tags, "title"), _value(tags, "artist"), _value(tags, "album"), bool(lyrics), lyrics,
            bool(cover), cover.data if cover else None, cover.mime if cover else None,
            1 if lyrics else 0, len(pictures), True, _generic_info(path, audio, "FLAC", len(tags or {})),
        )

    def write(self, source: Path, changes: AudioMetadataChanges, destination: Path | None) -> Path:
        from mutagen.flac import FLAC, Picture
        lyrics = read_lrc(changes.lyrics_path) if changes.lyrics_path else None
        cover = read_cover(changes.cover_path) if changes.cover_path else None
        def edit(path: Path) -> None:
            audio = FLAC(path)
            if audio.tags is None:
                audio.add_tags()
            for key, value in (("title", changes.title), ("artist", changes.artist), ("album", changes.album)):
                if value is not None:
                    if value.strip(): audio[key] = [value.strip()]
                    elif key in audio: del audio[key]
            if changes.remove_lyrics:
                for key in ("lyrics", "unsyncedlyrics"):
                    if key in audio: del audio[key]
            elif lyrics is not None:
                audio["lyrics"] = [lyrics]
            if changes.remove_cover or cover is not None:
                audio.clear_pictures()
            if cover is not None:
                picture = Picture(); picture.type = 3; picture.mime = cover[1]; picture.desc = "Cover"; picture.data = cover[0]
                audio.add_picture(picture)
            audio.save()
        return _atomic_copy(source, destination, edit)


class Mp4Adapter:
    writable = True

    def read(self, path: Path) -> AudioMetadata:
        from mutagen.mp4 import MP4, MP4Cover
        audio = MP4(path); tags = audio.tags or {}
        lyrics = _value(tags, "©lyr")
        covers = tags.get("covr", [])
        cover = covers[0] if covers else None
        mime = None
        if cover is not None:
            mime = "image/png" if cover.imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
        return AudioMetadata(
            _value(tags, "©nam"), _value(tags, "©ART"), _value(tags, "©alb"), bool(lyrics), lyrics,
            bool(cover), bytes(cover) if cover else None, mime, 1 if lyrics else 0, len(covers), True,
            _generic_info(path, audio, "M4A", len(tags)),
        )

    def write(self, source: Path, changes: AudioMetadataChanges, destination: Path | None) -> Path:
        from mutagen.mp4 import MP4, MP4Cover
        lyrics = read_lrc(changes.lyrics_path) if changes.lyrics_path else None
        cover = read_cover(changes.cover_path) if changes.cover_path else None
        def edit(path: Path) -> None:
            audio = MP4(path)
            if audio.tags is None: audio.add_tags()
            for key, value in (("©nam", changes.title), ("©ART", changes.artist), ("©alb", changes.album)):
                if value is not None:
                    if value.strip(): audio.tags[key] = [value.strip()]
                    else: audio.tags.pop(key, None)
            if changes.remove_lyrics: audio.tags.pop("©lyr", None)
            elif lyrics is not None: audio.tags["©lyr"] = [lyrics]
            if changes.remove_cover: audio.tags.pop("covr", None)
            elif cover is not None:
                image_format = MP4Cover.FORMAT_PNG if cover[1] == "image/png" else MP4Cover.FORMAT_JPEG
                audio.tags["covr"] = [MP4Cover(cover[0], imageformat=image_format)]
            audio.save()
        return _atomic_copy(source, destination, edit)


class OggAdapter:
    writable = True

    def _open(self, path: Path) -> tuple[object, str]:
        from mutagen.oggopus import OggOpus
        from mutagen.oggvorbis import OggVorbis
        if path.suffix.lower() == ".opus": return OggOpus(path), "Opus"
        try: return OggVorbis(path), "OGG Vorbis"
        except Exception: return OggOpus(path), "Opus"

    def read(self, path: Path) -> AudioMetadata:
        from mutagen.flac import Picture
        audio, label = self._open(path); tags = audio.tags or {}
        lyrics = _value(tags, "lyrics") or _value(tags, "unsyncedlyrics")
        encoded = tags.get("metadata_block_picture", [])
        pictures = []
        for item in encoded:
            try: pictures.append(Picture(base64.b64decode(item)))
            except Exception: continue
        cover = next((item for item in pictures if item.type == 3), pictures[0] if pictures else None)
        return AudioMetadata(
            _value(tags, "title"), _value(tags, "artist"), _value(tags, "album"), bool(lyrics), lyrics,
            bool(cover), cover.data if cover else None, cover.mime if cover else None,
            1 if lyrics else 0, len(pictures), True, _generic_info(path, audio, label, len(tags)),
        )

    def write(self, source: Path, changes: AudioMetadataChanges, destination: Path | None) -> Path:
        from mutagen.flac import Picture
        lyrics = read_lrc(changes.lyrics_path) if changes.lyrics_path else None
        cover = read_cover(changes.cover_path) if changes.cover_path else None
        def edit(path: Path) -> None:
            audio, _label = self._open(path)
            if audio.tags is None: audio.add_tags()
            for key, value in (("title", changes.title), ("artist", changes.artist), ("album", changes.album)):
                if value is not None:
                    if value.strip(): audio[key] = [value.strip()]
                    elif key in audio: del audio[key]
            if changes.remove_lyrics:
                for key in ("lyrics", "unsyncedlyrics"):
                    if key in audio: del audio[key]
            elif lyrics is not None: audio["lyrics"] = [lyrics]
            if changes.remove_cover: audio.pop("metadata_block_picture", None)
            elif cover is not None:
                picture = Picture(); picture.type = 3; picture.mime = cover[1]; picture.desc = "Cover"; picture.data = cover[0]
                audio["metadata_block_picture"] = [base64.b64encode(picture.write()).decode("ascii")]
            audio.save()
        return _atomic_copy(source, destination, edit)


class WavReadOnlyAdapter:
    writable = False
    def read(self, path: Path) -> AudioMetadata:
        from mutagen.wave import WAVE
        audio = WAVE(path); tags = audio.tags
        return AudioMetadata(
            _value(tags, "TIT2"), _value(tags, "TPE1"), _value(tags, "TALB"), False, "",
            False, None, None, 0, 0, False, _generic_info(path, audio, "WAV", len(tags or {})),
        )
    def write(self, source: Path, changes: AudioMetadataChanges, destination: Path | None) -> Path:
        raise AudioMetadataError("WAV 当前仅支持读取信息，暂不支持保存歌词和封面。")


_ADAPTERS: dict[str, MetadataAdapter] = {
    ".mp3": Mp3Adapter(), ".flac": FlacAdapter(), ".m4a": Mp4Adapter(),
    ".ogg": OggAdapter(), ".opus": OggAdapter(), ".wav": WavReadOnlyAdapter(),
}


def _adapter(path: Path) -> MetadataAdapter:
    adapter = _ADAPTERS.get(path.suffix.lower())
    if adapter is None:
        raise AudioMetadataError("不支持该音频标签格式。")
    if not path.is_file():
        raise AudioMetadataError("音频文件不存在或无法访问。")
    return adapter


def read_metadata(file: str | Path) -> AudioMetadata:
    path = Path(file)
    try: return _adapter(path).read(path)
    except AudioMetadataError: raise
    except Exception as exc: raise AudioMetadataError(f"无法读取音频标签：{exc}") from exc


def write_metadata(
    file: str | Path, changes: AudioMetadataChanges, destination: str | Path | None = None
) -> Path:
    path = Path(file); target = Path(destination) if destination is not None else None
    adapter = _adapter(path)
    if not adapter.writable: raise AudioMetadataError("该格式当前仅支持读取信息。")
    try: return adapter.write(path, changes, target)
    except AudioMetadataError: raise
    except Exception as exc: raise AudioMetadataError(f"保存音频标签失败：{exc}") from exc


def export_metadata_lyrics(file: str | Path, directory: str | Path) -> Path:
    state = read_metadata(file)
    if not state.has_lyrics: raise AudioMetadataError("当前音频没有可导出的歌词。")
    extension = ".lrc" if "[" in state.lyrics and ":" in state.lyrics else ".txt"
    from .mp3_exporter import unique_export_path
    output = unique_export_path(directory, Path(file).stem, extension)
    output.write_text(state.lyrics, encoding="utf-8-sig", newline="\n")
    return output


def export_metadata_cover(file: str | Path, directory: str | Path) -> Path:
    state = read_metadata(file)
    if not state.cover_data: raise AudioMetadataError("当前音频没有可导出的封面。")
    extension = ".png" if state.cover_mime == "image/png" else ".jpg"
    from .mp3_exporter import unique_export_path
    output = unique_export_path(directory, Path(file).stem, extension)
    output.write_bytes(state.cover_data)
    return output
