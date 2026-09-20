from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest

from PIL import Image

from sub2lrc.audio_converter import find_ffmpeg
from sub2lrc.audio_metadata import (
    AudioMetadataChanges,
    AudioMetadataError,
    export_metadata_cover,
    export_metadata_lyrics,
    read_metadata,
    write_metadata,
)


class AudioMetadataAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ffmpeg = find_ffmpeg(os.environ.get("SUB2LRC_TEST_FFMPEG"))

    def _make_audio(self, path: Path) -> None:
        codecs = {
            ".mp3": ["-c:a", "libmp3lame"], ".flac": ["-c:a", "flac"],
            ".m4a": ["-c:a", "aac"], ".ogg": ["-c:a", "libvorbis"],
            ".opus": ["-c:a", "libopus"], ".wav": ["-c:a", "pcm_s16le"],
        }
        subprocess.run(
            [str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=440:duration=0.3", *codecs[path.suffix], "-y", str(path)],
            check=True, capture_output=True,
        )

    def _pcm_hash(self, path: Path) -> str:
        result = subprocess.run(
            [str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-i", str(path),
             "-map", "0:a:0", "-f", "s16le", "-"], check=True, capture_output=True,
        )
        return hashlib.sha256(result.stdout).hexdigest()

    def test_all_writable_adapters_round_trip_unicode_lyrics_cover_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lrc = root / "歌词.lrc"; lrc.write_text("[00:00.00]中文 日本語 English\n", encoding="utf-8")
            cover = root / "封面.png"; Image.new("RGB", (24, 24), "orange").save(cover)
            for suffix in (".mp3", ".flac", ".m4a", ".ogg", ".opus"):
                with self.subTest(format=suffix):
                    audio = root / f"测试音频{suffix}"
                    self._make_audio(audio)
                    before_audio = self._pcm_hash(audio)
                    write_metadata(
                        audio,
                        AudioMetadataChanges(
                            title="中文歌名", artist="日本語歌手", album="English Album",
                            lyrics_path=lrc, cover_path=cover,
                        ),
                    )
                    state = read_metadata(audio)
                    self.assertEqual((state.title, state.artist, state.album), ("中文歌名", "日本語歌手", "English Album"))
                    self.assertIn("中文 日本語 English", state.lyrics)
                    self.assertTrue(state.has_cover)
                    self.assertEqual(state.cover_mime, "image/png")
                    self.assertEqual(self._pcm_hash(audio), before_audio)

    def test_changing_title_preserves_lyrics_and_cover_for_non_mp3_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lrc = root / "a.lrc"; lrc.write_text("[00:00.00]歌词\n", encoding="utf-8")
            cover = root / "a.jpg"; Image.new("RGB", (20, 20), "blue").save(cover)
            for suffix in (".flac", ".m4a", ".ogg", ".opus"):
                with self.subTest(format=suffix):
                    audio = root / f"preserve{suffix}"; self._make_audio(audio)
                    write_metadata(audio, AudioMetadataChanges(title="旧", lyrics_path=lrc, cover_path=cover))
                    original = read_metadata(audio)
                    write_metadata(audio, AudioMetadataChanges(title="新"))
                    saved = read_metadata(audio)
                    self.assertEqual(saved.title, "新")
                    self.assertEqual(saved.lyrics, original.lyrics)
                    self.assertEqual(saved.cover_data, original.cover_data)

    def test_save_as_keeps_source_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "源文件.flac"; self._make_audio(source)
            before = source.read_bytes(); destination = root / "另存为.flac"
            write_metadata(source, AudioMetadataChanges(title="新标题"), destination)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(read_metadata(destination).title, "新标题")

    def test_removing_lyrics_or_cover_preserves_the_other_for_all_writable_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lrc = root / "keep.lrc"; lrc.write_text("[00:00.00]保留内容\n", encoding="utf-8")
            cover = root / "keep.png"; Image.new("RGB", (16, 16), "green").save(cover)
            for suffix in (".mp3", ".flac", ".m4a", ".ogg", ".opus"):
                with self.subTest(format=suffix):
                    audio = root / f"remove{suffix}"; self._make_audio(audio)
                    write_metadata(audio, AudioMetadataChanges(lyrics_path=lrc, cover_path=cover))
                    write_metadata(audio, AudioMetadataChanges(remove_lyrics=True))
                    without_lyrics = read_metadata(audio)
                    self.assertFalse(without_lyrics.has_lyrics)
                    self.assertTrue(without_lyrics.has_cover)
                    write_metadata(audio, AudioMetadataChanges(lyrics_path=lrc))
                    write_metadata(audio, AudioMetadataChanges(remove_cover=True))
                    without_cover = read_metadata(audio)
                    self.assertTrue(without_cover.has_lyrics)
                    self.assertFalse(without_cover.has_cover)

    def test_wav_is_read_only_with_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wav = Path(directory) / "只读.wav"; self._make_audio(wav)
            state = read_metadata(wav)
            self.assertFalse(state.writable)
            self.assertEqual(state.info.format_label, "WAV")
            with self.assertRaisesRegex(AudioMetadataError, "仅支持读取"):
                write_metadata(wav, AudioMetadataChanges(title="不能保存"))

    def test_generic_exports_work_for_non_mp3_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); audio = root / "中文歌曲.flac"; self._make_audio(audio)
            lrc = root / "input.lrc"; lrc.write_text("[00:00.00]导出歌词\n", encoding="utf-8")
            cover = root / "input.png"; Image.new("RGB", (12, 12), "purple").save(cover)
            write_metadata(audio, AudioMetadataChanges(lyrics_path=lrc, cover_path=cover))
            output_dir = root / "output"; output_dir.mkdir()
            lyrics_output = export_metadata_lyrics(audio, output_dir)
            cover_output = export_metadata_cover(audio, output_dir)
            self.assertEqual(lyrics_output.name, "中文歌曲.lrc")
            self.assertIn("导出歌词", lyrics_output.read_text(encoding="utf-8-sig"))
            self.assertEqual(cover_output.name, "中文歌曲.png")
            self.assertGreater(cover_output.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
