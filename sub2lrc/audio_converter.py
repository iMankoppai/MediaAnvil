"""Generic audio format conversion through one centralized FFmpeg wrapper."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Callable, Iterable


SUPPORTED_BITRATES = (128, 192, 256, 320)
AAC_BITRATES = (96, 128, 192, 256)
FLAC_COMPRESSION_LEVELS = (0, 5, 8)
OGG_QUALITY_LEVELS = (3, 5, 7, 9)
SUPPORTED_SAMPLE_RATES = (44_100, 48_000, 96_000)
SUPPORTED_CHANNELS = (1, 2)
ProgressCallback = Callable[[Path, int, int, float, float], None]


class AudioConversionError(ValueError):
    """Raised when an audio conversion cannot be completed."""


class FfmpegNotFoundError(AudioConversionError):
    """Raised when no usable FFmpeg executable can be found."""


@dataclass(frozen=True)
class FormatSpec:
    key: str
    label: str
    extension: str
    codec: str
    parameter_label: str | None
    parameter_options: tuple[int, ...]
    default_parameter: int | None


FORMAT_SPECS: dict[str, FormatSpec] = {
    "mp3": FormatSpec("mp3", "MP3", ".mp3", "libmp3lame", "比特率", SUPPORTED_BITRATES, 192),
    "wav": FormatSpec("wav", "WAV", ".wav", "pcm_s16le", None, (), None),
    "flac": FormatSpec("flac", "FLAC", ".flac", "flac", "压缩等级", FLAC_COMPRESSION_LEVELS, 5),
    "m4a": FormatSpec("m4a", "M4A（AAC）", ".m4a", "aac", "比特率", AAC_BITRATES, 192),
    "aac": FormatSpec("aac", "AAC", ".aac", "aac", "比特率", AAC_BITRATES, 192),
    "ogg": FormatSpec("ogg", "OGG Vorbis", ".ogg", "libvorbis", "质量等级", OGG_QUALITY_LEVELS, 5),
}
SUPPORTED_INPUT_EXTENSIONS = frozenset(spec.extension for spec in FORMAT_SPECS.values())


@dataclass(frozen=True)
class AudioConversionSettings:
    output_format: str = "mp3"
    parameter: int | None = None
    sample_rate: int | None = None
    channels: int | None = None

    @property
    def format_spec(self) -> FormatSpec:
        try:
            return FORMAT_SPECS[self.output_format]
        except KeyError as exc:
            raise AudioConversionError("不支持所选的输出格式。") from exc

    @property
    def resolved_parameter(self) -> int | None:
        return self.format_spec.default_parameter if self.parameter is None else self.parameter

    def validate(self) -> None:
        spec = self.format_spec
        parameter = self.resolved_parameter
        if spec.parameter_options and parameter not in spec.parameter_options:
            choices = "、".join(str(value) for value in spec.parameter_options)
            raise AudioConversionError(f"{spec.label} 的{spec.parameter_label}只能选择 {choices}。")
        if not spec.parameter_options and parameter is not None:
            raise AudioConversionError(f"{spec.label} 不需要额外的编码参数。")
        if self.sample_rate is not None and self.sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise AudioConversionError("采样率只能保持原始值，或选择 44100、48000、96000 Hz。")
        if self.channels is not None and self.channels not in SUPPORTED_CHANNELS:
            raise AudioConversionError("声道只能保持原始值，或选择单声道、立体声。")


@dataclass(frozen=True)
class ConversionFailure:
    source: Path
    message: str


@dataclass(frozen=True)
class BatchConversionResult:
    outputs: tuple[Path, ...]
    failures: tuple[ConversionFailure, ...]


def find_ffmpeg(explicit: str | Path | None = None) -> Path:
    """Find FFmpeg in the packaged app, beside it, in source, or on PATH."""
    if explicit is not None:
        candidate = Path(explicit)
        if candidate.is_file():
            return candidate
        raise FfmpegNotFoundError(f"找不到指定的 FFmpeg：{candidate}")
    names = ("ffmpeg.exe", "ffmpeg") if os.name == "nt" else ("ffmpeg", "ffmpeg.exe")
    bundled_folder = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    project_folder = Path(__file__).resolve().parent.parent
    folders = (
        bundled_folder,
        Path(sys.executable).resolve().parent,
        project_folder / "vendor" / "ffmpeg",
        project_folder,
    )
    for folder in folders:
        for name in names:
            candidate = folder / name
            if candidate.is_file():
                return candidate
    located = shutil.which("ffmpeg")
    if located:
        return Path(located)
    raise FfmpegNotFoundError(
        "没有找到 FFmpeg。请使用包含内置 FFmpeg 的正式版 MediaAnvil，"
        "或把 ffmpeg.exe 放在程序同一目录。"
    )


def source_format(path: str | Path) -> str:
    extension = Path(path).suffix.lower()
    for key, spec in FORMAT_SPECS.items():
        if spec.extension == extension:
            return key
    supported = "、".join(spec.label for spec in FORMAT_SPECS.values())
    raise AudioConversionError(f"不支持该输入格式。请选择 {supported} 文件。")


def unique_audio_output(output_dir: str | Path, source: str | Path, output_format: str) -> Path:
    """Return a same-stem output path without overwriting an existing file."""
    try:
        extension = FORMAT_SPECS[output_format].extension
    except KeyError as exc:
        raise AudioConversionError("不支持所选的输出格式。") from exc
    directory = Path(output_dir)
    source_path = Path(source)
    candidate = directory / f"{source_path.stem}{extension}"
    index = 1
    while candidate.exists():
        candidate = directory / f"{source_path.stem}_{index}{extension}"
        index += 1
    return candidate


def unique_mp3_output(output_dir: str | Path, source: str | Path) -> Path:
    """Backward-compatible MP3 output helper."""
    return unique_audio_output(output_dir, source, "mp3")


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _duration_seconds(ffmpeg: Path, source: Path) -> float | None:
    try:
        result = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-i", str(source)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _progress_seconds(line: str) -> float | None:
    key, separator, value = line.strip().partition("=")
    if not separator:
        return None
    try:
        if key in {"out_time_us", "out_time_ms"}:
            return int(value) / 1_000_000
        if key == "out_time":
            hours, minutes, seconds = value.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (ValueError, TypeError):
        return None
    return None


def build_ffmpeg_command(
    ffmpeg: str | Path,
    source: str | Path,
    destination: str | Path,
    settings: AudioConversionSettings,
) -> list[str]:
    """Build every format's FFmpeg command in one centralized function."""
    settings.validate()
    spec = settings.format_spec
    command = [
        str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-map", "0:a:0", "-map_metadata", "0", "-vn",
        "-codec:a", spec.codec,
    ]
    parameter = settings.resolved_parameter
    if spec.key in {"mp3", "m4a", "aac"}:
        command.extend(("-b:a", f"{parameter}k"))
    elif spec.key == "flac":
        command.extend(("-compression_level", str(parameter)))
    elif spec.key == "ogg":
        command.extend(("-q:a", str(parameter)))
    if settings.sample_rate is not None:
        command.extend(("-ar", str(settings.sample_rate)))
    if settings.channels is not None:
        command.extend(("-ac", str(settings.channels)))
    if spec.key == "mp3":
        command.extend(("-id3v2_version", "3"))
    command.extend(("-n", "-progress", "pipe:1", "-nostats", str(destination)))
    return command


def convert_audio(
    source: str | Path,
    output_dir: str | Path,
    settings: AudioConversionSettings,
    progress: Callable[[float], None] | None = None,
    ffmpeg_path: str | Path | None = None,
) -> Path:
    """Convert one supported audio file using the selected output settings."""
    source_path = Path(source)
    directory = Path(output_dir)
    input_format = source_format(source_path)
    settings.validate()
    if not source_path.is_file():
        raise AudioConversionError("输入音频文件不存在或无法访问。")
    if not directory.is_dir():
        raise AudioConversionError("输出目录不存在或无法访问。")
    if input_format == settings.output_format:
        raise AudioConversionError("输出格式不能与源文件格式相同。")
    ffmpeg = find_ffmpeg(ffmpeg_path)
    destination = unique_audio_output(directory, source_path, settings.output_format)
    duration = _duration_seconds(ffmpeg, source_path)
    command = build_ffmpeg_command(ffmpeg, source_path, destination, settings)
    if progress:
        progress(0.0)
    try:
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
        ) as process:
            if process.stdout is None or process.stderr is None:
                raise OSError("无法读取 FFmpeg 进程输出。")
            for line in process.stdout:
                elapsed = _progress_seconds(line)
                if elapsed is not None and duration and progress:
                    progress(min(99.0, max(0.0, elapsed / duration * 100)))
            error_text = process.stderr.read().strip()
            return_code = process.wait()
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise AudioConversionError(f"无法启动 FFmpeg：{exc}") from exc
    if return_code != 0:
        destination.unlink(missing_ok=True)
        reason = error_text or f"FFmpeg 返回错误代码 {return_code}。"
        raise AudioConversionError(f"转换失败：{reason}")
    if not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise AudioConversionError("转换失败：FFmpeg 没有生成有效的音频文件。")
    if progress:
        progress(100.0)
    return destination


def convert_audio_batch(
    sources: Iterable[str | Path],
    output_dir: str | Path,
    settings: AudioConversionSettings,
    progress: ProgressCallback | None = None,
    ffmpeg_path: str | Path | None = None,
) -> BatchConversionResult:
    """Convert a batch and continue after each individual failure."""
    source_paths = tuple(Path(source) for source in sources)
    if not source_paths:
        raise AudioConversionError("请至少选择一个音频文件。")
    settings.validate()
    ffmpeg = find_ffmpeg(ffmpeg_path)
    outputs: list[Path] = []
    failures: list[ConversionFailure] = []
    total = len(source_paths)
    for index, source in enumerate(source_paths, start=1):
        def report(file_percent: float, *, current: Path = source, number: int = index) -> None:
            overall = ((number - 1) + file_percent / 100) / total * 100
            if progress:
                progress(current, number, total, file_percent, overall)
        try:
            outputs.append(convert_audio(source, output_dir, settings, report, ffmpeg))
        except AudioConversionError as exc:
            failures.append(ConversionFailure(source, str(exc)))
            report(100.0)
    return BatchConversionResult(tuple(outputs), tuple(failures))


def convert_wav(
    source: str | Path,
    output_dir: str | Path,
    bitrate: int = 192,
    progress: Callable[[float], None] | None = None,
    ffmpeg_path: str | Path | None = None,
) -> Path:
    """Backward-compatible WAV to MP3 wrapper."""
    if Path(source).suffix.lower() != ".wav":
        raise AudioConversionError("请选择扩展名为 .wav 的音频文件。")
    return convert_audio(source, output_dir, AudioConversionSettings("mp3", bitrate), progress, ffmpeg_path)


def convert_wav_batch(
    sources: Iterable[str | Path],
    output_dir: str | Path,
    bitrate: int = 192,
    progress: ProgressCallback | None = None,
    ffmpeg_path: str | Path | None = None,
) -> BatchConversionResult:
    """Backward-compatible WAV batch wrapper."""
    return convert_audio_batch(sources, output_dir, AudioConversionSettings("mp3", bitrate), progress, ffmpeg_path)
