from pathlib import Path
import tempfile
import unittest

from PIL import Image

from sub2lrc.image_converter import (
    IMAGE_FORMAT_SPECS,
    ImageConversionError,
    ImageConversionSettings,
    convert_image,
    convert_image_batch,
    detect_image_format,
    unique_image_output,
)


class ImageConverterTests(unittest.TestCase):
    def _make_source(self, path: Path, format_name: str, *, alpha: bool = False) -> None:
        if alpha:
            image = Image.new("RGBA", (17, 11), (20, 80, 160, 0))
            image.putpixel((8, 5), (255, 0, 0, 255))
        else:
            image = Image.new("RGB", (17, 11), (20, 80, 160))
        image.save(path, format=format_name)
        image.close()

    def test_all_four_input_formats_convert_to_all_four_output_formats(self) -> None:
        source_formats = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "bmp": "BMP"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = root / "outputs"
            outputs.mkdir()
            for input_key, pillow_format in source_formats.items():
                source = root / f"source_{input_key}.{input_key}"
                self._make_source(source, pillow_format, alpha=input_key in {"png", "webp"})
                for output_key, spec in IMAGE_FORMAT_SPECS.items():
                    with self.subTest(input=input_key, output=output_key):
                        output = convert_image(source, outputs, ImageConversionSettings(output_key))
                        with Image.open(output.destination) as converted:
                            self.assertEqual(converted.format, spec.pillow_format)
                            self.assertEqual(converted.size, (17, 11))

    def test_auto_detection_uses_file_content_and_supports_chinese_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "中文 目录"
            root.mkdir()
            disguised = root / "不是JPEG.jpg"
            self._make_source(disguised, "PNG")
            self.assertEqual(detect_image_format(disguised), "png")
            output = convert_image(disguised, root, ImageConversionSettings("bmp"))
            self.assertEqual(output.destination.name, "不是JPEG.bmp")

    def test_transparent_png_to_jpg_flattens_on_white_and_reports_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "透明图片.png"
            self._make_source(source, "PNG", alpha=True)
            output = convert_image(source, root, ImageConversionSettings("jpg", quality=100))
            self.assertTrue(output.transparency_removed)
            with Image.open(output.destination) as converted:
                red, green, blue = converted.convert("RGB").getpixel((0, 0))
                self.assertGreater(red, 240)
                self.assertGreater(green, 240)
                self.assertGreater(blue, 240)

    def test_png_and_webp_preserve_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "alpha.png"
            self._make_source(source, "PNG", alpha=True)
            for output_format in ("png", "webp"):
                with self.subTest(output=output_format):
                    output = convert_image(source, root, ImageConversionSettings(output_format, 100 if output_format == "webp" else None))
                    self.assertFalse(output.transparency_removed)
                    with Image.open(output.destination) as converted:
                        self.assertIn("A", converted.convert("RGBA").getbands())
                        self.assertLess(converted.convert("RGBA").getchannel("A").getextrema()[0], 255)

    def test_quality_validation_is_used_only_for_jpg_and_webp(self) -> None:
        ImageConversionSettings("jpg", 1).validate()
        ImageConversionSettings("webp", 100).validate()
        with self.assertRaises(ImageConversionError):
            ImageConversionSettings("jpg", 0).validate()
        with self.assertRaises(ImageConversionError):
            ImageConversionSettings("png", 90).validate()

    def test_existing_or_same_format_output_gets_new_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "照片.png"
            self._make_source(source, "PNG")
            self.assertEqual(unique_image_output(root, source, "png").name, "照片_1.png")
            (root / "照片.jpg").touch()
            self.assertEqual(unique_image_output(root, source, "jpg").name, "照片_1.jpg")

    def test_batch_continues_after_invalid_image_and_reports_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / "正常图片.png"
            invalid = root / "损坏图片.jpg"
            self._make_source(valid, "PNG")
            invalid.write_bytes(b"not an image")
            updates: list[float] = []
            result = convert_image_batch(
                (invalid, valid), root, ImageConversionSettings("webp", 90),
                lambda _source, _index, _total, overall: updates.append(overall),
            )
            self.assertEqual(len(result.outputs), 1)
            self.assertEqual(len(result.failures), 1)
            self.assertEqual(result.failures[0].source, invalid)
            self.assertEqual(updates[-1], 100.0)

    def test_missing_input_and_missing_output_directory_have_clear_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ImageConversionError, "不存在"):
                convert_image(root / "missing.png", root, ImageConversionSettings("jpg"))
            source = root / "source.png"
            self._make_source(source, "PNG")
            with self.assertRaisesRegex(ImageConversionError, "输出目录"):
                convert_image(source, root / "missing", ImageConversionSettings("jpg"))


if __name__ == "__main__":
    unittest.main()
