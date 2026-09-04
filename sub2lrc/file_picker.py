"""Small in-app file and directory picker that does not call tk_getOpenFile."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from typing import Literal


PickerMode = Literal["open", "save", "directory"]


def _windows_desktop_directory() -> Path | None:
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, "Desktop")
        candidate = Path(os.path.expandvars(value)).expanduser()
        return candidate if candidate.is_dir() else None
    except (ImportError, OSError, TypeError):
        return None


def desktop_directory() -> Path:
    """Return the real desktop, including OneDrive/redirection on Windows."""
    if sys.platform == "win32":
        registered = _windows_desktop_directory()
        conventional = (Path.home() / "Desktop").resolve()
        if registered is not None and registered.resolve() != conventional:
            return registered.resolve()
        one_drive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
        if one_drive:
            redirected = Path(one_drive) / "Desktop"
            if redirected.is_dir():
                return redirected.resolve()
        if registered is not None:
            return registered.resolve()
    conventional = Path.home() / "Desktop"
    return conventional.resolve() if conventional.is_dir() else Path.home().resolve()


def _usable_directory(value: str | Path | None) -> Path:
    candidate = Path(value).expanduser() if value else Path.home()
    if candidate.is_file():
        candidate = candidate.parent
    if candidate.is_dir():
        return candidate.resolve()
    return desktop_directory()


class InAppFilePicker:
    """Modal child window for selecting files without a native common dialog."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        mode: PickerMode,
        extensions: tuple[str, ...] = (),
        initialdir: str | Path | None = None,
        initialfile: str = "",
        default_extension: str = "",
        multiple: bool = False,
    ) -> None:
        self.parent = parent
        self.mode = mode
        self.extensions = tuple(
            extension.lower() if extension.startswith(".") else f".{extension.lower()}"
            for extension in extensions
        )
        self.default_extension = default_extension
        self.multiple = multiple
        self.current_dir = _usable_directory(initialdir)
        self.result: tuple[str, ...] | str | None = None
        self._paths: dict[str, Path] = {}
        self._overwrite_confirmation: Path | None = None

        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("760x520")
        self.top.minsize(560, 380)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._cancel)

        self.path_var = tk.StringVar(value=str(self.current_dir))
        self.filename_var = tk.StringVar(value=initialfile)
        self.status_var = tk.StringVar()
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        root = ttk.Frame(self.top, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        address = ttk.Frame(root)
        address.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        address.columnconfigure(1, weight=1)
        ttk.Button(address, text="上一级", command=self._go_up).grid(row=0, column=0, padx=(0, 6))
        path_entry = ttk.Entry(address, textvariable=self.path_var)
        path_entry.grid(row=0, column=1, sticky="ew")
        path_entry.bind("<Return>", self._go_to_typed_path)
        ttk.Button(address, text="转到", command=self._go_to_typed_path).grid(row=0, column=2, padx=(6, 0))

        shortcuts = ttk.Frame(root)
        shortcuts.grid(row=1, column=0, sticky="w", pady=(0, 8))
        ttk.Button(shortcuts, text="主目录", command=lambda: self._set_directory(Path.home())).pack(side="left")
        desktop = desktop_directory()
        if desktop.is_dir():
            ttk.Button(shortcuts, text="桌面", command=lambda: self._set_directory(desktop)).pack(
                side="left", padx=(6, 0)
            )

        selectmode = "extended" if self.multiple and self.mode == "open" else "browse"
        self.tree = ttk.Treeview(
            root, columns=("kind", "size"), show="tree headings", selectmode=selectmode
        )
        self.tree.heading("#0", text="名称", anchor="w")
        self.tree.heading("kind", text="类型", anchor="w")
        self.tree.heading("size", text="大小", anchor="e")
        self.tree.column("#0", width=470, minwidth=220)
        self.tree.column("kind", width=100, minwidth=80)
        self.tree.column("size", width=100, minwidth=80, anchor="e")
        self.tree.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-Button-1>", self._open_selected)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)

        bottom = ttk.Frame(root)
        bottom.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        bottom.columnconfigure(1, weight=1)
        if self.mode == "save":
            ttk.Label(bottom, text="文件名：").grid(row=0, column=0, sticky="w")
            ttk.Entry(bottom, textvariable=self.filename_var).grid(row=0, column=1, sticky="ew", padx=(6, 8))
        ttk.Label(bottom, textvariable=self.status_var, foreground="#a05a00").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )
        ttk.Button(bottom, text="取消", command=self._cancel).grid(row=0, column=2, padx=(0, 6))
        action_text = {
            "open": "选择文件",
            "save": "保存",
            "directory": "选择此文件夹",
        }[self.mode]
        ttk.Button(bottom, text=action_text, command=self._accept).grid(row=0, column=3)

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def _matches(self, path: Path) -> bool:
        return not self.extensions or path.suffix.lower() in self.extensions

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._paths.clear()
        self.path_var.set(str(self.current_dir))
        self.status_var.set("")
        try:
            entries = list(self.current_dir.iterdir())
        except OSError as exc:
            self.status_var.set(f"无法读取文件夹：{exc}")
            return
        directories = sorted((path for path in entries if path.is_dir()), key=lambda path: path.name.lower())
        files = sorted(
            (path for path in entries if path.is_file() and self._matches(path)),
            key=lambda path: path.name.lower(),
        )
        for path in directories:
            item = self.tree.insert("", "end", text=f"📁 {path.name}", values=("文件夹", ""))
            self._paths[item] = path
        if self.mode != "directory":
            for path in files:
                try:
                    size = self._format_size(path.stat().st_size)
                except OSError:
                    size = ""
                item = self.tree.insert("", "end", text=path.name, values=(path.suffix.upper().lstrip("."), size))
                self._paths[item] = path

    def _set_directory(self, path: Path) -> None:
        if path.is_dir():
            self.current_dir = path.resolve()
            self._overwrite_confirmation = None
            self._refresh()

    def _go_up(self) -> None:
        self._set_directory(self.current_dir.parent)

    def _go_to_typed_path(self, _event: object | None = None) -> None:
        candidate = Path(self.path_var.get().strip()).expanduser()
        if candidate.is_dir():
            self._set_directory(candidate)
        else:
            self.status_var.set("该文件夹不存在或无法访问。")

    def _selected_paths(self) -> list[Path]:
        return [self._paths[item] for item in self.tree.selection() if item in self._paths]

    def _selection_changed(self, _event: object | None = None) -> None:
        if self.mode != "save":
            return
        selected = self._selected_paths()
        if len(selected) == 1 and selected[0].is_file():
            self.filename_var.set(selected[0].name)
            self._overwrite_confirmation = None

    def _open_selected(self, _event: object | None = None) -> None:
        selected = self._selected_paths()
        if len(selected) == 1 and selected[0].is_dir():
            self._set_directory(selected[0])
        elif self.mode == "open":
            self._accept()

    def _accept(self) -> None:
        if self.mode == "directory":
            self.result = str(self.current_dir)
            self.top.destroy()
            return
        if self.mode == "open":
            files = [path for path in self._selected_paths() if path.is_file()]
            if not files:
                self.status_var.set("请选择一个文件。")
                return
            chosen = files if self.multiple else files[:1]
            self.result = tuple(str(path) for path in chosen)
            self.top.destroy()
            return

        name = self.filename_var.get().strip()
        if not name:
            self.status_var.set("请输入文件名。")
            return
        target = self.current_dir / name
        if not target.suffix and self.default_extension:
            extension = self.default_extension
            target = target.with_suffix(extension if extension.startswith(".") else f".{extension}")
        if self.extensions and target.suffix.lower() not in self.extensions:
            self.status_var.set(f"文件扩展名必须是：{'、'.join(self.extensions)}")
            return
        if target.exists() and self._overwrite_confirmation != target:
            self._overwrite_confirmation = target
            self.status_var.set("文件已存在；再次点击“保存”即可确认覆盖。")
            return
        self.result = str(target)
        self.top.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.top.destroy()

    def show(self) -> tuple[str, ...] | str | None:
        self.top.wait_visibility()
        self.top.grab_set()
        self.top.focus_set()
        self.parent.wait_window(self.top)
        return self.result


def ask_open_file(
    parent: tk.Misc,
    *,
    title: str,
    extensions: tuple[str, ...],
    initialdir: str | Path | None = None,
) -> str:
    result = InAppFilePicker(
        parent, title=title, mode="open", extensions=extensions, initialdir=initialdir
    ).show()
    return result[0] if isinstance(result, tuple) and result else ""


def ask_open_files(
    parent: tk.Misc,
    *,
    title: str,
    extensions: tuple[str, ...],
    initialdir: str | Path | None = None,
) -> tuple[str, ...]:
    result = InAppFilePicker(
        parent, title=title, mode="open", extensions=extensions, initialdir=initialdir, multiple=True
    ).show()
    return result if isinstance(result, tuple) else ()


def ask_directory(parent: tk.Misc, *, title: str, initialdir: str | Path | None = None) -> str:
    result = InAppFilePicker(parent, title=title, mode="directory", initialdir=initialdir).show()
    return result if isinstance(result, str) else ""


def ask_save_file(
    parent: tk.Misc,
    *,
    title: str,
    initialdir: str | Path | None = None,
    initialfile: str = "",
    default_extension: str = "",
    extensions: tuple[str, ...] = (),
) -> str:
    result = InAppFilePicker(
        parent,
        title=title,
        mode="save",
        extensions=extensions,
        initialdir=initialdir,
        initialfile=initialfile,
        default_extension=default_extension,
    ).show()
    return result if isinstance(result, str) else ""
