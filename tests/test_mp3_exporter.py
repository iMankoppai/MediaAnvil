from pathlib import Path
import tempfile
import unittest

from PIL import Image
from mutagen.id3 import APIC, ID3, SYLT, TALB, TIT2, TPE1, USLT

from sub2lrc.mp3_exporter import (
    Mp3ExportError,
    export_embedded_cover,
    export_embedded_lyrics,
    inspect_mp3,
    read_embedded_cover,
    read_embedded_lyrics,
)


MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413


def make_mp3(path: Path) -> None:
    path.write_bytes(MP3_FRAME * 800)


def image_bytes(path: Path, image_format: str, color: str) -> bytes:
    Image.new("RGB", (32, 24), color).save(path, format=image_format)
    return path.read_bytes()


class Mp3ExporterTests(unittest.TestCase):
    def test_inspector_reports_audio_file_and_tag_information(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "中文 歌曲.mp3"
            make_mp3(mp3)
            cover = image_bytes(root / "封面.png", "PNG", "navy")
            tags = ID3()
            tags.add(TIT2(encoding=3, text=["歌名"])); tags.add(TPE1(encoding=3, text=["歌手"]))
            tags.add(TALB(encoding=3, text=["专辑"])); tags.add(USLT(encoding=1, desc="Sub2LRC", text="歌词"))
            tags.add(APIC(encoding=1, mime="image/png", type=3, desc="Cover", data=cover))
            tags.save(mp3, v2_version=4)

            info = inspect_mp3(mp3)

            self.assertGreater(info.duration_seconds, 0)
            self.assertGreater(info.bitrate_kbps, 0)
            self.assertGreater(info.sample_rate_hz, 0)
            self.assertIn(info.channels, (1, 2))
            self.assertEqual(info.file_size_bytes, mp3.stat().st_size)
            self.assertEqual(info.id3_version, "ID3v2.4")
            self.assertGreaterEqual(info.tag_count, 5)
            self.assertEqual((info.lyrics_count, info.cover_count), (1, 1))

    def test_exports_timed_uslt_as_lrc_with_utf8_bom_without_modifying_mp3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "中文歌曲.mp3"; make_mp3(mp3)
            tags = ID3(); tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="[00:01.00]你好\n")); tags.save(mp3)
            before = mp3.read_bytes()

            output, count = export_embedded_lyrics(mp3, root)

            self.assertEqual(output.name, "中文歌曲.lrc")
            self.assertEqual(count, 1)
            self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertEqual(output.read_text(encoding="utf-8-sig"), "[00:01.00]你好\n")
            self.assertEqual(mp3.read_bytes(), before)

    def test_exports_plain_uslt_as_txt_and_prefers_sub2lrc_frame(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mp3 = root / "song.mp3"; make_mp3(mp3)
            tags = ID3()
            tags.add(USLT(encoding=1, lang="eng", desc="Other", text="other"))
            tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="普通歌词"))
            tags.save(mp3)
            lyrics = read_embedded_lyrics(mp3)
            output, count = export_embedded_lyrics(mp3, root)
            self.assertEqual((lyrics.text, lyrics.extension, lyrics.frame_count), ("普通歌词", ".txt", 2))
            self.assertEqual(output.suffix, ".txt")
            self.assertEqual(count, 2)

    def test_exports_sylt_as_timed_lrc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mp3 = root / "sync.mp3"; make_mp3(mp3)
            tags = ID3(); tags.add(SYLT(encoding=3, lang="und", format=2, type=1, desc="", text=[("第一句", 1000), ("第二句", 5250)])); tags.save(mp3)
            lyrics = read_embedded_lyrics(mp3)
            self.assertEqual(lyrics.extension, ".lrc")
            self.assertEqual(lyrics.text, "[00:01.00]第一句\n[00:05.25]第二句\n")

    def test_exports_front_cover_using_actual_png_content_and_avoids_existing_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mp3 = root / "歌曲.mp3"; make_mp3(mp3)
            front = image_bytes(root / "front.png", "PNG", "red")
            back = image_bytes(root / "back.jpg", "JPEG", "blue")
            tags = ID3()
            tags.add(APIC(encoding=1, mime="image/jpeg", type=4, desc="Back", data=back))
            tags.add(APIC(encoding=1, mime="image/jpeg", type=3, desc="Front", data=front))
            tags.save(mp3)
            (root / "歌曲.png").write_bytes(b"existing")
            before = mp3.read_bytes()

            selected = read_embedded_cover(mp3)
            output, count = export_embedded_cover(mp3, root)

            self.assertEqual((selected.data, selected.extension, selected.frame_count), (front, ".png", 2))
            self.assertEqual(output.name, "歌曲_1.png")
            self.assertEqual(output.read_bytes(), front)
            self.assertEqual(count, 2)
            self.assertEqual(mp3.read_bytes(), before)

    def test_missing_or_damaged_embedded_content_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mp3 = root / "empty.mp3"; make_mp3(mp3)
            with self.assertRaisesRegex(Mp3ExportError, "没有内嵌歌词"):
                read_embedded_lyrics(mp3)
            tags = ID3(); tags.add(APIC(encoding=1, mime="image/png", type=3, desc="Cover", data=b"bad")); tags.save(mp3)
            with self.assertRaisesRegex(Mp3ExportError, "损坏"):
                read_embedded_cover(mp3)


if __name__ == "__main__":
    unittest.main()
