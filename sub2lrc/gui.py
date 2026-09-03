"""Tkinter graphical interface for Sub2LRC."""

from __future__ import annotations

from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .converter import SubtitleError, convert_file, read_subtitle, convert_text, unique_output_path
from .cover import CoverEmbedError, embed_cover
from .cropper import CoverCropDialog
from .embedder import LyricsEmbedError, embed_lrc


class Sub2LRCApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sub2LRC - 字幕与 MP3 标签工具")
        self.geometry("900x620")
        self.minsize(720, 480)

        self.sources: list[Path] = []
        self.results: dict[str, tuple[Path, str]] = {}
        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.status = tk.StringVar(value="请选择 VTT 或 SRT 字幕文件")
        self.mp3_path = tk.StringVar()
        self.lrc_path = tk.StringVar()
        self.embed_status = tk.StringVar(value="请选择 MP3 文件和 LRC 歌词")
        self.cover_mp3_path = tk.StringVar()
        self.cover_image_path = tk.StringVar()
        self.cover_status = tk.StringVar(value="请选择 MP3 文件和封面图片")
        self._cropped_cover_path: Path | None = None
        self._cropped_source_path: Path | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)
        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)

        converter_tab = ttk.Frame(notebook, padding=12)
        embed_tab = ttk.Frame(notebook, padding=18)
        cover_tab = ttk.Frame(notebook, padding=18)
        notebook.add(converter_tab, text="字幕转 LRC")
        notebook.add(embed_tab, text="MP3 内嵌歌词")
        notebook.add(cover_tab, text="MP3 内嵌封面")
        self._build_converter_tab(converter_tab)
        self._build_embed_tab(embed_tab)
        self._build_cover_tab(cover_tab)

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
        ttk.Button(preview_frame, text="当前结果另存为…", command=self.save_current).grid(row=0, column=2, pady=(0, 6))

        self.preview = tk.Text(preview_frame, wrap="word", font=("Microsoft YaHei UI", 10), undo=False)
        self.preview.grid(row=1, column=0, columnspan=3, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview.yview)
        preview_scroll.grid(row=1, column=3, sticky="ns")
        self.preview.configure(yscrollcommand=preview_scroll.set, state="disabled")

        ttk.Label(root, textvariable=self.status, anchor="w").grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _build_embed_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="把 LRC 歌词写入 MP3 的 ID3 标签", font=("Microsoft YaHei UI", 13, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 20)
        )

        ttk.Label(root, text="MP3 文件：").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.mp3_path).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(root, text="选择歌曲…", command=self.choose_mp3).grid(row=1, column=2)

        ttk.Label(root, text="LRC 歌词：").grid(row=2, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.lrc_path).grid(row=2, column=1, sticky="ew", padx=8)
        ttk.Button(root, text="选择歌词…", command=self.choose_lrc).grid(row=2, column=2)

        ttk.Button(root, text="写入歌词", command=self.write_lyrics).grid(
            row=3, column=0, columnspan=3, pady=(22, 14), ipadx=30, ipady=6
        )
        ttk.Label(
            root,
            text="写入 ID3v2.3 USLT 歌词标签；操作前会在歌曲旁自动创建 .bak 备份。",
            foreground="#555555",
        ).grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Separator(root).grid(row=5, column=0, columnspan=3, sticky="ew", pady=18)
        ttk.Label(root, textvariable=self.embed_status, anchor="w", wraplength=760).grid(
            row=6, column=0, columnspan=3, sticky="ew"
        )

    def choose_mp3(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择 MP3 歌曲",
            filetypes=[("MP3 音频", "*.mp3")],
        )
        if selected:
            self.mp3_path.set(selected)
            matching_lrc = Path(selected).with_suffix(".lrc")
            if matching_lrc.is_file():
                self.lrc_path.set(str(matching_lrc))
            self.embed_status.set("已选择 MP3 文件")

    def choose_lrc(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择 LRC 歌词",
            filetypes=[("LRC 歌词", "*.lrc")],
        )
        if selected:
            self.lrc_path.set(selected)
            self.embed_status.set("已选择 LRC 歌词")

    def write_lyrics(self) -> None:
        mp3 = self.mp3_path.get().strip()
        lrc = self.lrc_path.get().strip()
        if not mp3 or not lrc:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件和 LRC 歌词。")
            return
        try:
            backup = embed_lrc(mp3, lrc)
        except (OSError, LyricsEmbedError) as exc:
            self.embed_status.set(f"写入失败：{exc}")
            messagebox.showerror("写入歌词失败", str(exc))
            return

        self.embed_status.set(f"歌词已写入：{mp3}；备份：{backup}")
        messagebox.showinfo("写入完成", f"LRC 歌词已写入 MP3。\n备份文件：{backup}")

    def _build_cover_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="把 JPG 或 PNG 封面写入 MP3", font=("Microsoft YaHei UI", 13, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 20)
        )

        ttk.Label(root, text="MP3 文件：").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.cover_mp3_path).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(root, text="选择歌曲…", command=self.choose_cover_mp3).grid(row=1, column=2)

        ttk.Label(root, text="封面图片：").grid(row=2, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.cover_image_path, state="readonly").grid(row=2, column=1, sticky="ew", padx=8)
        ttk.Button(root, text="选择图片…", command=self.choose_cover_image).grid(row=2, column=2)

        ttk.Button(root, text="写入封面", command=self.write_cover).grid(
            row=3, column=0, columnspan=3, pady=(22, 14), ipadx=30, ipady=6
        )
        ttk.Label(
            root,
            text="写入 ID3 APIC 正面封面标签；旧封面会被替换，其他标签会保留，并自动创建 .bak 备份。",
            foreground="#555555",
        ).grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Separator(root).grid(row=5, column=0, columnspan=3, sticky="ew", pady=18)
        ttk.Label(root, textvariable=self.cover_status, anchor="w", wraplength=760).grid(
            row=6, column=0, columnspan=3, sticky="ew"
        )

    def choose_cover_mp3(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择 MP3 歌曲",
            filetypes=[("MP3 音频", "*.mp3")],
        )
        if selected:
            self.cover_mp3_path.set(selected)
            self.cover_status.set("已选择 MP3 文件")

    def choose_cover_image(self) -> None:
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

            source_suffix = Path(selected).suffix.lower()
            output_format = "PNG" if source_suffix == ".png" else "JPEG"
            suffix = ".png" if output_format == "PNG" else ".jpg"
            if output_format == "JPEG" and cropped.mode not in {"RGB", "L"}:
                cropped = cropped.convert("RGB")
            temporary = tempfile.NamedTemporaryFile(prefix="sub2lrc-cover-", suffix=suffix, delete=False)
            temporary.close()
            temporary_path = Path(temporary.name)
            cropped.save(temporary_path, format=output_format, quality=95)
        except (OSError, ValueError) as exc:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)
            messagebox.showerror("封面图片错误", str(exc))
            return

        self._cleanup_cropped_cover()
        self._cropped_cover_path = temporary_path
        self._cropped_source_path = Path(selected).resolve()
        self.cover_image_path.set(selected)
        self.cover_status.set(f"封面已裁剪为 {cropped.width} × {cropped.height}，可以写入")

    def write_cover(self) -> None:
        mp3 = self.cover_mp3_path.get().strip()
        image_text = self.cover_image_path.get().strip()
        if not mp3 or not image_text:
            messagebox.showinfo("Sub2LRC", "请先选择 MP3 文件和封面图片。")
            return
        source_path = Path(image_text)
        image = source_path
        if self._cropped_cover_path and self._cropped_source_path == source_path.resolve():
            image = self._cropped_cover_path
        try:
            backup = embed_cover(mp3, image)
        except (OSError, CoverEmbedError) as exc:
            self.cover_status.set(f"写入失败：{exc}")
            messagebox.showerror("写入封面失败", str(exc))
            return

        self.cover_status.set(f"封面已写入：{mp3}；备份：{backup}")
        messagebox.showinfo("写入完成", f"封面已写入 MP3。\n备份文件：{backup}")

    def _cleanup_cropped_cover(self) -> None:
        if self._cropped_cover_path:
            try:
                self._cropped_cover_path.unlink(missing_ok=True)
            except OSError:
                pass
        self._cropped_cover_path = None
        self._cropped_source_path = None

    def destroy(self) -> None:
        self._cleanup_cropped_cover()
        super().destroy()

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
                # The destination name is unique even when two source folders
                # contain subtitles with the same filename.
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
        name = self.result_box.get()
        result = self.results.get(name)
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
            title="保存 LRC",
            initialfile=original_path.name,
            defaultextension=".lrc",
            filetypes=[("LRC 歌词", "*.lrc")],
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
