"""End-to-end acceptance tests for MP3 embedded cover writing."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib
import tempfile
import unittest

from PIL import Image
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, USLT
from mutagen.mp3 import MP3

from sub2lrc.cover import CoverEmbedError, embed_cover
from sub2lrc.embedder import embed_lrc


# A parseable MPEG-1 Layer III frame repeated to provide a stable MP3 payload.
# ID3 writes must leave these bytes exactly unchanged.
MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413


def write_test_mp3(path: Path) -> bytes:
    audio_frames = MP3_FRAME * 1000
    path.write_bytes(audio_frames)
    # Prove the test input is accepted as MP3 audio before exercising Sub2LRC.
    MP3(path)
    return audio_frames


def make_image(path: Path, image_format: str, color: tuple[int, int, int]) -> bytes:
    Image.new("RGB", (320, 240), color).save(path, format=image_format)
    data = path.read_bytes()
    with Image.open(BytesIO(data)) as decoded:
        decoded.verify()
        if decoded.format != image_format:
            raise AssertionError(f"expected {image_format}, got {decoded.format}")
    return data


def audio_frames(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(b"ID3"):
        return data
    tag_size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
    return data[10 + tag_size :]


def one_cover(path: Path) -> APIC:
    covers = ID3(path, translate=False).getall("APIC")
    if len(covers) != 1:
        raise AssertionError(f"expected exactly one APIC frame, got {len(covers)}")
    return covers[0]


class CoverAcceptanceTests(unittest.TestCase):
    def test_jpeg_front_cover_on_mp3_without_id3_preserves_audio_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3_path = root / "中文 歌曲.mp3"
            image_path = root / "中文 封面.jpg"
            original_frames = write_test_mp3(mp3_path)
            original_duration = MP3(mp3_path).info.length
            jpeg_data = make_image(image_path, "JPEG", (210, 40, 30))

            embed_cover(mp3_path, image_path)

            cover = one_cover(mp3_path)
            self.assertEqual(cover.type, 3)
            self.assertEqual(cover.mime, "image/jpeg")
            self.assertEqual(cover.data, jpeg_data)
            with Image.open(BytesIO(cover.data)) as decoded:
                decoded.verify()
                self.assertEqual(decoded.format, "JPEG")
            self.assertEqual(audio_frames(mp3_path), original_frames)
            self.assertEqual(
                hashlib.sha256(audio_frames(mp3_path)).digest(),
                hashlib.sha256(original_frames).digest(),
            )
            self.assertAlmostEqual(MP3(mp3_path).info.length, original_duration, places=6)

    def test_png_front_cover_has_correct_mime_and_preserves_audio_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3_path = root / "song.mp3"
            image_path = root / "cover.png"
            original_frames = write_test_mp3(mp3_path)
            png_data = make_image(image_path, "PNG", (20, 100, 220))

            embed_cover(mp3_path, image_path)

            cover = one_cover(mp3_path)
            self.assertEqual(cover.type, 3)
            self.assertEqual(cover.mime, "image/png")
            self.assertEqual(cover.data, png_data)
            with Image.open(BytesIO(cover.data)) as decoded:
                decoded.verify()
                self.assertEqual(decoded.format, "PNG")
            self.assertEqual(audio_frames(mp3_path), original_frames)

    def test_existing_covers_are_replaced_and_all_other_tags_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3_path = root / "tagged.mp3"
            image_path = root / "replacement.jpg"
            original_frames = write_test_mp3(mp3_path)
            replacement = make_image(image_path, "JPEG", (40, 190, 80))
            old_front = make_image(root / "old-front.png", "PNG", (1, 2, 3))
            old_back = make_image(root / "old-back.png", "PNG", (4, 5, 6))
            tags = ID3()
            tags.add(TIT2(encoding=3, text=["中文歌名"]))
            tags.add(TPE1(encoding=3, text=["Artist 艺术家"]))
            tags.add(TALB(encoding=3, text=["Album 专辑"]))
            tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="[00:01.00]歌词"))
            tags.add(APIC(encoding=1, mime="image/png", type=3, desc="old front", data=old_front))
            tags.add(APIC(encoding=1, mime="image/png", type=4, desc="old back", data=old_back))
            tags.save(mp3_path, v2_version=4)

            embed_cover(mp3_path, image_path)

            saved = ID3(mp3_path, translate=False)
            cover = one_cover(mp3_path)
            self.assertEqual(cover.type, 3)
            self.assertEqual(cover.mime, "image/jpeg")
            self.assertEqual(cover.data, replacement)
            self.assertEqual(saved.getall("TIT2")[0].text, ["中文歌名"])
            self.assertEqual(saved.getall("TPE1")[0].text, ["Artist 艺术家"])
            self.assertEqual(saved.getall("TALB")[0].text, ["Album 专辑"])
            self.assertEqual(saved.getall("USLT")[0].text, "[00:01.00]歌词")
            self.assertEqual(audio_frames(mp3_path), original_frames)

    def test_embed_lyrics_then_cover_leaves_both_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3_path = root / "先歌词 后封面.mp3"
            lrc_path = root / "歌词 中文.lrc"
            image_path = root / "封面 中文.png"
            original_frames = write_test_mp3(mp3_path)
            lyrics = "[00:01.00]第一句\n[00:05.00]English ～ & \"引号\" 😀\n"
            lrc_path.write_bytes(b"\xef\xbb\xbf" + lyrics.encode("utf-8"))
            png_data = make_image(image_path, "PNG", (110, 45, 170))

            embed_lrc(mp3_path, lrc_path)
            embed_cover(mp3_path, image_path)

            saved = ID3(mp3_path, translate=False)
            matching_lyrics = [
                frame for frame in saved.getall("USLT") if frame.desc == "Sub2LRC"
            ]
            self.assertEqual(len(matching_lyrics), 1)
            self.assertEqual(matching_lyrics[0].text, lyrics)
            cover = one_cover(mp3_path)
            self.assertEqual(cover.type, 3)
            self.assertEqual(cover.mime, "image/png")
            self.assertEqual(cover.data, png_data)
            self.assertEqual(audio_frames(mp3_path), original_frames)

    def test_invalid_inputs_raise_clear_errors_without_modifying_mp3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3_path = root / "unchanged.mp3"
            valid_image = root / "valid.jpg"
            write_test_mp3(mp3_path)
            make_image(valid_image, "JPEG", (80, 80, 80))
            original_file = mp3_path.read_bytes()

            cases = [
                (root / "empty.jpg", b""),
                (root / "broken.jpg", b"not an image"),
                # Correct-looking markers but invalid JPEG structure.
                (root / "fake.jpg", b"\xff\xd8\xffnot-a-real-jpeg\xff\xd9"),
                # Correct-looking PNG chunks but invalid/corrupt image data.
                (
                    root / "fake.png",
                    b"\x89PNG\r\n\x1a\n"
                    + b"\x00\x00\x00\x0dIHDR"
                    + b"\x00\x00\x00\x01\x00\x00\x00\x01"
                    + b"garbage-data-IEND\x00\x00\x00\x00",
                ),
            ]
            for image_path, data in cases:
                image_path.write_bytes(data)
                with self.subTest(image=image_path.name):
                    with self.assertRaisesRegex(CoverEmbedError, "有效的 JPEG 或 PNG"):
                        embed_cover(mp3_path, image_path)
                    self.assertEqual(mp3_path.read_bytes(), original_file)

            text_named_mp3 = root / "not-audio.mp3"
            text_named_mp3.write_text("This is not MP3 audio.", encoding="utf-8")
            with self.assertRaisesRegex(CoverEmbedError, "不是有效的 MP3"):
                embed_cover(text_named_mp3, valid_image)
            self.assertEqual(text_named_mp3.read_text(encoding="utf-8"), "This is not MP3 audio.")

            not_mp3 = root / "audio.wav"
            not_mp3.write_bytes(original_file)
            with self.assertRaisesRegex(CoverEmbedError, "扩展名为 .mp3"):
                embed_cover(not_mp3, valid_image)
            with self.assertRaisesRegex(CoverEmbedError, "MP3 文件不存在"):
                embed_cover(root / "missing.mp3", valid_image)
            with self.assertRaisesRegex(CoverEmbedError, "封面图片不存在"):
                embed_cover(mp3_path, root / "missing.jpg")


if __name__ == "__main__":
    unittest.main()
