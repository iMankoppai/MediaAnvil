"""Tkinter graphical interface for Sub2LRC."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .converter import SubtitleError, convert_file, read_subtitle, convert_text, unique_output_path


class Sub2LRCApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sub2LRC - 字幕转歌词")
        self.geometry("900x620")
        self.minsize(720, 480)

        self.sources: list[Path] = []
        self.results: dict[str, tuple[Path, str]] = {}
        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.status = tk.StringVar(value="请选择 VTT 或 SRT 字幕文件")
        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
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
