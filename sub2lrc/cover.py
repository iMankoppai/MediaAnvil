"""Write a JPEG or PNG cover image into an MP3 ID3 APIC frame."""

from __future__ import annotations

from pathlib import Path
import shutil

from .embedder import unique_backup_path


class CoverEmbedError(ValueError):
    """Raised when a cover image cannot be safely embedded."""


def read_cover(path: str | Path) -> tuple[bytes, str]:
    image_path = Path(path)
    if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise CoverEmbedError("请选择 JPG、JPEG 或 PNG 封面图片。")
    if not image_path.is_file():
        raise CoverEmbedError("封面图片不存在或无法访问。")
    try:
        data = image_path.read_bytes()
    except OSError as exc:
        raise CoverEmbedError(f"无法读取封面图片：{exc}") from exc

    if (
        len(data) >= 33
        and data.startswith(b"\x89PNG\r\n\x1a\n")
        and data[12:16] == b"IHDR"
        and int.from_bytes(data[16:20], "big") > 0
        and int.from_bytes(data[20:24], "big") > 0
        and data[-8:-4] == b"IEND"
    ):
        mime = "image/png"
    elif len(data) >= 16 and data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        mime = "image/jpeg"
    else:
        raise CoverEmbedError("图片内容不是有效的 JPEG 或 PNG 文件。")
    return data, mime


def embed_cover(mp3: str | Path, image: str | Path) -> Path:
    """Replace all MP3 cover frames with one front-cover APIC frame."""
    mp3_path = Path(mp3)
    image_path = Path(image)
    if mp3_path.suffix.lower() != ".mp3":
        raise CoverEmbedError("请选择扩展名为 .mp3 的歌曲文件。")
    if not mp3_path.is_file():
        raise CoverEmbedError("MP3 文件不存在或无法访问。")
    image_data, mime = read_cover(image_path)

    try:
        from mutagen import MutagenError
        from mutagen.id3 import APIC, ID3, ID3NoHeaderError
        from mutagen.mp3 import HeaderNotFoundError, MP3
    except ImportError as exc:
        raise CoverEmbedError("缺少 Mutagen 组件，请重新安装或重新打包 Sub2LRC。") from exc

    try:
        MP3(mp3_path)
    except (HeaderNotFoundError, MutagenError) as exc:
        raise CoverEmbedError("所选文件不是有效的 MP3，或音频数据已经损坏。") from exc

    backup_path = unique_backup_path(mp3_path)
    try:
        shutil.copy2(mp3_path, backup_path)
        try:
            tags = ID3(mp3_path, translate=False)
            original_version = tags.version[1]
            save_version = 4 if original_version == 4 else 3
            if save_version == 3:
                tags.update_to_v23()
        except ID3NoHeaderError:
            tags = ID3()
            save_version = 3

        tags.delall("APIC")
        tags.add(APIC(encoding=1, mime=mime, type=3, desc="Cover", data=image_data))
        tags.save(mp3_path, v2_version=save_version)

        saved_covers = ID3(mp3_path, translate=False).getall("APIC")
        if (
            len(saved_covers) != 1
            or saved_covers[0].mime != mime
            or saved_covers[0].type != 3
            or saved_covers[0].data != image_data
        ):
            raise CoverEmbedError("写入后的封面校验失败，原 MP3 已从备份恢复。")
    except (OSError, MutagenError, CoverEmbedError) as exc:
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, mp3_path)
            except OSError:
                pass
        if isinstance(exc, CoverEmbedError):
            raise
        raise CoverEmbedError(f"写入封面失败：{exc}") from exc

    return backup_path
