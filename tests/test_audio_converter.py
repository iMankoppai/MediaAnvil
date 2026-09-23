from io import StringIO
import math
import os
from pathlib import Path
import re
import struct
import subprocess
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
    convert_wav,
    convert_wav_batch,
    find_ffmpeg,
    unique_mp3_output,
)
from core.tasks import TaskCancelled


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

    def wait(self, timeout: float | None = None) -> int:
        return self.return_code

    def terminate(self) -> None:
        self.return_code = -15

    def kill(self) -> None:
        self.return_code = -9

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

    def test_timeout_stops_ffmpeg_and_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "slow.wav"
            source.write_bytes(b"wav")
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"fake")

            def popen(command: list[str], **_kwargs: object) -> FakeProcess:
                Path(command[-1]).write_bytes(b"partial")
                return FakeProcess(command)

            with patch("sub2lrc.audio_converter._duration_seconds", return_value=None), patch(
                "sub2lrc.audio_converter.subprocess.Popen", side_effect=popen
            ):
                with self.assertRaisesRegex(AudioConversionError, "转换超时"):
                    convert_audio(
                        source, root, AudioConversionSettings("mp3"),
                        ffmpeg_path=ffmpeg, timeout_seconds=0,
                    )
            self.assertFalse((root / "slow.mp3").exists())

    def test_cancellation_stops_ffmpeg_and_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cancel.wav"
            source.write_bytes(b"wav")
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_bytes(b"fake")

            def popen(command: list[str], **_kwargs: object) -> FakeProcess:
                Path(command[-1]).write_bytes(b"partial")
                return FakeProcess(command)

            with patch("sub2lrc.audio_converter._duration_seconds", return_value=None), patch(
                "sub2lrc.audio_converter.subprocess.Popen", side_effect=popen
            ):
                with self.assertRaises(TaskCancelled):
                    convert_audio(
                        source, root, AudioConversionSettings("mp3"),
                        ffmpeg_path=ffmpeg,
                        cancel_check=lambda: (_ for _ in ()).throw(TaskCancelled()),
                    )
            self.assertFalse((root / "cancel.mp3").exists())

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


class AudioJoinPolishTests(unittest.TestCase):
    """Fade and loudness treatment, measured on real FFmpeg output.

    These use the vendored FFmpeg and read the result back with FFmpeg's own
    measurement filters, because the whole point of the feature is what the audio
    actually sounds like: a command that merely builds without error proves
    nothing about the level at the start and end of the file.
    """

    def setUp(self) -> None:
        self.ffmpeg = required_real_ffmpeg()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _tone(self, name: str, frequency: int, seconds: float, gain: float) -> Path:
        path = self.root / name
        subprocess.run(
            [str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", f"sine=frequency={frequency}:duration={seconds}", "-af", f"volume={gain}",
             "-ac", "2", "-ar", "44100", "-y", str(path)],
            check=True, capture_output=True,
        )
        return path

    def _mean_volume(self, path: Path, start: float | None = None, span: float | None = None) -> float:
        """Mean level of a slice, in dBFS, measured by FFmpeg itself."""
        command = [str(self.ffmpeg), "-hide_banner", "-nostdin"]
        if start is not None:
            command += ["-ss", str(start)]
        command += ["-i", str(path)]
        if span is not None:
            command += ["-t", str(span)]
        command += ["-af", "volumedetect", "-f", "null", "-"]
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")
        match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", result.stderr)
        self.assertIsNotNone(match, f"volumedetect produced no level for {path.name}")
        return float(match.group(1))

    def _lufs(self, path: Path, start: float | None = None, span: float | None = None) -> float:
        """Integrated loudness in LUFS, measured by FFmpeg's EBU R128 scanner."""
        command = [str(self.ffmpeg), "-hide_banner", "-nostdin"]
        if start is not None:
            command += ["-ss", str(start)]
        command += ["-i", str(path)]
        if span is not None:
            command += ["-t", str(span)]
        command += ["-af", "ebur128=peak=true", "-f", "null", "-"]
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")
        values = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", result.stderr)
        self.assertTrue(values, f"ebur128 produced no loudness for {path.name}")
        return float(values[-1])

    def test_default_polish_is_off_and_changes_nothing(self) -> None:
        from sub2lrc.audio_join import AudioPolish
        self.assertEqual(AudioPolish(), AudioPolish(fade_seconds=0.0, normalize=False))
        # A negative fade is a programming error, not a silent no-op.
        with self.assertRaises(AudioConversionError):
            AudioPolish(fade_seconds=-1.0).validate()

    def test_merge_fade_quiets_only_the_two_ends(self) -> None:
        from sub2lrc.audio_join import AudioPolish, merge_audio
        first = self._tone("fade-a.wav", 440, 4, 0.8)
        second = self._tone("fade-b.wav", 660, 4, 0.8)
        plain = self.root / "plain"; plain.mkdir()
        faded_dir = self.root / "faded"; faded_dir.mkdir()
        base = merge_audio([first, second], "wav", plain, ffmpeg_path=self.ffmpeg)
        faded = merge_audio([first, second], "wav", faded_dir, ffmpeg_path=self.ffmpeg,
                            polish=AudioPolish(fade_seconds=1.0))
        # The ends get quieter...
        self.assertLess(self._mean_volume(faded, 0.0, 0.4), self._mean_volume(base, 0.0, 0.4) - 3.0)
        self.assertLess(self._mean_volume(faded, 7.6, 0.4), self._mean_volume(base, 7.6, 0.4) - 3.0)
        # ...while the middle, including the join between the two files, is untouched.
        self.assertAlmostEqual(self._mean_volume(faded, 3.6, 0.8), self._mean_volume(base, 3.6, 0.8), delta=0.5)

    def test_merge_normalisation_levels_tracks_recorded_at_different_volumes(self) -> None:
        from sub2lrc.audio_join import AudioPolish, merge_audio
        loud = self._tone("loud.wav", 440, 10, 0.5)
        quiet = self._tone("quiet.wav", 660, 10, 0.2)
        before = abs(self._lufs(loud) - self._lufs(quiet))
        self.assertGreater(before, 5.0, "the fixture must actually differ in level")
        directory = self.root / "normalised"; directory.mkdir()
        joined = merge_audio([loud, quiet], "wav", directory, ffmpeg_path=self.ffmpeg,
                             polish=AudioPolish(normalize=True))
        after = abs(self._lufs(joined, 0.5, 8.0) - self._lufs(joined, 10.5, 8.0))
        # Normalising each input before the join must bring the two halves together.
        self.assertLess(after, 1.0, f"halves differ by {after:.1f} LU after normalisation")
        self.assertLess(after, before)

    def test_split_applies_a_fade_to_every_piece(self) -> None:
        from sub2lrc.audio_join import AudioPolish, plan_equal_parts, split_audio
        source = self._tone("splitsrc.wav", 440, 8, 0.8)
        plain_dir = self.root / "split-plain"; plain_dir.mkdir()
        faded_dir = self.root / "split-faded"; faded_dir.mkdir()
        plans = plan_equal_parts(8.0, 4)
        base = split_audio(source, plans, "wav", plain_dir, ffmpeg_path=self.ffmpeg)
        faded = split_audio(source, plans, "wav", faded_dir, ffmpeg_path=self.ffmpeg,
                            polish=AudioPolish(fade_seconds=0.5))
        self.assertEqual(len(faded), 4)
        for index, (base_piece, faded_piece) in enumerate(zip(base, faded)):
            with self.subTest(piece=index):
                # Every piece is a standalone file, so every piece fades.
                self.assertLess(self._mean_volume(faded_piece, 0.0, 0.2),
                                self._mean_volume(base_piece, 0.0, 0.2) - 2.0)
                self.assertLess(self._mean_volume(faded_piece, 1.8, 0.2),
                                self._mean_volume(base_piece, 1.8, 0.2) - 2.0)

    def test_fades_never_overlap_on_a_clip_shorter_than_the_fade(self) -> None:
        from sub2lrc.audio_join import AudioPolish, merge_audio
        # 1.0 s of audio with a 3 s fade. Without clamping, the fade-out would be
        # scheduled past the end and the tail would fade back up instead of down.
        # With clamping each fade gets half the clip, so the level must fall
        # monotonically towards the end.
        short_a = self._tone("short-a.wav", 440, 0.5, 0.8)
        short_b = self._tone("short-b.wav", 660, 0.5, 0.8)
        directory = self.root / "short"; directory.mkdir()
        joined = merge_audio([short_a, short_b], "wav", directory, ffmpeg_path=self.ffmpeg,
                             polish=AudioPolish(fade_seconds=3.0))
        self.assertGreater(joined.stat().st_size, 0)
        head = self._mean_volume(joined, 0.0, 0.1)
        middle = self._mean_volume(joined, 0.45, 0.1)
        tail = self._mean_volume(joined, 0.88, 0.1)
        # The start is faded down, the middle is untouched, the tail is quietest.
        self.assertLess(head, middle - 5.0, "the start should be faded in")
        self.assertLess(tail, middle - 5.0, "the end should be faded out")
        # The decisive check: the tail is quieter than the middle rather than
        # louder, which is what a fade scheduled past the end would produce.
        self.assertLess(tail, middle)


class GenreTagTests(unittest.TestCase):
    """Genre must round-trip through every writable format, not just MP3."""

    def setUp(self) -> None:
        self.ffmpeg = required_real_ffmpeg()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _source(self) -> Path:
        path = self.root / "tone.wav"
        subprocess.run(
            [str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=440:duration=1", "-ac", "2", "-ar", "44100", "-y", str(path)],
            check=True, capture_output=True,
        )
        return path

    def test_genre_round_trips_in_every_writable_format(self) -> None:
        from sub2lrc.audio_metadata import AudioMetadataChanges, read_metadata, write_metadata
        source = self._source()
        for output_format in ("mp3", "flac", "m4a", "ogg"):
            with self.subTest(output=output_format):
                convert_audio(source, self.root, AudioConversionSettings(output_format),
                              ffmpeg_path=self.ffmpeg)
                produced = self.root / f"tone.{output_format}"
                self.assertEqual(read_metadata(produced).genre, "", "a fresh file has no genre")
                result = write_metadata(produced, AudioMetadataChanges(genre="爵士 Jazz"))
                saved = read_metadata(result)
                self.assertEqual(saved.genre, "爵士 Jazz")

    def test_genre_write_leaves_the_other_tags_alone(self) -> None:
        from sub2lrc.audio_metadata import AudioMetadataChanges, read_metadata, write_metadata
        source = self._source()
        convert_audio(source, self.root, AudioConversionSettings("mp3"), ffmpeg_path=self.ffmpeg)
        produced = self.root / "tone.mp3"
        write_metadata(produced, AudioMetadataChanges(title="原标题", artist="原歌手", album="原专辑", year="1999"))
        result = write_metadata(produced, AudioMetadataChanges(genre="Rock"))
        saved = read_metadata(result)
        self.assertEqual(saved.genre, "Rock")
        self.assertEqual(saved.title, "原标题")
        self.assertEqual(saved.artist, "原歌手")
        self.assertEqual(saved.album, "原专辑")
        self.assertEqual(saved.year, "1999")

    def test_clearing_a_genre_removes_it(self) -> None:
        from sub2lrc.audio_metadata import AudioMetadataChanges, read_metadata, write_metadata
        source = self._source()
        convert_audio(source, self.root, AudioConversionSettings("mp3"), ffmpeg_path=self.ffmpeg)
        produced = self.root / "tone.mp3"
        write_metadata(produced, AudioMetadataChanges(genre="Pop"))
        self.assertEqual(read_metadata(produced).genre, "Pop")
        # An empty string is a deliberate removal, not "leave unchanged".
        result = write_metadata(produced, AudioMetadataChanges(genre=""))
        self.assertEqual(read_metadata(result).genre, "")

    def test_track_number_round_trips_alongside_genre(self) -> None:
        from sub2lrc.audio_metadata import AudioMetadataChanges, read_metadata, write_metadata
        source = self._source()
        for output_format in ("mp3", "flac", "m4a", "ogg"):
            with self.subTest(output=output_format):
                convert_audio(source, self.root, AudioConversionSettings(output_format),
                              ffmpeg_path=self.ffmpeg)
                produced = self.root / f"tone.{output_format}"
                result = write_metadata(produced, AudioMetadataChanges(track="7", genre="Jazz"))
                saved = read_metadata(result)
                self.assertEqual(saved.track, "7")
                self.assertEqual(saved.genre, "Jazz")


if __name__ == "__main__":
    unittest.main()
