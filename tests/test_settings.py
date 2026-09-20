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
