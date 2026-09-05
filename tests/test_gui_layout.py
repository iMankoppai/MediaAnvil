from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from PIL import Image

from sub2lrc.gui import Sub2LRCApp
from sub2lrc.ui_widgets import ElidedLabel


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

    def test_product_branding_and_icon_are_loaded(self) -> None:
        app = self.make_app()
        self.assertEqual(app.title(), "MediaAnvil - 本地多媒体工具箱")
        self.assertIsNotNone(app._app_icon)

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

    def test_stop_preview_resets_position_and_time_without_changing_file(self) -> None:
        app = self.make_app()

        class FakePlayer:
            duration = 125.0
            stopped = False

            def stop(self) -> None:
                self.stopped = True

            def close(self) -> None:
                pass

        player = FakePlayer()
        app._preview_player = player  # type: ignore[assignment]
        app.preview_audio_path.set("C:/音乐/很长的中文歌曲名.mp3")
        app.preview_audio_position.set(72.0)
        app.stop_preview_audio()
        self.assertTrue(player.stopped)
        self.assertEqual(app.preview_audio_position.get(), 0.0)
        self.assertEqual(app.preview_current_time.get(), "00:00")
        self.assertEqual(app.preview_total_time.get(), "02:05")
        self.assertEqual(app.preview_audio_path.get(), "C:/音乐/很长的中文歌曲名.mp3")

    def test_long_label_is_elided_without_modifying_source_value(self) -> None:
        app = self.make_app()
        source = tk.StringVar(app, value="这是一首用于验证界面布局不会被撑坏的特别特别长的中文歌曲名称")
        host = tk.Frame(app, width=120, height=28)
        host.pack()
        label = ElidedLabel(host, textvariable=source)
        label.place(x=0, y=0, width=120, height=28)
        app.deiconify()
        app.update()
        label._refresh()
        self.assertEqual(source.get(), "这是一首用于验证界面布局不会被撑坏的特别特别长的中文歌曲名称")
        self.assertTrue(label.display_variable.get().endswith("…"))

    def test_batch_lists_support_horizontal_scrolling_and_empty_overlays(self) -> None:
        app = self.make_app()
        for page, listbox, overlay in (
            ("converter", app.file_list, app.subtitle_files_empty),
            ("audio", app.audio_file_list, app.audio_files_empty),
            ("image", app.image_file_list, app.image_files_empty),
        ):
            app.show_page(page)
            app.update_idletasks()
            self.assertTrue(str(listbox.cget("xscrollcommand")))
            self.assertEqual(overlay.winfo_manager(), "place")

    def test_editor_buttons_follow_writable_state(self) -> None:
        app = self.make_app()
        app._set_editor_writable(False)
        self.assertIn("disabled", app.editor_save_button.state())
        self.assertIn("disabled", app.editor_lyrics_choose_button.state())
        app._set_editor_writable(True)
        self.assertNotIn("disabled", app.editor_save_button.state())
        self.assertNotIn("disabled", app.editor_lyrics_choose_button.state())

    def test_pages_survive_supported_window_sizes_and_tk_scaling(self) -> None:
        app = self.make_app()
        app.deiconify()
        self.assertGreater(float(app.tk.call("tk", "scaling")), 0.0)
        for geometry in ("1050x760", "1500x900"):
            app.geometry(geometry)
            for page in ("preview", "editor", "converter", "audio", "image"):
                app.show_page(page)
                app.update_idletasks()
                self.assertGreater(app.pages[page].winfo_width(), 0)
                self.assertGreater(app.pages[page].winfo_height(), 0)


if __name__ == "__main__":
    unittest.main()
