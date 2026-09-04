from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from sub2lrc.gui import Sub2LRCApp


MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413


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

        app.main_notebook.select(editor)
        app.update()
        self.assertEqual(len(app.nametowidget(editor).winfo_children()), 2)
        self.assertFalse(app._editor_details_built)

        with tempfile.TemporaryDirectory() as directory:
            mp3 = Path(directory) / "中文 音频.mp3"
            mp3.write_bytes(MP3_FRAME * 100)
            self.assertTrue(app._load_editor_file(mp3, show_error=False))
            self.assertTrue(app._editor_details_built)
            self.assertGreater(len(app.nametowidget(editor).winfo_children()), 2)
            app.editor_title.set("尚未保存的新标题")

            app.main_notebook.select(preview)
            app.update()
            self.assertFalse(app.nametowidget(editor).winfo_children())
            app.main_notebook.select(editor)
            app.update()
            self.assertTrue(app._editor_details_built)
            self.assertEqual(app.editor_title.get(), "尚未保存的新标题")

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
