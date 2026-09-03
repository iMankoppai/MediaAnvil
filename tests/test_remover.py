import os
from pathlib import Path
import stat
import tempfile
import unittest

from mutagen.id3 import APIC, ID3, SYLT, TALB, TIT2, TPE1, USLT
from mutagen.mp3 import MP3

from sub2lrc.remover import TagRemovalError, remove_embedded_covers, remove_embedded_lyrics


MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413
IMAGE_DATA = b"\x89PNG\r\n\x1a\ncover"


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


def add_common_tags(path: Path) -> None:
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["歌名"]))
    tags.add(TPE1(encoding=3, text=["歌手"]))
    tags.add(TALB(encoding=3, text=["专辑"]))
    tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="[00:01.00]歌词"))
    tags.add(SYLT(encoding=1, lang="und", format=2, type=1, desc="Synced", text=[("同步歌词", 1000)]))
    tags.add(APIC(encoding=1, mime="image/png", type=3, desc="Front", data=IMAGE_DATA))
    tags.add(APIC(encoding=1, mime="image/png", type=4, desc="Back", data=IMAGE_DATA))
    tags.save(path, v2_version=4)


class RemoverTests(unittest.TestCase):
    def test_removes_all_lyrics_and_preserves_cover_metadata_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "中文 歌曲.mp3"
            original_audio = write_test_mp3(mp3)
            add_common_tags(mp3)
            before = mp3.read_bytes()
            duration_before = MP3(mp3).info.length

            result = remove_embedded_lyrics(mp3)

            saved = ID3(mp3, translate=False)
            self.assertEqual(result.removed_count, 2)
            self.assertEqual(result.output_path, mp3)
            self.assertFalse((root / "中文 歌曲.mp3.bak").exists())
            self.assertEqual(saved.getall("USLT"), [])
            self.assertEqual(saved.getall("SYLT"), [])
            self.assertEqual(len(saved.getall("APIC")), 2)
            self.assertEqual(saved.getall("TIT2")[0].text, ["歌名"])
            self.assertEqual(saved.getall("TPE1")[0].text, ["歌手"])
            self.assertEqual(saved.getall("TALB")[0].text, ["专辑"])
            self.assertEqual(audio_payload(mp3), original_audio)
            self.assertAlmostEqual(MP3(mp3).info.length, duration_before, places=6)

    def test_removes_all_covers_and_preserves_lyrics_metadata_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "song.mp3"
            original_audio = write_test_mp3(mp3)
            add_common_tags(mp3)

            result = remove_embedded_covers(mp3)

            saved = ID3(mp3, translate=False)
            self.assertEqual(result.removed_count, 2)
            self.assertEqual(saved.getall("APIC"), [])
            self.assertEqual(len(saved.getall("USLT")), 1)
            self.assertEqual(len(saved.getall("SYLT")), 1)
            self.assertEqual(saved.getall("TIT2")[0].text, ["歌名"])
            self.assertEqual(saved.getall("TPE1")[0].text, ["歌手"])
            self.assertEqual(saved.getall("TALB")[0].text, ["专辑"])
            self.assertEqual(audio_payload(mp3), original_audio)

    def test_no_matching_tags_is_a_noop_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "song.mp3"
            write_test_mp3(mp3)
            tags = ID3()
            tags.add(TIT2(encoding=3, text=["Title"]))
            tags.save(mp3, v2_version=3)
            before = mp3.read_bytes()

            lyrics_result = remove_embedded_lyrics(mp3)
            covers_result = remove_embedded_covers(mp3)

            self.assertEqual(lyrics_result.removed_count, 0)
            self.assertIsNone(lyrics_result.output_path)
            self.assertEqual(covers_result.removed_count, 0)
            self.assertIsNone(covers_result.output_path)
            self.assertEqual(mp3.read_bytes(), before)
            self.assertFalse((root / "song.mp3.bak").exists())

    def test_save_as_removal_keeps_source_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp3"
            destination = root / "without lyrics.mp3"
            write_test_mp3(source)
            add_common_tags(source)
            source_before = source.read_bytes()

            result = remove_embedded_lyrics(source, destination)

            self.assertEqual(result.output_path, destination)
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(ID3(destination).getall("USLT"), [])
            self.assertEqual(ID3(destination).getall("SYLT"), [])
            self.assertEqual(len(ID3(destination).getall("APIC")), 2)
            self.assertFalse(any(root.glob("*.bak")))

    def test_reports_missing_and_invalid_mp3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(TagRemovalError, "MP3 文件不存在"):
                remove_embedded_lyrics(root / "missing.mp3")
            broken = root / "broken.mp3"
            broken.write_bytes(b"not mp3")
            with self.assertRaisesRegex(TagRemovalError, "不是有效的 MP3"):
                remove_embedded_covers(broken)

    @unittest.skipUnless(os.name == "nt", "Windows read-only semantics")
    def test_read_only_mp3_reports_error_and_restores_original(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "只读歌曲.mp3"
            write_test_mp3(mp3)
            add_common_tags(mp3)
            before = mp3.read_bytes()
            os.chmod(mp3, stat.S_IREAD)
            try:
                with self.assertRaisesRegex(TagRemovalError, "移除内嵌歌词失败"):
                    remove_embedded_lyrics(mp3)
                self.assertEqual(mp3.read_bytes(), before)
            finally:
                os.chmod(mp3, stat.S_IWRITE)


if __name__ == "__main__":
    unittest.main()
