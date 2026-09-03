from pathlib import Path
import tempfile
import unittest

from PIL import Image
from mutagen.id3 import APIC, COMM, ID3, TALB, TIT2, TPE1, USLT

from sub2lrc.metadata import MetadataError, Mp3Metadata, read_mp3_metadata, save_mp3_metadata


MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413


def write_test_mp3(path: Path) -> bytes:
    frames = MP3_FRAME * 1000
    path.write_bytes(frames)
    return frames


def audio_frames(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(b"ID3"):
        return data
    size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
    return data[10 + size :]


class MetadataTests(unittest.TestCase):
    def test_reads_existing_values_and_detects_cover_and_lyrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mp3 = Path(directory) / "读取 标签.mp3"
            write_test_mp3(mp3)
            tags = ID3()
            tags.add(TIT2(encoding=3, text=["歌名 Title"]))
            tags.add(TPE1(encoding=3, text=["歌手 アーティスト"]))
            tags.add(TALB(encoding=3, text=["专辑 Album"]))
            tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="[00:01.00]歌词"))
            tags.add(APIC(encoding=1, mime="image/png", type=3, desc="Cover", data=b"cover bytes"))
            tags.save(mp3, v2_version=4)

            metadata = read_mp3_metadata(mp3)

            self.assertEqual(
                metadata,
                Mp3Metadata("歌名 Title", "歌手 アーティスト", "专辑 Album", True, True),
            )

    def test_creates_unicode_tags_when_mp3_has_no_id3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mp3 = Path(directory) / "没有标签.mp3"
            original_audio = write_test_mp3(mp3)

            save_mp3_metadata(mp3, "中文标题", "日本語の歌手", "English Album")

            self.assertEqual(
                read_mp3_metadata(mp3),
                Mp3Metadata("中文标题", "日本語の歌手", "English Album", False, False),
            )
            self.assertEqual(audio_frames(mp3), original_audio)

    def test_updates_only_basic_tags_and_preserves_cover_lyrics_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "完整 标签.mp3"
            image = root / "cover.png"
            Image.new("RGB", (32, 32), "purple").save(image, format="PNG")
            cover_data = image.read_bytes()
            original_audio = write_test_mp3(mp3)
            tags = ID3()
            tags.add(TIT2(encoding=3, text=["Old title"]))
            tags.add(TPE1(encoding=3, text=["Old artist"]))
            tags.add(TALB(encoding=3, text=["Old album"]))
            tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="[00:01.00]保留歌词"))
            tags.add(APIC(encoding=1, mime="image/png", type=3, desc="Cover", data=cover_data))
            tags.add(COMM(encoding=3, lang="und", desc="note", text=["保留备注"]))
            tags.save(mp3, v2_version=4)

            save_mp3_metadata(mp3, "新歌名 中文", "新歌手 日本語", "New Album")

            saved = ID3(mp3, translate=False)
            self.assertEqual(saved.getall("TIT2")[0].text, ["新歌名 中文"])
            self.assertEqual(saved.getall("TPE1")[0].text, ["新歌手 日本語"])
            self.assertEqual(saved.getall("TALB")[0].text, ["New Album"])
            self.assertEqual(saved.getall("USLT")[0].text, "[00:01.00]保留歌词")
            self.assertEqual(saved.getall("APIC")[0].data, cover_data)
            self.assertEqual(saved.getall("APIC")[0].type, 3)
            self.assertEqual(saved.getall("COMM")[0].text, ["保留备注"])
            self.assertEqual(audio_frames(mp3), original_audio)

    def test_empty_fields_remove_only_the_three_basic_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mp3 = Path(directory) / "clear.mp3"
            write_test_mp3(mp3)
            tags = ID3()
            tags.add(TIT2(encoding=3, text=["Title"]))
            tags.add(TPE1(encoding=3, text=["Artist"]))
            tags.add(TALB(encoding=3, text=["Album"]))
            tags.add(USLT(encoding=1, lang="und", desc="keep", text="Lyrics"))
            tags.save(mp3)

            save_mp3_metadata(mp3, "", "", "")

            saved = ID3(mp3, translate=False)
            self.assertEqual(saved.getall("TIT2"), [])
            self.assertEqual(saved.getall("TPE1"), [])
            self.assertEqual(saved.getall("TALB"), [])
            self.assertEqual(saved.getall("USLT")[0].text, "Lyrics")

    def test_preserves_id3v23_cover_and_lyrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mp3 = Path(directory) / "id3v23.mp3"
            original_audio = write_test_mp3(mp3)
            tags = ID3()
            tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="[00:02.00]歌词"))
            tags.add(APIC(encoding=1, mime="image/jpeg", type=3, desc="Cover", data=b"jpeg data"))
            tags.save(mp3, v2_version=3)

            save_mp3_metadata(mp3, "标题", "歌手", "专辑")

            saved = ID3(mp3, translate=False)
            self.assertEqual(saved.version[1], 3)
            self.assertEqual(saved.getall("USLT")[0].text, "[00:02.00]歌词")
            self.assertEqual(saved.getall("APIC")[0].data, b"jpeg data")
            self.assertEqual(audio_frames(mp3), original_audio)

    def test_save_as_does_not_modify_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp3"
            destination = root / "另存为.mp3"
            write_test_mp3(source)
            source_before = source.read_bytes()

            output = save_mp3_metadata(source, "Title", "Artist", "Album", destination)

            self.assertEqual(output, destination)
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(read_mp3_metadata(destination).title, "Title")

    def test_invalid_inputs_raise_clear_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(MetadataError, "扩展名为 .mp3"):
                read_mp3_metadata(root / "song.wav")
            with self.assertRaisesRegex(MetadataError, "MP3 文件不存在"):
                read_mp3_metadata(root / "missing.mp3")
            invalid = root / "broken.mp3"
            invalid.write_text("not audio", encoding="utf-8")
            before = invalid.read_bytes()
            with self.assertRaisesRegex(MetadataError, "不是有效的 MP3"):
                save_mp3_metadata(invalid, "a", "b", "c")
            self.assertEqual(invalid.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
