"""Tkinter graphical interface for Sub2LRC."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .converter import SubtitleError, convert_file, read_subtitle, convert_text, unique_output_path
from .cropper import CoverCropDialog
from .editor import Mp3Edits, Mp3EditorError, Mp3EditorState, read_mp3_editor_state, save_mp3_edits
from .embedder import LyricsEmbedError, read_lrc
from .metadata import MetadataError


class Sub2LRCApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sub2LRC - 字幕与 MP3 工具")
        self.geometry("940x720")
        self.minsize(800, 650)

        self.sources: list[Path] = []
        self.results: dict[str, tuple[Path, str]] = {}
        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.status = tk.StringVar(value="请选择 VTT 或 SRT 字幕文件")
        self.editor_mp3_path = tk.StringVar()
        self.editor_title = tk.StringVar()
        self.editor_artist = tk.StringVar()
        self.editor_album = tk.StringVar()
        self.editor_lyrics_state = tk.StringVar(value="尚未读取歌词")
        self.editor_cover_state = tk.StringVar(value="尚未读取封面")
        self.editor_output_mode = tk.StringVar(value="save_as")
        self.editor_status = tk.StringVar(value="请选择一个 MP3 文件开始编辑")
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
        notebook.add(converter_tab, text="字幕转 LRC")
        notebook.add(editor_tab, text="MP3 编辑")
        self._build_converter_tab(converter_tab)
        self._build_editor_tab(editor_tab)

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
        except (OSError, MetadataError, Mp3EditorError) as exc:
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
        self.editor_status.set("封面将在点击“保存到 MP3”后移除")

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
        self._cleanup_pending_cover()
        super().destroy()

    def _build_converter_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)
        toolbar = ttk.Frame(root)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="选择字幕文件…", command=self.choose_files).pack(side="left")
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
            title="选择字幕文件",
            filetypes=[("字幕文件", "*.vtt *.srt"), ("VTT 文件", "*.vtt"), ("SRT 文件", "*.srt")],
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
        selected = filedialog.askdirectory(title="选择 LRC 输出目录", initialdir=self.output_dir.get())
        if selected:
            self.output_dir.set(selected)

    def convert_all(self) -> None:
        if not self.sources:
            messagebox.showinfo("Sub2LRC", "请先选择至少一个 VTT 或 SRT 文件。")
            return
        output_dir_text = self.output_dir.get().strip()
        if not output_dir_text:
            messagebox.showwarning("Sub2LRC", "请选择输出目录。")
            return
        output_dir = Path(output_dir_text)
        successes = 0
        errors: list[str] = []
        self.results.clear()
        for source in self.sources:
            try:
                lrc = convert_text(read_subtitle(source))
                destination = unique_output_path(output_dir, source)
                convert_file(source, destination)
                self.results[destination.name] = (destination, lrc)
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
            messagebox.showinfo("转换完成", f"已生成 {successes} 个 LRC 文件。\n保存位置：{output_dir}")

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
        selected = filedialog.asksaveasfilename(
            title="保存 LRC", initialfile=original_path.name, defaultextension=".lrc", filetypes=[("LRC 歌词", "*.lrc")]
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
