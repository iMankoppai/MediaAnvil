from pathlib import Path
import tempfile
import unittest

from sub2lrc.converter import (
    SubtitleError,
    convert_file,
    convert_text,
    parse_subtitle,
    read_subtitle,
    unique_output_path,
)


class ConverterTests(unittest.TestCase):
    def test_srt_multiline_and_chinese(self) -> None:
        source = """1
00:00:01,230 --> 00:00:03,000
你好
世界

2
01:02:03,999 --> 01:02:05,000
结束
"""
        self.assertEqual(convert_text(source), "[00:01.23]你好\n[00:01.23]世界\n[62:04.00]结束\n")

    def test_vtt_tags_settings_and_short_timestamp(self) -> None:
        source = """WEBVTT

cue-id
00:02.500 --> 00:04.000 position:10%
<v 小明>中文 & English</v>
"""
        self.assertEqual(convert_text(source), "[00:02.50]中文 & English\n")

    def test_multiline_preserves_each_original_line(self) -> None:
        source = """WEBVTT

00:00:05.000 --> 00:00:08.000
第一行
第二行
第三行
"""
        self.assertEqual(
            convert_text(source),
            "[00:05.00]第一行\n[00:05.00]第二行\n[00:05.00]第三行\n",
        )

    def test_invalid_file(self) -> None:
        with self.assertRaises(SubtitleError):
            parse_subtitle("这不是字幕")

    def test_output_is_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "中文.srt"
            output = Path(directory) / "中文.lrc"
            source.write_text("1\n00:00:01,000 --> 00:00:02,000\n歌词\n", encoding="utf-8")
            convert_file(source, output)
            raw = output.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            self.assertIn("歌词", raw.decode("utf-8-sig"))

    def test_reads_gb18030_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "旧编码.srt"
            content = "1\n00:00:01,000 --> 00:00:02,000\n中文歌词\n"
            source.write_bytes(content.encode("gb18030"))
            self.assertEqual(read_subtitle(source), content)

    def test_output_name_removes_audio_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(unique_output_path(directory, "歌曲.wav.vtt").name, "歌曲.lrc")
            self.assertEqual(unique_output_path(directory, "歌曲.MP3.srt").name, "歌曲.lrc")
            self.assertEqual(unique_output_path(directory, "歌曲.flac.vtt").name, "歌曲.lrc")
            self.assertEqual(unique_output_path(directory, "歌曲.srt").name, "歌曲.lrc")

    def test_output_name_still_avoids_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "歌曲.lrc"
            existing.touch()
            self.assertEqual(unique_output_path(directory, "歌曲.wav.vtt").name, "歌曲_1.lrc")


if __name__ == "__main__":
    unittest.main()
