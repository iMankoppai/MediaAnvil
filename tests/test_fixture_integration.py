from pathlib import Path
import tempfile
import unittest

from sub2lrc.converter import convert_file, unique_output_path


FIXTURES = Path(__file__).parent / "fixtures"


class RealFileIntegrationTests(unittest.TestCase):
    def test_five_real_subtitle_files(self) -> None:
        expected = {
            "chinese_dialogue.wav.vtt": (
                "chinese_dialogue.lrc",
                "[00:01.25]你好，欢迎使用 Sub2LRC！\n"
                "[00:04.00]第一行保持原样。\n"
                "[00:04.00]第二行也不会被合并。\n"
                "[01:02.35]中文、数字 123，以及“引号”都应保留。\n",
            ),
            "english_song.mp3.srt": (
                "english_song.lrc",
                "[00:00.50]Hello, world!\n"
                "[00:03.13]Don't merge this line.\n"
                "[00:03.13]Keep this line separate.\n"
                "[02:11.00]Question marks? Exclamation marks! Apostrophes aren't lost.\n",
            ),
            "long_caption.flac.vtt": (
                "long_caption.lrc",
                "[10:00.01]这是一条很长的字幕，用来确认转换程序不会因为文字很多就截断内容；其中包含中文、English words、数字 2026、逗号，句号。以及各种常见字符。\n"
                "[10:00.01]This is the second original line of the same long cue, and it must remain complete and independent after conversion without being joined to the previous line.\n",
            ),
            "punctuation.srt": (
                "punctuation.lrc",
                "[62:03.46]“你好！”她问：你好吗？\n"
                "[62:09.01]括号（测试）、方括号【保留】、省略号……\n"
                "[62:14.00]A&B / C+D = E; 100% ready.\n",
            ),
            "blank_lines.vtt": (
                "blank_lines.lrc",
                "[00:05.00]空行前后的第一条字幕\n"
                "[00:08.00]空行前后的第二条字幕\n",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            for source_name, (output_name, expected_text) in expected.items():
                source = FIXTURES / source_name
                output = unique_output_path(output_dir, source)
                self.assertEqual(output.name, output_name)
                convert_file(source, output)
                self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))
                self.assertEqual(output.read_text(encoding="utf-8-sig"), expected_text)


if __name__ == "__main__":
    unittest.main()
