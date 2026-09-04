from pathlib import Path
import tkinter as tk
import unittest

from sub2lrc.gui import Sub2LRCApp


class LazyTabGuiTests(unittest.TestCase):
    def test_only_current_tool_page_exists_and_state_is_restored(self) -> None:
        try:
            app = Sub2LRCApp()
        except tk.TclError as exc:
            self.skipTest(f"Tk display is unavailable: {exc}")
        self.addCleanup(app.destroy)
        app.withdraw()
        app.update()

        preview, editor, converter, audio, image = app.main_notebook.tabs()
        self.assertTrue(app.nametowidget(preview).winfo_children())
        for tab_id in (editor, converter, audio, image):
            self.assertFalse(app.nametowidget(tab_id).winfo_children())

        app.audio_sources.append(Path("中文 测试.wav"))
        app.main_notebook.select(audio)
        app.update()
        app.audio_parameter.set("320")
        self.assertEqual(app.audio_file_list.get(0), "中文 测试.wav")

        app.main_notebook.select(converter)
        app.update()
        self.assertFalse(app.nametowidget(audio).winfo_children())
        self.assertTrue(app.nametowidget(converter).winfo_children())

        app.main_notebook.select(audio)
        app.update()
        self.assertFalse(app.nametowidget(converter).winfo_children())
        self.assertEqual(app.audio_parameter.get(), "320")
        self.assertEqual(app.audio_file_list.get(0), "中文 测试.wav")

        app.main_notebook.select(preview)
        app.update()
        self.assertFalse(app.nametowidget(audio).winfo_children())


if __name__ == "__main__":
    unittest.main()
