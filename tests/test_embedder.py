from pathlib import Path
import tempfile
import unittest

from mutagen.id3 import ID3, TDRC, TIT2, USLT

from sub2lrc.embedder import LyricsEmbedError, embed_lrc, read_lrc


MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413


def write_test_mp3(path: Path) -> bytes:
    audio = MP3_FRAME * 10
    path.write_bytes(audio)
    return audio


class EmbedderTests(unittest.TestCase):
    def test_embeds_chinese_lrc_and_preserves_existing_tags_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "歌曲.mp3"
            lrc = root / "歌曲.lrc"
            audio_payload = write_test_mp3(mp3)
            original_tags = ID3()
            original_tags.add(TIT2(encoding=3, text=["原歌曲标题"]))
            original_tags.add(USLT(encoding=1, lang="eng", desc="OtherApp", text="Existing lyrics"))
            original_tags.save(mp3, v2_version=3)
            before = mp3.read_bytes()
            lyrics = "[00:01.25]你好，世界！\n[00:03.50]第二行\n"
            lrc.write_text(lyrics, encoding="utf-8-sig", newline="\n")

            backup = embed_lrc(mp3, lrc)

            self.assertEqual(backup.read_bytes(), before)
            self.assertTrue(mp3.read_bytes().endswith(audio_payload))
            saved = ID3(mp3, v2_version=3)
            self.assertEqual(saved.getall("TIT2")[0].text, ["原歌曲标题"])
            self.assertEqual(
                [frame.text for frame in saved.getall("USLT") if frame.desc == "OtherApp"],
                ["Existing lyrics"],
            )
            self.assertEqual(
                [frame.text for frame in saved.getall("USLT") if frame.desc == "Sub2LRC"],
                [lyrics],
            )

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
            self.assertTrue((root / "song.mp3.bak").exists())
            self.assertTrue((root / "song.mp3.1.bak").exists())

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
