import base64
from io import BytesIO
import os
from pathlib import Path
import stat
import tempfile
import unittest

from PIL import Image
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, USLT
from mutagen.mp3 import MP3

from sub2lrc.cover import CoverEmbedError, embed_cover, read_cover
from sub2lrc.cropper import crop_square


MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/"
    "8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAA"
    "AAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAA"
    "AAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/a"
    "AAgBAQABPyF//9oADAMBAAIAAwAAABAf/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPxB//8QAFBEBAAAAAAAAAAAA"
    "AAAAAAAAAP/aAAgBAgEBPxB//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxB//9k="
)


def write_test_mp3(path: Path) -> bytes:
    audio = MP3_FRAME * 1000
    path.write_bytes(audio)
    return audio


def audio_payload(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(b"ID3"):
        return data
    size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
    return data[10 + size :]


class CoverTests(unittest.TestCase):
    def test_cropped_square_is_the_image_embedded_in_apic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "song.mp3"
            image_path = root / "cropped.png"
            original_audio = write_test_mp3(mp3)
            landscape = Image.new("RGB", (400, 200), "red")
            landscape.paste("blue", (200, 0, 400, 200))
            cropped = crop_square(landscape, (200, 0, 400, 200))
            cropped.save(image_path, format="PNG")

            embed_cover(mp3, image_path)

            cover_data = ID3(mp3).getall("APIC")[0].data
            with Image.open(BytesIO(cover_data)) as embedded:
                self.assertEqual(embedded.size, (200, 200))
                self.assertEqual(embedded.getpixel((100, 100)), (0, 0, 255))
            self.assertEqual(audio_payload(mp3), original_audio)

    def test_writes_png_cover_to_mp3_without_id3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "中文 歌曲.mp3"
            image = root / "中文 封面.png"
            original_audio = write_test_mp3(mp3)
            duration_before = MP3(mp3).info.length
            image.write_bytes(PNG_1X1)

            output = embed_cover(mp3, image)

            covers = ID3(mp3, translate=False).getall("APIC")
            self.assertEqual(output, mp3)
            self.assertFalse((root / "中文 歌曲.mp3.bak").exists())
            self.assertEqual(len(covers), 1)
            self.assertEqual(covers[0].mime, "image/png")
            self.assertEqual(covers[0].type, 3)
            self.assertEqual(covers[0].data, PNG_1X1)
            self.assertEqual(audio_payload(mp3), original_audio)
            self.assertAlmostEqual(MP3(mp3).info.length, duration_before, places=6)

    def test_save_as_keeps_source_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp3"
            destination = root / "new cover.mp3"
            image = root / "cover.png"
            write_test_mp3(source)
            source_before = source.read_bytes()
            image.write_bytes(PNG_1X1)

            output = embed_cover(source, image, destination)

            self.assertEqual(output, destination)
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(ID3(destination).getall("APIC")[0].data, PNG_1X1)
            self.assertFalse(any(root.glob("*.bak")))

    def test_jpeg_replaces_all_old_covers_and_preserves_other_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "song.mp3"
            image = root / "cover.jpeg"
            original_audio = write_test_mp3(mp3)
            tags = ID3()
            tags.add(TIT2(encoding=3, text=["Title"]))
            tags.add(TPE1(encoding=3, text=["Artist"]))
            tags.add(TALB(encoding=3, text=["Album"]))
            tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="[00:01.00]Lyrics"))
            tags.add(APIC(encoding=1, mime="image/png", type=3, desc="Old front", data=PNG_1X1))
            tags.add(APIC(encoding=1, mime="image/png", type=4, desc="Old back", data=PNG_1X1))
            tags.save(mp3, v2_version=4)
            image.write_bytes(JPEG_1X1)

            embed_cover(mp3, image)

            saved = ID3(mp3, translate=False)
            covers = saved.getall("APIC")
            self.assertEqual(saved.version[1], 4)
            self.assertEqual(len(covers), 1)
            self.assertEqual(covers[0].mime, "image/jpeg")
            self.assertEqual(covers[0].data, JPEG_1X1)
            self.assertEqual(saved.getall("TIT2")[0].text, ["Title"])
            self.assertEqual(saved.getall("TPE1")[0].text, ["Artist"])
            self.assertEqual(saved.getall("TALB")[0].text, ["Album"])
            self.assertEqual(saved.getall("USLT")[0].text, "[00:01.00]Lyrics")
            self.assertEqual(audio_payload(mp3), original_audio)

    def test_detects_mime_from_image_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            png_with_jpg_name = root / "cover.jpg"
            jpeg_with_png_name = root / "cover.png"
            png_with_jpg_name.write_bytes(PNG_1X1)
            jpeg_with_png_name.write_bytes(JPEG_1X1)
            self.assertEqual(read_cover(png_with_jpg_name), (PNG_1X1, "image/png"))
            self.assertEqual(read_cover(jpeg_with_png_name), (JPEG_1X1, "image/jpeg"))

    def test_reports_missing_and_invalid_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "song.mp3"
            write_test_mp3(mp3)
            with self.assertRaisesRegex(CoverEmbedError, "封面图片不存在"):
                embed_cover(mp3, root / "missing.png")
            with self.assertRaisesRegex(CoverEmbedError, "MP3 文件不存在"):
                embed_cover(root / "missing.mp3", root / "missing.png")

            invalid = root / "broken.jpg"
            invalid.write_bytes(b"not an image")
            with self.assertRaisesRegex(CoverEmbedError, "不是有效的 JPEG 或 PNG"):
                embed_cover(mp3, invalid)

            truncated_png = root / "truncated.png"
            truncated_png.write_bytes(b"\x89PNG\r\n\x1a\n")
            with self.assertRaisesRegex(CoverEmbedError, "不是有效的 JPEG 或 PNG"):
                embed_cover(mp3, truncated_png)

            truncated_jpeg = root / "truncated.jpeg"
            truncated_jpeg.write_bytes(b"\xff\xd8\xff" + b"broken data")
            with self.assertRaisesRegex(CoverEmbedError, "不是有效的 JPEG 或 PNG"):
                embed_cover(mp3, truncated_jpeg)

    @unittest.skipUnless(os.name == "nt", "Windows read-only semantics")
    def test_read_only_mp3_reports_error_and_restores_original(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "只读歌曲.mp3"
            image = root / "封面.jpg"
            write_test_mp3(mp3)
            image.write_bytes(JPEG_1X1)
            before = mp3.read_bytes()
            os.chmod(mp3, stat.S_IREAD)
            try:
                with self.assertRaisesRegex(CoverEmbedError, "写入封面失败"):
                    embed_cover(mp3, image)
                self.assertEqual(mp3.read_bytes(), before)
            finally:
                os.chmod(mp3, stat.S_IWRITE)


if __name__ == "__main__":
    unittest.main()
