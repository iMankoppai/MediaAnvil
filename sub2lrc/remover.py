"""Safely remove embedded lyrics or cover frames from MP3 ID3 tags."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from .embedder import unique_backup_path


class TagRemovalError(ValueError):
    """Raised when embedded tags cannot be safely removed."""


@dataclass(frozen=True)
class RemovalResult:
    removed_count: int
    backup_path: Path | None


def _remove_frames(mp3: str | Path, frame_ids: tuple[str, ...], label: str) -> RemovalResult:
    mp3_path = Path(mp3)
    if mp3_path.suffix.lower() != ".mp3":
        raise TagRemovalError("请选择扩展名为 .mp3 的歌曲文件。")
    if not mp3_path.is_file():
        raise TagRemovalError("MP3 文件不存在或无法访问。")

    try:
        from mutagen import MutagenError
        from mutagen.id3 import ID3, ID3NoHeaderError
        from mutagen.mp3 import HeaderNotFoundError, MP3
    except ImportError as exc:
        raise TagRemovalError("缺少 Mutagen 组件，请重新安装或重新打包 Sub2LRC。") from exc

    try:
        MP3(mp3_path)
    except (HeaderNotFoundError, MutagenError) as exc:
        raise TagRemovalError("所选文件不是有效的 MP3，或音频数据已经损坏。") from exc

    try:
        tags = ID3(mp3_path, translate=False)
    except ID3NoHeaderError:
        return RemovalResult(0, None)
    except MutagenError as exc:
        raise TagRemovalError(f"无法读取 MP3 的 ID3 标签：{exc}") from exc

    original_version = tags.version[1]
    save_version = 4 if original_version == 4 else 3
    if save_version == 3:
        tags.update_to_v23()
    removed_count = sum(len(tags.getall(frame_id)) for frame_id in frame_ids)
    if removed_count == 0:
        return RemovalResult(0, None)

    backup_path = unique_backup_path(mp3_path)

    try:
        shutil.copy2(mp3_path, backup_path)
        for frame_id in frame_ids:
            tags.delall(frame_id)
        tags.save(mp3_path, v2_version=save_version)

        saved = ID3(mp3_path, translate=False)
        if any(saved.getall(frame_id) for frame_id in frame_ids):
            raise TagRemovalError(f"移除{label}后的校验失败，原 MP3 已从备份恢复。")
    except (OSError, MutagenError, TagRemovalError) as exc:
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, mp3_path)
            except OSError:
                pass
        if isinstance(exc, TagRemovalError):
            raise
        raise TagRemovalError(f"移除{label}失败：{exc}") from exc

    return RemovalResult(removed_count, backup_path)


def remove_embedded_lyrics(mp3: str | Path) -> RemovalResult:
    """Remove all unsynchronised and synchronised ID3 lyrics frames."""
    return _remove_frames(mp3, ("USLT", "SYLT"), "内嵌歌词")


def remove_embedded_covers(mp3: str | Path) -> RemovalResult:
    """Remove all ID3 attached-picture frames."""
    return _remove_frames(mp3, ("APIC",), "内嵌封面")
