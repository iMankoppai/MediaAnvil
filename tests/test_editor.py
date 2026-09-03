from pathlib import Path
import tempfile
import unittest

from PIL import Image
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, USLT

from sub2lrc.editor import Mp3Edits, read_mp3_editor_state, save_mp3_edits


MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413


def audio_frames(path: Path) -> bytes:
    data = path.read_bytes()
    start = 0
    if data.startswith(b"ID3"):
        start = 10 + ((data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9])
    end = len(data) - 128 if data[-128:-125] == b"TAG" else len(data)
    return data[start:end]


def make_image(path: Path, image_format: str, color: str) -> bytes:
    Image.new("RGB", (120, 90), color).save(path, format=image_format)
    return path.read_bytes()


def make_tagged_mp3(root: Path) -> tuple[Path, bytes, bytes]:
    mp3 = root / "中文歌曲.mp3"
    audio = MP3_FRAME * 1000
    mp3.write_bytes(audio)
    old_cover = make_image(root / "old.png", "PNG", "navy")
    tags = ID3()
    tags.add(TIT2(encoding=3, text=["原歌名"]))
    tags.add(TPE1(encoding=3, text=["原歌手"]))
    tags.add(TALB(encoding=3, text=["原专辑"]))
    tags.add(USLT(encoding=1, lang="und", desc="Sub2LRC", text="[00:01.00]原歌词"))
    tags.add(APIC(encoding=1, mime="image/png", type=3, desc="Cover", data=old_cover))
    tags.save(mp3, v2_version=4)
    return mp3, audio, old_cover


class UnifiedEditorIntegrationTests(unittest.TestCase):
    def test_reads_basic_info_lyrics_and_cover_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mp3, _audio, cover = make_tagged_mp3(Path(directory))

            state = read_mp3_editor_state(mp3)

            self.assertEqual((state.title, state.artist, state.album), ("原歌名", "原歌手", "原专辑"))
            self.assertTrue(state.has_lyrics)
            self.assertEqual(state.lyrics, "[00:01.00]原歌词")
            self.assertTrue(state.has_cover)
            self.assertEqual(state.cover_data, cover)
            self.assertEqual(state.cover_mime, "image/png")

    def test_changing_title_preserves_lyrics_cover_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mp3, audio, cover = make_tagged_mp3(Path(directory))

            save_mp3_edits(mp3, Mp3Edits(title="新歌名"))

            state = read_mp3_editor_state(mp3)
            self.assertEqual((state.title, state.artist, state.album), ("新歌名", "原歌手", "原专辑"))
            self.assertEqual(state.lyrics, "[00:01.00]原歌词")
            self.assertEqual(state.cover_data, cover)
            self.assertEqual(audio_frames(mp3), audio)

    def test_replacing_lyrics_preserves_cover_basic_info_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3, audio, cover = make_tagged_mp3(root)
            lrc = root / "新歌词.lrc"
            lyrics = "[00:02.00]中文\n[00:05.00]日本語 English\n"
            lrc.write_bytes(b"\xef\xbb\xbf" + lyrics.encode("utf-8"))

            save_mp3_edits(mp3, Mp3Edits(lyrics_path=lrc))

            state = read_mp3_editor_state(mp3)
            self.assertEqual((state.title, state.artist, state.album), ("原歌名", "原歌手", "原专辑"))
            self.assertEqual(state.lyrics, lyrics)
            self.assertEqual(state.cover_data, cover)
            self.assertEqual(audio_frames(mp3), audio)

    def test_replacing_cover_preserves_lyrics_basic_info_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3, audio, _old_cover = make_tagged_mp3(root)
            new_cover_path = root / "新封面.jpg"
            new_cover = make_image(new_cover_path, "JPEG", "orange")

            save_mp3_edits(mp3, Mp3Edits(cover_path=new_cover_path))

            state = read_mp3_editor_state(mp3)
            self.assertEqual((state.title, state.artist, state.album), ("原歌名", "原歌手", "原专辑"))
            self.assertEqual(state.lyrics, "[00:01.00]原歌词")
            self.assertEqual(state.cover_data, new_cover)
            self.assertEqual(state.cover_mime, "image/jpeg")
            self.assertEqual(audio_frames(mp3), audio)

    def test_removing_lyrics_does_not_remove_cover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mp3, audio, cover = make_tagged_mp3(Path(directory))

            save_mp3_edits(mp3, Mp3Edits(remove_lyrics=True))

            state = read_mp3_editor_state(mp3)
            self.assertFalse(state.has_lyrics)
            self.assertEqual(state.cover_data, cover)
            self.assertEqual(audio_frames(mp3), audio)

    def test_removing_cover_does_not_remove_lyrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mp3, audio, _cover = make_tagged_mp3(Path(directory))

            save_mp3_edits(mp3, Mp3Edits(remove_cover=True))

            state = read_mp3_editor_state(mp3)
            self.assertFalse(state.has_cover)
            self.assertEqual(state.lyrics, "[00:01.00]原歌词")
            self.assertEqual(audio_frames(mp3), audio)

    def test_changes_title_lyrics_and_cover_in_one_save(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3, audio, _cover = make_tagged_mp3(root)
            lrc = root / "combined.lrc"
            lyrics = "[00:03.00]一次完成\n"
            lrc.write_text(lyrics, encoding="utf-8", newline="\n")
            cover_path = root / "combined.png"
            cover = make_image(cover_path, "PNG", "green")

            save_mp3_edits(
                mp3,
                Mp3Edits(title="一次修改", lyrics_path=lrc, cover_path=cover_path),
            )

            state = read_mp3_editor_state(mp3)
            self.assertEqual((state.title, state.artist, state.album), ("一次修改", "原歌手", "原专辑"))
            self.assertEqual(state.lyrics, lyrics)
            self.assertEqual(state.cover_data, cover)
            self.assertEqual(audio_frames(mp3), audio)

    def test_save_as_keeps_source_and_writes_all_changes_to_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, audio, old_cover = make_tagged_mp3(root)
            source_before = source.read_bytes()
            destination = root / "另存结果.mp3"
            lrc = root / "save-as.lrc"
            lyrics = "[00:04.00]另存歌词\n"
            lrc.write_text(lyrics, encoding="utf-8", newline="\n")
            cover_path = root / "save-as.jpg"
            new_cover = make_image(cover_path, "JPEG", "red")

            output = save_mp3_edits(
                source,
                Mp3Edits(title="另存歌名", lyrics_path=lrc, cover_path=cover_path),
                destination,
            )

            self.assertEqual(output, destination)
            self.assertEqual(source.read_bytes(), source_before)
            source_state = read_mp3_editor_state(source)
            self.assertEqual(source_state.title, "原歌名")
            self.assertEqual(source_state.cover_data, old_cover)
            saved = read_mp3_editor_state(destination)
            self.assertEqual(saved.title, "另存歌名")
            self.assertEqual(saved.lyrics, lyrics)
            self.assertEqual(saved.cover_data, new_cover)
            self.assertEqual(audio_frames(destination), audio)


if __name__ == "__main__":
    unittest.main()
