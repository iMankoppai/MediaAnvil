"""Tkinter graphical interface for Sub2LRC."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .audio_converter import (
    AudioConversionError,
    AudioConversionSettings,
    BatchConversionResult,
    FORMAT_SPECS,
    FfmpegNotFoundError,
    convert_audio_batch,
    find_ffmpeg,
)
from .audio_preview import (
    AudioPreviewError,
    AudioPreviewPlayer,
    LyricLine,
    PlaybackState,
    current_lyric_index,
    load_audio_lyrics,
    lyric_index_from_display_line,
)
from .converter import SubtitleError, convert_file, read_subtitle, unique_output_path
from .cropper import CoverCropDialog
from .editor import Mp3Edits, Mp3EditorError, Mp3EditorState, read_mp3_editor_state, save_mp3_edits
from .embedder import LyricsEmbedError, read_lrc
from .image_converter import (
    IMAGE_FORMAT_SPECS,
    ImageBatchConversionResult,
    ImageConversionError,
    ImageConversionSettings,
    convert_image_batch,
)
from .metadata import MetadataError
from .mp3_exporter import (
    Mp3AudioInfo,
    Mp3ExportError,
    export_embedded_cover,
    export_embedded_lyrics,
    inspect_mp3,
)


class Sub2LRCApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sub2LRC - 本地多媒体工具箱")
        self.geometry("940x720")
        self.minsize(800, 650)

        self.sources: list[Path] = []
        self.results: dict[str, tuple[Path, str]] = {}
        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.subtitle_output_format = tk.StringVar(value="LRC")
        self.subtitle_final_duration = tk.StringVar(value="5")
        self.status = tk.StringVar(value="请选择 LRC、SRT 或 VTT 文件")
        self.audio_sources: list[Path] = []
        self.audio_output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.audio_format_label = tk.StringVar(value="MP3")
        self.audio_parameter = tk.StringVar(value="192")
        self.audio_sample_rate = tk.StringVar(value="保持原始采样率")
        self.audio_channels = tk.StringVar(value="保持原始声道")
        self.audio_current = tk.StringVar(value="请选择一个或多个音频文件")
        self.audio_summary = tk.StringVar(value="")
        self.audio_progress = tk.DoubleVar(value=0.0)
        self._audio_running = False
        self.image_sources: list[Path] = []
        self.image_output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.image_format_label = tk.StringVar(value="JPG / JPEG")
        self.image_quality = tk.StringVar(value="90")
        self.image_current = tk.StringVar(value="请选择一张或多张图片")
        self.image_summary = tk.StringVar(value="")
        self.image_progress = tk.DoubleVar(value=0.0)
        self._image_running = False
        self.preview_audio_path = tk.StringVar()
        self.preview_audio_status = tk.StringVar(value="请选择一首音频进行预览")
        self.preview_audio_time = tk.StringVar(value="00:00 / 00:00")
        self.preview_audio_position = tk.DoubleVar(value=0.0)
        self.preview_audio_volume = tk.DoubleVar(value=80.0)
        self._preview_player: AudioPreviewPlayer | None = None
        self._preview_timeline: tuple[LyricLine, ...] = ()
        self._preview_seeking = False
        self._preview_lyric_index: int | None = None
        self.editor_mp3_path = tk.StringVar()
        self.editor_title = tk.StringVar()
        self.editor_artist = tk.StringVar()
        self.editor_album = tk.StringVar()
        self.editor_lyrics_state = tk.StringVar(value="尚未读取歌词")
        self.editor_cover_state = tk.StringVar(value="尚未读取封面")
        self.editor_output_mode = tk.StringVar(value="save_as")
        self.editor_status = tk.StringVar(value="请选择一个 MP3 文件开始编辑")
        self.editor_audio_info = tk.StringVar(value="选择 MP3 后显示格式、时长、码率、采样率、声道和大小")
        self.lyrics_button_text = tk.StringVar(value="导入 LRC…")
        self.cover_button_text = tk.StringVar(value="选择图片…")
        self._original_editor_state: Mp3EditorState | None = None
        self._lyrics_action = "unchanged"
        self._pending_lrc_path: Path | None = None
        self._cover_action = "unchanged"
        self._pending_cover_path: Path | None = None
        self._cover_photo: ImageTk.PhotoImage | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)
        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)
        converter_tab = ttk.Frame(notebook, padding=12)
        editor_tab = ttk.Frame(notebook, padding=14)
        audio_tab = ttk.Frame(notebook, padding=14)
        image_tab = ttk.Frame(notebook, padding=14)
        preview_tab = ttk.Frame(notebook, padding=14)
        notebook.add(converter_tab, text="歌词 / 字幕转换")
        notebook.add(editor_tab, text="音频标签编辑")
        notebook.add(preview_tab, text="音频预览")
        notebook.add(audio_tab, text="音频格式转换")
        notebook.add(image_tab, text="图片格式转换")
        self._build_converter_tab(converter_tab)
        self._build_editor_tab(editor_tab)
        self._build_audio_tab(audio_tab)
        self._build_image_tab(image_tab)
        self._build_preview_tab(preview_tab)

    def _build_preview_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)
        ttk.Label(root, text="音频预览", font=("Microsoft YaHei UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )
        source = ttk.LabelFrame(root, text="音频文件", padding=10)
        source.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        source.columnconfigure(0, weight=1)
        ttk.Entry(source, textvariable=self.preview_audio_path, state="readonly").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(source, text="选择音频…", command=self.choose_preview_audio).grid(row=0, column=1)

        controls = ttk.LabelFrame(root, text="播放控制", padding=10)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(3, weight=1)
        ttk.Button(controls, text="播放", command=self.play_preview_audio).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(controls, text="暂停", command=self.pause_preview_audio).grid(row=0, column=1, padx=6)
        ttk.Button(controls, text="停止", command=self.stop_preview_audio).grid(row=0, column=2, padx=(6, 12))
        self.preview_audio_scale = ttk.Scale(
            controls, from_=0, to=1, variable=self.preview_audio_position, orient="horizontal"
        )
        self.preview_audio_scale.grid(row=0, column=3, sticky="ew")
        self.preview_audio_scale.bind("<ButtonPress-1>", self._begin_preview_seek)
        self.preview_audio_scale.bind("<ButtonRelease-1>", self._end_preview_seek)
        ttk.Label(controls, textvariable=self.preview_audio_time, width=15, anchor="e").grid(
            row=0, column=4, padx=(10, 0)
        )
        ttk.Label(controls, text="音量：").grid(row=1, column=0, columnspan=2, sticky="e", pady=(10, 0))
        self.preview_volume_scale = ttk.Scale(
            controls, from_=0, to=100, variable=self.preview_audio_volume, orient="horizontal", length=180
        )
        self.preview_volume_scale.grid(row=1, column=2, columnspan=2, sticky="w", pady=(10, 0))
        self.preview_volume_scale.bind("<ButtonRelease-1>", self._apply_preview_volume)
        ttk.Label(controls, textvariable=self.preview_audio_status, foreground="#555555").grid(
            row=1, column=4, sticky="e", pady=(10, 0)
        )

        lyrics = ttk.LabelFrame(root, text="同步歌词", padding=10)
        lyrics.grid(row=3, column=0, sticky="nsew")
        lyrics.columnconfigure(0, weight=1)
        lyrics.rowconfigure(0, weight=1)
        self.preview_lyrics = tk.Text(
            lyrics, wrap="word", font=("Microsoft YaHei UI", 11), state="disabled", spacing2=4
        )
        self.preview_lyrics.grid(row=0, column=0, sticky="nsew")
        lyric_scroll = ttk.Scrollbar(lyrics, orient="vertical", command=self.preview_lyrics.yview)
        lyric_scroll.grid(row=0, column=1, sticky="ns")
        self.preview_lyrics.configure(yscrollcommand=lyric_scroll.set)
        self.preview_lyrics.tag_configure("center", justify="center", spacing1=3, spacing3=3)
        self.preview_lyrics.tag_configure("current", background="#fff2a8", foreground="#9a3b00")
        self.preview_lyrics.bind("<Button-1>", self._click_preview_lyric)
        self.after(200, self._poll_preview_audio)

    def choose_preview_audio(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择预览音频",
            filetypes=[
                ("支持的音频", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg"),
                ("MP3", "*.mp3"), ("WAV", "*.wav"), ("FLAC", "*.flac"),
                ("M4A / AAC", "*.m4a *.aac"), ("OGG", "*.ogg"),
            ],
        )
        if not selected:
            return
        if self._preview_player is not None:
            self._preview_player.close()
        try:
            player = AudioPreviewPlayer()
            duration = player.load(selected)
        except AudioPreviewError as exc:
            self._preview_player = None
            messagebox.showerror("无法预览音频", str(exc))
            return
        self._preview_player = player
        self.preview_audio_path.set(selected)
        self.preview_audio_position.set(0.0)
        self.preview_audio_scale.configure(to=duration)
        self._preview_lyric_index = None
        try:
            _lyrics, self._preview_timeline = load_audio_lyrics(selected)
        except (OSError, SubtitleError) as exc:
            self._preview_timeline = ()
            self.preview_audio_status.set(f"音频已载入，歌词读取失败：{exc}")
        else:
            self.preview_audio_status.set("音频与歌词已载入" if self._preview_timeline else "音频已载入（没有同步歌词）")
        self.preview_lyrics.configure(state="normal")
        self.preview_lyrics.delete("1.0", "end")
        if self._preview_timeline:
            self.preview_lyrics.insert("1.0", "\n".join(line.text for line in self._preview_timeline))
            self.preview_lyrics.tag_add("center", "1.0", "end")
        self.preview_lyrics.configure(state="disabled")
        self._update_preview_time(0.0, duration)

    def play_preview_audio(self) -> None:
        if self._preview_player is None:
            messagebox.showinfo("Sub2LRC", "请先选择一首音频。")
            return
        try:
            self._preview_player.play()
            self.preview_audio_status.set("正在播放")
        except AudioPreviewError as exc:
            messagebox.showerror("播放失败", str(exc))

    def pause_preview_audio(self) -> None:
        if self._preview_player is None:
            return
        try:
            self._preview_player.pause()
            if self._preview_player.state == PlaybackState.PAUSED:
                self.preview_audio_status.set("已暂停")
        except AudioPreviewError as exc:
            messagebox.showerror("暂停失败", str(exc))

    def stop_preview_audio(self) -> None:
        if self._preview_player is None:
            return
        self._preview_player.stop()
        self.preview_audio_position.set(0.0)
        self.preview_audio_status.set("已停止")
        self._highlight_preview_lyric(None)
        self._update_preview_time(0.0, self._preview_player.duration)

    def _begin_preview_seek(self, _event: object) -> None:
        self._preview_seeking = True

    def _end_preview_seek(self, _event: object) -> None:
        self._preview_seeking = False
        if self._preview_player is not None:
            self._preview_player.seek(self.preview_audio_position.get())

    def _apply_preview_volume(self, _event: object) -> None:
        if self._preview_player is None:
            return
        try:
            self._preview_player.set_volume(round(self.preview_audio_volume.get()))
        except AudioPreviewError as exc:
            messagebox.showerror("音量调整失败", str(exc))

    def _poll_preview_audio(self) -> None:
        player = self._preview_player
        if player is not None:
            position = player.position
            if not self._preview_seeking:
                self.preview_audio_position.set(position)
            self._update_preview_time(position, player.duration)
            lyric_index = current_lyric_index(self._preview_timeline, position)
            self._highlight_preview_lyric(lyric_index)
            if player.state == PlaybackState.STOPPED and position >= player.duration:
                self.preview_audio_status.set("播放完成")
        self.after(200, self._poll_preview_audio)

    def _highlight_preview_lyric(self, index: int | None) -> None:
        if index == self._preview_lyric_index:
            return
        self._preview_lyric_index = index
        self.preview_lyrics.configure(state="normal")
        self.preview_lyrics.tag_remove("current", "1.0", "end")
        if index is not None:
            line = index + 1
            start, end = f"{line}.0", f"{line}.end"
            self.preview_lyrics.tag_add("current", start, end)
            self.preview_lyrics.see(start)
            total_lines = max(1, len(self._preview_timeline))
            self.preview_lyrics.yview_moveto(max(0.0, min(1.0, (line - 1) / total_lines - 0.35)))
        self.preview_lyrics.configure(state="disabled")

    def _click_preview_lyric(self, event: tk.Event) -> str | None:
        player = self._preview_player
        if player is None or not self._preview_timeline:
            return None
        clicked_line = int(self.preview_lyrics.index(f"@{event.x},{event.y}").split(".")[0])
        index = lyric_index_from_display_line(self._preview_timeline, clicked_line)
        if index is None:
            return None
        was_stopped = player.state == PlaybackState.STOPPED
        target = self._preview_timeline[index].time_seconds
        player.seek(target)
        if was_stopped:
            try:
                player.play()
            except AudioPreviewError as exc:
                messagebox.showerror("播放失败", str(exc))
                return "break"
        self.preview_audio_position.set(target)
        self._update_preview_time(target, player.duration)
        self._highlight_preview_lyric(index)
        self.preview_audio_status.set("已跳转到所选歌词")
        return "break"

    def _update_preview_time(self, position: float, duration: float) -> None:
        def format_time(value: float) -> str:
            total = max(0, round(value))
            minutes, seconds = divmod(total, 60)
            return f"{minutes:02d}:{seconds:02d}"
        self.preview_audio_time.set(f"{format_time(position)} / {format_time(duration)}")

    def _build_image_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        ttk.Label(root, text="图片格式转换", font=("Microsoft YaHei UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )

        files = ttk.LabelFrame(root, text="1. 输入图片", padding=10)
        files.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        files.columnconfigure(0, weight=1)
        files.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(files)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="选择图片…", command=self.choose_image_files).pack(side="left")
        ttk.Button(toolbar, text="移除选中", command=self.remove_selected_images).pack(side="left", padx=6)
        ttk.Button(toolbar, text="清空", command=self.clear_image_files).pack(side="left")
        self.image_file_list = tk.Listbox(files, height=10, selectmode="extended")
        self.image_file_list.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(files, orient="vertical", command=self.image_file_list.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.image_file_list.configure(yscrollcommand=scrollbar.set)

        settings = ttk.LabelFrame(root, text="2. 转换设置", padding=10)
        settings.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="输出格式：").grid(row=0, column=0, sticky="w", pady=6)
        format_box = ttk.Combobox(
            settings,
            textvariable=self.image_format_label,
            values=tuple(spec.label for spec in IMAGE_FORMAT_SPECS.values()),
            state="readonly",
            width=18,
        )
        format_box.grid(row=0, column=1, sticky="w", padx=8, pady=6)
        format_box.bind("<<ComboboxSelected>>", self._update_image_parameter_ui)
        self.image_quality_label = ttk.Label(settings, text="图片质量：")
        self.image_quality_label.grid(row=1, column=0, sticky="w", pady=6)
        self.image_quality_box = ttk.Spinbox(
            settings, from_=1, to=100, increment=1, textvariable=self.image_quality, width=10
        )
        self.image_quality_box.grid(row=1, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(settings, text="输出目录：").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(settings, textvariable=self.image_output_dir).grid(
            row=2, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Button(settings, text="浏览…", command=self.choose_image_output_dir).grid(row=2, column=2, pady=6)
        self.image_transparency_hint = ttk.Label(
            settings,
            text="保持原始宽高；透明图片转为 JPG 或 BMP 时使用白色背景。",
            foreground="#666666",
        )
        self.image_transparency_hint.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        progress_area = ttk.LabelFrame(root, text="3. 转换进度", padding=10)
        progress_area.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        progress_area.columnconfigure(0, weight=1)
        ttk.Label(progress_area, textvariable=self.image_current, anchor="w").grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Progressbar(progress_area, variable=self.image_progress, maximum=100).grid(
            row=1, column=0, sticky="ew", pady=(8, 4)
        )
        ttk.Label(progress_area, textvariable=self.image_summary, anchor="w", foreground="#555555").grid(
            row=2, column=0, sticky="ew"
        )
        self.image_start_button = ttk.Button(root, text="开始转换", command=self.start_image_conversion)
        self.image_start_button.grid(row=4, column=0, sticky="e", ipadx=28, ipady=7)
        self._update_image_parameter_ui()

    def choose_image_files(self) -> None:
        names = filedialog.askopenfilenames(
            title="选择图片文件",
            filetypes=[
                ("支持的图片", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("JPG / JPEG", "*.jpg *.jpeg"), ("PNG", "*.png"),
                ("WebP", "*.webp"), ("BMP", "*.bmp"),
            ],
        )
        existing = {path.resolve() for path in self.image_sources}
        for name in names:
            path = Path(name)
            if path.resolve() not in existing:
                self.image_sources.append(path)
                self.image_file_list.insert("end", str(path))
                existing.add(path.resolve())
        if names:
            self.image_output_dir.set(str(Path(names[0]).parent))
            self.image_current.set(f"已选择 {len(self.image_sources)} 张图片")

    def remove_selected_images(self) -> None:
        if self._image_running:
            return
        for index in reversed(self.image_file_list.curselection()):
            self.image_file_list.delete(index)
            del self.image_sources[index]
        self.image_current.set(f"当前有 {len(self.image_sources)} 张待转换图片")

    def clear_image_files(self) -> None:
        if self._image_running:
            return
        self.image_sources.clear()
        self.image_file_list.delete(0, "end")
        self.image_current.set("已清空图片列表")
        self.image_progress.set(0.0)
        self.image_summary.set("")

    def choose_image_output_dir(self) -> None:
        if self._image_running:
            return
        selected = filedialog.askdirectory(title="选择图片输出目录", initialdir=self.image_output_dir.get())
        if selected:
            self.image_output_dir.set(selected)

    def _selected_image_format_key(self) -> str:
        for key, spec in IMAGE_FORMAT_SPECS.items():
            if spec.label == self.image_format_label.get():
                return key
        raise ImageConversionError("请选择有效的图片输出格式。")

    def _update_image_parameter_ui(self, _event: object | None = None) -> None:
        spec = IMAGE_FORMAT_SPECS[self._selected_image_format_key()]
        if spec.supports_quality:
            self.image_quality.set(str(spec.default_quality))
            self.image_quality_label.grid()
            self.image_quality_box.grid()
        else:
            self.image_quality_label.grid_remove()
            self.image_quality_box.grid_remove()
        color = "#a05a00" if not spec.supports_transparency else "#666666"
        self.image_transparency_hint.configure(foreground=color)

    def _current_image_settings(self) -> ImageConversionSettings:
        format_key = self._selected_image_format_key()
        spec = IMAGE_FORMAT_SPECS[format_key]
        try:
            quality = int(self.image_quality.get()) if spec.supports_quality else None
        except ValueError as exc:
            raise ImageConversionError("图片质量必须是 1 到 100 的整数。") from exc
        settings = ImageConversionSettings(format_key, quality)
        settings.validate()
        return settings

    def start_image_conversion(self) -> None:
        if self._image_running:
            return
        if not self.image_sources:
            messagebox.showinfo("Sub2LRC", "请至少选择一张图片。")
            return
        output_dir = Path(self.image_output_dir.get().strip())
        if not output_dir.is_dir():
            messagebox.showerror("输出目录错误", "输出目录不存在或无法访问。")
            return
        try:
            settings = self._current_image_settings()
        except ImageConversionError as exc:
            messagebox.showerror("转换设置错误", str(exc))
            return
        sources = tuple(self.image_sources)
        self._image_running = True
        self.image_progress.set(0.0)
        self.image_summary.set("")
        self.image_start_button.configure(state="disabled")

        def report(source: Path, index: int, total: int, overall: float) -> None:
            self.after(0, self._update_image_progress, source, index, total, overall)

        def worker() -> None:
            try:
                result = convert_image_batch(sources, output_dir, settings, report)
            except ImageConversionError as exc:
                self.after(0, self._finish_image_conversion, None, exc)
                return
            self.after(0, self._finish_image_conversion, result, None)

        threading.Thread(target=worker, name="Sub2LRC-Image-Conversion", daemon=True).start()

    def _update_image_progress(self, source: Path, index: int, total: int, overall: float) -> None:
        self.image_progress.set(overall)
        self.image_current.set(f"正在转换 {index}/{total}：{source.name}")

    def _finish_image_conversion(
        self, result: ImageBatchConversionResult | None, error: ImageConversionError | None
    ) -> None:
        self._image_running = False
        self.image_start_button.configure(state="normal")
        if error is not None:
            self.image_current.set("转换失败")
            messagebox.showerror("图片转换失败", str(error))
            return
        if result is None:
            return
        successes = len(result.outputs)
        failures = len(result.failures)
        transparency_count = sum(output.transparency_removed for output in result.outputs)
        self.image_progress.set(100.0)
        self.image_current.set("转换完成")
        self.image_summary.set(f"成功 {successes} 张，失败 {failures} 张")
        messages: list[str] = []
        if transparency_count:
            messages.append(f"有 {transparency_count} 张图片包含透明区域，已使用白色背景。")
        messages.extend(f"{failure.source.name}：{failure.message}" for failure in result.failures[:10])
        if messages:
            messagebox.showwarning("图片转换提示", "\n".join(messages))
        else:
            messagebox.showinfo(
                "转换完成", f"已生成 {successes} 张图片。\n保存位置：{self.image_output_dir.get()}"
            )

    def _build_audio_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        ttk.Label(root, text="音频格式转换", font=("Microsoft YaHei UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )
        files = ttk.LabelFrame(root, text="1. 输入音频", padding=10)
        files.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        files.columnconfigure(0, weight=1)
        files.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(files)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="选择音频…", command=self.choose_audio_files).pack(side="left")
        ttk.Button(toolbar, text="移除选中", command=self.remove_selected_audio).pack(side="left", padx=6)
        ttk.Button(toolbar, text="清空", command=self.clear_audio_files).pack(side="left")
        self.audio_file_list = tk.Listbox(files, height=10, selectmode="extended")
        self.audio_file_list.grid(row=1, column=0, sticky="nsew")
        file_scroll = ttk.Scrollbar(files, orient="vertical", command=self.audio_file_list.yview)
        file_scroll.grid(row=1, column=1, sticky="ns")
        self.audio_file_list.configure(yscrollcommand=file_scroll.set)

        settings = ttk.LabelFrame(root, text="2. 转换设置", padding=10)
        settings.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="输出格式：").grid(row=0, column=0, sticky="w", pady=6)
        format_box = ttk.Combobox(
            settings,
            textvariable=self.audio_format_label,
            values=tuple(spec.label for spec in FORMAT_SPECS.values()),
            state="readonly",
            width=18,
        )
        format_box.grid(row=0, column=1, sticky="w", padx=8, pady=6)
        format_box.bind("<<ComboboxSelected>>", self._update_audio_parameter_ui)
        self.audio_parameter_label = ttk.Label(settings, text="比特率：")
        self.audio_parameter_label.grid(row=1, column=0, sticky="w", pady=6)
        self.audio_parameter_box = ttk.Combobox(
            settings, textvariable=self.audio_parameter, state="readonly", width=18
        )
        self.audio_parameter_box.grid(row=1, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(settings, text="采样率：").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(
            settings,
            textvariable=self.audio_sample_rate,
            values=("保持原始采样率", "44100 Hz", "48000 Hz", "96000 Hz"),
            state="readonly",
            width=18,
        ).grid(row=2, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(settings, text="声道：").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Combobox(
            settings,
            textvariable=self.audio_channels,
            values=("保持原始声道", "单声道", "立体声"),
            state="readonly",
            width=18,
        ).grid(row=3, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(settings, text="输出目录：").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Entry(settings, textvariable=self.audio_output_dir).grid(row=4, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(settings, text="浏览…", command=self.choose_audio_output_dir).grid(row=4, column=2, pady=6)
        ttk.Label(
            settings,
            text="默认保持原采样率和声道；已有同名输出时会自动生成新文件名。",
            foreground="#666666",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))

        progress_area = ttk.LabelFrame(root, text="3. 转换进度", padding=10)
        progress_area.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        progress_area.columnconfigure(0, weight=1)
        ttk.Label(progress_area, textvariable=self.audio_current, anchor="w").grid(row=0, column=0, sticky="ew")
        ttk.Progressbar(progress_area, variable=self.audio_progress, maximum=100).grid(
            row=1, column=0, sticky="ew", pady=(8, 4)
        )
        ttk.Label(progress_area, textvariable=self.audio_summary, anchor="w", foreground="#555555").grid(
            row=2, column=0, sticky="ew"
        )
        self.audio_start_button = ttk.Button(root, text="开始转换", command=self.start_audio_conversion)
        self.audio_start_button.grid(row=4, column=0, sticky="e", ipadx=28, ipady=7)
        self._update_audio_parameter_ui()

    def choose_audio_files(self) -> None:
        names = filedialog.askopenfilenames(
            title="选择音频文件",
            filetypes=[
                ("支持的音频", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg"),
                ("MP3", "*.mp3"), ("WAV", "*.wav"), ("FLAC", "*.flac"),
                ("M4A / AAC", "*.m4a *.aac"), ("OGG", "*.ogg"),
            ],
        )
        existing = {path.resolve() for path in self.audio_sources}
        for name in names:
            path = Path(name)
            if path.resolve() not in existing:
                self.audio_sources.append(path)
                self.audio_file_list.insert("end", str(path))
                existing.add(path.resolve())
        if names:
            self.audio_output_dir.set(str(Path(names[0]).parent))
            self.audio_current.set(f"已选择 {len(self.audio_sources)} 个音频文件")

    def remove_selected_audio(self) -> None:
        if self._audio_running:
            return
        for index in reversed(self.audio_file_list.curselection()):
            self.audio_file_list.delete(index)
            del self.audio_sources[index]
        self.audio_current.set(f"当前有 {len(self.audio_sources)} 个待转换文件")

    def clear_audio_files(self) -> None:
        if self._audio_running:
            return
        self.audio_sources.clear()
        self.audio_file_list.delete(0, "end")
        self.audio_current.set("已清空音频文件列表")
        self.audio_progress.set(0.0)
        self.audio_summary.set("")

    def choose_audio_output_dir(self) -> None:
        if self._audio_running:
            return
        selected = filedialog.askdirectory(title="选择音频输出目录", initialdir=self.audio_output_dir.get())
        if selected:
            self.audio_output_dir.set(selected)

    def start_audio_conversion(self) -> None:
        if self._audio_running:
            return
        if not self.audio_sources:
            messagebox.showinfo("Sub2LRC", "请至少选择一个音频文件。")
            return
        output_dir = Path(self.audio_output_dir.get().strip())
        if not output_dir.is_dir():
            messagebox.showerror("输出目录错误", "输出目录不存在或无法访问。")
            return
        try:
            ffmpeg = find_ffmpeg()
        except FfmpegNotFoundError as exc:
            self.audio_current.set("未找到 FFmpeg")
            messagebox.showerror("缺少 FFmpeg", str(exc))
            return

        sources = tuple(self.audio_sources)
        try:
            settings = self._current_audio_settings()
        except AudioConversionError as exc:
            messagebox.showerror("转换设置错误", str(exc))
            return
        self._audio_running = True
        self.audio_progress.set(0.0)
        self.audio_summary.set("")
        self.audio_start_button.configure(state="disabled")

        def report(source: Path, index: int, total: int, file_percent: float, overall: float) -> None:
            self.after(0, self._update_audio_progress, source, index, total, file_percent, overall)

        def worker() -> None:
            try:
                result = convert_audio_batch(sources, output_dir, settings, report, ffmpeg)
            except AudioConversionError as exc:
                self.after(0, self._finish_audio_conversion, None, exc)
                return
            self.after(0, self._finish_audio_conversion, result, None)

        threading.Thread(target=worker, name="Sub2LRC-Audio-Conversion", daemon=True).start()

    def _update_audio_progress(
        self, source: Path, index: int, total: int, file_percent: float, overall: float
    ) -> None:
        self.audio_progress.set(overall)
        self.audio_current.set(f"正在转换 {index}/{total}：{source.name}（{file_percent:.0f}%）")

    def _finish_audio_conversion(
        self, result: BatchConversionResult | None, error: AudioConversionError | None
    ) -> None:
        self._audio_running = False
        self.audio_start_button.configure(state="normal")
        if error is not None:
            self.audio_current.set("转换失败")
            messagebox.showerror("音频转换失败", str(error))
            return
        if result is None:
            return
        successes = len(result.outputs)
        failures = len(result.failures)
        self.audio_progress.set(100.0)
        self.audio_current.set("转换完成")
        self.audio_summary.set(f"成功 {successes} 个，失败 {failures} 个")
        if result.failures:
            details = "\n".join(f"{failure.source.name}：{failure.message}" for failure in result.failures[:10])
            messagebox.showwarning("部分文件转换失败", details)
        else:
            messagebox.showinfo("转换完成", f"已生成 {successes} 个音频文件。\n保存位置：{self.audio_output_dir.get()}")

    def _selected_audio_format_key(self) -> str:
        for key, spec in FORMAT_SPECS.items():
            if spec.label == self.audio_format_label.get():
                return key
        raise AudioConversionError("请选择有效的输出格式。")

    def _update_audio_parameter_ui(self, _event: object | None = None) -> None:
        spec = FORMAT_SPECS[self._selected_audio_format_key()]
        if spec.parameter_label is None:
            self.audio_parameter_label.grid_remove()
            self.audio_parameter_box.grid_remove()
            self.audio_parameter.set("")
            return
        self.audio_parameter_label.configure(text=f"{spec.parameter_label}：")
        self.audio_parameter_box.configure(values=tuple(str(value) for value in spec.parameter_options))
        self.audio_parameter.set(str(spec.default_parameter))
        self.audio_parameter_label.grid()
        self.audio_parameter_box.grid()

    def _current_audio_settings(self) -> AudioConversionSettings:
        format_key = self._selected_audio_format_key()
        spec = FORMAT_SPECS[format_key]
        parameter = int(self.audio_parameter.get()) if spec.parameter_label else None
        sample_rate_values = {
            "保持原始采样率": None, "44100 Hz": 44_100, "48000 Hz": 48_000, "96000 Hz": 96_000,
        }
        channel_values = {"保持原始声道": None, "单声道": 1, "立体声": 2}
        settings = AudioConversionSettings(
            format_key,
            parameter,
            sample_rate_values[self.audio_sample_rate.get()],
            channel_values[self.audio_channels.get()],
        )
        settings.validate()
        return settings

    def _build_editor_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        file_area = ttk.LabelFrame(root, text="1. MP3 文件", padding=10)
        file_area.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        file_area.columnconfigure(0, weight=1)
        ttk.Entry(file_area, textvariable=self.editor_mp3_path, state="readonly").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(file_area, text="选择 MP3…", command=self.choose_editor_mp3).grid(row=0, column=1)
        ttk.Label(
            file_area, textvariable=self.editor_audio_info, foreground="#555555", wraplength=820
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        upper = ttk.Frame(root)
        upper.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        upper.columnconfigure(0, weight=3)
        upper.columnconfigure(1, weight=2)
        basic = ttk.LabelFrame(upper, text="2. 基础信息", padding=12)
        basic.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        basic.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate(
            (("歌名：", self.editor_title), ("歌手：", self.editor_artist), ("专辑：", self.editor_album))
        ):
            ttk.Label(basic, text=label).grid(row=row, column=0, sticky="w", pady=7)
            ttk.Entry(basic, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=7)
        ttk.Label(basic, text="留空并保存会移除对应信息。", foreground="#666666").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

        cover = ttk.LabelFrame(upper, text="4. 封面", padding=10)
        cover.grid(row=0, column=1, sticky="nsew")
        cover.columnconfigure(0, weight=1)
        preview_box = ttk.Frame(cover, width=190, height=145)
        preview_box.grid(row=0, column=0, sticky="nsew")
        preview_box.grid_propagate(False)
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(0, weight=1)
        self.cover_preview = ttk.Label(preview_box, text="", anchor="center")
        self.cover_preview.grid(row=0, column=0, sticky="nsew")
        self.cover_state_label = ttk.Label(cover, textvariable=self.editor_cover_state, anchor="center")
        self.cover_state_label.grid(
            row=1, column=0, sticky="ew", pady=(6, 4)
        )
        cover_actions = ttk.Frame(cover)
        cover_actions.grid(row=2, column=0)
        ttk.Button(cover_actions, textvariable=self.cover_button_text, command=self.choose_editor_cover).pack(
            side="left", padx=3
        )
        ttk.Button(cover_actions, text="导出", command=self.export_editor_cover).pack(side="left", padx=3)
        ttk.Button(cover_actions, text="移除", command=self.mark_cover_for_removal).pack(side="left", padx=3)

        lyrics = ttk.LabelFrame(root, text="3. 歌词", padding=10)
        lyrics.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        lyrics.columnconfigure(0, weight=1)
        lyrics.rowconfigure(1, weight=1)
        lyrics_toolbar = ttk.Frame(lyrics)
        lyrics_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.lyrics_state_label = ttk.Label(lyrics_toolbar, textvariable=self.editor_lyrics_state)
        self.lyrics_state_label.pack(side="left")
        ttk.Button(lyrics_toolbar, text="移除歌词", command=self.mark_lyrics_for_removal).pack(side="right")
        ttk.Button(lyrics_toolbar, text="导出歌词…", command=self.export_editor_lyrics).pack(
            side="right", padx=(0, 6)
        )
        ttk.Button(lyrics_toolbar, textvariable=self.lyrics_button_text, command=self.choose_editor_lrc).pack(
            side="right", padx=(0, 6)
        )
        self.lyrics_preview = tk.Text(
            lyrics, height=9, wrap="word", font=("Microsoft YaHei UI", 10), state="disabled"
        )
        self.lyrics_preview.grid(row=1, column=0, sticky="nsew")
        lyrics_scroll = ttk.Scrollbar(lyrics, orient="vertical", command=self.lyrics_preview.yview)
        lyrics_scroll.grid(row=1, column=1, sticky="ns")
        self.lyrics_preview.configure(yscrollcommand=lyrics_scroll.set)

        save_area = ttk.Frame(root)
        save_area.grid(row=3, column=0, sticky="sew")
        save_mode = ttk.LabelFrame(save_area, text="5. 保存方式", padding=(10, 6))
        save_mode.pack(fill="x")
        ttk.Radiobutton(
            save_mode, text="覆盖原文件", variable=self.editor_output_mode, value="overwrite"
        ).pack(side="left", padx=(0, 20))
        ttk.Radiobutton(
            save_mode, text="另存为", variable=self.editor_output_mode, value="save_as"
        ).pack(side="left")
        bottom = ttk.Frame(save_area)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Label(bottom, textvariable=self.editor_status, anchor="w", wraplength=650).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(bottom, text="保存到 MP3", command=self.save_editor, style="Accent.TButton").pack(
            side="right", ipadx=28, ipady=7
        )
        ttk.Button(bottom, text="取消修改", command=self.cancel_editor_changes).pack(
            side="right", padx=(0, 8), ipadx=14, ipady=7
        )

    def choose_editor_mp3(self) -> None:
        if self._has_pending_changes() and not messagebox.askyesno(
            "尚未保存", "当前修改尚未保存。选择其他 MP3 会放弃这些修改，是否继续？"
        ):
            return
        selected = filedialog.askopenfilename(title="选择 MP3 歌曲", filetypes=[("MP3 音频", "*.mp3")])
        if selected:
            self._load_editor_file(Path(selected), show_error=True)

    def _load_editor_file(self, path: Path, show_error: bool) -> bool:
        try:
            state = read_mp3_editor_state(path)
            audio_info = inspect_mp3(path)
        except (OSError, MetadataError, Mp3EditorError, Mp3ExportError) as exc:
            self.editor_status.set(f"读取失败：{exc}")
            if show_error:
                messagebox.showerror("读取 MP3 失败", str(exc))
            return False
        self._cleanup_pending_cover()
        self._original_editor_state = state
        self._lyrics_action = "unchanged"
        self._pending_lrc_path = None
        self._cover_action = "unchanged"
        self.editor_mp3_path.set(str(path))
        self.editor_title.set(state.title)
        self.editor_artist.set(state.artist)
        self.editor_album.set(state.album)
        self.editor_audio_info.set(self._format_audio_info(audio_info))
        self.editor_lyrics_state.set("已内嵌歌词" if state.has_lyrics else "未检测到内嵌歌词")
        self.lyrics_state_label.configure(foreground="#26734d" if state.has_lyrics else "#c62828")
        self.lyrics_button_text.set("更换歌词…" if state.has_lyrics else "导入 LRC…")
        self._set_lyrics_preview(state.lyrics)
        self.editor_cover_state.set("已内嵌封面" if state.has_cover else "未检测到内嵌封面")
        self.cover_state_label.configure(foreground="#26734d" if state.has_cover else "#c62828")
        self.cover_button_text.set("更换封面…" if state.has_cover else "选择图片…")
        self._show_cover_data(state.cover_data)
        self.editor_status.set("信息读取完成；修改需要调整的内容后统一保存")
        return True

    @staticmethod
    def _format_audio_info(info: Mp3AudioInfo) -> str:
        total_seconds = max(0, round(info.duration_seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
        channels = {1: "单声道", 2: "立体声"}.get(info.channels, f"{info.channels} 声道")
        size_mb = info.file_size_bytes / 1024 / 1024
        return (
            f"MP3  ·  {duration}  ·  {info.bitrate_kbps} kbps  ·  "
            f"{info.sample_rate_hz:,} Hz  ·  {channels}  ·  {size_mb:.1f} MB  ·  "
            f"{info.id3_version}（{info.tag_count} 个标签）"
        )

    def export_editor_lyrics(self) -> None:
        state = self._original_editor_state
        source_text = self.editor_mp3_path.get().strip()
        if state is None or not source_text:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件。")
            return
        if not state.has_lyrics:
            messagebox.showinfo("没有内嵌歌词", "当前 MP3 没有可导出的内嵌歌词。")
            return
        selected = filedialog.askdirectory(title="选择歌词导出目录", initialdir=str(Path(source_text).parent))
        if not selected:
            return
        try:
            output, frame_count = export_embedded_lyrics(source_text, selected)
        except (OSError, Mp3ExportError) as exc:
            messagebox.showerror("导出歌词失败", str(exc))
            return
        self.editor_status.set(f"已导出歌词：{output}")
        if frame_count > 1:
            messagebox.showwarning(
                "歌词已导出",
                f"检测到 {frame_count} 个歌词标签，已优先导出本软件写入的歌词。\n输出文件：{output}",
            )
        else:
            messagebox.showinfo("歌词已导出", f"输出文件：{output}")

    def export_editor_cover(self) -> None:
        state = self._original_editor_state
        source_text = self.editor_mp3_path.get().strip()
        if state is None or not source_text:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件。")
            return
        if not state.has_cover:
            messagebox.showinfo("没有内嵌封面", "当前 MP3 没有可导出的内嵌封面。")
            return
        selected = filedialog.askdirectory(title="选择封面导出目录", initialdir=str(Path(source_text).parent))
        if not selected:
            return
        try:
            output, frame_count = export_embedded_cover(source_text, selected)
        except (OSError, Mp3ExportError) as exc:
            messagebox.showerror("导出封面失败", str(exc))
            return
        self.editor_status.set(f"已导出封面：{output}")
        if frame_count > 1:
            messagebox.showwarning(
                "封面已导出",
                f"检测到 {frame_count} 张内嵌图片，已优先导出正面封面。\n输出文件：{output}",
            )
        else:
            messagebox.showinfo("封面已导出", f"输出文件：{output}")

    def choose_editor_lrc(self) -> None:
        if self._original_editor_state is None:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件。")
            return
        selected = filedialog.askopenfilename(title="选择 LRC 歌词", filetypes=[("LRC 歌词", "*.lrc")])
        if not selected:
            return
        try:
            lyrics = read_lrc(selected)
        except (OSError, LyricsEmbedError) as exc:
            messagebox.showerror("读取歌词失败", str(exc))
            return
        self._pending_lrc_path = Path(selected)
        self._lyrics_action = "replace"
        self._set_lyrics_preview(lyrics)
        self.editor_lyrics_state.set(f"待保存：{Path(selected).name}")
        self.lyrics_state_label.configure(foreground="#8a5a00")
        self.lyrics_button_text.set("更换歌词…")
        self.editor_status.set("已选择新歌词，点击“保存到 MP3”后写入")

    def mark_lyrics_for_removal(self) -> None:
        if self._original_editor_state is None:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件。")
            return
        if not self._original_editor_state.has_lyrics and self._lyrics_action != "replace":
            messagebox.showinfo("没有内嵌歌词", "当前 MP3 没有可移除的内嵌歌词。")
            return
        self._pending_lrc_path = None
        self._lyrics_action = "remove"
        self._set_lyrics_preview("")
        self.editor_lyrics_state.set("待保存：移除内嵌歌词")
        self.lyrics_state_label.configure(foreground="#c62828")
        self.lyrics_button_text.set("导入 LRC…")
        self.editor_status.set("歌词将在点击“保存到 MP3”后移除")

    def choose_editor_cover(self) -> None:
        if self._original_editor_state is None:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件。")
            return
        selected = filedialog.askopenfilename(
            title="选择封面图片",
            filetypes=[("封面图片", "*.jpg *.jpeg *.png"), ("JPEG 图片", "*.jpg *.jpeg"), ("PNG 图片", "*.png")],
        )
        if not selected:
            return
        temporary_path: Path | None = None
        try:
            dialog = CoverCropDialog(self, selected)
            self.wait_window(dialog)
            cropped = dialog.result
            if cropped is None:
                return
            output_format = "PNG" if Path(selected).suffix.lower() == ".png" else "JPEG"
            suffix = ".png" if output_format == "PNG" else ".jpg"
            if output_format == "JPEG" and cropped.mode not in {"RGB", "L"}:
                cropped = cropped.convert("RGB")
            temporary = tempfile.NamedTemporaryFile(prefix="sub2lrc-cover-", suffix=suffix, delete=False)
            temporary.close()
            temporary_path = Path(temporary.name)
            cropped.save(temporary_path, format=output_format, quality=95)
            cover_data = temporary_path.read_bytes()
        except (OSError, ValueError) as exc:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)
            messagebox.showerror("封面图片错误", str(exc))
            return
        self._cleanup_pending_cover()
        self._pending_cover_path = temporary_path
        self._cover_action = "replace"
        self._show_cover_data(cover_data)
        self.editor_cover_state.set(f"待保存：{Path(selected).name}（已裁剪为 1:1）")
        self.cover_state_label.configure(foreground="#8a5a00")
        self.cover_button_text.set("更换封面…")
        self.editor_status.set("已选择新封面，点击“保存到 MP3”后写入")

    def mark_cover_for_removal(self) -> None:
        if self._original_editor_state is None:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件。")
            return
        if not self._original_editor_state.has_cover and self._cover_action != "replace":
            messagebox.showinfo("没有内嵌封面", "当前 MP3 没有可移除的内嵌封面。")
            return
        self._cleanup_pending_cover()
        self._cover_action = "remove"
        self._show_cover_data(None, "保存后移除封面")
        self.editor_cover_state.set("待保存：移除内嵌封面")
        self.cover_state_label.configure(foreground="#c62828")
        self.cover_button_text.set("选择图片…")
        self.editor_status.set("")

    def save_editor(self) -> None:
        source_text = self.editor_mp3_path.get().strip()
        state = self._original_editor_state
        if not source_text or state is None:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件。")
            return
        edits = Mp3Edits(
            title=self.editor_title.get() if self.editor_title.get() != state.title else None,
            artist=self.editor_artist.get() if self.editor_artist.get() != state.artist else None,
            album=self.editor_album.get() if self.editor_album.get() != state.album else None,
            lyrics_path=self._pending_lrc_path if self._lyrics_action == "replace" else None,
            remove_lyrics=self._lyrics_action == "remove",
            cover_path=self._pending_cover_path if self._cover_action == "replace" else None,
            remove_cover=self._cover_action == "remove",
        )
        if not self._has_pending_changes() and self.editor_output_mode.get() == "overwrite":
            messagebox.showinfo("没有修改", "当前没有需要保存的修改。")
            return
        proceed, destination = self._choose_mp3_destination(source_text, self.editor_output_mode.get())
        if not proceed:
            return
        try:
            output = save_mp3_edits(source_text, edits, destination)
        except (OSError, MetadataError, Mp3EditorError) as exc:
            self.editor_status.set(f"保存失败：{exc}")
            messagebox.showerror("保存 MP3 失败", str(exc))
            return
        self._load_editor_file(output, show_error=False)
        self.editor_status.set(f"已保存：{output}")
        messagebox.showinfo("保存完成", f"所有修改已保存到 MP3。\n输出文件：{output}")

    def cancel_editor_changes(self) -> None:
        state = self._original_editor_state
        if state is None:
            messagebox.showinfo("Sub2LRC", "当前没有正在编辑的 MP3。")
            return
        if not self._has_pending_changes():
            self.editor_status.set("当前没有尚未保存的修改")
            return
        if not messagebox.askyesno("取消修改", "确定放弃当前所有尚未保存的修改吗？"):
            return

        self._cleanup_pending_cover()
        self._lyrics_action = "unchanged"
        self._pending_lrc_path = None
        self._cover_action = "unchanged"
        self.editor_title.set(state.title)
        self.editor_artist.set(state.artist)
        self.editor_album.set(state.album)
        self.editor_lyrics_state.set("已内嵌歌词" if state.has_lyrics else "未检测到内嵌歌词")
        self.lyrics_state_label.configure(foreground="#26734d" if state.has_lyrics else "#c62828")
        self.lyrics_button_text.set("更换歌词…" if state.has_lyrics else "导入 LRC…")
        self._set_lyrics_preview(state.lyrics)
        self.editor_cover_state.set("已内嵌封面" if state.has_cover else "未检测到内嵌封面")
        self.cover_state_label.configure(foreground="#26734d" if state.has_cover else "#c62828")
        self.cover_button_text.set("更换封面…" if state.has_cover else "选择图片…")
        self._show_cover_data(state.cover_data)
        self.editor_status.set("已取消尚未保存的修改，MP3 文件没有改变")

    def _has_pending_changes(self) -> bool:
        state = self._original_editor_state
        return bool(
            state
            and (
                self.editor_title.get() != state.title
                or self.editor_artist.get() != state.artist
                or self.editor_album.get() != state.album
                or self._lyrics_action != "unchanged"
                or self._cover_action != "unchanged"
            )
        )

    def _set_lyrics_preview(self, content: str) -> None:
        self.lyrics_preview.configure(state="normal")
        self.lyrics_preview.delete("1.0", "end")
        if content:
            self.lyrics_preview.insert("1.0", content)
        self.lyrics_preview.configure(state="disabled")

    def _show_cover_data(self, data: bytes | None, empty_text: str = "") -> None:
        self._cover_photo = None
        if not data:
            self.cover_preview.configure(image="", text=empty_text)
            return
        try:
            with Image.open(BytesIO(data)) as opened:
                preview = opened.copy()
            preview.thumbnail((180, 140), Image.Resampling.LANCZOS)
            self._cover_photo = ImageTk.PhotoImage(preview)
            self.cover_preview.configure(image=self._cover_photo, text="")
        except OSError:
            self.cover_preview.configure(image="", text="封面存在，但无法预览")

    def _choose_mp3_destination(self, source: str, mode: str) -> tuple[bool, Path | None]:
        if mode == "overwrite":
            return True, None
        source_path = Path(source)
        selected = filedialog.asksaveasfilename(
            title="另存为 MP3",
            initialdir=str(source_path.parent),
            initialfile=source_path.name,
            defaultextension=".mp3",
            filetypes=[("MP3 音频", "*.mp3")],
            confirmoverwrite=True,
        )
        return (True, Path(selected)) if selected else (False, None)

    def _cleanup_pending_cover(self) -> None:
        if self._pending_cover_path:
            try:
                self._pending_cover_path.unlink(missing_ok=True)
            except OSError:
                pass
        self._pending_cover_path = None

    def destroy(self) -> None:
        if self._preview_player is not None:
            self._preview_player.close()
        self._cleanup_pending_cover()
        super().destroy()

    def _build_converter_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)
        toolbar = ttk.Frame(root)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="选择歌词 / 字幕…", command=self.choose_files).pack(side="left")
        ttk.Button(toolbar, text="移除选中", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Button(toolbar, text="清空", command=self.clear_files).pack(side="left")
        files_frame = ttk.LabelFrame(root, text="待转换文件", padding=8)
        files_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        files_frame.columnconfigure(0, weight=1)
        self.file_list = tk.Listbox(files_frame, height=6, selectmode="extended")
        self.file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scrollbar.set)
        output = ttk.Frame(root)
        output.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="输出目录：").grid(row=0, column=0)
        ttk.Entry(output, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(output, text="浏览…", command=self.choose_output_dir).grid(row=0, column=2)
        ttk.Button(output, text="开始批量转换", command=self.convert_all).grid(row=0, column=3, padx=(12, 0))
        ttk.Label(output, text="输出格式：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        format_box = ttk.Combobox(
            output,
            textvariable=self.subtitle_output_format,
            values=("LRC", "SRT", "VTT"),
            state="readonly",
            width=10,
        )
        format_box.grid(row=1, column=1, sticky="w", padx=6, pady=(8, 0))
        format_box.bind("<<ComboboxSelected>>", self._update_subtitle_format_ui)
        self.subtitle_duration_label = ttk.Label(output, text="最后一句持续时间：")
        self.subtitle_duration_label.grid(row=1, column=2, sticky="e", pady=(8, 0))
        self.subtitle_duration_box = ttk.Spinbox(
            output, from_=0.1, to=3600, increment=0.5,
            textvariable=self.subtitle_final_duration, width=7
        )
        self.subtitle_duration_box.grid(row=1, column=3, sticky="w", padx=(6, 0), pady=(8, 0))
        self.subtitle_duration_unit = ttk.Label(output, text="秒（仅补全无结束时间的歌词）")
        self.subtitle_duration_unit.grid(row=1, column=4, sticky="w", padx=(4, 0), pady=(8, 0))
        self._update_subtitle_format_ui()
        preview_frame = ttk.LabelFrame(root, text="转换结果预览", padding=8)
        preview_frame.grid(row=3, column=0, sticky="nsew")
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        ttk.Label(preview_frame, text="结果：").grid(row=0, column=0, sticky="w")
        self.result_box = ttk.Combobox(preview_frame, state="readonly")
        self.result_box.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=(0, 6))
        self.result_box.bind("<<ComboboxSelected>>", self.show_selected_result)
        ttk.Button(preview_frame, text="当前结果另存为…", command=self.save_current).grid(
            row=0, column=2, pady=(0, 6)
        )
        self.preview = tk.Text(preview_frame, wrap="word", font=("Microsoft YaHei UI", 10), undo=False)
        self.preview.grid(row=1, column=0, columnspan=3, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview.yview)
        preview_scroll.grid(row=1, column=3, sticky="ns")
        self.preview.configure(yscrollcommand=preview_scroll.set, state="disabled")
        ttk.Label(root, textvariable=self.status, anchor="w").grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def choose_files(self) -> None:
        names = filedialog.askopenfilenames(
            title="选择歌词 / 字幕文件",
            filetypes=[
                ("支持的文件", "*.lrc *.srt *.vtt"),
                ("LRC 歌词", "*.lrc"), ("SRT 字幕", "*.srt"), ("VTT 字幕", "*.vtt"),
            ],
        )
        existing = {path.resolve() for path in self.sources}
        for name in names:
            path = Path(name)
            if path.resolve() not in existing:
                self.sources.append(path)
                self.file_list.insert("end", str(path))
                existing.add(path.resolve())
        if names:
            self.output_dir.set(str(Path(names[0]).parent))
            self.status.set(f"已选择 {len(self.sources)} 个文件")

    def remove_selected(self) -> None:
        for index in reversed(self.file_list.curselection()):
            self.file_list.delete(index)
            del self.sources[index]
        self.status.set(f"当前有 {len(self.sources)} 个待转换文件")

    def clear_files(self) -> None:
        self.sources.clear()
        self.file_list.delete(0, "end")
        self.status.set("已清空文件列表")

    def choose_output_dir(self) -> None:
        selected = filedialog.askdirectory(title="选择输出目录", initialdir=self.output_dir.get())
        if selected:
            self.output_dir.set(selected)

    def _update_subtitle_format_ui(self, _event: object | None = None) -> None:
        state = "disabled" if self.subtitle_output_format.get().lower() == "lrc" else "normal"
        self.subtitle_duration_box.configure(state=state)
        color = "#888888" if state == "disabled" else "#333333"
        self.subtitle_duration_label.configure(foreground=color)
        self.subtitle_duration_unit.configure(foreground=color)

    def convert_all(self) -> None:
        if not self.sources:
            messagebox.showinfo("Sub2LRC", "请先选择至少一个 LRC、SRT 或 VTT 文件。")
            return
        output_dir_text = self.output_dir.get().strip()
        if not output_dir_text:
            messagebox.showwarning("Sub2LRC", "请选择输出目录。")
            return
        output_dir = Path(output_dir_text)
        output_format = self.subtitle_output_format.get().lower()
        try:
            final_duration = float(self.subtitle_final_duration.get())
            if output_format != "lrc" and final_duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Sub2LRC", "最后一句持续时间必须是大于 0 的数字。")
            return
        successes = 0
        errors: list[str] = []
        self.results.clear()
        for source in self.sources:
            try:
                destination = unique_output_path(output_dir, source, output_format)
                convert_file(source, destination, output_format, final_duration)
                content = read_subtitle(destination)
                self.results[destination.name] = (destination, content)
                successes += 1
            except (OSError, SubtitleError) as exc:
                errors.append(f"{source.name}：{exc}")
        names = list(self.results)
        self.result_box["values"] = names
        if names:
            self.result_box.current(0)
            self.show_selected_result()
        self.status.set(f"转换完成：成功 {successes} 个，失败 {len(errors)} 个")
        if errors:
            messagebox.showwarning("部分文件转换失败", "\n".join(errors[:10]))
        elif successes:
            messagebox.showinfo(
                "转换完成",
                f"已生成 {successes} 个 {output_format.upper()} 文件。\n保存位置：{output_dir}",
            )

    def show_selected_result(self, _event: object | None = None) -> None:
        result = self.results.get(self.result_box.get())
        if not result:
            return
        path, content = result
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", content)
        self.preview.configure(state="disabled")
        self.status.set(f"预览：{path}")

    def save_current(self) -> None:
        result = self.results.get(self.result_box.get())
        if not result:
            messagebox.showinfo("Sub2LRC", "请先完成一次转换。")
            return
        original_path, content = result
        suffix = original_path.suffix.lower()
        labels = {".lrc": "LRC 歌词", ".srt": "SRT 字幕", ".vtt": "VTT 字幕"}
        selected = filedialog.asksaveasfilename(
            title="保存转换结果",
            initialfile=original_path.name,
            defaultextension=suffix,
            filetypes=[(labels.get(suffix, "文本文件"), f"*{suffix}")],
        )
        if selected:
            try:
                Path(selected).write_text(content, encoding="utf-8-sig", newline="\n")
                self.status.set(f"已保存：{selected}")
            except OSError as exc:
                messagebox.showerror("保存失败", str(exc))


def main() -> None:
    app = Sub2LRCApp()
    app.mainloop()


if __name__ == "__main__":
    main()
