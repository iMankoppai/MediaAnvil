"""Write LRC text into an MP3 ID3 lyrics frame."""

from __future__ import annotations

from pathlib import Path
import re

from .mp3io import apply_to_mp3_copy


class LyricsEmbedError(ValueError):
    """Raised when lyrics cannot be safely embedded into an MP3 file."""


_TIMESTAMP = re.compile(r"^\[\d+:\d{2}(?:\.\d{1,3})?\]", re.MULTILINE)


def read_lrc(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise LyricsEmbedError("无法识别 LRC 编码。请使用 UTF-8、UTF-16 或 GB18030。")

    if not text.strip():
        raise LyricsEmbedError("LRC 文件内容为空。")
    if not _TIMESTAMP.search(text):
        raise LyricsEmbedError("LRC 中没有找到有效时间标签，例如 [00:10.50]。")
    return text


def embed_lrc(mp3: str | Path, lrc: str | Path, destination: str | Path | None = None) -> Path:
    """Embed timed LRC text and return the overwritten or saved-as MP3 path."""
    mp3_path = Path(mp3)
    lrc_path = Path(lrc)
    if mp3_path.suffix.lower() != ".mp3":
        raise LyricsEmbedError("请选择扩展名为 .mp3 的歌曲文件。")
    if lrc_path.suffix.lower() != ".lrc":
        raise LyricsEmbedError("请选择扩展名为 .lrc 的歌词文件。")
    if not mp3_path.is_file():
        raise LyricsEmbedError("MP3 文件不存在或无法访问。")
    if not lrc_path.is_file():
        raise LyricsEmbedError("LRC 文件不存在或无法访问。")

    lyrics = read_lrc(lrc_path)
    try:
        from mutagen.id3 import ID3, ID3NoHeaderError, USLT
        from mutagen import MutagenError
        from mutagen.mp3 import MP3, HeaderNotFoundError
    except ImportError as exc:
        raise LyricsEmbedError("缺少 Mutagen 组件，请重新安装或重新打包 Sub2LRC。") from exc

    try:
        MP3(mp3_path)
    except (HeaderNotFoundError, MutagenError) as exc:
        raise LyricsEmbedError("所选文件不是有效的 MP3，或音频数据已经损坏。") from exc

    def edit(target: Path) -> None:
        try:
            tags = ID3(target, translate=False)
            original_version = tags.version[1]
            save_version = 4 if original_version == 4 else 3
            if save_version == 3:
                tags.update_to_v23()
        except ID3NoHeaderError:
            tags = ID3()
            save_version = 3

        # Preserve all existing tags and lyrics not written by this program.
        for key in list(tags.keys()):
            if key.startswith("USLT:Sub2LRC:"):
                del tags[key]
        tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text=lyrics))
        tags.save(target, v2_version=save_version)

        saved = ID3(target, translate=False)
        matches = [frame for frame in saved.getall("USLT") if frame.desc == "Sub2LRC"]
        if len(matches) != 1 or matches[0].text != lyrics:
            raise LyricsEmbedError("写入后的歌词校验失败，原文件未被修改。")

    try:
        return apply_to_mp3_copy(mp3_path, destination, edit)
    except (OSError, MutagenError, LyricsEmbedError, ValueError) as exc:
        if isinstance(exc, LyricsEmbedError):
            raise
        raise LyricsEmbedError(f"写入 ID3 标签失败：{exc}") from exc
