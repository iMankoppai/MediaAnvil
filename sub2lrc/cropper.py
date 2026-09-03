"""Square image cropping helpers and Tkinter crop dialog."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk, UnidentifiedImageError


def crop_square(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """Return a square crop after validating that the box is inside the image."""
    left, top, right, bottom = box
    if right <= left or bottom <= top or right - left != bottom - top:
        raise ValueError("裁剪区域必须是有效的正方形。")
    if left < 0 or top < 0 or right > image.width or bottom > image.height:
        raise ValueError("裁剪区域超出了图片范围。")
    return image.crop(box)


class CoverCropDialog(tk.Toplevel):
    """Modal dialog for choosing a draggable, resizable 1:1 crop area."""

    CANVAS_WIDTH = 640
    CANVAS_HEIGHT = 430

    def __init__(self, parent: tk.Misc, image_path: str | Path) -> None:
        super().__init__(parent)
        self.title("裁剪封面（1:1）")
        self.resizable(False, False)
        self.transient(parent)
        self.result: Image.Image | None = None
        self._drag_offset = (0.0, 0.0)

        try:
            with Image.open(image_path) as opened:
                opened.verify()
            with Image.open(image_path) as opened:
                self.original = opened.copy()
        except (OSError, UnidentifiedImageError) as exc:
            self.destroy()
            raise ValueError(f"无法打开封面图片：{exc}") from exc

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="拖动黄色方框选择封面区域；使用滑块调整裁剪范围。", anchor="w").pack(fill="x", pady=(0, 8))

        self.canvas = tk.Canvas(
            root,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            background="#202020",
            highlightthickness=0,
            cursor="fleur",
        )
        self.canvas.pack()

        self.display_scale = min(
            self.CANVAS_WIDTH / self.original.width,
            self.CANVAS_HEIGHT / self.original.height,
            1.0,
        )
        display_size = (
            max(1, round(self.original.width * self.display_scale)),
            max(1, round(self.original.height * self.display_scale)),
        )
        preview = self.original.copy()
        preview.thumbnail(display_size, Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(preview)
        self.image_left = (self.CANVAS_WIDTH - preview.width) / 2
        self.image_top = (self.CANVAS_HEIGHT - preview.height) / 2
        self.display_width = preview.width
        self.display_height = preview.height
        self.canvas.create_image(self.image_left, self.image_top, image=self.photo, anchor="nw")

        self.crop_percent = tk.DoubleVar(value=100.0)
        self.crop_size = float(min(self.display_width, self.display_height))
        self.crop_left = self.image_left + (self.display_width - self.crop_size) / 2
        self.crop_top = self.image_top + (self.display_height - self.crop_size) / 2
        self.crop_rectangle = self.canvas.create_rectangle(
            self.crop_left,
            self.crop_top,
            self.crop_left + self.crop_size,
            self.crop_top + self.crop_size,
            outline="#ffd400",
            width=3,
        )
        self.canvas.bind("<Button-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)

        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(10, 0))
        ttk.Label(controls, text="裁剪范围：").pack(side="left")
        ttk.Scale(
            controls,
            from_=20,
            to=100,
            variable=self.crop_percent,
            command=self._resize_crop,
        ).pack(side="left", fill="x", expand=True, padx=(6, 12))
        ttk.Button(controls, text="取消", command=self.cancel).pack(side="right")
        ttk.Button(controls, text="确认裁剪", command=self.confirm).pack(side="right", padx=(0, 8))

    def _clamp_position(self, left: float, top: float) -> tuple[float, float]:
        min_left = self.image_left
        min_top = self.image_top
        max_left = self.image_left + self.display_width - self.crop_size
        max_top = self.image_top + self.display_height - self.crop_size
        return min(max(left, min_left), max_left), min(max(top, min_top), max_top)

    def _draw_crop(self) -> None:
        self.canvas.coords(
            self.crop_rectangle,
            self.crop_left,
            self.crop_top,
            self.crop_left + self.crop_size,
            self.crop_top + self.crop_size,
        )

    def _start_drag(self, event: tk.Event) -> None:
        inside = (
            self.crop_left <= event.x <= self.crop_left + self.crop_size
            and self.crop_top <= event.y <= self.crop_top + self.crop_size
        )
        if inside:
            self._drag_offset = (event.x - self.crop_left, event.y - self.crop_top)
        else:
            self._drag_offset = (self.crop_size / 2, self.crop_size / 2)
            self.crop_left, self.crop_top = self._clamp_position(
                event.x - self._drag_offset[0], event.y - self._drag_offset[1]
            )
            self._draw_crop()

    def _drag(self, event: tk.Event) -> None:
        self.crop_left, self.crop_top = self._clamp_position(
            event.x - self._drag_offset[0], event.y - self._drag_offset[1]
        )
        self._draw_crop()

    def _resize_crop(self, _value: str) -> None:
        old_center_x = self.crop_left + self.crop_size / 2
        old_center_y = self.crop_top + self.crop_size / 2
        self.crop_size = min(self.display_width, self.display_height) * self.crop_percent.get() / 100
        self.crop_left, self.crop_top = self._clamp_position(
            old_center_x - self.crop_size / 2,
            old_center_y - self.crop_size / 2,
        )
        self._draw_crop()

    def confirm(self) -> None:
        scale = self.display_scale
        left = round((self.crop_left - self.image_left) / scale)
        top = round((self.crop_top - self.image_top) / scale)
        size = max(1, round(self.crop_size / scale))
        size = min(size, self.original.width - left, self.original.height - top)
        try:
            self.result = crop_square(self.original, (left, top, left + size, top + size))
        except ValueError as exc:
            messagebox.showerror("裁剪失败", str(exc), parent=self)
            return
        self.destroy()

    def cancel(self) -> None:
        self.result = None
        self.destroy()
