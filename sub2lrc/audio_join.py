"""Join several audio files into one, or cut one file into pieces.

Both operations drive the FFmpeg that already ships with MediaAnvil, and both
write to a new file: the source is never modified or deleted. Progress is
reported per output, and cancellation stops FFmpeg and removes the partial file
so an interrupted run never leaves a broken result behind.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Callable, Iterable

from core.windows_paths import sanitize_windows_stem

from .audio_converter import (
    DEFAULT_FFMPEG_TIMEOUT_SECONDS,
    FORMAT_SPECS,
    SUPPORTED_INPUT_EXTENSIONS,
    AudioConversionError,
    _creation_flags,
    _duration_seconds,
    _progress_seconds,
    _read_lines,
    _read_text,
    _stop_process,
    find_ffmpeg,
)

ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class SplitPlan:
    """One output piece: where it starts and how long it lasts."""

    start_seconds: float
    duration_seconds: float


def audio_duration(source: str | Path, ffmpeg_path: str | Path | None = None) -> float:
    """Return the duration in seconds, raising when it cannot be determined.

    Splitting by time needs this, and FFmpeg probes the file, so callers must
    run it off the GUI thread.
    """
    path = Path(source)
    if not path.is_file():
        raise AudioConversionError("输入音频文件不存在或无法访问。")
    seconds = _duration_seconds(find_ffmpeg(ffmpeg_path), path)
    if not seconds:
        raise AudioConversionError("无法读取音频时长，不能按时长分段。")
    return seconds


def plan_equal_parts(total_seconds: float, parts: int) -> tuple[SplitPlan, ...]:
    """Split a duration into ``parts`` pieces of equal length."""
    if parts < 1:
        raise AudioConversionError("分段数量必须大于 0。")
    if total_seconds <= 0:
        raise AudioConversionError("无法确定音频时长，不能按时长等分。")
    length = total_seconds / parts
    return tuple(SplitPlan(index * length, length) for index in range(parts))


def plan_fixed_length(total_seconds: float, length_seconds: float) -> tuple[SplitPlan, ...]:
    """Split a duration into pieces of at most ``length_seconds`` each."""
    if length_seconds <= 0:
        raise AudioConversionError("每段时长必须大于 0 秒。")
    if total_seconds <= 0:
        raise AudioConversionError("无法确定音频时长，不能按时长分段。")
    plans: list[SplitPlan] = []
    start = 0.0
    while start < total_seconds - 1e-6:
        plans.append(SplitPlan(start, min(length_seconds, total_seconds - start)))
        start += length_seconds
    return tuple(plans)


def _output_directory(output_dir: str | Path | None, source: Path) -> Path:
    if output_dir:
        directory = Path(output_dir)
        if not directory.is_dir():
            raise AudioConversionError("输出目录不存在或无法访问。")
        return directory
    return source.parent


def _unique(directory: Path, stem: str, extension: str) -> Path:
    candidate = directory / f"{stem}{extension}"
    index = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{index}{extension}"
        index += 1
    return candidate


def _run(command: list[str], destination: Path, expected_seconds: float | None,
         progress: ProgressCallback | None, offset: float, span: float,
         cancel_check: Callable[[], None] | None,
         process_callback: Callable[[subprocess.Popen[str] | None], None] | None,
         timeout_seconds: float) -> None:
    """Run one FFmpeg job, reporting progress inside ``offset``..``offset+span``."""
    lines: Queue[str | None] = Queue()
    errors: list[str] = []
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=_creation_flags(),
        )
    except OSError as exc:
        raise AudioConversionError(f"无法启动 FFmpeg：{exc}") from exc
    if process_callback:
        process_callback(process)
    readers = [
        Thread(target=_read_lines, args=(process.stdout, lines), daemon=True),
        Thread(target=_read_text, args=(process.stderr, errors), daemon=True),
    ]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout_seconds
    return_code: int | None = None
    try:
        while return_code is None:
            if cancel_check:
                cancel_check()
            if time.monotonic() > deadline:
                _stop_process(process)
                raise AudioConversionError("处理超时，已停止 FFmpeg 并删除未完成文件。")
            try:
                line = lines.get(timeout=0.1)
            except Empty:
                return_code = process.poll()
                continue
            if line is None:
                return_code = process.poll()
                continue
            seconds = _progress_seconds(line)
            if seconds is not None and progress and expected_seconds:
                fraction = min(1.0, seconds / expected_seconds)
                progress(offset + fraction * span, destination.name)
    except BaseException:
        if process is not None:
            _stop_process(process)
        destination.unlink(missing_ok=True)
        raise
    finally:
        if process_callback:
            process_callback(None)
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except (OSError, ValueError):
                        pass
    return_code = process.wait() if return_code is None else return_code
    if return_code != 0:
        destination.unlink(missing_ok=True)
        reason = "".join(errors).strip() or f"FFmpeg 返回错误代码 {return_code}。"
        raise AudioConversionError(f"处理失败：{reason}")
    if not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise AudioConversionError("处理失败：FFmpeg 没有生成有效的音频文件。")


def merge_audio(sources: Iterable[str | Path], output_format: str = "mp3",
                output_dir: str | Path | None = None,
                progress: ProgressCallback | None = None,
                ffmpeg_path: str | Path | None = None,
                *, cancel_check: Callable[[], None] | None = None,
                process_callback: Callable[[subprocess.Popen[str] | None], None] | None = None,
                timeout_seconds: float = DEFAULT_FFMPEG_TIMEOUT_SECONDS) -> Path:
    """Concatenate audio files in the given order into one new file."""
    paths = [Path(source) for source in sources]
    if len(paths) < 2:
        raise AudioConversionError("合并至少需要两个音频文件。")
    for path in paths:
        if not path.is_file():
            raise AudioConversionError(f"输入音频文件不存在或无法访问：{path.name}")
        if path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
            raise AudioConversionError(f"不支持该输入格式：{path.name}")
    if output_format not in FORMAT_SPECS:
        raise AudioConversionError("不支持所选的输出格式。")
    ffmpeg = find_ffmpeg(ffmpeg_path)
    directory = _output_directory(output_dir, paths[0])
    extension = FORMAT_SPECS[output_format].extension
    stem = sanitize_windows_stem(paths[0].stem) or "merged"
    destination = _unique(directory, f"{stem}-合并", extension)
    total = sum(_duration_seconds(ffmpeg, path) or 0.0 for path in paths) or None
    spec = FORMAT_SPECS[output_format]
    command = [str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error"]
    for path in paths:
        command.extend(("-i", str(path)))
    # The concat filter joins every input in order. Mapping "0:a:0" alone would
    # silently emit only the first file, so all inputs are routed through it.
    streams = "".join(f"[{index}:a:0]" for index in range(len(paths)))
    command.extend((
        "-filter_complex", f"{streams}concat=n={len(paths)}:v=0:a=1[joined]",
        "-map", "[joined]", "-vn", "-codec:a", spec.codec,
    ))
    if spec.key in {"mp3", "m4a", "aac"}:
        command.extend(("-b:a", f"{spec.default_parameter}k"))
    if spec.key == "mp3":
        command.extend(("-id3v2_version", "3"))
    command.extend(("-n", "-progress", "pipe:1", "-nostats", str(destination)))
    _run(command, destination, total, progress, 0.0, 100.0,
         cancel_check, process_callback, timeout_seconds)
    return destination


def split_audio(source: str | Path, plans: Iterable[SplitPlan], output_format: str = "mp3",
                output_dir: str | Path | None = None,
                progress: ProgressCallback | None = None,
                ffmpeg_path: str | Path | None = None,
                *, cancel_check: Callable[[], None] | None = None,
                process_callback: Callable[[subprocess.Popen[str] | None], None] | None = None,
                timeout_seconds: float = DEFAULT_FFMPEG_TIMEOUT_SECONDS) -> tuple[Path, ...]:
    """Cut one audio file into the pieces described by ``plans``."""
    path = Path(source)
    if not path.is_file():
        raise AudioConversionError("输入音频文件不存在或无法访问。")
    if path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
        raise AudioConversionError("不支持该输入格式。")
    if output_format not in FORMAT_SPECS:
        raise AudioConversionError("不支持所选的输出格式。")
    pieces = tuple(plans)
    if not pieces:
        raise AudioConversionError("没有生成任何分段，请检查分段设置。")
    ffmpeg = find_ffmpeg(ffmpeg_path)
    directory = _output_directory(output_dir, path)
    extension = FORMAT_SPECS[output_format].extension
    spec = FORMAT_SPECS[output_format]
    stem = sanitize_windows_stem(path.stem) or "audio"
    outputs: list[Path] = []
    for index, plan in enumerate(pieces, 1):
        destination = _unique(directory, f"{stem}-{index:02d}", extension)
        command = [
            str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
            "-ss", f"{plan.start_seconds:.3f}", "-i", str(path),
            "-t", f"{plan.duration_seconds:.3f}",
            "-map", "0:a:0", "-vn", "-codec:a", spec.codec,
        ]
        if spec.key in {"mp3", "m4a", "aac"}:
            command.extend(("-b:a", f"{spec.default_parameter}k"))
        if spec.key == "mp3":
            command.extend(("-id3v2_version", "3"))
        command.extend(("-n", "-progress", "pipe:1", "-nostats", str(destination)))
        span = 100.0 / len(pieces)
        _run(command, destination, plan.duration_seconds, progress,
             (index - 1) * span, span, cancel_check, process_callback, timeout_seconds)
        outputs.append(destination)
    return tuple(outputs)


__all__ = [
    "SplitPlan",
    "audio_duration",
    "merge_audio",
    "plan_equal_parts",
    "plan_fixed_length",
    "split_audio",
]
