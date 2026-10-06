from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from core.audio_renamer import (
    MissingRenameFieldError,
    RenameTemplateError,
    build_rename_plan,
    execute_rename_plan,
    read_rename_fields,
    render_filename_template,
    sanitize_filename,
    undo_rename,
)


class AudioRenamerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def touch(self, name: str, content: bytes = b"audio-content") -> Path:
        path = self.root / name
        path.write_bytes(content)
        return path

    @staticmethod
    def metadata(artist: str = "周杰伦", title: str = "晴天", album: str = "叶惠美", track: str = "1/12", year: str = "2003", genre: str = "流行") -> SimpleNamespace:
        return SimpleNamespace(artist=artist, title=title, album=album, track=track, year=year, genre=genre)

    def test_artist_title_template_and_two_digit_track(self) -> None:
        audio = self.touch("001.mp3")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata()):
            fields = read_rename_fields(audio)
            self.assertEqual(fields.track, "01")
            self.assertEqual(render_filename_template("{artist} - {title}", fields), "周杰伦 - 晴天.mp3")
            self.assertEqual(render_filename_template("{track} - {title}", fields), "01 - 晴天.mp3")

    def test_all_supported_tag_formats_use_the_same_reader(self) -> None:
        paths = [self.touch(f"track-{suffix}{suffix}") for suffix in (".mp3", ".flac", ".m4a", ".ogg", ".opus")]
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata(artist="林俊杰", title="江南")) as reader:
            for path in paths:
                self.assertEqual(read_rename_fields(path).title, "江南")
        self.assertEqual(reader.call_count, len(paths))

    def test_missing_fields_are_blocked_by_default_and_can_use_original_stem(self) -> None:
        audio = self.touch("001.mp3")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata(artist="", title="晴天")):
            fields = read_rename_fields(audio)
            with self.assertRaises(MissingRenameFieldError):
                render_filename_template("{artist} - {title}", fields)
            self.assertEqual(
                render_filename_template("{artist} - {title}", fields, fallback_missing=True),
                "001 - 晴天.mp3",
            )

    def test_illegal_characters_are_sanitized_and_long_names_are_limited(self) -> None:
        self.assertEqual(sanitize_filename(' A/B:C*? "歌". '), "A B C 歌")
        self.assertEqual(sanitize_filename("CON"), "CON_")
        self.assertEqual(sanitize_filename("nul"), "nul_")
        audio = self.touch("long.mp3")
        fields = read_rename_fields
        fake = self.metadata(artist="歌手", title="x" * 400)
        with patch("core.audio_renamer.read_metadata", return_value=fake):
            rendered = render_filename_template("{artist} - {title}", fields(audio))
        self.assertLessEqual(len(rendered), 240)
        self.assertTrue(rendered.endswith(".mp3"))

    def test_existing_target_is_avoided_and_batch_internal_collision_is_reported(self) -> None:
        first = self.touch("001.mp3")
        existing = self.touch("周杰伦 - 晴天.mp3")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata()):
            plan = build_rename_plan((first,), "{artist} - {title}")
        self.assertEqual(plan.items[0].status, "可重命名（自动避让）")
        self.assertEqual(plan.items[0].new_name, "周杰伦 - 晴天_1.mp3")
        self.assertTrue(existing.exists())

        second = self.touch("002.mp3")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata()):
            collision = build_rename_plan((first, second), "{artist} - {title}")
        self.assertEqual([item.status for item in collision.items], ["文件名冲突", "文件名冲突"])

    def test_unknown_template_variable_fails_before_any_rename(self) -> None:
        audio = self.touch("001.mp3")
        before = audio.read_bytes()
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata()):
            with self.assertRaises(RenameTemplateError):
                build_rename_plan((audio,), "{composer} - {title}")
        self.assertTrue(audio.exists())
        self.assertEqual(audio.read_bytes(), before)

    def test_genre_is_available_to_templates_like_the_other_tag_fields(self) -> None:
        audio = self.touch("001.mp3")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata()):
            fields = read_rename_fields(audio)
            self.assertEqual(fields.genre, "流行")
            self.assertEqual(render_filename_template("{genre} - {title}", fields), "流行 - 晴天.mp3")
            self.assertEqual(render_filename_template("{track} {genre} {title}", fields), "01 流行 晴天.mp3")

    def test_genre_follows_the_same_illegal_character_rules_as_other_fields(self) -> None:
        """A genre such as "Rock/Pop" must not be able to escape the folder."""
        audio = self.touch("001.mp3")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata(genre="Rock/Pop")):
            fields = read_rename_fields(audio)
            rendered = render_filename_template("{genre} - {title}", fields)
            self.assertNotIn("/", rendered)
            self.assertNotIn("\\", rendered)
            self.assertEqual(rendered, "Rock Pop - 晴天.mp3")

    def test_empty_genre_is_blocked_and_can_fall_back_to_the_original_stem(self) -> None:
        """A missing genre must behave exactly like any other missing field."""
        audio = self.touch("001.mp3")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata(genre="")):
            fields = read_rename_fields(audio)
            with self.assertRaises(MissingRenameFieldError):
                render_filename_template("{genre} - {title}", fields)
            self.assertEqual(
                render_filename_template("{genre} - {title}", fields, fallback_missing=True),
                "001 - 晴天.mp3",
            )

    def test_execute_isolates_one_failure_and_preserves_content(self) -> None:
        good = self.touch("001.mp3", b"good")
        bad = self.touch("002.mp3", b"bad")
        values = {good: self.metadata(title="一"), bad: self.metadata(title="二")}
        with patch("core.audio_renamer.read_metadata", side_effect=lambda path: values[Path(path)]):
            plan = build_rename_plan((good, bad), "{artist} - {title}")

        original_rename = Path.rename

        def rename_with_one_failure(source: Path, target: Path) -> Path:
            if source.name == "002.mp3":
                raise OSError("文件被占用")
            return original_rename(source, target)

        with patch.object(Path, "rename", autospec=True, side_effect=rename_with_one_failure):
            result = execute_rename_plan(plan)
        self.assertEqual(result.success_count, 1)
        self.assertEqual(len(result.failures), 1)
        renamed = self.root / "周杰伦 - 一.mp3"
        self.assertEqual(renamed.read_bytes(), b"good")
        self.assertEqual(bad.read_bytes(), b"bad")

    def test_matching_lyric_and_cover_follow_the_audio_rename(self) -> None:
        audio = self.touch("001.mp3", b"audio")
        audio.with_suffix(".lrc").write_text("[00:01.00]歌词", encoding="utf-8")
        audio.with_suffix(".jpg").write_bytes(b"cover")
        audio.with_name("001.mp3.vtt").write_text("WEBVTT", encoding="utf-8")
        # Ambiguous candidates must not be renamed automatically.
        other = self.touch("001 副本.png", b"ambiguous")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata(title="晴天")):
            plan = build_rename_plan((audio,), "{title}")
        item = plan.items[0]
        self.assertEqual(
            {record.old_path.name for record in item.related},
            {"001.lrc", "001.jpg", "001.mp3.vtt"},
        )
        result = execute_rename_plan(plan)
        self.assertEqual(result.success_count, 1)
        self.assertEqual(
            {record.old_path.name for record in result.related_records},
            {"001.lrc", "001.jpg", "001.mp3.vtt"},
        )
        renamed = self.root / "晴天.mp3"
        self.assertTrue(renamed.exists())
        self.assertEqual(renamed.read_bytes(), b"audio")
        self.assertTrue((self.root / "晴天.lrc").exists())
        self.assertTrue((self.root / "晴天.jpg").exists())
        self.assertTrue((self.root / "晴天.mp3.vtt").exists())
        self.assertFalse((self.root / "001.lrc").exists())
        self.assertFalse((self.root / "001.jpg").exists())
        self.assertFalse((self.root / "001.mp3.vtt").exists())
        self.assertTrue(other.exists())

    def test_exact_lyric_wins_and_copy_is_left_in_place(self) -> None:
        audio = self.touch("001.mp3", b"audio")
        audio.with_suffix(".lrc").write_text("first", encoding="utf-8")
        self.touch("001 - 副本.lrc").write_bytes(b"second")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata(title="晴天")):
            plan = build_rename_plan((audio,), "{title}")
        self.assertEqual([record.old_path.name for record in plan.items[0].related], ["001.lrc"])
        result = execute_rename_plan(plan)
        self.assertEqual(result.success_count, 1)
        self.assertEqual([record.old_path.name for record in result.related_records], ["001.lrc"])
        self.assertFalse((self.root / "001.lrc").exists())
        self.assertTrue((self.root / "晴天.lrc").exists())
        self.assertTrue((self.root / "001 - 副本.lrc").exists())
        self.assertTrue((self.root / "晴天.mp3").exists())

    def test_existing_related_target_blocks_only_that_related_file(self) -> None:
        audio = self.touch("001.mp3", b"audio")
        audio.with_suffix(".lrc").write_text("lyrics", encoding="utf-8")
        audio.with_suffix(".png").write_bytes(b"cover")
        self.touch("晴天.lrc").write_bytes(b"occupied")
        self.touch("晴天.png").write_bytes(b"occupied-cover")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata(title="晴天")):
            plan = build_rename_plan((audio,), "{title}")
        self.assertEqual(plan.items[0].related, ())
        result = execute_rename_plan(plan)
        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.related_records, ())
        self.assertTrue((self.root / "001.lrc").exists())
        self.assertTrue((self.root / "晴天.lrc").exists())
        self.assertTrue((self.root / "001.png").exists())
        self.assertTrue((self.root / "晴天.png").exists())
        self.assertTrue((self.root / "晴天.mp3").exists())

    def test_related_names_follow_an_automatically_avoided_audio_target(self) -> None:
        audio = self.touch("001.mp3", b"audio")
        audio.with_suffix(".lrc").write_text("lyrics", encoding="utf-8")
        self.touch("晴天.mp3").write_bytes(b"occupied")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata(title="晴天")):
            plan = build_rename_plan((audio,), "{title}")
        item = plan.items[0]
        self.assertEqual(item.target.name, "晴天_1.mp3")
        self.assertEqual([record.new_path.name for record in item.related], ["晴天_1.lrc"])
        result = execute_rename_plan(plan)
        self.assertEqual(result.success_count, 1)
        self.assertTrue((self.root / "晴天_1.mp3").exists())
        self.assertTrue((self.root / "晴天_1.lrc").exists())
        self.assertFalse((self.root / "001.lrc").exists())
        self.assertTrue((self.root / "晴天.mp3").exists())

    def test_undo_restores_last_batch_without_overwriting(self) -> None:
        source = self.touch("001.mp3", b"content")
        with patch("core.audio_renamer.read_metadata", return_value=self.metadata()):
            plan = build_rename_plan((source,), "{artist} - {title}")
        result = execute_rename_plan(plan)
        self.assertEqual(result.success_count, 1)
        undo = undo_rename(result.records)
        self.assertEqual(len(undo.records), 1)
        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"content")


if __name__ == "__main__":
    unittest.main()
