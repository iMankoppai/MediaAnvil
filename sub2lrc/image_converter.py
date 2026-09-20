"""Image format conversion logic, independent from the Tkinter interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, UnidentifiedImageError


class ImageConversionError(ValueError):
    """Raised when an image or conversion setting is invalid."""


@dataclass(frozen=True)
class ImageFormatSpec:
    key: str
    label: str
    extension: str
    pillow_format: str
    supports_quality: bool
    supports_transparency: bool
    default_quality: int | None = None


IMAGE_FORMAT_SPECS: dict[str, ImageFormatSpec] = {
    "jpg": ImageFormatSpec("jpg", "JPG / JPEG", ".jpg", "JPEG", True, False, 90),
    "png": ImageFormatSpec("png", "PNG", ".png", "PNG", False, True),
    "webp": ImageFormatSpec("webp", "WebP", ".webp", "WEBP", True, True, 90),
    # Although some BMP variants can carry alpha, player/viewer support is
    # inconsistent. Flattening produces the most portable BMP output.
    "bmp": ImageFormatSpec("bmp", "BMP", ".bmp", "BMP", False, False),
}
SUPPORTED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})
_PILLOW_FORMAT_TO_KEY = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "BMP": "bmp"}
ImageProgressCallback = Callable[[Path, int, int, float], None]


@dataclass(frozen=True)
class ImageConversionSettings:
    output_format: str = "jpg"
    quality: int | None = None
    background: tuple[int, int, int] = (255, 255, 255)

    @property
    def format_spec(self) -> ImageFormatSpec:
        try:
            return IMAGE_FORMAT_SPECS[self.output_format]
        except KeyError as exc:
            raise ImageConversionError("不支持所选的图片输出格式。") from exc

    @property
    def resolved_quality(self) -> int | None:
        return self.format_spec.default_quality if self.quality is None else self.quality

    def validate(self) -> None:
        spec = self.format_spec
        quality = self.resolved_quality
        if spec.supports_quality:
            if quality is None or not 1 <= quality <= 100:
                raise ImageConversionError(f"{spec.label} 质量必须是 1 到 100 的整数。")
        elif self.quality is not None:
            raise ImageConversionError(f"{spec.label} 不需要质量设置。")
        if len(self.background) != 3 or any(not 0 <= value <= 255 for value in self.background):
            raise ImageConversionError("背景颜色必须是有效的 RGB 颜色。")


@dataclass(frozen=True)
class ImageConversionOutput:
    source: Path
    destination: Path
    transparency_removed: bool


@dataclass(frozen=True)
class ImageConversionFailure:
    source: Path
    message: str


@dataclass(frozen=True)
class ImageBatchConversionResult:
    outputs: tuple[ImageConversionOutput, ...]
    failures: tuple[ImageConversionFailure, ...]


def detect_image_format(path: str | Path) -> str:
    """Identify an image from its bytes rather than trusting its extension."""
    source = Path(path)
    if not source.is_file():
        raise ImageConversionError("输入图片不存在或无法访问。")
    try:
        with Image.open(source) as image:
            detected = _PILLOW_FORMAT_TO_KEY.get((image.format or "").upper())
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageConversionError(f"无法读取图片或图片已损坏：{exc}") from exc
    if detected is None:
        supported = "、".join(spec.label for spec in IMAGE_FORMAT_SPECS.values())
        raise ImageConversionError(f"不支持该图片格式。请选择 {supported} 文件。")
    return detected


def unique_image_output(output_dir: str | Path, source: str | Path, output_format: str) -> Path:
    """Return a same-stem output path without overwriting any existing file."""
    try:
        extension = IMAGE_FORMAT_SPECS[output_format].extension
    except KeyError as exc:
        raise ImageConversionError("不支持所选的图片输出格式。") from exc
    directory = Path(output_dir)
    source_path = Path(source)
    candidate = directory / f"{source_path.stem}{extension}"
    index = 1
    while candidate.exists() or candidate.resolve() == source_path.resolve():
        candidate = directory / f"{source_path.stem}_{index}{extension}"
        index += 1
    return candidate


def _has_transparency(image: Image.Image) -> bool:
    if "A" in image.getbands():
        alpha = image.getchannel("A")
        return alpha.getextrema()[0] < 255
    if image.mode == "P" and "transparency" in image.info:
        return True
    return False


def _flatten_transparency(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    rgba = image.convert("RGBA")
    flattened = Image.new("RGB", rgba.size, background)
    flattened.paste(rgba, mask=rgba.getchannel("A"))
    return flattened


def _prepare_image(
    image: Image.Image, spec: ImageFormatSpec, background: tuple[int, int, int]
) -> tuple[Image.Image, bool]:
    transparency_removed = _has_transparency(image) and not spec.supports_transparency
    if transparency_removed:
        return _flatten_transparency(image, background), True
    if spec.key == "jpg":
        return image.convert("RGB"), False
    if spec.key == "bmp" and image.mode not in {"1", "L", "P", "RGB"}:
        return image.convert("RGB"), False
    if spec.key in {"png", "webp"} and image.mode == "CMYK":
        return image.convert("RGB"), False
    return image.copy(), False


def convert_image(
    source: str | Path,
    output_dir: str | Path,
    settings: ImageConversionSettings,
) -> ImageConversionOutput:
    """Convert one image while preserving its pixel dimensions."""
    source_path = Path(source)
    directory = Path(output_dir)
    settings.validate()
    detect_image_format(source_path)
    if not directory.is_dir():
        raise ImageConversionError("输出目录不存在或无法访问。")
    destination = unique_image_output(directory, source_path, settings.output_format)
    spec = settings.format_spec
    try:
        with Image.open(source_path) as opened:
            opened.load()
            original_size = opened.size
            prepared, transparency_removed = _prepare_image(opened, spec, settings.background)
            save_options: dict[str, object] = {}
            if spec.supports_quality:
                save_options["quality"] = settings.resolved_quality
            if "dpi" in opened.info:
                save_options["dpi"] = opened.info["dpi"]
            prepared.save(destination, format=spec.pillow_format, **save_options)
            prepared.close()
        with Image.open(destination) as result:
            result.verify()
            if result.size != original_size:
                raise ImageConversionError("转换后的图片尺寸发生了意外变化。")
    except ImageConversionError:
        destination.unlink(missing_ok=True)
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        destination.unlink(missing_ok=True)
        raise ImageConversionError(f"图片转换失败：{exc}") from exc
    return ImageConversionOutput(source_path, destination, transparency_removed)


def convert_image_batch(
    sources: Iterable[str | Path],
    output_dir: str | Path,
    settings: ImageConversionSettings,
    progress: ImageProgressCallback | None = None,
) -> ImageBatchConversionResult:
    """Convert a batch, recording failures without aborting later files."""
    source_paths = tuple(Path(source) for source in sources)
    if not source_paths:
        raise ImageConversionError("请至少选择一张图片。")
    settings.validate()
    outputs: list[ImageConversionOutput] = []
    failures: list[ImageConversionFailure] = []
    total = len(source_paths)
    for index, source in enumerate(source_paths, start=1):
        if progress:
            progress(source, index, total, (index - 1) / total * 100)
        try:
            outputs.append(convert_image(source, output_dir, settings))
        except ImageConversionError as exc:
            failures.append(ImageConversionFailure(source, str(exc)))
        if progress:
            progress(source, index, total, index / total * 100)
    return ImageBatchConversionResult(tuple(outputs), tuple(failures))
