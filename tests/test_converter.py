from pathlib import Path
import tempfile
import unittest

from sub2lrc.converter import (
    SubtitleCue,
    SubtitleError,
    convert_file,
    convert_text,
    parse_subtitle,
    read_subtitle,
    shift_cues,
    shift_lrc,
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

    def test_shift_lrc_moves_every_timestamp(self) -> None:
        source = "[00:01.00]第一句\n[00:05.50]第二句\n"
        self.assertEqual(shift_lrc(source, 2.0), "[00:03.00]第一句\n[00:07.50]第二句\n")
        self.assertEqual(shift_lrc(source, -0.5), "[00:00.50]第一句\n[00:05.00]第二句\n")

    def test_shift_lrc_keeps_metadata_and_layout(self) -> None:
        """Parsing drops [ti:]/[ar:], so a shift must rewrite text in place."""
        source = "[ti:我的歌]\n[ar:歌手]\n[00:01.00]第一句\n\n[00:10.00]第二句\n"
        shifted = shift_lrc(source, 1.0)
        self.assertIn("[ti:我的歌]", shifted)
        self.assertIn("[ar:歌手]", shifted)
        self.assertIn("\n\n", shifted)
        self.assertEqual(shifted.count("\n"), source.count("\n"))
        self.assertEqual(shift_lrc(source, 0), source)

    def test_shift_lrc_clamps_instead_of_producing_negative_times(self) -> None:
        shifted = shift_lrc("[00:01.00]早\n[00:09.00]晚\n", -5.0)
        self.assertEqual(shifted, "[00:00.00]早\n[00:04.00]晚\n")
        self.assertNotIn("[-", shifted)

    def test_shift_lrc_round_trips(self) -> None:
        source = "[00:01.00]一\n[00:02.50]二\n[00:03.25]三\n"
        self.assertEqual(shift_lrc(shift_lrc(source, 7.5), -7.5), source)

    def test_shift_lrc_handles_multiple_stamps_and_milliseconds(self) -> None:
        source = "[00:01.00][00:02.000]重复行\n"
        shifted = shift_lrc(source, 1.0)
        self.assertEqual(shifted, "[00:02.00][00:03.00]重复行\n")

    def test_shift_cues_never_lets_an_end_precede_its_start(self) -> None:
        cues = [SubtitleCue(1.0, "a", 3.0), SubtitleCue(10.0, "b", None)]
        shifted = shift_cues(cues, -5.0)
        self.assertEqual([(c.start_seconds, c.end_seconds) for c in shifted], [(0.0, 0.0), (5.0, None)])
        self.assertEqual(shift_cues(cues, 0), cues)

    def test_output_name_still_avoids_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "歌曲.lrc"
            existing.touch()
            self.assertEqual(unique_output_path(directory, "歌曲.wav.vtt").name, "歌曲_1.lrc")


if __name__ == "__main__":
    unittest.main()
