from io import StringIO
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from mutagen.mp3 import MP3

from sub2lrc.audio_converter import (
    AudioConversionError,
    FfmpegNotFoundError,
    convert_wav,
    convert_wav_batch,
    find_ffmpeg,
    unique_mp3_output,
)


class FakeProcess:
    def __init__(self, command: list[str], return_code: int = 0, error: str = "") -> None:
        self.command = command
        self.return_code = return_code
        self.stdout = StringIO("out_time_us=5000000\nprogress=continue\nout_time_us=10000000\nprogress=end\n")
        self.stderr = StringIO(error)
        if return_code == 0:
            Path(command[-1]).write_bytes(b"ID3 fake mp3")

    def wait(self) -> int:
        return self.return_code

    def __enter__(self) -> "FakeProcess":
        return self

    def __exit__(self, *_args: object) -> None:
        self.stdout.close()
        self.stderr.close()


class AudioConverterTests(unittest.TestCase):
    def test_missing_ffmpeg_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FfmpegNotFoundError, "找不到指定的 FFmpeg"):
                find_ffmpeg(Path(directory) / "missing-ffmpeg.exe")

    def test_finds_ffmpeg_extracted_from_packaged_application(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundled = Path(directory) / "ffmpeg.exe"
            bundled.write_bytes(b"bundled ffmpeg")
            with patch("sub2lrc.audio_converter.sys._MEIPASS", directory, create=True):
                self.assertEqual(find_ffmpeg(), bundled)

    def test_output_keeps_name_and_avoids_existing_mp3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "中文 音频.wav"
            source.write_bytes(b"wav")
            self.assertEqual(unique_mp3_output(root, source), root / "中文 音频.mp3")
            (root / "中文 音频.mp3").write_bytes(b"existing")
            self.assertEqual(unique_mp3_output(root, source), root / "中文 音频_1.mp3")

    def test_conversion_uses_ffmpeg_bitrate_chinese_paths_and_reports_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "中文 输入.wav"
            source.write_bytes(b"RIFF test")
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"fake")
            progress: list[float] = []
            commands: list[list[str]] = []

            def popen(command: list[str], **_kwargs: object) -> FakeProcess:
                commands.append(command)
                return FakeProcess(command)

            with patch("sub2lrc.audio_converter._duration_seconds", return_value=10.0), patch(
                "sub2lrc.audio_converter.subprocess.Popen", side_effect=popen
            ):
                output = convert_wav(source, root, 256, progress.append, ffmpeg)

            self.assertEqual(output, root / "中文 输入.mp3")
            self.assertEqual(progress, [0.0, 50.0, 99.0, 100.0])
            self.assertIn(str(source), commands[0])
            self.assertIn("256k", commands[0])
            self.assertIn("libmp3lame", commands[0])
            self.assertEqual(commands[0][-1], str(output))

    def test_ffmpeg_failure_removes_partial_file_and_reports_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.wav"
            source.write_bytes(b"broken")
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"fake")

            def popen(command: list[str], **_kwargs: object) -> FakeProcess:
                Path(command[-1]).write_bytes(b"partial")
                return FakeProcess(command, 1, "Invalid data found when processing input")

            with patch("sub2lrc.audio_converter._duration_seconds", return_value=None), patch(
                "sub2lrc.audio_converter.subprocess.Popen", side_effect=popen
            ):
                with self.assertRaisesRegex(AudioConversionError, "Invalid data found"):
                    convert_wav(source, root, 192, ffmpeg_path=ffmpeg)
            self.assertFalse((root / "broken.mp3").exists())

    def test_validates_wav_bitrate_and_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav = root / "input.wav"
            wav.write_bytes(b"wav")
            with self.assertRaisesRegex(AudioConversionError, "扩展名为 .wav"):
                convert_wav(root / "input.mp3", root)
            with self.assertRaisesRegex(AudioConversionError, "不存在"):
                convert_wav(root / "missing.wav", root)
            with self.assertRaisesRegex(AudioConversionError, "比特率"):
                convert_wav(wav, root, 160)
            with self.assertRaisesRegex(AudioConversionError, "输出目录"):
                convert_wav(wav, root / "missing", 192)

    def test_batch_continues_after_one_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.wav"
            second = root / "second.wav"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"fake")
            calls: list[tuple[Path, float]] = []

            def fake_convert(source: Path, *_args: object, **kwargs: object) -> Path:
                report = kwargs.get("progress")
                if report:
                    report(100.0)
                if source == first:
                    raise AudioConversionError("测试失败")
                output = root / "second.mp3"
                output.write_bytes(b"mp3")
                return output

            def report(path: Path, _index: int, _total: int, _file: float, overall: float) -> None:
                calls.append((path, overall))

            with patch("sub2lrc.audio_converter.convert_wav", side_effect=fake_convert):
                result = convert_wav_batch((first, second), root, 192, report, ffmpeg)

            self.assertEqual(result.outputs, (root / "second.mp3",))
            self.assertEqual(len(result.failures), 1)
            self.assertEqual(result.failures[0].source, first)
            self.assertTrue(calls)

    @unittest.skipUnless(os.environ.get("SUB2LRC_TEST_FFMPEG"), "real FFmpeg path not provided")
    def test_real_ffmpeg_converts_chinese_wav_at_all_supported_bitrates(self) -> None:
        ffmpeg = Path(os.environ["SUB2LRC_TEST_FFMPEG"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "中文 实际测试.wav"
            sample_rate = 44_100
            samples = b"".join(
                struct.pack("<h", int(12_000 * math.sin(2 * math.pi * 440 * index / sample_rate)))
                for index in range(sample_rate)
            )
            with wave.open(str(source), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(sample_rate)
                output.writeframes(samples)

            for target_bitrate in (128, 192, 256, 320):
                with self.subTest(bitrate=target_bitrate):
                    progress: list[float] = []
                    converted = convert_wav(source, root, target_bitrate, progress.append, ffmpeg)
                    info = MP3(converted).info
                    self.assertGreater(converted.stat().st_size, 0)
                    self.assertAlmostEqual(info.length, 1.0, delta=0.1)
                    self.assertAlmostEqual(info.bitrate, target_bitrate * 1000, delta=2000)
                    self.assertEqual(progress[0], 0.0)
                    self.assertEqual(progress[-1], 100.0)


if __name__ == "__main__":
    unittest.main()
