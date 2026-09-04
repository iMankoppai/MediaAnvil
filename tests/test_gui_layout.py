from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from PIL import Image

from sub2lrc.gui import Sub2LRCApp


class GuiLayoutTests(unittest.TestCase):
    def make_app(self) -> Sub2LRCApp:
        try:
            app = Sub2LRCApp()
        except tk.TclError as exc:
            self.skipTest(f"Tk display is unavailable: {exc}")
        self.addCleanup(app.destroy)
        app.withdraw()
        app.update()
        return app

    def test_sidebar_exposes_seven_pages_and_switches_without_losing_widgets(self) -> None:
        app = self.make_app()
        expected = {"preview", "editor", "converter", "audio", "image", "settings", "about"}
        self.assertEqual(set(app.pages), expected)
        self.assertEqual(set(app.nav_buttons), expected)
        self.assertEqual(app.current_page, "preview")

        for key in expected:
            app.show_page(key)
            app.update_idletasks()
            self.assertEqual(app.current_page, key)
            self.assertTrue(app.pages[key].winfo_children())

        self.assertTrue(app.preview_audio_scale.winfo_exists())
        self.assertTrue(app.editor_save_button.winfo_exists())
        self.assertTrue(app.result_box.winfo_exists())
        self.assertTrue(app.audio_start_button.winfo_exists())
        self.assertTrue(app.image_start_button.winfo_exists())

    def test_unknown_page_is_rejected(self) -> None:
        app = self.make_app()
        with self.assertRaises(KeyError):
            app.show_page("missing")

    def test_advanced_subtitle_settings_are_collapsible(self) -> None:
        app = self.make_app()
        app.show_page("converter")
        self.assertEqual(app.subtitle_advanced_frame.winfo_manager(), "")
        app.subtitle_advanced_visible.set(True)
        app._toggle_subtitle_advanced()
        app.update_idletasks()
        self.assertEqual(app.subtitle_advanced_frame.winfo_manager(), "grid")

    def test_image_selection_populates_preview_without_modifying_file(self) -> None:
        app = self.make_app()
        app.show_page("image")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "中文 预览.png"
            Image.new("RGBA", (64, 32), (20, 120, 220, 128)).save(path)
            before = path.read_bytes()
            app.image_sources.append(path)
            app.image_file_list.insert("end", str(path))
            app.image_file_list.selection_set(0)
            app._show_selected_image_preview()
            self.assertEqual(app.image_preview_name.get(), path.name)
            self.assertIn("64 × 32", app.image_preview_details.get())
            self.assertIsNotNone(app._image_preview_photo)
            self.assertEqual(path.read_bytes(), before)

    def test_audio_progress_separates_current_file_and_overall_values(self) -> None:
        app = self.make_app()
        app._update_audio_progress(Path("示例.wav"), 2, 4, 75.0, 43.0)
        self.assertEqual(app.audio_file_progress.get(), 75.0)
        self.assertEqual(app.audio_progress.get(), 43.0)
        self.assertIn("2/4", app.audio_current.get())


if __name__ == "__main__":
    unittest.main()
