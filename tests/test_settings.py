import json
from pathlib import Path
import tempfile
import unittest

from core.settings import (
    default_settings,
    get_setting,
    last_load_warning,
    load_settings,
    reset_settings,
    save_settings,
    set_setting,
    settings_path,
)


class SettingsTests(unittest.TestCase):
    def test_first_run_uses_safe_defaults_and_appdata_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = settings_path(directory)
            self.assertFalse(path.exists())
            values = load_settings(path)
            self.assertEqual(values["default_save_mode"], "save_as")
            self.assertEqual(values["default_mp3_bitrate"], 192)
            self.assertFalse(values["include_subfolders"])
            self.assertFalse(values["prefer_embedded_mp3_lyrics"])
            self.assertIsNone(last_load_warning())

    def test_save_and_reload_preserves_chinese_custom_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MediaAnvil" / "settings.json"
            values = default_settings()
            values.update({
                "default_output_location": "custom",
                "default_output_directory": "C:/音乐/转换后",
                "default_volume": 35,
            })
            saved = save_settings(values, path)
            self.assertEqual(saved, path)
            loaded = load_settings(path)
            self.assertEqual(loaded["default_output_directory"], "C:/音乐/转换后")
            self.assertEqual(loaded["default_volume"], 35)

    def test_recent_dialog_directories_are_persisted_as_known_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            values = default_settings()
            values.update({
                "last_audio_directory": "C:/媒体/音乐",
                "last_image_directory": "C:/媒体/图片",
                "last_subtitle_directory": "C:/媒体/字幕",
                "last_output_directory": "C:/媒体/输出",
            })
            save_settings(values, path)
            loaded = load_settings(path)
            for key in (
                "last_audio_directory",
                "last_image_directory",
                "last_subtitle_directory",
                "last_output_directory",
            ):
                self.assertEqual(loaded[key], values[key])

    def test_recent_dialog_filters_are_persisted_and_default_to_empty(self) -> None:
        self.assertEqual(default_settings()["last_audio_filter"], "")
        self.assertEqual(default_settings()["last_image_filter"], "")
        self.assertEqual(default_settings()["last_subtitle_filter"], "")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            values = default_settings()
            values.update({
                "last_audio_filter": "所有文件 (*)",
                "last_image_filter": "图片 (*.png)",
                "last_subtitle_filter": "歌词 / 字幕 (*.lrc *.srt *.vtt)",
            })
            save_settings(values, path)
            loaded = load_settings(path)
            for key in ("last_audio_filter", "last_image_filter", "last_subtitle_filter"):
                self.assertEqual(loaded[key], values[key])
            # a non-string value must fall back to the empty default
            path.write_text(json.dumps({"last_audio_filter": 7}), encoding="utf-8")
            self.assertEqual(load_settings(path)["last_audio_filter"], "")

    def test_corrupt_json_falls_back_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("{ this is not json", encoding="utf-8")
            values = load_settings(path)
            self.assertEqual(values, default_settings())
            self.assertIn("无法读取", last_load_warning() or "")

    def test_old_config_merges_defaults_and_ignores_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"default_volume": 20, "old_field": "ignored"}), encoding="utf-8")
            values = load_settings(path)
            self.assertEqual(values["default_volume"], 20)
            self.assertEqual(values["default_save_mode"], "save_as")
            self.assertNotIn("old_field", values)

    def test_removed_no_op_settings_are_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({
                "default_keep_image_size": False,
                "remember_last_page": True,
                "last_page": "image",
            }), encoding="utf-8")
            values = load_settings(path)
            self.assertNotIn("default_keep_image_size", values)
            self.assertNotIn("remember_last_page", values)
            self.assertNotIn("last_page", values)

    def test_set_get_and_reset_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            load_settings(path)
            self.assertEqual(set_setting("default_volume", 55), 55)
            self.assertEqual(get_setting("default_volume"), 55)
            save_settings(config_path=path)
            self.assertEqual(load_settings(path)["default_volume"], 55)
            restored = reset_settings(path)
            self.assertEqual(restored, default_settings())
            self.assertEqual(load_settings(path)["default_save_mode"], "save_as")

    def test_invalid_values_are_normalised_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({
                "default_mp3_bitrate": 999,
                "default_volume": 180,
                "default_image_quality": 0,
                "subtitle_final_duration": -1,
                "default_save_mode": "unsafe",
            }), encoding="utf-8")
            values = load_settings(path)
            self.assertEqual(values["default_mp3_bitrate"], 192)
            self.assertEqual(values["default_volume"], 100)
            self.assertEqual(values["default_image_quality"], 1)
            self.assertEqual(values["subtitle_final_duration"], 0.1)
            self.assertEqual(values["default_save_mode"], "save_as")


if __name__ == "__main__":
    unittest.main()
