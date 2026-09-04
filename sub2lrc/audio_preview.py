"""Lightweight, read-only audio preview through bundled FFplay."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Callable

from .audio_converter import SUPPORTED_INPUT_EXTENSIONS, _duration_seconds, find_ffmpeg
from .converter import read_subtitle
from .mp3_exporter import Mp3ExportError, read_embedded_lyrics


class AudioPreviewError(ValueError):
    """Raised when preview playback cannot be prepared."""


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass(frozen=True)
class LyricLine:
    time_seconds: float
    text: str
    source_line: int


_LRC_TIME = re.compile(r"\[(?P<minutes>\d+):(?P<seconds>\d{2})(?:\.(?P<fraction>\d{1,3}))?\]")


def parse_lrc_timeline(content: str) -> tuple[LyricLine, ...]:
    """Parse timestamps without changing the text shown in the lyric panel."""
    timeline: list[LyricLine] = []
    for line_number, raw_line in enumerate(content.replace("\r\n", "\n").replace("\r", "\n").split("\n")):
        matches = list(_LRC_TIME.finditer(raw_line))
        if not matches:
            continue
        text = raw_line[matches[-1].end():]
        for match in matches:
            fraction_text = match.group("fraction") or "0"
            fraction = int(fraction_text) / (10 ** len(fraction_text))
            seconds = int(match.group("minutes")) * 60 + int(match.group("seconds")) + fraction
            timeline.append(LyricLine(seconds, text, line_number))
    return tuple(sorted(timeline, key=lambda item: item.time_seconds))


def current_lyric_index(timeline: tuple[LyricLine, ...], position: float) -> int | None:
    if not timeline:
        return None
    index = bisect_right([line.time_seconds for line in timeline], position) - 1
    return index if index >= 0 else None


def lyric_index_from_display_line(timeline: tuple[LyricLine, ...], line_number: int) -> int | None:
    """Map a one-based line in the clean lyric view back to its timeline item."""
    index = line_number - 1
    return index if 0 <= index < len(timeline) else None


def load_audio_lyrics(path: str | Path) -> tuple[str, tuple[LyricLine, ...]]:
    """Prefer a same-name external LRC, then a timed embedded MP3 lyric."""
    audio_path = Path(path)
    external = audio_path.with_suffix(".lrc")
    content = ""
    if external.is_file():
        content = read_subtitle(external)
    elif audio_path.suffix.lower() == ".mp3":
        try:
            embedded = read_embedded_lyrics(audio_path)
            if embedded.extension == ".lrc":
                content = embedded.text
        except Mp3ExportError:
            pass
    return content, parse_lrc_timeline(content)


def find_ffplay(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        candidate = Path(explicit)
        if candidate.is_file():
            return candidate
        raise AudioPreviewError(f"找不到指定的 FFplay：{candidate}")
    executable_dir = Path(sys.executable).resolve().parent
    bundled_dir = Path(getattr(sys, "_MEIPASS", executable_dir))
    project_dir = Path(__file__).resolve().parent.parent
    for folder in (bundled_dir, executable_dir, project_dir / "vendor" / "ffmpeg", project_dir):
        for name in (("ffplay.exe", "ffplay") if os.name == "nt" else ("ffplay", "ffplay.exe")):
            candidate = folder / name
            if candidate.is_file():
                return candidate
    from shutil import which
    located = which("ffplay")
    if located:
        return Path(located)
    raise AudioPreviewError("没有找到 FFplay。请使用包含音频预览组件的正式版软件。")


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _suspend_process(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        import ctypes
        if ctypes.windll.ntdll.NtSuspendProcess(int(process._handle)) != 0:  # type: ignore[attr-defined]
            raise OSError("系统无法暂停播放进程。")
    else:
        os.kill(process.pid, signal.SIGSTOP)


def _resume_process(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        import ctypes
        if ctypes.windll.ntdll.NtResumeProcess(int(process._handle)) != 0:  # type: ignore[attr-defined]
            raise OSError("系统无法恢复播放进程。")
    else:
        os.kill(process.pid, signal.SIGCONT)


class AudioPreviewPlayer:
    """Single-file playback controller with pause, seek and volume restart."""

    def __init__(
        self,
        ffplay_path: str | Path | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ffplay_path = find_ffplay(ffplay_path)
        self.clock = clock
        self.source: Path | None = None
        self.duration = 0.0
        self.volume = 80
        self.state = PlaybackState.STOPPED
        self._position = 0.0
        self._started_at = 0.0
        self._process: subprocess.Popen[bytes] | None = None

    def load(self, path: str | Path) -> float:
        self.stop()
        source = Path(path)
        if source.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
            raise AudioPreviewError("不支持该音频格式。")
        if not source.is_file():
            raise AudioPreviewError("音频文件不存在或无法访问。")
        duration = _duration_seconds(find_ffmpeg(), source)
        if duration is None or duration <= 0:
            raise AudioPreviewError("无法读取音频时长，文件可能已损坏。")
        self.source = source
        self.duration = duration
        self._position = 0.0
        return duration

    @property
    def position(self) -> float:
        if self.state == PlaybackState.PLAYING:
            if self._process is not None and self._process.poll() is not None:
                self.state = PlaybackState.STOPPED
                self._process = None
                self._position = self.duration
                return self._position
            return min(self.duration, self._position + self.clock() - self._started_at)
        return self._position

    def _start_process(self, position: float) -> None:
        if self.source is None:
            raise AudioPreviewError("请先选择音频文件。")
        command = [
            str(self.ffplay_path), "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "error",
            "-ss", f"{position:.3f}", "-volume", str(self.volume), str(self.source),
        ]
        try:
            self._process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=_creation_flags(),
            )
        except OSError as exc:
            raise AudioPreviewError(f"无法启动音频预览：{exc}") from exc
        self._position = position
        self._started_at = self.clock()
        self.state = PlaybackState.PLAYING

    def play(self) -> None:
        if self.source is None:
            raise AudioPreviewError("请先选择音频文件。")
        if self.state == PlaybackState.PLAYING:
            return
        if self.state == PlaybackState.PAUSED and self._process is not None:
            try:
                _resume_process(self._process)
            except OSError as exc:
                raise AudioPreviewError(str(exc)) from exc
            self._started_at = self.clock()
            self.state = PlaybackState.PLAYING
            return
        if self._position >= self.duration:
            self._position = 0.0
        self._start_process(self._position)

    def pause(self) -> None:
        if self.state != PlaybackState.PLAYING or self._process is None:
            return
        position = self.position
        try:
            _suspend_process(self._process)
        except OSError as exc:
            raise AudioPreviewError(str(exc)) from exc
        self._position = position
        self.state = PlaybackState.PAUSED

    def _terminate(self) -> None:
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    def stop(self) -> None:
        self._terminate()
        self.state = PlaybackState.STOPPED
        self._position = 0.0

    def seek(self, position: float) -> None:
        if self.source is None:
            return
        target = min(self.duration, max(0.0, float(position)))
        previous_state = self.state
        self._terminate()
        self._position = target
        self.state = PlaybackState.STOPPED
        if previous_state in {PlaybackState.PLAYING, PlaybackState.PAUSED} and target < self.duration:
            self._start_process(target)
            if previous_state == PlaybackState.PAUSED:
                self.pause()

    def set_volume(self, volume: int) -> None:
        if not 0 <= volume <= 100:
            raise AudioPreviewError("音量必须在 0 到 100 之间。")
        if volume == self.volume:
            return
        position, previous_state = self.position, self.state
        self.volume = volume
        if previous_state in {PlaybackState.PLAYING, PlaybackState.PAUSED}:
            self._terminate()
            self._position = position
            self.state = PlaybackState.STOPPED
            if position < self.duration:
                self._start_process(position)
                if previous_state == PlaybackState.PAUSED:
                    self.pause()

    def close(self) -> None:
        self.stop()
