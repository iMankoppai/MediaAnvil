from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from sub2lrc.file_picker import InAppFilePicker, desktop_directory


class InAppFilePickerTests(unittest.TestCase):
    def test_onedrive_desktop_wins_when_registry_only_reports_conventional_desktop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            conventional = home / "Desktop"
            redirected = home / "OneDrive" / "Desktop"
            conventional.mkdir()
            redirected.mkdir(parents=True)
            with (
                patch("sub2lrc.file_picker.sys.platform", "win32"),
                patch("sub2lrc.file_picker.Path.home", return_value=home),
                patch("sub2lrc.file_picker._windows_desktop_directory", return_value=conventional),
                patch.dict("sub2lrc.file_picker.os.environ", {"OneDrive": str(home / "OneDrive")}),
            ):
                self.assertEqual(desktop_directory(), redirected.resolve())

    def make_root(self) -> tk.Tk:
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display is unavailable: {exc}")
        self.addCleanup(root.destroy)
        root.withdraw()
        return root

    def test_open_picker_filters_extensions_and_returns_multiple_unicode_files(self) -> None:
        root = self.make_root()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = folder / "中文 图片.png"
            second = folder / "第二张.JPG"
            ignored = folder / "忽略.txt"
            first.write_bytes(b"png")
            second.write_bytes(b"jpg")
            ignored.write_text("text", encoding="utf-8")

            picker = InAppFilePicker(
                root,
                title="测试",
                mode="open",
                extensions=(".png", ".jpg"),
                initialdir=folder,
                multiple=True,
            )
            shown = set(picker._paths.values())
            self.assertIn(first, shown)
            self.assertIn(second, shown)
            self.assertNotIn(ignored, shown)
            items = [item for item, path in picker._paths.items() if path in {first, second}]
            picker.tree.selection_set(items)
            picker._accept()
            self.assertEqual(set(picker.result), {str(first), str(second)})

    def test_save_picker_adds_extension_and_requires_second_click_to_overwrite(self) -> None:
        root = self.make_root()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            existing = folder / "歌词.lrc"
            existing.write_text("old", encoding="utf-8")
            picker = InAppFilePicker(
                root,
                title="测试保存",
                mode="save",
                extensions=(".lrc",),
                initialdir=folder,
                initialfile="歌词",
                default_extension=".lrc",
            )
            picker._accept()
            self.assertIsNone(picker.result)
            self.assertIn("再次点击", picker.status_var.get())
            picker._accept()
            self.assertEqual(picker.result, str(existing))

    def test_directory_picker_returns_current_unicode_directory(self) -> None:
        root = self.make_root()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "中文 输出"
            folder.mkdir()
            picker = InAppFilePicker(root, title="测试目录", mode="directory", initialdir=folder)
            picker._accept()
            self.assertEqual(picker.result, str(folder.resolve()))


if __name__ == "__main__":
    unittest.main()
