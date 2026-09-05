"""Write a JPEG or PNG cover image into an MP3 ID3 APIC frame."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from .mp3io import apply_to_mp3_copy


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

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise CoverEmbedError("缺少 Pillow 图片组件，请重新安装或重新打包 MediaAnvil。") from exc

    try:
        with Image.open(BytesIO(data)) as decoded:
            decoded.verify()
            image_format = decoded.format
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise CoverEmbedError("图片内容不是有效的 JPEG 或 PNG 文件。") from exc

    mime_by_format = {"JPEG": "image/jpeg", "PNG": "image/png"}
    try:
        mime = mime_by_format[image_format]
    except KeyError as exc:
        raise CoverEmbedError("图片内容不是有效的 JPEG 或 PNG 文件。") from exc
    return data, mime


def embed_cover(mp3: str | Path, image: str | Path, destination: str | Path | None = None) -> Path:
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
        raise CoverEmbedError("缺少 Mutagen 组件，请重新安装或重新打包 MediaAnvil。") from exc

    try:
        MP3(mp3_path)
    except (HeaderNotFoundError, MutagenError) as exc:
        raise CoverEmbedError("所选文件不是有效的 MP3，或音频数据已经损坏。") from exc

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

        tags.delall("APIC")
        tags.add(APIC(encoding=1, mime=mime, type=3, desc="Cover", data=image_data))
        tags.save(target, v2_version=save_version)

        saved_covers = ID3(target, translate=False).getall("APIC")
        if (
            len(saved_covers) != 1
            or saved_covers[0].mime != mime
            or saved_covers[0].type != 3
            or saved_covers[0].data != image_data
        ):
            raise CoverEmbedError("写入后的封面校验失败，原文件未被修改。")

    try:
        return apply_to_mp3_copy(mp3_path, destination, edit)
    except (OSError, MutagenError, CoverEmbedError, ValueError) as exc:
        if isinstance(exc, CoverEmbedError):
            raise
        raise CoverEmbedError(f"写入封面失败：{exc}") from exc
