"""Tkinter graphical interface for MediaAnvil."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

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
from .audio_metadata import (
    AudioFileInfo,
    AudioMetadata,
    AudioMetadataChanges,
    AudioMetadataError,
    export_metadata_cover,
    export_metadata_lyrics,
    read_metadata,
    write_metadata,
)
from .converter import SubtitleError, convert_file, read_subtitle, unique_output_path
from .cropper import CoverCropDialog
from .embedder import LyricsEmbedError, read_lrc
from .image_converter import (
    IMAGE_FORMAT_SPECS,
    ImageBatchConversionResult,
    ImageConversionError,
    ImageConversionSettings,
    convert_image_batch,
)
from .ui_theme import COLORS, SIZES, STATUS_STYLES, configure_theme
from .ui_widgets import ElidedLabel, attach_variable_tooltip, set_text_empty_state


PRODUCT_NAME = "MediaAnvil"
APP_VERSION = "0.3"


def _resource_path(relative_path: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / relative_path


class Sub2LRCApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(PRODUCT_NAME)
        self._app_icon: tk.PhotoImage | None = None
        try:
            self._app_icon = tk.PhotoImage(file=str(_resource_path("assets/mediaanvil-icon.png")))
            self.iconphoto(True, self._app_icon)
        except (OSError, tk.TclError):
            # A missing icon must never prevent the application from opening.
            self._app_icon = None
        self._sidebar_icon = self._app_icon.subsample(28, 28) if self._app_icon is not None else None
        self.geometry("1280x820")
        self.minsize(1050, 760)
        self.configure(background=COLORS["window"])
        configure_theme(self)

        self.sources: list[Path] = []
        self.results: dict[str, tuple[Path, str]] = {}
        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.subtitle_output_format = tk.StringVar(value="LRC")
        self.subtitle_final_duration = tk.StringVar(value="5")
        self.subtitle_advanced_visible = tk.BooleanVar(value=False)
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
        self.audio_file_progress = tk.DoubleVar(value=0.0)
        self._audio_running = False
        self.image_sources: list[Path] = []
        self.image_output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.image_format_label = tk.StringVar(value="JPG / JPEG")
        self.image_quality = tk.StringVar(value="90")
        self.image_current = tk.StringVar(value="请选择一张或多张图片")
        self.image_summary = tk.StringVar(value="")
        self.image_preview_name = tk.StringVar()
        self.image_preview_details = tk.StringVar()
        self.image_progress = tk.DoubleVar(value=0.0)
        self._image_preview_photo: ImageTk.PhotoImage | None = None
        self._image_running = False
        self.preview_audio_path = tk.StringVar()
        self.preview_audio_status = tk.StringVar(value="请选择一首音频进行预览")
        self.preview_audio_time = tk.StringVar(value="00:00 / 00:00")
        self.preview_current_time = tk.StringVar(value="00:00")
        self.preview_total_time = tk.StringVar(value="00:00")
        self.preview_track_name = tk.StringVar(value="尚未选择音频")
        self.preview_track_details = tk.StringVar(value="选择文件后显示格式与时长")
        self.preview_audio_position = tk.DoubleVar(value=0.0)
        self.preview_audio_volume = tk.DoubleVar(value=80.0)
        self._preview_player: AudioPreviewPlayer | None = None
        self._preview_timeline: tuple[LyricLine, ...] = ()
        self._preview_seeking = False
        self._preview_lyric_index: int | None = None
        self._preview_hover_line: int | None = None
        self._preview_pointer_xy: tuple[int, int] | None = None
        self._preview_padding_lines = 0
        self._preview_space_down = False
        self._preview_poll_job: str | None = None
        self.editor_mp3_path = tk.StringVar()
        self.editor_title = tk.StringVar()
        self.editor_artist = tk.StringVar()
        self.editor_album = tk.StringVar()
        self.editor_lyrics_state = tk.StringVar(value="尚未读取歌词")
        self.editor_cover_state = tk.StringVar(value="尚未读取封面")
        self.editor_output_mode = tk.StringVar(value="save_as")
        self.editor_status = tk.StringVar(value="请选择一个音频文件开始编辑")
        self.editor_audio_info = tk.StringVar(value="选择音频后显示格式、时长、码率、采样率、声道和大小")
        self.lyrics_button_text = tk.StringVar(value="导入 LRC…")
        self.cover_button_text = tk.StringVar(value="选择图片…")
        self._original_editor_state: AudioMetadata | None = None
        self._lyrics_action = "unchanged"
        self._pending_lrc_path: Path | None = None
        self._cover_action = "unchanged"
        self._pending_cover_path: Path | None = None
        self._cover_photo: ImageTk.PhotoImage | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, style="Page.TFrame")
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(shell, width=218, padding=(14, 18), style="Sidebar.TFrame")
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        brand = ttk.Frame(sidebar, style="Sidebar.TFrame")
        brand.grid(row=0, column=0, rowspan=2, sticky="ew", padx=6, pady=(0, 16))
        if self._sidebar_icon is not None:
            ttk.Label(brand, image=self._sidebar_icon, style="BrandSub.TLabel").pack(side="left", padx=(0, 10))
        else:
            ttk.Label(brand, text="▰", style="Brand.TLabel").pack(side="left", padx=(0, 10))
        ttk.Label(brand, text=PRODUCT_NAME, style="Brand.TLabel").pack(side="left", anchor="w")

        content = ttk.Frame(
            shell,
            padding=(SIZES["page_pad_x"], SIZES["page_pad_y"]),
            style="Page.TFrame",
        )
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        page_specs = (
            ("preview", "♫", "音频预览", self._build_preview_tab),
            ("editor", "◇", "音频标签编辑", self._build_editor_tab),
            ("converter", "A", "歌词 / 字幕转换", self._build_converter_tab),
            ("audio", "⇄", "音频格式转换", self._build_audio_tab),
            ("image", "▧", "图片格式转换", self._build_image_tab),
            ("settings", "⚙", "设置", self._build_settings_page),
            ("about", "ⓘ", "关于", self._build_about_page),
        )
        self.pages: dict[str, ttk.Frame] = {}
        self.nav_buttons: dict[str, tk.Frame] = {}
        self.nav_icon_labels: dict[str, tk.Label] = {}
        self.nav_text_labels: dict[str, tk.Label] = {}
        for index, (key, icon, label, builder) in enumerate(page_specs):
            page = ttk.Frame(content, padding=4, style="Page.TFrame")
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page
            builder(page)
            nav_row = index + 2 if index < 5 else index + 4
            button = tk.Frame(
                sidebar,
                relief="flat",
                borderwidth=0,
                background=COLORS["sidebar"],
                cursor="hand2",
            )
            button.grid(row=nav_row, column=0, sticky="ew", pady=2)
            button.columnconfigure(1, weight=1)
            icon_label = tk.Label(
                button,
                text=icon,
                width=3,
                anchor="center",
                borderwidth=0,
                background=COLORS["sidebar"],
                foreground=COLORS["text"],
                font=("Microsoft YaHei UI", 10, "bold"),
                cursor="hand2",
            )
            icon_label.grid(row=0, column=0, padx=(9, 3), pady=11)
            text_label = tk.Label(
                button,
                text=label,
                anchor="w",
                borderwidth=0,
                background=COLORS["sidebar"],
                foreground=COLORS["text"],
                font=("Microsoft YaHei UI", 10, "bold"),
                cursor="hand2",
            )
            text_label.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=11)
            for widget in (button, icon_label, text_label):
                widget.bind("<Button-1>", lambda _event, page_key=key: self.show_page(page_key))
                widget.bind("<Enter>", lambda _event, page_key=key: self._set_nav_hover(page_key, True))
                widget.bind("<Leave>", lambda _event, page_key=key: self._set_nav_hover(page_key, False))
            self.nav_buttons[key] = button
            self.nav_icon_labels[key] = icon_label
            self.nav_text_labels[key] = text_label
        sidebar.rowconfigure(7, weight=1)
        ttk.Label(sidebar, text=f"v{APP_VERSION}", style="BrandSub.TLabel").grid(
            row=11, column=0, sticky="w", padx=8, pady=(12, 0)
        )
        self.preview_tab = self.pages["preview"]
        self.current_page = ""
        self.show_page("preview")
        self.bind("<KeyPress-space>", self._toggle_preview_with_space)
        self.bind("<KeyRelease-space>", self._release_preview_space)

    def show_page(self, key: str) -> None:
        if key not in self.pages:
            raise KeyError(f"未知页面：{key}")
        self.current_page = key
        self.pages[key].tkraise()
        for page_key, button in self.nav_buttons.items():
            selected = page_key == key
            background = COLORS["blue"] if selected else COLORS["sidebar"]
            foreground = "#ffffff" if selected else COLORS["text"]
            for widget in (button, self.nav_icon_labels[page_key], self.nav_text_labels[page_key]):
                widget.configure(background=background)
            self.nav_icon_labels[page_key].configure(foreground=foreground)
            self.nav_text_labels[page_key].configure(foreground=foreground)

    def _set_nav_hover(self, key: str, hovering: bool) -> None:
        if key == self.current_page:
            return
        background = COLORS["blue_soft"] if hovering else COLORS["sidebar"]
        foreground = COLORS["blue"] if hovering else COLORS["text"]
        for widget in (self.nav_buttons[key], self.nav_icon_labels[key], self.nav_text_labels[key]):
            widget.configure(background=background)
        self.nav_icon_labels[key].configure(foreground=foreground)
        self.nav_text_labels[key].configure(foreground=foreground)

    def _build_settings_page(self, root: ttk.Frame) -> None:
        self._page_header(root, "⚙", "设置", "调整应用程序的常用选项")
        card = ttk.LabelFrame(root, text="常规", padding=SIZES["card_pad"], style="Card.TLabelframe")
        card.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(card, text="当前版本暂时没有需要配置的全局选项。", style="Card.TLabel").pack(anchor="w")
        ttk.Label(card, text="各转换参数会保存在对应功能页面中。", style="CardMuted.TLabel").pack(anchor="w", pady=(8, 0))

    def _build_about_page(self, root: ttk.Frame) -> None:
        self._page_header(root, "ⓘ", "关于", f"{PRODUCT_NAME} 本地多媒体工具箱")
        card = ttk.LabelFrame(root, text=f"{PRODUCT_NAME} v{APP_VERSION}", padding=SIZES["card_pad"], style="Card.TLabelframe")
        card.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(card, text="一个简单、离线的 Windows 多媒体处理工具。", style="Card.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="支持音频预览与同步歌词、音频标签编辑、歌词/字幕互转、音频格式转换和图片格式转换。",
            style="CardMuted.TLabel",
            wraplength=760,
        ).pack(anchor="w", pady=(10, 0))

    def _page_header(self, root: ttk.Frame, icon: str, title: str, subtitle: str) -> ttk.Frame:
        root.columnconfigure(0, weight=1)
        header = ttk.Frame(root, style="Page.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(header, text=icon, font=("Microsoft YaHei UI", 26, "bold"), foreground=COLORS["blue"]).pack(side="left", padx=(0, 14))
        text = ttk.Frame(header, style="Page.TFrame")
        text.pack(side="left", fill="x", expand=True)
        ttk.Label(text, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(text, text=subtitle, style="Subtitle.TLabel").pack(anchor="w", pady=(3, 0))
        return header

    @staticmethod
    def _set_status_style(label: ttk.Label, kind: str) -> None:
        label.configure(style=STATUS_STYLES.get(kind, STATUS_STYLES["info"]))

    @staticmethod
    def _show_empty_overlay(label: ttk.Label, visible: bool, target: tk.Widget) -> None:
        if visible:
            label.place(in_=target, relx=0.5, rely=0.5, anchor="center")
        else:
            label.place_forget()

    def _build_preview_tab(self, root: ttk.Frame) -> None:
        self._create_preview_scale_style()
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        self._page_header(root, "♫", "音频预览", "播放本地音频并查看同步歌词")

        source = ttk.LabelFrame(root, text="选择音频", padding=12, style="Card.TLabelframe")
        source.grid(row=1, column=0, sticky="ew", pady=(14, 12))
        source.columnconfigure(0, weight=1)
        self.preview_path_entry = ttk.Entry(source, textvariable=self.preview_audio_path, state="readonly")
        self.preview_path_entry.grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        attach_variable_tooltip(self.preview_path_entry, self.preview_audio_path)
        self.preview_select_button = ttk.Button(
            source, text="选择音频文件…", command=self.choose_preview_audio, style="Secondary.TButton"
        )
        self.preview_select_button.grid(row=0, column=1)

        body = ttk.Frame(root, style="Page.TFrame")
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=2, uniform="preview")
        body.columnconfigure(1, weight=3, uniform="preview")
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Page.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        info = ttk.LabelFrame(left, text="歌曲信息", padding=SIZES["card_pad"], style="Card.TLabelframe")
        info.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            info, text="♫", style="Info.Status.TLabel", font=("Microsoft YaHei UI", 22, "bold")
        ).pack(side="left", padx=(0, 12))
        track_text = ttk.Frame(info, style="Card.TFrame")
        track_text.pack(side="left", fill="x", expand=True)
        self.preview_track_title_label = ElidedLabel(track_text, textvariable=self.preview_track_name, style="Card.TLabel", font=("Microsoft YaHei UI", 12, "bold"), anchor="w")
        self.preview_track_title_label.pack(fill="x", anchor="w")
        ttk.Label(track_text, textvariable=self.preview_track_details, style="CardMuted.TLabel", wraplength=320).pack(anchor="w", pady=(5, 0))

        controls = ttk.LabelFrame(left, text="播放控制", padding=SIZES["card_pad"], style="Card.TLabelframe")
        controls.grid(row=1, column=0, sticky="nsew")
        controls.columnconfigure(0, weight=1)
        control_buttons = ttk.Frame(controls, style="Card.TFrame")
        control_buttons.grid(row=0, column=0, sticky="ew")
        control_buttons.columnconfigure((0, 1, 2), weight=1)
        self.preview_play_button = ttk.Button(control_buttons, text="▶  播放", command=self.play_preview_audio, style="Accent.TButton")
        self.preview_play_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.preview_pause_button = ttk.Button(
            control_buttons, text="Ⅱ  暂停", command=self.pause_preview_audio, style="Secondary.TButton"
        )
        self.preview_pause_button.grid(row=0, column=1, sticky="ew", padx=5)
        self.preview_stop_button = ttk.Button(
            control_buttons, text="■  停止", command=self.stop_preview_audio, style="Secondary.TButton"
        )
        self.preview_stop_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))
        for button in (self.preview_select_button, self.preview_play_button, self.preview_pause_button, self.preview_stop_button):
            button.bind("<KeyPress-space>", self._toggle_preview_with_space)
            button.bind("<KeyRelease-space>", self._release_preview_space)
        timeline = ttk.Frame(controls, style="Card.TFrame")
        timeline.grid(row=1, column=0, sticky="ew", pady=(22, 0))
        ttk.Label(timeline, textvariable=self.preview_current_time, style="CardMuted.TLabel").grid(row=0, column=0, padx=(0, 8))
        self.preview_audio_scale = ttk.Scale(
            timeline, from_=0, to=1, variable=self.preview_audio_position,
            orient="horizontal", style="Preview.Horizontal.TScale", length=240
        )
        self.preview_audio_scale.grid(row=0, column=1)
        self.preview_audio_scale.bind("<ButtonPress-1>", self._begin_preview_seek)
        self.preview_audio_scale.bind("<B1-Motion>", self._drag_preview_seek)
        self.preview_audio_scale.bind("<ButtonRelease-1>", self._end_preview_seek)
        ttk.Label(timeline, textvariable=self.preview_total_time, style="CardMuted.TLabel", anchor="e").grid(row=0, column=2, padx=(8, 0))
        volume = ttk.Frame(controls, style="Card.TFrame")
        volume.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        ttk.Label(volume, text="音量", style="Card.TLabel").grid(row=0, column=0, padx=(0, 10))
        self.preview_volume_scale = ttk.Scale(
            volume, from_=0, to=100, variable=self.preview_audio_volume,
            orient="horizontal", style="Preview.Horizontal.TScale", length=240
        )
        self.preview_volume_scale.grid(row=0, column=1)
        self.preview_volume_scale.bind("<ButtonPress-1>", self._begin_preview_volume)
        self.preview_volume_scale.bind("<B1-Motion>", self._drag_preview_volume)
        self.preview_volume_scale.bind("<ButtonRelease-1>", self._end_preview_volume)
        self.preview_status_label = ttk.Label(controls, textvariable=self.preview_audio_status, style=STATUS_STYLES["info"], wraplength=360)
        self.preview_status_label.grid(row=3, column=0, sticky="w", pady=(16, 0))

        lyrics = ttk.LabelFrame(body, text="同步歌词", padding=12, style="Card.TLabelframe")
        lyrics.grid(row=0, column=1, sticky="nsew")
        lyrics.columnconfigure(0, weight=1)
        lyrics.rowconfigure(0, weight=1)
        self.preview_lyrics = tk.Text(
            lyrics, wrap="word", font=("Microsoft YaHei UI", 11), state="disabled", spacing2=6,
            relief="flat", borderwidth=0, background="#ffffff", foreground=COLORS["text"], padx=12, pady=12
        )
        self.preview_lyrics.grid(row=0, column=0, sticky="nsew")
        lyric_scroll = ttk.Scrollbar(lyrics, orient="vertical", command=self.preview_lyrics.yview)
        lyric_scroll.grid(row=0, column=1, sticky="ns")
        def update_lyric_scroll(first: str, last: str) -> None:
            lyric_scroll.set(first, last)
            self.after_idle(self._refresh_preview_hover)
        self.preview_lyrics.configure(yscrollcommand=update_lyric_scroll)
        self.preview_lyrics.tag_configure("center", justify="center", spacing1=3, spacing3=3)
        self.preview_lyrics.tag_configure("current", foreground="#b8860b")
        self.preview_lyrics.tag_configure("hover", background="#fff4cc")
        self.preview_lyrics.bind("<Button-1>", self._click_preview_lyric)
        self.preview_lyrics.bind("<Motion>", self._hover_preview_lyric)
        self.preview_lyrics.bind("<Leave>", self._leave_preview_lyrics)
        set_text_empty_state(self.preview_lyrics, "♫", "尚未加载歌词", "选择音频后将自动查找同名或内嵌歌词")
        self._preview_poll_job = self.after(200, self._poll_preview_audio)

    def _create_preview_scale_style(self) -> None:
        large = Image.new("RGBA", (36, 36), (0, 0, 0, 0))
        draw = ImageDraw.Draw(large)
        draw.ellipse((2, 2, 33, 33), fill="#6faee5", outline="#5596cb", width=2)
        thumb = large.resize((18, 18), Image.Resampling.LANCZOS)
        self._preview_scale_thumb_photo = ImageTk.PhotoImage(thumb)
        track = Image.new("RGBA", (12, 8), (0, 0, 0, 0))
        ImageDraw.Draw(track).rounded_rectangle((0, 1, 11, 6), radius=3, fill="#e2eaf3")
        self._preview_scale_track_photo = ImageTk.PhotoImage(track)
        style = ttk.Style(self)
        style.configure(
            "Preview.Horizontal.TScale",
            background="#ffffff",
            troughcolor="#ffffff",
            bordercolor="#ffffff",
        )
        slider_element = "Preview.Horizontal.Scale.slider"
        track_element = "Preview.Horizontal.Scale.track"
        try:
            style.element_create(slider_element, "image", self._preview_scale_thumb_photo, border=0)
            style.element_create(track_element, "image", self._preview_scale_track_photo, border=5, sticky="ew")
        except tk.TclError:
            pass
        style.layout(
            "Preview.Horizontal.TScale",
            [("Scale.focus", {"sticky": "nswe", "children": [
                ("Horizontal.Scale.trough", {"sticky": "nswe", "children": [
                    (track_element, {"sticky": "we"}),
                    (slider_element, {"side": "left", "sticky": ""}),
                ]}),
            ]})],
        )

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
            player.set_volume(round(self.preview_audio_volume.get()))
        except AudioPreviewError as exc:
            self._preview_player = None
            messagebox.showerror("无法预览音频", str(exc))
            return
        self._preview_player = player
        self.preview_audio_path.set(selected)
        selected_path = Path(selected)
        self.preview_track_name.set(selected_path.stem)
        self.preview_track_details.set(f"{selected_path.suffix.upper().lstrip('.')} 音频  ·  总时长 {self._format_preview_duration(duration)}")
        self.preview_audio_position.set(0.0)
        self.preview_audio_scale.configure(to=duration)
        self._preview_lyric_index = None
        self._preview_hover_line = None
        self._preview_pointer_xy = None
        lyrics_error: str | None = None
        try:
            _lyrics, self._preview_timeline = load_audio_lyrics(selected)
        except (OSError, SubtitleError) as exc:
            self._preview_timeline = ()
            lyrics_error = str(exc)
            self.preview_audio_status.set(f"音频已载入，歌词读取失败：{exc}")
            self._set_status_style(self.preview_status_label, "warning")
        else:
            self.preview_audio_status.set("音频与歌词已载入" if self._preview_timeline else "音频已载入（没有同步歌词）")
            self._set_status_style(self.preview_status_label, "success" if self._preview_timeline else "info")
        if self._preview_timeline:
            self.preview_lyrics.configure(state="normal")
            self.preview_lyrics.delete("1.0", "end")
            self.preview_lyrics.insert("1.0", "\n".join(line.text for line in self._preview_timeline))
            self.preview_lyrics.update_idletasks()
            line_info = self.preview_lyrics.dlineinfo("1.0")
            line_height = line_info[3] if line_info is not None else 24
            self._preview_padding_lines = max(
                1, round(self.preview_lyrics.winfo_height() / max(1, line_height) / 2)
            )
            clean_lyrics = "\n".join(line.text for line in self._preview_timeline)
            padding = "\n" * self._preview_padding_lines
            self.preview_lyrics.delete("1.0", "end")
            self.preview_lyrics.insert("1.0", f"{padding}{clean_lyrics}{padding}")
            self.preview_lyrics.tag_add("center", "1.0", "end")
            self.preview_lyrics.configure(state="disabled")
        else:
            self._preview_padding_lines = 0
            if lyrics_error:
                set_text_empty_state(self.preview_lyrics, "!", "歌词读取失败", "音频仍可正常播放，请检查歌词文件格式")
            else:
                set_text_empty_state(self.preview_lyrics, "♫", "没有同步歌词", "音频可以正常播放，也可以添加同名 LRC 文件")
        if self._preview_timeline:
            self._center_preview_lyric_line(f"{self._preview_padding_lines + 1}.0")
        self._update_preview_time(0.0, duration)

    @staticmethod
    def _format_preview_duration(value: float) -> str:
        total = max(0, round(value))
        minutes, seconds = divmod(total, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def play_preview_audio(self) -> None:
        if self._preview_player is None:
            messagebox.showinfo(PRODUCT_NAME, "请先选择一首音频。")
            return
        try:
            self._preview_player.play()
            self.preview_audio_status.set("正在播放")
            self._set_status_style(self.preview_status_label, "success")
        except AudioPreviewError as exc:
            messagebox.showerror("播放失败", str(exc))

    def pause_preview_audio(self) -> None:
        if self._preview_player is None:
            return
        try:
            self._preview_player.pause()
            if self._preview_player.state == PlaybackState.PAUSED:
                self.preview_audio_status.set("已暂停")
                self._set_status_style(self.preview_status_label, "info")
        except AudioPreviewError as exc:
            messagebox.showerror("暂停失败", str(exc))

    def stop_preview_audio(self) -> None:
        if self._preview_player is None:
            return
        self._preview_player.stop()
        self.preview_audio_position.set(0.0)
        self._update_preview_time(0.0, self._preview_player.duration)
        self._highlight_preview_lyric(None)
        self.preview_audio_status.set("已停止")
        self._set_status_style(self.preview_status_label, "info")

    def _toggle_preview_with_space(self, _event: tk.Event) -> str | None:
        if self.current_page != "preview":
            return None
        if self._preview_space_down:
            return "break"
        self._preview_space_down = True
        if self._preview_player is None:
            return "break"
        if self._preview_player.state == PlaybackState.PLAYING:
            self.pause_preview_audio()
        else:
            self.play_preview_audio()
        return "break"

    def _release_preview_space(self, _event: tk.Event) -> str | None:
        self._preview_space_down = False
        return "break" if self.current_page == "preview" else None

    @staticmethod
    def _scale_value_from_x(scale: ttk.Scale, x: int, lower: float, upper: float) -> float:
        thumb_radius = 9
        usable_width = max(1, scale.winfo_width() - thumb_radius * 2)
        fraction = min(1.0, max(0.0, (x - thumb_radius) / usable_width))
        return lower + fraction * (upper - lower)

    def _preview_seek_position_from_x(self, x: int) -> float:
        duration = self._preview_player.duration if self._preview_player is not None else 0.0
        position = self._scale_value_from_x(self.preview_audio_scale, x, 0.0, duration)
        self.preview_audio_position.set(position)
        self._update_preview_time(position, duration)
        self._highlight_preview_lyric(current_lyric_index(self._preview_timeline, position))
        return position

    def _begin_preview_seek(self, event: tk.Event) -> str:
        self._preview_seeking = True
        self._preview_seek_position_from_x(event.x)
        return "break"

    def _drag_preview_seek(self, event: tk.Event) -> str:
        self._preview_seek_position_from_x(event.x)
        return "break"

    def _end_preview_seek(self, event: tk.Event) -> str:
        position = self._preview_seek_position_from_x(event.x)
        self._preview_seeking = False
        if self._preview_player is not None:
            self._preview_player.seek(position)
            self.preview_audio_status.set("已跳转到所选进度")
            self._set_status_style(self.preview_status_label, "info")
        return "break"

    def _preview_volume_from_x(self, x: int) -> int:
        volume = round(self._scale_value_from_x(self.preview_volume_scale, x, 0.0, 100.0))
        self.preview_audio_volume.set(volume)
        return volume

    def _begin_preview_volume(self, event: tk.Event) -> str:
        self._preview_volume_from_x(event.x)
        return "break"

    def _drag_preview_volume(self, event: tk.Event) -> str:
        self._preview_volume_from_x(event.x)
        return "break"

    def _end_preview_volume(self, event: tk.Event) -> str:
        volume = self._preview_volume_from_x(event.x)
        if self._preview_player is None:
            return "break"
        try:
            self._preview_player.set_volume(volume)
        except AudioPreviewError as exc:
            messagebox.showerror("音量调整失败", str(exc))
        return "break"

    def _poll_preview_audio(self) -> None:
        self._preview_poll_job = None
        player = self._preview_player
        if player is not None:
            position = player.position
            if not self._preview_seeking:
                self.preview_audio_position.set(position)
                self._update_preview_time(position, player.duration)
                lyric_index = current_lyric_index(self._preview_timeline, position)
                self._highlight_preview_lyric(lyric_index)
            self._refresh_preview_hover()
            if player.state == PlaybackState.STOPPED and position >= player.duration:
                self.preview_audio_status.set("播放完成")
                self._set_status_style(self.preview_status_label, "success")
        self._preview_poll_job = self.after(200, self._poll_preview_audio)

    def _highlight_preview_lyric(self, index: int | None, *, force_scroll: bool = False) -> None:
        if index == self._preview_lyric_index and not force_scroll:
            return
        self._preview_lyric_index = index
        self.preview_lyrics.configure(state="normal")
        self.preview_lyrics.tag_remove("current", "1.0", "end")
        if index is not None:
            line = self._preview_padding_lines + index + 1
            start, end = f"{line}.0", f"{line}.end"
            self.preview_lyrics.tag_add("current", start, end)
            self._center_preview_lyric_line(start)
        self.preview_lyrics.configure(state="disabled")

    def _center_preview_lyric_line(self, text_index: str) -> None:
        """Center a visible lyric using its actual rendered position, not a line estimate."""
        self.preview_lyrics.see(text_index)
        self.preview_lyrics.update_idletasks()
        for _attempt in range(2):
            line_info = self.preview_lyrics.dlineinfo(text_index)
            if line_info is None:
                return
            _x, y, _width, line_height, _baseline = line_info
            anchor_y = self.preview_lyrics.winfo_height() * 0.48
            offset = y + line_height / 2 - anchor_y
            display_lines = round(offset / max(1, line_height))
            if display_lines == 0:
                return
            self.preview_lyrics.yview_scroll(display_lines, "units")
            self.preview_lyrics.update_idletasks()

    def _hover_preview_lyric(self, event: tk.Event) -> None:
        self._preview_pointer_xy = (event.x, event.y)
        self._refresh_preview_hover()

    def _refresh_preview_hover(self) -> None:
        hover_line = None
        if self._preview_pointer_xy is not None:
            hover_line = self._preview_line_at_coordinates(*self._preview_pointer_xy)
        if hover_line == self._preview_hover_line:
            return
        self._preview_hover_line = hover_line
        self.preview_lyrics.configure(state="normal")
        self.preview_lyrics.tag_remove("hover", "1.0", "end")
        if hover_line is not None:
            self.preview_lyrics.tag_add("hover", f"{hover_line}.0", f"{hover_line + 1}.0")
            self.preview_lyrics.configure(cursor="hand2")
        else:
            self.preview_lyrics.configure(cursor="arrow")
        self.preview_lyrics.configure(state="disabled")

    def _leave_preview_lyrics(self, _event: tk.Event) -> None:
        self._preview_pointer_xy = None
        self._preview_hover_line = None
        self.preview_lyrics.configure(state="normal")
        self.preview_lyrics.tag_remove("hover", "1.0", "end")
        self.preview_lyrics.configure(state="disabled", cursor="arrow")

    def _preview_line_at_coordinates(self, x: int, y_pointer: int) -> int | None:
        display_line = int(self.preview_lyrics.index(f"@{x},{y_pointer}").split(".")[0])
        lyric_line = display_line - self._preview_padding_lines
        if lyric_index_from_display_line(self._preview_timeline, lyric_line) is None:
            return None
        line_info = self.preview_lyrics.dlineinfo(f"{display_line}.0")
        if line_info is None:
            return None
        _x, y, _width, height, _baseline = line_info
        return display_line if y <= y_pointer < y + height else None

    def _click_preview_lyric(self, event: tk.Event) -> str | None:
        player = self._preview_player
        if player is None or not self._preview_timeline:
            return None
        clicked_line = self._preview_line_at_coordinates(event.x, event.y)
        if clicked_line is None:
            return None
        lyric_line = clicked_line - self._preview_padding_lines
        index = lyric_index_from_display_line(self._preview_timeline, lyric_line)
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
        self._highlight_preview_lyric(index, force_scroll=True)
        self.preview_audio_status.set("已跳转到所选歌词")
        self._set_status_style(self.preview_status_label, "info")
        return "break"

    def _update_preview_time(self, position: float, duration: float) -> None:
        def format_time(value: float) -> str:
            total = max(0, round(value))
            minutes, seconds = divmod(total, 60)
            return f"{minutes:02d}:{seconds:02d}"
        current = format_time(position)
        total = format_time(duration)
        self.preview_current_time.set(current)
        self.preview_total_time.set(total)
        self.preview_audio_time.set(f"{current} / {total}")

    def _build_image_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        self._page_header(root, "▧", "图片格式转换", "支持 JPG、PNG、WebP、BMP 批量互转")

        body = ttk.Frame(root, style="Page.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(14, 10))
        body.columnconfigure(0, weight=1, uniform="image")
        body.columnconfigure(1, weight=1, uniform="image")
        body.rowconfigure(0, weight=1)
        files = ttk.LabelFrame(body, text="1  选择图片", padding=12, style="Card.TLabelframe")
        files.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        files.columnconfigure(0, weight=1)
        files.rowconfigure(2, weight=1)
        toolbar = ttk.Frame(files, style="Card.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="选择图片…", command=self.choose_image_files, style="Compact.TButton").pack(side="left")
        ttk.Button(toolbar, text="移除选中", command=self.remove_selected_images, style="Compact.TButton").pack(side="left", padx=6)
        ttk.Button(toolbar, text="清空", command=self.clear_image_files, style="CompactDanger.TButton").pack(side="left")
        ttk.Label(files, text="文件路径", style="CardMuted.TLabel").grid(row=1, column=0, sticky="w", padx=5, pady=(0, 4))
        self.image_file_list = tk.Listbox(files, height=10, selectmode="extended", relief="flat", borderwidth=1, background="#ffffff", foreground=COLORS["text"])
        self.image_file_list.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(files, orient="vertical", command=self.image_file_list.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        image_horizontal = ttk.Scrollbar(files, orient="horizontal", command=self.image_file_list.xview)
        image_horizontal.grid(row=3, column=0, sticky="ew")
        self.image_file_list.configure(yscrollcommand=scrollbar.set, xscrollcommand=image_horizontal.set)
        self.image_file_list.bind("<<ListboxSelect>>", self._show_selected_image_preview)
        self.image_files_empty = ttk.Label(files, text="▧\n尚未选择图片\n点击上方按钮添加一张或多张图片", justify="center", style="CardMuted.TLabel")
        self._show_empty_overlay(self.image_files_empty, True, self.image_file_list)

        right = ttk.Frame(body, style="Page.TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        settings = ttk.LabelFrame(right, text="2  转换设置", padding=12, style="Card.TLabelframe")
        settings.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="输出格式", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=5)
        format_box = ttk.Combobox(
            settings,
            textvariable=self.image_format_label,
            values=tuple(spec.label for spec in IMAGE_FORMAT_SPECS.values()),
            state="readonly",
            width=18,
        )
        format_box.grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        format_box.bind("<<ComboboxSelected>>", self._update_image_parameter_ui)
        self.image_quality_label = ttk.Label(settings, text="图片质量", style="Card.TLabel")
        self.image_quality_label.grid(row=1, column=0, sticky="w", pady=5)
        self.image_quality_box = ttk.Spinbox(
            settings, from_=1, to=100, increment=1, textvariable=self.image_quality, width=10
        )
        self.image_quality_box.grid(row=1, column=1, sticky="w", padx=8, pady=5)
        ttk.Label(settings, text="输出目录", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=5)
        self.image_output_entry = ttk.Entry(settings, textvariable=self.image_output_dir)
        self.image_output_entry.grid(
            row=2, column=1, sticky="ew", padx=8, pady=5
        )
        attach_variable_tooltip(self.image_output_entry, self.image_output_dir)
        ttk.Button(settings, text="浏览…", command=self.choose_image_output_dir).grid(row=2, column=2, pady=6)
        self.image_transparency_hint = ttk.Label(
            settings,
            text="保持原始宽高；透明图片转为 JPG 或 BMP 时使用白色背景。",
            style="CardMuted.TLabel",
            wraplength=330,
        )
        self.image_transparency_hint.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        preview = ttk.LabelFrame(right, text="预览（当前选中）", padding=12, style="Card.TLabelframe")
        preview.grid(row=1, column=0, sticky="nsew")
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(0, weight=1)
        self.image_preview_box = ttk.Frame(preview, width=360, height=230, style="Card.TFrame")
        self.image_preview_box.grid(row=0, column=0, sticky="nsew")
        self.image_preview_box.grid_propagate(False)
        self.image_preview_box.columnconfigure(0, weight=1)
        self.image_preview_box.rowconfigure(0, weight=1)
        self.image_preview_label = ttk.Label(
            self.image_preview_box,
            text="▧\n\n尚未选择图片\n选择列表中的图片后显示预览",
            anchor="center", justify="center", style="CardMuted.TLabel"
        )
        self.image_preview_label.grid(row=0, column=0, sticky="nsew")
        ElidedLabel(preview, textvariable=self.image_preview_name, style="Card.TLabel", font=("Microsoft YaHei UI", 10, "bold"), anchor="w").grid(row=1, column=0, sticky="ew", pady=(10, 2))
        ttk.Label(preview, textvariable=self.image_preview_details, style="CardMuted.TLabel").grid(row=2, column=0, sticky="w")

        progress_area = ttk.LabelFrame(root, text="3  转换进度", padding=12, style="Card.TLabelframe")
        progress_area.grid(row=2, column=0, sticky="ew")
        progress_area.columnconfigure(0, weight=1)
        self.image_status_label = ttk.Label(progress_area, textvariable=self.image_current, anchor="w", style=STATUS_STYLES["info"])
        self.image_status_label.grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Progressbar(progress_area, variable=self.image_progress, maximum=100).grid(
            row=1, column=0, sticky="ew", pady=(8, 4)
        )
        self.image_summary_label = ttk.Label(progress_area, textvariable=self.image_summary, anchor="w", style=STATUS_STYLES["info"])
        self.image_summary_label.grid(
            row=2, column=0, sticky="ew"
        )
        self.image_start_button = ttk.Button(progress_area, text="开始转换", command=self.start_image_conversion, style="Accent.TButton")
        self.image_start_button.grid(row=0, column=1, rowspan=3, sticky="ns", padx=(18, 0), ipadx=20)
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
            self._set_status_style(self.image_status_label, "info")
            if not self.image_file_list.curselection():
                self.image_file_list.selection_set(0)
                self._show_selected_image_preview()
        self._show_empty_overlay(self.image_files_empty, not self.image_sources, self.image_file_list)

    def remove_selected_images(self) -> None:
        if self._image_running:
            return
        for index in reversed(self.image_file_list.curselection()):
            self.image_file_list.delete(index)
            del self.image_sources[index]
        self.image_current.set(f"当前有 {len(self.image_sources)} 张待转换图片")
        self._set_status_style(self.image_status_label, "info")
        self._show_selected_image_preview()
        self._show_empty_overlay(self.image_files_empty, not self.image_sources, self.image_file_list)

    def clear_image_files(self) -> None:
        if self._image_running:
            return
        self.image_sources.clear()
        self.image_file_list.delete(0, "end")
        self.image_current.set("已清空图片列表")
        self._set_status_style(self.image_status_label, "info")
        self.image_progress.set(0.0)
        self.image_summary.set("")
        self._clear_image_preview()
        self._show_empty_overlay(self.image_files_empty, True, self.image_file_list)

    def _clear_image_preview(self) -> None:
        self._image_preview_photo = None
        self.image_preview_label.configure(
            image="", text="▧\n\n尚未选择图片\n选择列表中的图片后显示预览",
            style="CardMuted.TLabel", justify="center"
        )
        self.image_preview_name.set("")
        self.image_preview_details.set("")

    def _show_selected_image_preview(self, _event: object | None = None) -> None:
        selection = self.image_file_list.curselection()
        if not selection or selection[0] >= len(self.image_sources):
            self._clear_image_preview()
            return
        path = self.image_sources[selection[0]]
        try:
            with Image.open(path) as opened:
                width, height = opened.size
                format_name = opened.format or path.suffix.lstrip(".").upper()
                image = opened.convert("RGBA")
            image.thumbnail((360, 220), Image.Resampling.LANCZOS)
            self._image_preview_photo = ImageTk.PhotoImage(image)
            self.image_preview_label.configure(image=self._image_preview_photo, text="", style="Card.TLabel")
            size_mb = path.stat().st_size / 1024 / 1024
            self.image_preview_name.set(path.name)
            self.image_preview_details.set(f"{width} × {height}  ·  {format_name}  ·  {size_mb:.2f} MB")
        except (OSError, ValueError):
            self._image_preview_photo = None
            self.image_preview_label.configure(image="", text="!\n\n无法预览此图片\n转换时会给出明确错误", style="Warning.Status.TLabel", justify="center")
            self.image_preview_name.set(path.name)
            self.image_preview_details.set("图片无法读取，但批量转换时会给出明确错误。")

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
            messagebox.showinfo(PRODUCT_NAME, "请至少选择一张图片。")
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
        self._set_status_style(self.image_status_label, "info")
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
        self._set_status_style(self.image_status_label, "info")

    def _finish_image_conversion(
        self, result: ImageBatchConversionResult | None, error: ImageConversionError | None
    ) -> None:
        self._image_running = False
        self.image_start_button.configure(state="normal")
        if error is not None:
            self.image_current.set("转换失败")
            self._set_status_style(self.image_status_label, "error")
            messagebox.showerror("图片转换失败", str(error))
            return
        if result is None:
            return
        successes = len(result.outputs)
        failures = len(result.failures)
        transparency_count = sum(output.transparency_removed for output in result.outputs)
        self.image_progress.set(100.0)
        self.image_current.set("转换完成")
        self.image_summary.set(f"成功 {successes} 张  ·  失败 {failures} 张  ·  总数 {successes + failures} 张")
        self._set_status_style(self.image_status_label, "success" if failures == 0 else "warning")
        self._set_status_style(self.image_summary_label, "success" if failures == 0 else "warning")
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
        self._page_header(root, "⇄", "音频格式转换", "批量转换 MP3、WAV、FLAC、M4A、AAC、OGG")

        files = ttk.LabelFrame(root, text="1  添加音频文件", padding=12, style="Card.TLabelframe")
        files.grid(row=1, column=0, sticky="nsew", pady=(14, 10))
        files.columnconfigure(0, weight=1)
        files.rowconfigure(2, weight=1)
        toolbar = ttk.Frame(files, style="Card.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="选择音频文件…", command=self.choose_audio_files, style="Compact.TButton").pack(side="left")
        ttk.Button(toolbar, text="移除选中", command=self.remove_selected_audio, style="Compact.TButton").pack(side="left", padx=6)
        ttk.Button(toolbar, text="清空", command=self.clear_audio_files, style="CompactDanger.TButton").pack(side="left")
        ttk.Label(files, text="文件路径", style="CardMuted.TLabel").grid(row=1, column=0, sticky="w", padx=5, pady=(0, 4))
        self.audio_file_list = tk.Listbox(files, height=8, selectmode="extended", relief="flat", borderwidth=1, background="#ffffff", foreground=COLORS["text"])
        self.audio_file_list.grid(row=2, column=0, sticky="nsew")
        file_scroll = ttk.Scrollbar(files, orient="vertical", command=self.audio_file_list.yview)
        file_scroll.grid(row=2, column=1, sticky="ns")
        audio_horizontal = ttk.Scrollbar(files, orient="horizontal", command=self.audio_file_list.xview)
        audio_horizontal.grid(row=3, column=0, sticky="ew")
        self.audio_file_list.configure(yscrollcommand=file_scroll.set, xscrollcommand=audio_horizontal.set)
        self.audio_files_empty = ttk.Label(files, text="♫\n尚未选择音频\n点击上方按钮添加一个或多个音频文件", justify="center", style="CardMuted.TLabel")
        self._show_empty_overlay(self.audio_files_empty, True, self.audio_file_list)

        settings = ttk.LabelFrame(root, text="2  转换设置", padding=12, style="Card.TLabelframe")
        settings.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)
        ttk.Label(settings, text="输出格式", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=5)
        format_box = ttk.Combobox(
            settings,
            textvariable=self.audio_format_label,
            values=tuple(spec.label for spec in FORMAT_SPECS.values()),
            state="readonly",
            width=18,
        )
        format_box.grid(row=0, column=1, sticky="ew", padx=(8, 24), pady=5)
        format_box.bind("<<ComboboxSelected>>", self._update_audio_parameter_ui)
        self.audio_parameter_label = ttk.Label(settings, text="比特率", style="Card.TLabel")
        self.audio_parameter_label.grid(row=0, column=2, sticky="w", pady=5)
        self.audio_parameter_box = ttk.Combobox(
            settings, textvariable=self.audio_parameter, state="readonly", width=18
        )
        self.audio_parameter_box.grid(row=0, column=3, sticky="ew", padx=(8, 0), pady=5)
        ttk.Label(settings, text="采样率", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            settings,
            textvariable=self.audio_sample_rate,
            values=("保持原始采样率", "44100 Hz", "48000 Hz", "96000 Hz"),
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 24), pady=5)
        ttk.Label(settings, text="声道", style="Card.TLabel").grid(row=1, column=2, sticky="w", pady=5)
        ttk.Combobox(
            settings,
            textvariable=self.audio_channels,
            values=("保持原始声道", "单声道", "立体声"),
            state="readonly",
            width=18,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 0), pady=5)
        ttk.Label(settings, text="输出目录", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=5)
        self.audio_output_entry = ttk.Entry(settings, textvariable=self.audio_output_dir)
        self.audio_output_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        attach_variable_tooltip(self.audio_output_entry, self.audio_output_dir)
        ttk.Button(settings, text="浏览…", command=self.choose_audio_output_dir).grid(row=2, column=3, sticky="e", pady=5)
        ttk.Label(
            settings,
            text="默认保持原采样率和声道；已有同名输出时会自动生成新文件名。",
            style="CardMuted.TLabel",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

        progress_area = ttk.LabelFrame(root, text="3  转换进度", padding=12, style="Card.TLabelframe")
        progress_area.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        progress_area.columnconfigure(1, weight=1)
        ttk.Label(progress_area, text="当前文件", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.audio_status_label = ttk.Label(progress_area, textvariable=self.audio_current, anchor="w", style=STATUS_STYLES["info"])
        self.audio_status_label.grid(row=0, column=1, sticky="ew")
        ttk.Progressbar(progress_area, variable=self.audio_file_progress, maximum=100).grid(row=1, column=1, sticky="ew", pady=(6, 5))
        ttk.Label(progress_area, text="总体进度", style="Card.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 12))
        ttk.Progressbar(progress_area, variable=self.audio_progress, maximum=100).grid(row=2, column=1, sticky="ew", pady=5)
        self.audio_summary_label = ttk.Label(progress_area, textvariable=self.audio_summary, anchor="w", style=STATUS_STYLES["info"])
        self.audio_summary_label.grid(row=3, column=1, sticky="ew", pady=(5, 0))
        self.audio_start_button = ttk.Button(progress_area, text="开始转换", command=self.start_audio_conversion, style="Accent.TButton")
        self.audio_start_button.grid(row=0, column=2, rowspan=4, sticky="ns", padx=(18, 0), ipadx=20)
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
            self._set_status_style(self.audio_status_label, "info")
        self._show_empty_overlay(self.audio_files_empty, not self.audio_sources, self.audio_file_list)

    def remove_selected_audio(self) -> None:
        if self._audio_running:
            return
        for index in reversed(self.audio_file_list.curselection()):
            self.audio_file_list.delete(index)
            del self.audio_sources[index]
        self.audio_current.set(f"当前有 {len(self.audio_sources)} 个待转换文件")
        self._set_status_style(self.audio_status_label, "info")
        self._show_empty_overlay(self.audio_files_empty, not self.audio_sources, self.audio_file_list)

    def clear_audio_files(self) -> None:
        if self._audio_running:
            return
        self.audio_sources.clear()
        self.audio_file_list.delete(0, "end")
        self.audio_current.set("已清空音频文件列表")
        self._set_status_style(self.audio_status_label, "info")
        self.audio_file_progress.set(0.0)
        self.audio_progress.set(0.0)
        self.audio_summary.set("")
        self._show_empty_overlay(self.audio_files_empty, True, self.audio_file_list)

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
            messagebox.showinfo(PRODUCT_NAME, "请至少选择一个音频文件。")
            return
        output_dir = Path(self.audio_output_dir.get().strip())
        if not output_dir.is_dir():
            messagebox.showerror("输出目录错误", "输出目录不存在或无法访问。")
            return
        try:
            ffmpeg = find_ffmpeg()
        except FfmpegNotFoundError as exc:
            self.audio_current.set("未找到 FFmpeg")
            self._set_status_style(self.audio_status_label, "error")
            messagebox.showerror("缺少 FFmpeg", str(exc))
            return

        sources = tuple(self.audio_sources)
        try:
            settings = self._current_audio_settings()
        except AudioConversionError as exc:
            messagebox.showerror("转换设置错误", str(exc))
            return
        self._audio_running = True
        self.audio_file_progress.set(0.0)
        self.audio_progress.set(0.0)
        self.audio_summary.set("")
        self._set_status_style(self.audio_status_label, "info")
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
        self.audio_file_progress.set(file_percent)
        self.audio_progress.set(overall)
        self.audio_current.set(f"正在转换 {index}/{total}：{source.name}（{file_percent:.0f}%）")
        self._set_status_style(self.audio_status_label, "info")

    def _finish_audio_conversion(
        self, result: BatchConversionResult | None, error: AudioConversionError | None
    ) -> None:
        self._audio_running = False
        self.audio_start_button.configure(state="normal")
        if error is not None:
            self.audio_current.set("转换失败")
            self._set_status_style(self.audio_status_label, "error")
            messagebox.showerror("音频转换失败", str(error))
            return
        if result is None:
            return
        successes = len(result.outputs)
        failures = len(result.failures)
        self.audio_progress.set(100.0)
        self.audio_file_progress.set(100.0)
        self.audio_current.set("转换完成")
        self.audio_summary.set(f"成功 {successes} 个  ·  失败 {failures} 个  ·  总数 {successes + failures} 个")
        self._set_status_style(self.audio_status_label, "success" if failures == 0 else "warning")
        self._set_status_style(self.audio_summary_label, "success" if failures == 0 else "warning")
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
        root.rowconfigure(3, weight=1)
        self._page_header(root, "◇", "音频标签编辑", "查看和修改歌曲信息、歌词与封面")

        file_area = ttk.LabelFrame(root, text="音频文件", padding=12, style="Card.TLabelframe")
        file_area.grid(row=1, column=0, sticky="ew", pady=(14, 10))
        file_area.columnconfigure(0, weight=1)
        self.editor_path_entry = ttk.Entry(file_area, textvariable=self.editor_mp3_path, state="readonly")
        self.editor_path_entry.grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        attach_variable_tooltip(self.editor_path_entry, self.editor_mp3_path)
        ttk.Button(file_area, text="选择音频文件…", command=self.choose_editor_mp3, style="Secondary.TButton").grid(row=0, column=1)

        overview = ttk.LabelFrame(root, text="音频概要", padding=(14, 10), style="Card.TLabelframe")
        overview.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.editor_overview_label = ElidedLabel(
            overview, textvariable=self.editor_audio_info, style="CardMuted.TLabel", anchor="w"
        )
        self.editor_overview_label.pack(fill="x", anchor="w")

        editor = ttk.Frame(root, style="Page.TFrame")
        editor.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        editor.columnconfigure(0, weight=3, uniform="editor")
        editor.columnconfigure(1, weight=4, uniform="editor")
        editor.columnconfigure(2, weight=3, uniform="editor")
        editor.rowconfigure(0, weight=1)

        basic = ttk.LabelFrame(editor, text="1  基础信息", padding=SIZES["card_pad"], style="Card.TLabelframe")
        basic.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        basic.columnconfigure(0, weight=1)
        self.editor_basic_entries: list[ttk.Entry] = []
        for row, (label, variable) in enumerate(
            (("歌名", self.editor_title), ("歌手", self.editor_artist), ("专辑", self.editor_album))
        ):
            ttk.Label(basic, text=label, style="Card.TLabel").grid(row=row * 2, column=0, sticky="w", pady=(4, 4))
            entry = ttk.Entry(basic, textvariable=variable)
            entry.grid(row=row * 2 + 1, column=0, sticky="ew", pady=(0, 5))
            self.editor_basic_entries.append(entry)
        ttk.Label(basic, text="留空保存会移除该项。", style="CardMuted.TLabel").grid(
            row=6, column=0, sticky="w", pady=(8, 0)
        )

        lyrics = ttk.LabelFrame(editor, text="2  歌词", padding=12, style="Card.TLabelframe")
        lyrics.grid(row=0, column=1, sticky="nsew", padx=8)
        lyrics.columnconfigure(0, weight=1)
        lyrics.rowconfigure(1, weight=1)
        self.lyrics_state_label = ttk.Label(lyrics, textvariable=self.editor_lyrics_state, style="CardMuted.TLabel")
        self.lyrics_state_label.grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.lyrics_preview = tk.Text(
            lyrics, height=9, wrap="word", font=("Microsoft YaHei UI", 10), state="disabled",
            relief="flat", borderwidth=1, background="#ffffff", foreground=COLORS["text"], padx=8, pady=8
        )
        self.lyrics_preview.grid(row=1, column=0, sticky="nsew")
        lyrics_scroll = ttk.Scrollbar(lyrics, orient="vertical", command=self.lyrics_preview.yview)
        lyrics_scroll.grid(row=1, column=1, sticky="ns")
        self.lyrics_preview.configure(yscrollcommand=lyrics_scroll.set)
        set_text_empty_state(self.lyrics_preview, "♫", "未检测到内嵌歌词", "可以导入 LRC 歌词后保存到音频")
        lyrics_actions = ttk.Frame(lyrics, style="Card.TFrame")
        lyrics_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        lyrics_actions.columnconfigure((0, 1), weight=1)
        self.editor_lyrics_choose_button = ttk.Button(
            lyrics_actions, textvariable=self.lyrics_button_text, command=self.choose_editor_lrc,
            style="Compact.TButton"
        )
        self.editor_lyrics_choose_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(
            lyrics_actions, text="导出歌词…", command=self.export_editor_lyrics, style="Compact.TButton"
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.editor_lyrics_remove_button = ttk.Button(
            lyrics_actions, text="移除歌词", command=self.mark_lyrics_for_removal,
            style="CompactDanger.TButton"
        )
        self.editor_lyrics_remove_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        cover = ttk.LabelFrame(editor, text="3  封面", padding=12, style="Card.TLabelframe")
        cover.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        cover.columnconfigure(0, weight=1)
        cover.rowconfigure(0, weight=1)
        preview_box = ttk.Frame(cover, width=230, height=220, style="Card.TFrame")
        preview_box.grid(row=0, column=0, sticky="nsew")
        preview_box.grid_propagate(False)
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(0, weight=1)
        self.cover_preview = ttk.Label(
            preview_box, text="▧\n\n未检测到内嵌封面\n可以选择图片作为封面",
            anchor="center", justify="center", style="CardMuted.TLabel"
        )
        self.cover_preview.grid(row=0, column=0, sticky="nsew")
        self.cover_state_label = ttk.Label(cover, textvariable=self.editor_cover_state, anchor="center", style="CardMuted.TLabel")
        self.cover_state_label.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        cover_actions = ttk.Frame(cover, style="Card.TFrame")
        cover_actions.grid(row=2, column=0, sticky="ew")
        cover_actions.columnconfigure((0, 1), weight=1)
        self.editor_cover_choose_button = ttk.Button(
            cover_actions, textvariable=self.cover_button_text, command=self.choose_editor_cover,
            style="Compact.TButton"
        )
        self.editor_cover_choose_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(cover_actions, text="导出封面…", command=self.export_editor_cover, style="Compact.TButton").grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.editor_cover_remove_button = ttk.Button(cover_actions, text="移除封面", command=self.mark_cover_for_removal, style="CompactDanger.TButton")
        self.editor_cover_remove_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        save_area = ttk.LabelFrame(root, text="4  保存方式", padding=12, style="Card.TLabelframe")
        save_area.grid(row=4, column=0, sticky="ew")
        save_mode = ttk.Frame(save_area, style="Card.TFrame")
        save_mode.pack(side="left")
        ttk.Radiobutton(
            save_mode, text="覆盖原文件", variable=self.editor_output_mode, value="overwrite"
        ).pack(side="left", padx=(0, 20))
        ttk.Radiobutton(
            save_mode, text="另存为", variable=self.editor_output_mode, value="save_as"
        ).pack(side="left")
        bottom = ttk.Frame(save_area, style="Card.TFrame")
        bottom.pack(side="right", fill="x", expand=True)
        self.editor_status_label = ttk.Label(bottom, textvariable=self.editor_status, anchor="w", wraplength=480, style=STATUS_STYLES["info"])
        self.editor_status_label.pack(
            side="left", fill="x", expand=True
        )
        self.editor_save_button = ttk.Button(
            bottom, text="保存到音频", command=self.save_editor, style="Accent.TButton"
        )
        self.editor_save_button.pack(side="right", padx=(8, 0))
        ttk.Button(bottom, text="取消修改", command=self.cancel_editor_changes).pack(
            side="right", padx=(8, 0)
        )

    def choose_editor_mp3(self) -> None:
        if self._has_pending_changes() and not messagebox.askyesno(
            "尚未保存", "当前修改尚未保存。选择其他音频会放弃这些修改，是否继续？"
        ):
            return
        selected = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("支持的音频标签", "*.mp3 *.flac *.m4a *.ogg *.opus *.wav"),
                ("MP3", "*.mp3"), ("FLAC", "*.flac"), ("M4A", "*.m4a"),
                ("OGG / Opus", "*.ogg *.opus"), ("WAV（只读）", "*.wav"),
            ],
        )
        if selected:
            self._load_editor_file(Path(selected), show_error=True)

    def _load_editor_file(self, path: Path, show_error: bool) -> bool:
        try:
            state = read_metadata(path)
        except (OSError, AudioMetadataError) as exc:
            self.editor_status.set(f"读取失败：{exc}")
            self._set_status_style(self.editor_status_label, "error")
            if show_error:
                messagebox.showerror("读取音频标签失败", str(exc))
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
        self.editor_audio_info.set(self._format_audio_info(state.info))
        self.editor_lyrics_state.set("已内嵌歌词" if state.has_lyrics else "未检测到内嵌歌词")
        self._set_status_style(self.lyrics_state_label, "success" if state.has_lyrics else "warning")
        self.lyrics_button_text.set("更换歌词…" if state.has_lyrics else "导入 LRC…")
        self._set_lyrics_preview(state.lyrics)
        self.editor_cover_state.set("已内嵌封面" if state.has_cover else "未检测到内嵌封面")
        self._set_status_style(self.cover_state_label, "success" if state.has_cover else "warning")
        self.cover_button_text.set("更换封面…" if state.has_cover else "选择图片…")
        self._show_cover_data(state.cover_data)
        self._set_editor_writable(state.writable)
        self.editor_status.set(
            "信息读取完成；修改需要调整的内容后统一保存"
            if state.writable else "WAV 当前仅提供信息读取，标签保存暂未开放"
        )
        self._set_status_style(self.editor_status_label, "success" if state.writable else "warning")
        return True

    def _set_editor_writable(self, writable: bool) -> None:
        state = "normal" if writable else "disabled"
        for entry in self.editor_basic_entries:
            entry.configure(state=state)
        for button in (
            self.editor_cover_choose_button, self.editor_cover_remove_button,
            self.editor_lyrics_choose_button, self.editor_lyrics_remove_button, self.editor_save_button,
        ):
            button.configure(state=state)

    @staticmethod
    def _format_audio_info(info: AudioFileInfo) -> str:
        total_seconds = max(0, round(info.duration_seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
        channels = {1: "单声道", 2: "立体声"}.get(info.channels, f"{info.channels} 声道")
        size_mb = info.file_size_bytes / 1024 / 1024
        return (
            f"{info.format_label}  ·  {duration}  ·  {info.bitrate_kbps} kbps  ·  "
            f"{info.sample_rate_hz:,} Hz  ·  {channels}  ·  {size_mb:.1f} MB  ·  "
            f"{info.tag_count} 个标签"
        )

    def export_editor_lyrics(self) -> None:
        state = self._original_editor_state
        source_text = self.editor_mp3_path.get().strip()
        if state is None or not source_text:
            messagebox.showinfo(PRODUCT_NAME, "请先选择音频文件。")
            return
        if not state.has_lyrics:
            messagebox.showinfo("没有内嵌歌词", "当前音频没有可导出的内嵌歌词。")
            return
        selected = filedialog.askdirectory(title="选择歌词导出目录", initialdir=str(Path(source_text).parent))
        if not selected:
            return
        try:
            output = export_metadata_lyrics(source_text, selected)
        except (OSError, AudioMetadataError) as exc:
            messagebox.showerror("导出歌词失败", str(exc))
            return
        self.editor_status.set(f"已导出歌词：{output}")
        self._set_status_style(self.editor_status_label, "success")
        if state.lyrics_count > 1:
            messagebox.showwarning(
                "歌词已导出",
                f"检测到 {state.lyrics_count} 个歌词标签，已导出优先歌词。\n输出文件：{output}",
            )
        else:
            messagebox.showinfo("歌词已导出", f"输出文件：{output}")

    def export_editor_cover(self) -> None:
        state = self._original_editor_state
        source_text = self.editor_mp3_path.get().strip()
        if state is None or not source_text:
            messagebox.showinfo(PRODUCT_NAME, "请先选择音频文件。")
            return
        if not state.has_cover:
            messagebox.showinfo("没有内嵌封面", "当前音频没有可导出的内嵌封面。")
            return
        selected = filedialog.askdirectory(title="选择封面导出目录", initialdir=str(Path(source_text).parent))
        if not selected:
            return
        try:
            output = export_metadata_cover(source_text, selected)
        except (OSError, AudioMetadataError) as exc:
            messagebox.showerror("导出封面失败", str(exc))
            return
        self.editor_status.set(f"已导出封面：{output}")
        self._set_status_style(self.editor_status_label, "success")
        if state.cover_count > 1:
            messagebox.showwarning(
                "封面已导出",
                f"检测到 {state.cover_count} 张内嵌图片，已优先导出正面封面。\n输出文件：{output}",
            )
        else:
            messagebox.showinfo("封面已导出", f"输出文件：{output}")

    def choose_editor_lrc(self) -> None:
        if self._original_editor_state is None:
            messagebox.showinfo(PRODUCT_NAME, "请先选择音频文件。")
            return
        if not self._original_editor_state.writable:
            messagebox.showinfo("只读格式", "当前格式暂时只支持读取标签。")
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
        self._set_status_style(self.lyrics_state_label, "warning")
        self.lyrics_button_text.set("更换歌词…")
        self.editor_status.set("已选择新歌词，点击“保存到音频”后写入")
        self._set_status_style(self.editor_status_label, "warning")

    def mark_lyrics_for_removal(self) -> None:
        if self._original_editor_state is None:
            messagebox.showinfo(PRODUCT_NAME, "请先选择音频文件。")
            return
        if not self._original_editor_state.has_lyrics and self._lyrics_action != "replace":
            messagebox.showinfo("没有内嵌歌词", "当前 MP3 没有可移除的内嵌歌词。")
            return
        self._pending_lrc_path = None
        self._lyrics_action = "remove"
        self._set_lyrics_preview("")
        self.editor_lyrics_state.set("待保存：移除内嵌歌词")
        self._set_status_style(self.lyrics_state_label, "error")
        self.lyrics_button_text.set("导入 LRC…")
        self.editor_status.set("歌词将在点击“保存到音频”后移除")
        self._set_status_style(self.editor_status_label, "warning")

    def choose_editor_cover(self) -> None:
        if self._original_editor_state is None:
            messagebox.showinfo(PRODUCT_NAME, "请先选择音频文件。")
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
        self._set_status_style(self.cover_state_label, "warning")
        self.cover_button_text.set("更换封面…")
        self.editor_status.set("已选择新封面，点击“保存到音频”后写入")
        self._set_status_style(self.editor_status_label, "warning")

    def mark_cover_for_removal(self) -> None:
        if self._original_editor_state is None:
            messagebox.showinfo(PRODUCT_NAME, "请先选择音频文件。")
            return
        if not self._original_editor_state.has_cover and self._cover_action != "replace":
            messagebox.showinfo("没有内嵌封面", "当前 MP3 没有可移除的内嵌封面。")
            return
        self._cleanup_pending_cover()
        self._cover_action = "remove"
        self._show_cover_data(None, "保存后移除封面")
        self.editor_cover_state.set("待保存：移除内嵌封面")
        self._set_status_style(self.cover_state_label, "error")
        self.cover_button_text.set("选择图片…")
        self.editor_status.set("封面将在点击“保存到音频”后移除")
        self._set_status_style(self.editor_status_label, "warning")

    def save_editor(self) -> None:
        source_text = self.editor_mp3_path.get().strip()
        state = self._original_editor_state
        if not source_text or state is None:
            messagebox.showinfo(PRODUCT_NAME, "请先选择音频文件。")
            return
        if not state.writable:
            messagebox.showinfo("只读格式", "当前格式暂时只支持读取标签。")
            return
        edits = AudioMetadataChanges(
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
        proceed, destination = self._choose_audio_destination(source_text, self.editor_output_mode.get())
        if not proceed:
            return
        try:
            output = write_metadata(source_text, edits, destination)
        except (OSError, AudioMetadataError) as exc:
            self.editor_status.set(f"保存失败：{exc}")
            self._set_status_style(self.editor_status_label, "error")
            messagebox.showerror("保存音频标签失败", str(exc))
            return
        self._load_editor_file(output, show_error=False)
        self.editor_status.set(f"已保存：{output}")
        self._set_status_style(self.editor_status_label, "success")
        messagebox.showinfo("保存完成", f"所有修改已保存到音频。\n输出文件：{output}")

    def cancel_editor_changes(self) -> None:
        state = self._original_editor_state
        if state is None:
            messagebox.showinfo(PRODUCT_NAME, "当前没有正在编辑的音频。")
            return
        if not self._has_pending_changes():
            self.editor_status.set("当前没有尚未保存的修改")
            self._set_status_style(self.editor_status_label, "info")
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
        self._set_status_style(self.lyrics_state_label, "success" if state.has_lyrics else "warning")
        self.lyrics_button_text.set("更换歌词…" if state.has_lyrics else "导入 LRC…")
        self._set_lyrics_preview(state.lyrics)
        self.editor_cover_state.set("已内嵌封面" if state.has_cover else "未检测到内嵌封面")
        self._set_status_style(self.cover_state_label, "success" if state.has_cover else "warning")
        self.cover_button_text.set("更换封面…" if state.has_cover else "选择图片…")
        self._show_cover_data(state.cover_data)
        self.editor_status.set("已取消尚未保存的修改，音频文件没有改变")
        self._set_status_style(self.editor_status_label, "info")

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
        if not content:
            if self._lyrics_action == "remove":
                set_text_empty_state(self.lyrics_preview, "×", "保存后将移除歌词", "保存前可以导入新歌词或取消修改")
            else:
                set_text_empty_state(self.lyrics_preview, "♫", "未检测到内嵌歌词", "可以导入 LRC 歌词后保存到音频")
            return
        self.lyrics_preview.configure(state="normal")
        self.lyrics_preview.delete("1.0", "end")
        self.lyrics_preview.insert("1.0", content)
        self.lyrics_preview.configure(state="disabled")

    def _show_cover_data(self, data: bytes | None, empty_text: str = "") -> None:
        self._cover_photo = None
        if not data:
            if empty_text:
                text = f"×\n\n{empty_text}\n保存前可以选择新图片或取消修改"
            else:
                text = "▧\n\n未检测到内嵌封面\n可以选择图片作为封面"
            self.cover_preview.configure(image="", text=text, style="CardMuted.TLabel", justify="center")
            return
        try:
            with Image.open(BytesIO(data)) as opened:
                preview = opened.copy()
            preview.thumbnail((180, 140), Image.Resampling.LANCZOS)
            self._cover_photo = ImageTk.PhotoImage(preview)
            self.cover_preview.configure(image=self._cover_photo, text="", style="Card.TLabel")
        except OSError:
            self.cover_preview.configure(
                image="", text="!\n\n封面存在，但无法预览\n保存操作仍会保留原始封面",
                style="Warning.Status.TLabel", justify="center"
            )

    def _choose_audio_destination(self, source: str, mode: str) -> tuple[bool, Path | None]:
        if mode == "overwrite":
            return True, None
        source_path = Path(source)
        selected = filedialog.asksaveasfilename(
            title="另存音频标签文件",
            initialdir=str(source_path.parent),
            initialfile=source_path.name,
            defaultextension=source_path.suffix,
            filetypes=[(f"{source_path.suffix.upper().lstrip('.')} 音频", f"*{source_path.suffix}")],
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
        if self._preview_poll_job is not None:
            try:
                self.after_cancel(self._preview_poll_job)
            except tk.TclError:
                pass
            self._preview_poll_job = None
        if self._preview_player is not None:
            self._preview_player.close()
        self._cleanup_pending_cover()
        super().destroy()

    def _build_converter_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        self._page_header(root, "A", "歌词 / 字幕转换", "支持 LRC、SRT、VTT 相互转换")

        body = ttk.Frame(root, style="Page.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        body.columnconfigure(0, weight=4, uniform="converter")
        body.columnconfigure(1, weight=6, uniform="converter")
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body, style="Page.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        files_frame = ttk.LabelFrame(left, text="1  选择歌词 / 字幕文件", padding=12, style="Card.TLabelframe")
        files_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(2, weight=1)
        toolbar = ttk.Frame(files_frame, style="Card.TFrame")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Button(
            toolbar, text="选择文件…", command=self.choose_files, style="Compact.TButton", width=9
        ).pack(side="left")
        ttk.Button(
            toolbar, text="移除选中", command=self.remove_selected, style="Compact.TButton", width=8
        ).pack(side="left", padx=6)
        ttk.Button(
            toolbar, text="清空", command=self.clear_files, style="CompactDanger.TButton", width=5
        ).pack(side="left")
        ttk.Label(files_frame, text="文件路径", style="CardMuted.TLabel").grid(row=1, column=0, sticky="w", padx=5, pady=(0, 4))
        self.file_list = tk.Listbox(files_frame, height=7, selectmode="extended", relief="flat", borderwidth=1, background="#ffffff", foreground=COLORS["text"])
        self.file_list.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.file_list.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        subtitle_horizontal = ttk.Scrollbar(files_frame, orient="horizontal", command=self.file_list.xview)
        subtitle_horizontal.grid(row=3, column=0, sticky="ew")
        self.file_list.configure(yscrollcommand=scrollbar.set, xscrollcommand=subtitle_horizontal.set)
        self.subtitle_files_empty = ttk.Label(files_frame, text="A\n尚未选择转换文件\n支持批量添加 LRC、SRT 和 VTT", justify="center", style="CardMuted.TLabel")
        self._show_empty_overlay(self.subtitle_files_empty, True, self.file_list)

        output = ttk.LabelFrame(left, text="2  转换设置", padding=12, style="Card.TLabelframe")
        output.grid(row=1, column=0, sticky="ew")
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="输出目录", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=5)
        self.subtitle_output_entry = ttk.Entry(output, textvariable=self.output_dir)
        self.subtitle_output_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        attach_variable_tooltip(self.subtitle_output_entry, self.output_dir)
        ttk.Button(output, text="浏览…", command=self.choose_output_dir).grid(row=0, column=2)
        ttk.Label(output, text="输出格式", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=5)
        format_box = ttk.Combobox(
            output,
            textvariable=self.subtitle_output_format,
            values=("LRC", "SRT", "VTT"),
            state="readonly",
            width=10,
        )
        format_box.grid(row=1, column=1, sticky="w", padx=8, pady=5)
        format_box.bind("<<ComboboxSelected>>", self._update_subtitle_format_ui)
        ttk.Checkbutton(
            output, text="高级设置（可选）", variable=self.subtitle_advanced_visible,
            command=self._toggle_subtitle_advanced
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 4))
        self.subtitle_advanced_frame = ttk.Frame(output, style="Card.TFrame")
        self.subtitle_advanced_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(2, 6))
        self.subtitle_duration_label = ttk.Label(self.subtitle_advanced_frame, text="最后一句持续时间", style="Card.TLabel")
        self.subtitle_duration_label.pack(side="left")
        self.subtitle_duration_box = ttk.Spinbox(
            self.subtitle_advanced_frame, from_=0.1, to=3600, increment=0.5,
            textvariable=self.subtitle_final_duration, width=7
        )
        self.subtitle_duration_box.pack(side="left", padx=(10, 5))
        self.subtitle_duration_unit = ttk.Label(self.subtitle_advanced_frame, text="秒（仅补全无结束时间的歌词）", style="CardMuted.TLabel")
        self.subtitle_duration_unit.pack(side="left")
        ttk.Button(output, text="开始批量转换", command=self.convert_all, style="Accent.TButton").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0)
        )
        self._toggle_subtitle_advanced()
        self._update_subtitle_format_ui()

        preview_frame = ttk.LabelFrame(body, text="3  转换结果预览", padding=12, style="Card.TLabelframe")
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        ttk.Label(preview_frame, text="结果", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        self.result_box = ttk.Combobox(preview_frame, state="readonly")
        self.result_box.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=(0, 6))
        self.result_box.bind("<<ComboboxSelected>>", self.show_selected_result)
        ttk.Button(preview_frame, text="当前结果另存为…", command=self.save_current).grid(
            row=0, column=2, pady=(0, 6)
        )
        self.preview = tk.Text(
            preview_frame, wrap="word", font=("Consolas", 10), undo=False,
            relief="flat", borderwidth=1, background="#ffffff", foreground=COLORS["text"], padx=10, pady=10
        )
        self.preview.grid(row=1, column=0, columnspan=3, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview.yview)
        preview_scroll.grid(row=1, column=3, sticky="ns")
        self.preview.configure(yscrollcommand=preview_scroll.set, state="disabled")
        self.converter_status_label = ttk.Label(preview_frame, textvariable=self.status, anchor="w", style=STATUS_STYLES["info"], wraplength=650)
        self.converter_status_label.grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0)
        )

    def _toggle_subtitle_advanced(self) -> None:
        if self.subtitle_advanced_visible.get():
            self.subtitle_advanced_frame.grid()
        else:
            self.subtitle_advanced_frame.grid_remove()

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
            self._set_status_style(self.converter_status_label, "info")
        self._show_empty_overlay(self.subtitle_files_empty, not self.sources, self.file_list)

    def remove_selected(self) -> None:
        for index in reversed(self.file_list.curselection()):
            self.file_list.delete(index)
            del self.sources[index]
        self.status.set(f"当前有 {len(self.sources)} 个待转换文件")
        self._set_status_style(self.converter_status_label, "info")
        self._show_empty_overlay(self.subtitle_files_empty, not self.sources, self.file_list)

    def clear_files(self) -> None:
        self.sources.clear()
        self.file_list.delete(0, "end")
        self.status.set("已清空文件列表")
        self._set_status_style(self.converter_status_label, "info")
        self._show_empty_overlay(self.subtitle_files_empty, True, self.file_list)

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
            messagebox.showinfo(PRODUCT_NAME, "请先选择至少一个 LRC、SRT 或 VTT 文件。")
            return
        output_dir_text = self.output_dir.get().strip()
        if not output_dir_text:
            messagebox.showwarning(PRODUCT_NAME, "请选择输出目录。")
            return
        output_dir = Path(output_dir_text)
        output_format = self.subtitle_output_format.get().lower()
        try:
            final_duration = float(self.subtitle_final_duration.get())
            if output_format != "lrc" and final_duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(PRODUCT_NAME, "最后一句持续时间必须是大于 0 的数字。")
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
        self._set_status_style(self.converter_status_label, "success" if not errors else "warning")
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
        self._set_status_style(self.converter_status_label, "success")

    def save_current(self) -> None:
        result = self.results.get(self.result_box.get())
        if not result:
            messagebox.showinfo(PRODUCT_NAME, "请先完成一次转换。")
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
                self._set_status_style(self.converter_status_label, "success")
            except OSError as exc:
                self._set_status_style(self.converter_status_label, "error")
                messagebox.showerror("保存失败", str(exc))


def main() -> None:
    app = Sub2LRCApp()
    app.mainloop()


if __name__ == "__main__":
    main()
