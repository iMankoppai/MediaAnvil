from pathlib import Path
import tempfile
import unittest

from sub2lrc.converter import (
    SubtitleError,
    convert_content,
    convert_file,
    detect_format,
    parse_text,
    unique_output_path,
)


SRT = """1
00:00:01,250 --> 00:00:03,500
第一行
Second line!

2
00:00:06,000 --> 00:00:08,000
结束～ & emoji 😀
"""

VTT = """WEBVTT

00:00:01.250 --> 00:00:03.500
第一行
Second line!

00:00:06.000 --> 00:00:08.000
结束～ & emoji 😀
"""

LRC = """[ar:测试歌手]
[00:01.25]第一行
[00:01.25]Second line!
[00:06.00]结束～ & emoji 😀
"""


class SubtitleFormatConversionTests(unittest.TestCase):
    def test_srt_to_lrc_preserves_established_output(self) -> None:
        self.assertEqual(
            convert_content(SRT, "srt", "lrc"),
            "[00:01.25]第一行\n[00:01.25]Second line!\n[00:06.00]结束～ & emoji 😀\n",
        )

    def test_vtt_to_lrc_preserves_established_output(self) -> None:
        self.assertEqual(
            convert_content(VTT, "vtt", "lrc"),
            "[00:01.25]第一行\n[00:01.25]Second line!\n[00:06.00]结束～ & emoji 😀\n",
        )

    def test_lrc_to_srt_uses_next_start_and_configurable_final_duration(self) -> None:
        output = convert_content(LRC, "lrc", "srt", final_duration=2.5)
        self.assertIn("00:00:01,250 --> 00:00:06,000\n第一行\nSecond line!", output)
        self.assertIn("00:00:06,000 --> 00:00:08,500\n结束～ & emoji 😀", output)

    def test_lrc_to_vtt_uses_next_start_and_default_final_duration(self) -> None:
        output = convert_content(LRC, "lrc", "vtt")
        self.assertTrue(output.startswith("WEBVTT\n\n"))
        self.assertIn("00:00:01.250 --> 00:00:06.000", output)
        self.assertIn("00:00:06.000 --> 00:00:11.000", output)

    def test_srt_to_vtt_keeps_explicit_end_times_and_multiline_text(self) -> None:
        output = convert_content(SRT, "srt", "vtt")
        self.assertIn("00:00:01.250 --> 00:00:03.500\n第一行\nSecond line!", output)
        self.assertIn("00:00:06.000 --> 00:00:08.000", output)

    def test_vtt_to_srt_keeps_explicit_end_times_and_multiline_text(self) -> None:
        output = convert_content(VTT, "vtt", "srt")
        self.assertIn("1\n00:00:01,250 --> 00:00:03,500\n第一行\nSecond line!", output)
        self.assertIn("2\n00:00:06,000 --> 00:00:08,000", output)

    def test_all_nine_input_output_combinations_parse_successfully(self) -> None:
        samples = {"lrc": LRC, "srt": SRT, "vtt": VTT}
        for input_format, content in samples.items():
            for output_format in samples:
                with self.subTest(input=input_format, output=output_format):
                    output = convert_content(content, input_format, output_format)
                    self.assertTrue(parse_text(output, output_format))

    def test_detects_format_by_extension_case_insensitively_and_content_fallback(self) -> None:
        self.assertEqual(detect_format("歌词.LRC"), "lrc")
        self.assertEqual(detect_format("字幕.SRT"), "srt")
        self.assertEqual(detect_format("字幕.VTT"), "vtt")
        self.assertEqual(detect_format("未知.txt", VTT), "vtt")
        self.assertEqual(detect_format("未知.txt", LRC), "lrc")

    def test_file_conversion_auto_detects_and_writes_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "中文 歌词.lrc"
            output = Path(directory) / "中文 歌词.srt"
            source.write_text(LRC, encoding="utf-8")
            convert_file(source, output, "srt", final_duration=3)
            raw = output.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            self.assertIn("结束～ & emoji 😀", raw.decode("utf-8-sig"))

    def test_does_not_overwrite_input_without_explicit_choice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "歌词.lrc"
            source.write_text(LRC, encoding="utf-8")
            with self.assertRaisesRegex(SubtitleError, "不能覆盖"):
                convert_file(source, source, "lrc")
            convert_file(source, source, "lrc", overwrite=True)
            self.assertTrue(parse_text(source.read_text(encoding="utf-8-sig"), "lrc"))

    def test_same_format_output_gets_a_new_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "歌词.lrc"
            source.write_text(LRC, encoding="utf-8")
            self.assertEqual(unique_output_path(directory, source, "lrc").name, "歌词_1.lrc")

    def test_invalid_final_duration_is_rejected(self) -> None:
        with self.assertRaises(SubtitleError):
            convert_content(LRC, "lrc", "srt", final_duration=0)

    def test_empty_lrc_lyric_line_is_not_silently_removed(self) -> None:
        self.assertEqual(convert_content("[00:01.00]\n", "lrc", "lrc"), "[00:01.00]\n")


if __name__ == "__main__":
    unittest.main()
