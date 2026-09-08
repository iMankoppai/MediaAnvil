from io import StringIO
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TALB, TIT2, TPE1
from mutagen.mp3 import MP3

from sub2lrc.audio_converter import (
    AAC_BITRATES,
    FLAC_COMPRESSION_LEVELS,
    FORMAT_SPECS,
    OGG_QUALITY_LEVELS,
    AudioConversionSettings,
    AudioConversionError,
    FfmpegNotFoundError,
    build_ffmpeg_command,
    convert_audio,
    convert_audio_batch,
    convert_wav,
    convert_wav_batch,
    find_ffmpeg,
    unique_mp3_output,
)


def required_real_ffmpeg() -> Path:
    """Return the real test binary, failing rather than silently skipping."""
    configured = os.environ.get("SUB2LRC_TEST_FFMPEG")
    ffmpeg = Path(configured) if configured else Path(__file__).resolve().parents[1] / "vendor" / "ffmpeg" / "ffmpeg.exe"
    if not ffmpeg.is_file():
        raise AssertionError(f"真实 FFmpeg 测试必需文件不存在：{ffmpeg}")
    return ffmpeg


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

            def fake_convert(source: Path, *args: object, **_kwargs: object) -> Path:
                report = args[2]
                report(100.0)
                if source == first:
                    raise AudioConversionError("测试失败")
                output = root / "second.mp3"
                output.write_bytes(b"mp3")
                return output

            def report(path: Path, _index: int, _total: int, _file: float, overall: float) -> None:
                calls.append((path, overall))

            with patch("sub2lrc.audio_converter.convert_audio", side_effect=fake_convert):
                result = convert_wav_batch((first, second), root, 192, report, ffmpeg)

            self.assertEqual(result.outputs, (root / "second.mp3",))
            self.assertEqual(len(result.failures), 1)
            self.assertEqual(result.failures[0].source, first)
            self.assertTrue(calls)

    def test_all_formats_use_one_central_command_builder(self) -> None:
        source = Path("输入.mp3")
        expected = {
            "mp3": ("libmp3lame", "-b:a", "192k"),
            "wav": ("pcm_s16le", None, None),
            "flac": ("flac", "-compression_level", "5"),
            "m4a": ("aac", "-b:a", "192k"),
            "aac": ("aac", "-b:a", "192k"),
            "ogg": ("libvorbis", "-q:a", "5"),
        }
        for format_key, (codec, option, value) in expected.items():
            with self.subTest(format=format_key):
                settings = AudioConversionSettings(format_key)
                command = build_ffmpeg_command("ffmpeg.exe", source, Path(f"输出.{format_key}"), settings)
                self.assertIn(codec, command)
                self.assertIn("-map_metadata", command)
                if option:
                    index = command.index(option)
                    self.assertEqual(command[index + 1], value)
                else:
                    self.assertNotIn("-b:a", command)
                    self.assertNotIn("-q:a", command)
                    self.assertNotIn("-compression_level", command)

    def test_format_parameter_options_and_sample_channel_controls(self) -> None:
        self.assertEqual(FORMAT_SPECS["mp3"].parameter_options, (128, 192, 256, 320))
        self.assertEqual(FORMAT_SPECS["m4a"].parameter_options, AAC_BITRATES)
        self.assertEqual(FORMAT_SPECS["aac"].parameter_options, AAC_BITRATES)
        self.assertEqual(FORMAT_SPECS["flac"].parameter_options, FLAC_COMPRESSION_LEVELS)
        self.assertEqual(FORMAT_SPECS["ogg"].parameter_options, OGG_QUALITY_LEVELS)
        command = build_ffmpeg_command(
            "ffmpeg.exe",
            "input.wav",
            "output.mp3",
            AudioConversionSettings("mp3", 256, sample_rate=48_000, channels=2),
        )
        self.assertEqual(command[command.index("-ar") + 1], "48000")
        self.assertEqual(command[command.index("-ac") + 1], "2")

    def test_metadata_copy_can_be_disabled_without_changing_encoding_options(self) -> None:
        command = build_ffmpeg_command(
            "ffmpeg.exe", "input.wav", "output.mp3",
            AudioConversionSettings("mp3", 192, preserve_metadata=False),
        )
        self.assertNotIn("-map_metadata", command)
        self.assertIn("-codec:a", command)

    def test_rejects_same_input_and_output_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "same.flac"
            source.write_bytes(b"fake")
            with self.assertRaisesRegex(AudioConversionError, "不能与源文件格式相同"):
                convert_audio(source, root, AudioConversionSettings("flac"))

    def test_real_ffmpeg_converts_chinese_wav_at_all_supported_bitrates(self) -> None:
        ffmpeg = required_real_ffmpeg()
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

    def test_real_ffmpeg_converts_every_supported_input_and_output_format(self) -> None:
        ffmpeg = required_real_ffmpeg()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "中文 通用输入.wav"
            sample_rate = 44_100
            samples = b"".join(
                struct.pack("<h", int(10_000 * math.sin(2 * math.pi * 330 * index / sample_rate)))
                for index in range(sample_rate)
            )
            with wave.open(str(source), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(sample_rate)
                output.writeframes(samples)

            converted: dict[str, Path] = {}
            for output_format in ("mp3", "flac", "m4a", "aac", "ogg"):
                with self.subTest(output=output_format):
                    path = convert_audio(source, root, AudioConversionSettings(output_format), ffmpeg_path=ffmpeg)
                    media = MutagenFile(path)
                    self.assertIsNotNone(media)
                    self.assertGreater(path.stat().st_size, 0)
                    self.assertAlmostEqual(media.info.length, 1.0, delta=0.15)
                    self.assertEqual(media.info.sample_rate, sample_rate)
                    self.assertEqual(media.info.channels, 1)
                    converted[output_format] = path

            decoded = root / "decoded"
            decoded.mkdir()
            for input_format, path in converted.items():
                with self.subTest(input=input_format):
                    wav_output = convert_audio(path, decoded, AudioConversionSettings("wav"), ffmpeg_path=ffmpeg)
                    with wave.open(str(wav_output), "rb") as decoded_wave:
                        self.assertEqual(decoded_wave.getframerate(), sample_rate)
                        self.assertEqual(decoded_wave.getnchannels(), 1)

            tagged_mp3 = converted["mp3"]
            tags = ID3()
            tags.add(TIT2(encoding=3, text=["中文标题"]))
            tags.add(TPE1(encoding=3, text=["日本語歌手"]))
            tags.add(TALB(encoding=3, text=["English Album"]))
            tags.save(tagged_mp3, v2_version=3)
            metadata_output = root / "metadata"
            metadata_output.mkdir()
            flac = convert_audio(tagged_mp3, metadata_output, AudioConversionSettings("flac"), ffmpeg_path=ffmpeg)
            metadata = MutagenFile(flac, easy=True)
            self.assertEqual(metadata["title"], ["中文标题"])
            self.assertEqual(metadata["artist"], ["日本語歌手"])
            self.assertEqual(metadata["album"], ["English Album"])


if __name__ == "__main__":
    unittest.main()
