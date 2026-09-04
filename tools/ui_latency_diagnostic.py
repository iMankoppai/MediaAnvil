"""Diagnostic Sub2LRC build that records Tk event-loop scheduling latency."""

from __future__ import annotations

import math
import statistics
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
import traceback

from sub2lrc.gui import Sub2LRCApp


def summarize_latency(samples: list[float]) -> str:
    if not samples:
        return "没有采集到数据。"
    ordered = sorted(samples)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return (
        f"样本 {len(samples)}｜平均 {statistics.fmean(samples):.2f} ms｜"
        f"P95 {ordered[p95_index]:.2f} ms｜最大 {max(samples):.2f} ms｜"
        f">16 ms: {sum(value > 16 for value in samples)}｜"
        f">33 ms: {sum(value > 33 for value in samples)}｜"
        f">50 ms: {sum(value > 50 for value in samples)}"
    )


class DiagnosticApp(Sub2LRCApp):
    INTERVAL_MS = 16

    def _build_ui(self) -> None:
        self._latency_samples: list[float] = []
        self._latency_job: str | None = None
        self._latency_expected = 0.0
        self._latency_heartbeat = 0.0
        self._watchdog_generation = 0
        self._stall_stacks: list[str] = []
        self._main_thread_id = threading.get_ident()
        self.latency_result = tk.StringVar(
            value="点击“开始记录”，拖动窗口约 5～8 秒，然后点击“停止记录”。"
        )
        self.latency_cause = tk.StringVar(value="出现超过 100 ms 的停顿时，这里会显示主线程位置。")

        panel = ttk.LabelFrame(self, text="UI 响应延迟诊断", padding=(8, 6))
        panel.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        buttons = ttk.Frame(panel)
        buttons.pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="开始记录", command=self._start_latency_recording).pack(side="left")
        ttk.Button(buttons, text="停止记录", command=self._stop_latency_recording).pack(
            side="left", padx=(6, 10)
        )
        report = ttk.Frame(panel)
        report.pack(side="left", fill="x", expand=True)
        ttk.Label(report, textvariable=self.latency_result, anchor="w").pack(
            fill="x", expand=True
        )
        ttk.Label(report, textvariable=self.latency_cause, anchor="w", foreground="#7a4d00").pack(
            fill="x", expand=True
        )
        super()._build_ui()

    def _start_latency_recording(self) -> None:
        self._cancel_latency_job()
        self._latency_samples.clear()
        self._stall_stacks.clear()
        self.latency_result.set("正在记录……请连续拖动窗口 5～8 秒。")
        self.latency_cause.set("看门狗正在等待超过 100 ms 的停顿……")
        self._latency_expected = time.perf_counter() + self.INTERVAL_MS / 1000
        self._latency_heartbeat = time.perf_counter()
        self._latency_job = self.after(self.INTERVAL_MS, self._sample_latency)
        self._watchdog_generation += 1
        generation = self._watchdog_generation
        threading.Thread(
            target=self._watch_for_stall,
            args=(generation,),
            name="Sub2LRC-UI-Latency-Watchdog",
            daemon=True,
        ).start()

    def _sample_latency(self) -> None:
        self._latency_job = None
        now = time.perf_counter()
        self._latency_heartbeat = now
        self._latency_samples.append(max(0.0, (now - self._latency_expected) * 1000))
        self._latency_expected = now + self.INTERVAL_MS / 1000
        self._latency_job = self.after(self.INTERVAL_MS, self._sample_latency)

    def _stop_latency_recording(self) -> None:
        self._cancel_latency_job()
        self._watchdog_generation += 1
        self.latency_result.set(summarize_latency(self._latency_samples))
        if self._stall_stacks:
            self.latency_cause.set(f"停顿时主线程：{self._stall_stacks[-1]}")
        else:
            self.latency_cause.set("没有捕获到超过 100 ms 的主线程停顿。")

    def _watch_for_stall(self, generation: int) -> None:
        captured_current_stall = False
        while generation == self._watchdog_generation:
            time.sleep(0.02)
            delay = time.perf_counter() - self._latency_heartbeat
            if delay < 0.05:
                captured_current_stall = False
                continue
            if delay < 0.1 or captured_current_stall:
                continue
            frame = sys._current_frames().get(self._main_thread_id)
            if frame is not None:
                names = [entry.name for entry in traceback.extract_stack(frame)]
                self._stall_stacks.append(" → ".join(names[-7:]))
            captured_current_stall = True

    def _cancel_latency_job(self) -> None:
        if self._latency_job is None:
            return
        try:
            self.after_cancel(self._latency_job)
        except tk.TclError:
            pass
        self._latency_job = None

    def destroy(self) -> None:
        self._watchdog_generation += 1
        self._cancel_latency_job()
        super().destroy()


def main() -> None:
    app = DiagnosticApp()
    app.title("Sub2LRC - UI 延迟诊断版")
    app.mainloop()


if __name__ == "__main__":
    main()
