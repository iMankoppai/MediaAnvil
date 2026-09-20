from pathlib import Path
import os
import stat
import tempfile
import unittest

from mutagen.id3 import APIC, ID3, TDRC, TIT2, TPE1, USLT
from mutagen.mp3 import MP3

from sub2lrc.embedder import LyricsEmbedError, embed_lrc, read_lrc


MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413


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


class EmbedderTests(unittest.TestCase):
    def test_embeds_chinese_lrc_and_preserves_existing_tags_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "歌曲.mp3"
            lrc = root / "歌曲.lrc"
            original_audio = write_test_mp3(mp3)
            original_tags = ID3()
            original_tags.add(TIT2(encoding=3, text=["原歌曲标题"]))
            original_tags.add(TPE1(encoding=3, text=["原歌手"]))
            cover = b"\x89PNG\r\n\x1a\nTEST-COVER-DATA"
            original_tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Cover", data=cover))
            original_tags.add(USLT(encoding=1, lang="eng", desc="OtherApp", text="Existing lyrics"))
            original_tags.save(mp3, v2_version=3)
            before = mp3.read_bytes()
            duration_before = MP3(mp3).info.length
            lyrics = (
                "[00:01.00]中文：第一句～“你好” 😊\n"
                "[00:05.00]English & 日本語：第二句\n"
            )
            lrc.write_text(lyrics, encoding="utf-8-sig", newline="\n")

            output = embed_lrc(mp3, lrc)

            self.assertEqual(output, mp3)
            self.assertFalse((root / "歌曲.mp3.bak").exists())
            self.assertEqual(audio_payload(mp3), original_audio)
            self.assertAlmostEqual(MP3(mp3).info.length, duration_before, places=6)
            self.assertLess(abs(mp3.stat().st_size - len(before)), 128 * 1024)
            saved = ID3(mp3, v2_version=3)
            self.assertEqual(saved.getall("TIT2")[0].text, ["原歌曲标题"])
            self.assertEqual(saved.getall("TPE1")[0].text, ["原歌手"])
            self.assertEqual(saved.getall("APIC")[0].data, cover)
            self.assertEqual(
                [frame.text for frame in saved.getall("USLT") if frame.desc == "OtherApp"],
                ["Existing lyrics"],
            )
            self.assertEqual(
                [frame.text for frame in saved.getall("USLT") if frame.desc == "Sub2LRC"],
                [lyrics],
            )

    def test_mp3_without_id3_gets_lyrics_without_changing_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "中文 歌曲.mp3"
            lrc = root / "中文 歌曲.lrc"
            original_audio = write_test_mp3(mp3)
            duration_before = MP3(mp3).info.length
            lrc.write_text("[00:01.00]第一句\n[00:05.00]第二句\n", encoding="utf-8-sig", newline="\n")

            embed_lrc(mp3, lrc)

            self.assertEqual(audio_payload(mp3), original_audio)
            self.assertAlmostEqual(MP3(mp3).info.length, duration_before, places=6)
            self.assertEqual(ID3(mp3, translate=False).version[1], 3)

    def test_reembedding_replaces_only_sub2lrc_frame(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "song.mp3"
            lrc = root / "song.lrc"
            write_test_mp3(mp3)
            lrc.write_text("[00:01.00]first\n", encoding="utf-8", newline="\n")
            embed_lrc(mp3, lrc)
            lrc.write_text("[00:02.00]second\n", encoding="utf-8", newline="\n")
            embed_lrc(mp3, lrc)

            frames = [frame for frame in ID3(mp3).getall("USLT") if frame.desc == "Sub2LRC"]
            self.assertEqual(len(frames), 1)
            self.assertEqual(frames[0].text, "[00:02.00]second\n")
            self.assertFalse((root / "song.mp3.bak").exists())

    def test_save_as_keeps_source_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp3"
            destination = root / "saved as.mp3"
            lrc = root / "lyrics.lrc"
            write_test_mp3(source)
            source_before = source.read_bytes()
            lrc.write_text("[00:01.00]lyrics\n", encoding="utf-8", newline="\n")

            output = embed_lrc(source, lrc, destination)

            self.assertEqual(output, destination)
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(
                [frame.text for frame in ID3(destination).getall("USLT") if frame.desc == "Sub2LRC"],
                ["[00:01.00]lyrics\n"],
            )
            self.assertFalse(any(root.glob("*.bak")))

    def test_preserves_existing_id3v24_version_and_frame(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "song.mp3"
            lrc = root / "song.lrc"
            write_test_mp3(mp3)
            tags = ID3()
            tags.add(TDRC(encoding=3, text=["2026-09-03"]))
            tags.save(mp3, v2_version=4)
            lrc.write_text("[00:01.00]lyrics\n", encoding="utf-8", newline="\n")

            embed_lrc(mp3, lrc)

            saved = ID3(mp3, translate=False)
            self.assertEqual(saved.version[1], 4)
            self.assertEqual(str(saved.getall("TDRC")[0]), "2026-09-03")

    def test_rejects_invalid_files_and_lyrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "song.mp3"
            lrc = root / "song.lrc"
            write_test_mp3(mp3)
            lrc.write_text("没有时间标签", encoding="utf-8")
            with self.assertRaisesRegex(LyricsEmbedError, "没有找到有效时间标签"):
                embed_lrc(mp3, lrc)
            with self.assertRaisesRegex(LyricsEmbedError, "扩展名为 .mp3"):
                embed_lrc(root / "song.wav", lrc)

            broken = root / "broken.mp3"
            broken.write_bytes(b"not mp3 audio")
            valid_lrc = root / "valid.lrc"
            valid_lrc.write_text("[00:01.00]lyrics\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(LyricsEmbedError, "不是有效的 MP3"):
                embed_lrc(broken, valid_lrc)

            empty = root / "empty.lrc"
            empty.write_bytes(b"")
            with self.assertRaisesRegex(LyricsEmbedError, "内容为空"):
                embed_lrc(mp3, empty)

    @unittest.skipUnless(os.name == "nt", "Windows read-only semantics")
    def test_read_only_mp3_reports_error_and_remains_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "只读 歌曲.mp3"
            lrc = root / "只读 歌曲.lrc"
            write_test_mp3(mp3)
            before = mp3.read_bytes()
            lrc.write_text("[00:01.00]歌词\n", encoding="utf-8", newline="\n")
            os.chmod(mp3, stat.S_IREAD)
            try:
                with self.assertRaisesRegex(LyricsEmbedError, "写入 ID3 标签失败"):
                    embed_lrc(mp3, lrc)
                self.assertEqual(mp3.read_bytes(), before)
            finally:
                os.chmod(mp3, stat.S_IWRITE)

    def test_reads_utf16_lrc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lrc = Path(directory) / "歌词.lrc"
            text = "[00:01.00]中文歌词\n"
            lrc.write_text(text, encoding="utf-16", newline="\n")
            self.assertEqual(read_lrc(lrc), text)

    def test_preserves_crlf_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lrc = Path(directory) / "lyrics.lrc"
            raw = b"\xef\xbb\xbf[00:01.00]first\r\n[00:02.00]second\r\n"
            lrc.write_bytes(raw)
            self.assertEqual(read_lrc(lrc), "[00:01.00]first\r\n[00:02.00]second\r\n")


if __name__ == "__main__":
    unittest.main()
