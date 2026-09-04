"""Diagnostic Sub2LRC build that measures cursor-to-window tracking while dragging."""

from __future__ import annotations

import ctypes
import math
import threading
import time
import tkinter as tk
from tkinter import ttk

from sub2lrc.gui import Sub2LRCApp


DragSample = tuple[float, bool, int, int, int, int]


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


def _split_pressed_segments(samples: list[DragSample]) -> list[list[DragSample]]:
    segments: list[list[DragSample]] = []
    current: list[DragSample] = []
    for sample in samples:
        if sample[1]:
            current.append(sample)
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    return segments


def _path_length(segment: list[DragSample], x_index: int, y_index: int) -> float:
    return sum(
        math.hypot(current[x_index] - previous[x_index], current[y_index] - previous[y_index])
        for previous, current in zip(segment, segment[1:])
    )


def analyze_drag_tracking(samples: list[DragSample]) -> tuple[str, str]:
    """Summarize cursor/window tracking for real window-drag segments."""
    drag_segments = []
    for segment in _split_pressed_segments(samples):
        duration = segment[-1][0] - segment[0][0]
        cursor_travel = _path_length(segment, 2, 3)
        window_travel = _path_length(segment, 4, 5)
        if duration >= 0.15 and cursor_travel >= 40 and window_travel >= 40:
            drag_segments.append(segment)

    if not drag_segments:
        return (
            "没有识别到有效的窗口拖动。",
            "请从标题栏按住鼠标左键，连续移动窗口后再松开。",
        )

    tracking_errors: list[float] = []
    sample_gaps: list[float] = []
    total_travel = 0.0
    for segment in drag_segments:
        # The mouse-down cursor-to-window offset is the grab point. It should
        # remain nearly fixed during a correctly tracked native window drag.
        reference_x = segment[0][2] - segment[0][4]
        reference_y = segment[0][3] - segment[0][5]
        total_travel += _path_length(segment, 4, 5)
        for sample in segment:
            offset_x = sample[2] - sample[4]
            offset_y = sample[3] - sample[5]
            tracking_errors.append(math.hypot(offset_x - reference_x, offset_y - reference_y))
        sample_gaps.extend(
            (current[0] - previous[0]) * 1000
            for previous, current in zip(segment, segment[1:])
        )

    p95_error = _percentile(tracking_errors, 0.95)
    max_error = max(tracking_errors)
    p95_gap = _percentile(sample_gaps, 0.95) if sample_gaps else 0.0
    max_gap = max(sample_gaps, default=0.0)
    summary = (
        f"有效拖动 {len(drag_segments)} 次｜采样 {len(tracking_errors)}｜"
        f"窗口移动 {total_travel:.0f} px｜偏离 P95 {p95_error:.1f} px｜最大 {max_error:.1f} px"
    )
    detail = f"采样间隔 P95 {p95_gap:.1f} ms｜最大 {max_gap:.1f} ms"
    return summary, detail


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class DiagnosticApp(Sub2LRCApp):
    SAMPLE_INTERVAL_SECONDS = 0.005

    def _build_ui(self) -> None:
        self._tracking_samples: list[DragSample] = []
        self._tracking_generation = 0
        self.tracking_result = tk.StringVar(
            value="点击“开始记录”，从标题栏连续拖动窗口约 5～8 秒。"
        )
        self.tracking_detail = tk.StringVar(
            value="此版本直接比较 Windows 鼠标位置与窗口位置。"
        )

        panel = ttk.LabelFrame(self, text="窗口拖动跟随诊断", padding=(8, 6))
        panel.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        buttons = ttk.Frame(panel)
        buttons.pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="开始记录", command=self._start_tracking).pack(side="left")
        ttk.Button(buttons, text="停止记录", command=self._stop_tracking).pack(
            side="left", padx=(6, 10)
        )
        report = ttk.Frame(panel)
        report.pack(side="left", fill="x", expand=True)
        ttk.Label(report, textvariable=self.tracking_result, anchor="w").pack(fill="x")
        ttk.Label(
            report,
            textvariable=self.tracking_detail,
            anchor="w",
            foreground="#7a4d00",
        ).pack(fill="x")
        super()._build_ui()

    def _start_tracking(self) -> None:
        self._tracking_generation += 1
        generation = self._tracking_generation
        self._tracking_samples.clear()
        self.tracking_result.set("正在记录……请从标题栏连续拖动窗口 5～8 秒。")
        self.tracking_detail.set("记录时可以多次按住、移动和松开鼠标。")
        hwnd = int(self.winfo_id())
        threading.Thread(
            target=self._sample_windows_positions,
            args=(generation, hwnd),
            name="Sub2LRC-Window-Tracking-Diagnostic",
            daemon=True,
        ).start()

    def _sample_windows_positions(self, generation: int, hwnd: int) -> None:
        user32 = ctypes.windll.user32
        while generation == self._tracking_generation:
            point = _Point()
            rect = _Rect()
            if user32.GetCursorPos(ctypes.byref(point)) and user32.GetWindowRect(
                hwnd, ctypes.byref(rect)
            ):
                left_pressed = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
                self._tracking_samples.append(
                    (time.perf_counter(), left_pressed, point.x, point.y, rect.left, rect.top)
                )
            time.sleep(self.SAMPLE_INTERVAL_SECONDS)

    def _stop_tracking(self) -> None:
        self._tracking_generation += 1
        summary, detail = analyze_drag_tracking(list(self._tracking_samples))
        self.tracking_result.set(summary)
        self.tracking_detail.set(detail)

    def destroy(self) -> None:
        self._tracking_generation += 1
        super().destroy()


def main() -> None:
    app = DiagnosticApp()
    app.title("Sub2LRC - 窗口拖动诊断版")
    app.mainloop()


if __name__ == "__main__":
    main()
