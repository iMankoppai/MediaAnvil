"""WAV to MP3 conversion through an installed FFmpeg executable."""

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
ProgressCallback = Callable[[Path, int, int, float, float], None]


class AudioConversionError(ValueError):
    """Raised when WAV to MP3 conversion cannot be completed."""


class FfmpegNotFoundError(AudioConversionError):
    """Raised when no usable FFmpeg executable can be found."""


@dataclass(frozen=True)
class ConversionFailure:
    source: Path
    message: str


@dataclass(frozen=True)
class BatchConversionResult:
    outputs: tuple[Path, ...]
    failures: tuple[ConversionFailure, ...]


def find_ffmpeg(explicit: str | Path | None = None) -> Path:
    """Find FFmpeg beside the app, in the source folder, or on PATH."""
    if explicit is not None:
        candidate = Path(explicit)
        if candidate.is_file():
            return candidate
        raise FfmpegNotFoundError(f"找不到指定的 FFmpeg：{candidate}")

    names = ("ffmpeg.exe", "ffmpeg") if os.name == "nt" else ("ffmpeg", "ffmpeg.exe")
    bundled_folder = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    folders = (
        bundled_folder,
        Path(sys.executable).resolve().parent,
        Path(__file__).resolve().parent.parent,
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
        "没有找到 FFmpeg。请安装 FFmpeg 并加入系统 PATH，"
        "或者把 ffmpeg.exe 放在 Sub2LRC.exe 同一目录后重试。"
    )


def unique_mp3_output(output_dir: str | Path, source: str | Path) -> Path:
    """Return a same-stem MP3 path without overwriting an existing output."""
    directory = Path(output_dir)
    source_path = Path(source)
    candidate = directory / f"{source_path.stem}.mp3"
    index = 1
    while candidate.exists():
        candidate = directory / f"{source_path.stem}_{index}.mp3"
        index += 1
    return candidate


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _duration_seconds(ffmpeg: Path, source: Path) -> float | None:
    """Read the duration from FFmpeg's input summary without decoding the file."""
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


def convert_wav(
    source: str | Path,
    output_dir: str | Path,
    bitrate: int = 192,
    progress: Callable[[float], None] | None = None,
    ffmpeg_path: str | Path | None = None,
) -> Path:
    """Convert one WAV file to MP3 and report progress from 0 through 100."""
    source_path = Path(source)
    directory = Path(output_dir)
    if source_path.suffix.lower() != ".wav":
        raise AudioConversionError("请选择扩展名为 .wav 的音频文件。")
    if not source_path.is_file():
        raise AudioConversionError("WAV 文件不存在或无法访问。")
    if bitrate not in SUPPORTED_BITRATES:
        raise AudioConversionError("MP3 比特率只能选择 128、192、256 或 320 kbps。")
    if not directory.is_dir():
        raise AudioConversionError("输出目录不存在或无法访问。")

    ffmpeg = find_ffmpeg(ffmpeg_path)
    destination = unique_mp3_output(directory, source_path)
    if destination.resolve() == source_path.resolve():
        raise AudioConversionError("输出文件不能覆盖源 WAV 文件。")
    duration = _duration_seconds(ffmpeg, source_path)
    command = [
        str(ffmpeg),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        f"{bitrate}k",
        "-n",
        "-progress",
        "pipe:1",
        "-nostats",
        str(destination),
    ]
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
        raise AudioConversionError("转换失败：FFmpeg 没有生成有效的 MP3 文件。")
    if progress:
        progress(100.0)
    return destination


def convert_wav_batch(
    sources: Iterable[str | Path],
    output_dir: str | Path,
    bitrate: int = 192,
    progress: ProgressCallback | None = None,
    ffmpeg_path: str | Path | None = None,
) -> BatchConversionResult:
    """Convert every WAV, continue after individual failures, and return a summary."""
    source_paths = tuple(Path(source) for source in sources)
    if not source_paths:
        raise AudioConversionError("请至少选择一个 WAV 文件。")
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
            outputs.append(convert_wav(source, output_dir, bitrate, report, ffmpeg))
        except AudioConversionError as exc:
            failures.append(ConversionFailure(source, str(exc)))
            report(100.0)
    return BatchConversionResult(tuple(outputs), tuple(failures))
