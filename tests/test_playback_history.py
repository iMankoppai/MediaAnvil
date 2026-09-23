"""The three resume rules are product decisions, so they are pinned here."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.playback_history import (
    FINISHED_TAIL_SECONDS,
    MINIMUM_RESUME_SECONDS,
    clear_positions,
    forget_position,
    is_finished,
    position_key,
    record_position,
    saved_position,
    should_remember,
)
from core.settings import default_settings, load_settings, save_settings


class PlaybackHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def audio(self, name: str = "track.mp3") -> Path:
        path = self.root / name
        path.write_bytes(b"audio")
        return path

    def test_a_short_listen_is_not_remembered(self) -> None:
        """Auditioning files must not leave a trail of resume points."""
        self.assertFalse(should_remember(MINIMUM_RESUME_SECONDS - 0.1, 3600.0))
        self.assertFalse(should_remember(0.0, 3600.0))
        self.assertFalse(should_remember(5.0, 3600.0))
        self.assertTrue(should_remember(MINIMUM_RESUME_SECONDS, 3600.0))

    def test_the_tail_of_a_file_counts_as_finished(self) -> None:
        duration = 1000.0
        self.assertTrue(is_finished(duration - FINISHED_TAIL_SECONDS, duration))
        self.assertTrue(is_finished(duration, duration))
        self.assertFalse(is_finished(duration - FINISHED_TAIL_SECONDS - 0.1, duration))
        self.assertFalse(should_remember(duration - 5.0, duration))

    def test_a_finished_file_is_not_offered_for_resuming(self) -> None:
        settings = default_settings()
        audio = self.audio()
        self.assertFalse(record_position(settings, audio, 3600.0 - 5.0, 3600.0))
        self.assertIsNone(saved_position(settings, audio, 3600.0))

    def test_each_file_keeps_its_own_position(self) -> None:
        """The point of scheme B: several long files can be part-way through."""
        settings = default_settings()
        first = self.audio("first.mp3")
        second = self.audio("second.mp3")
        third = self.audio("third.mp3")
        record_position(settings, first, 47 * 60 + 12, 2 * 3600.0)
        record_position(settings, second, 22 * 60 + 8, 3600.0)
        record_position(settings, third, 3 * 60 + 17, 3600.0)
        self.assertEqual(saved_position(settings, first), 2832.0)
        self.assertEqual(saved_position(settings, second), 1328.0)
        self.assertEqual(saved_position(settings, third), 197.0)
        # Recording a fourth file must not disturb the earlier three.
        record_position(settings, self.audio("fourth.mp3"), 600.0, 3600.0)
        self.assertEqual(saved_position(settings, first), 2832.0)
        self.assertEqual(saved_position(settings, second), 1328.0)

    def test_a_file_without_a_record_reports_none(self) -> None:
        settings = default_settings()
        self.assertIsNone(saved_position(settings, self.audio()))
        self.assertIsNone(saved_position(settings, self.root / "never-played.mp3"))

    def test_replaying_from_the_start_clears_the_record(self) -> None:
        settings = default_settings()
        audio = self.audio()
        record_position(settings, audio, 600.0, 3600.0)
        self.assertIsNotNone(saved_position(settings, audio))
        # A fresh short listen replaces the old position with nothing.
        self.assertFalse(record_position(settings, audio, 4.0, 3600.0))
        self.assertIsNone(saved_position(settings, audio))

    def test_switching_the_feature_off_ignores_existing_records(self) -> None:
        settings = default_settings()
        audio = self.audio()
        record_position(settings, audio, 600.0, 3600.0)
        self.assertIsNotNone(saved_position(settings, audio))
        settings["remember_playback_position"] = False
        self.assertIsNone(saved_position(settings, audio))
        # And it must not write new ones either.
        self.assertFalse(record_position(settings, audio, 900.0, 3600.0))

    def test_forget_and_clear_remove_only_what_they_should(self) -> None:
        settings = default_settings()
        first = self.audio("first.mp3")
        second = self.audio("second.mp3")
        record_position(settings, first, 600.0, 3600.0)
        record_position(settings, second, 700.0, 3600.0)
        forget_position(settings, first)
        self.assertIsNone(saved_position(settings, first))
        self.assertIsNotNone(saved_position(settings, second))
        clear_positions(settings)
        self.assertIsNone(saved_position(settings, second))

    def test_a_position_beyond_the_end_is_ignored(self) -> None:
        """A re-encoded or replaced file must not resume past its own end."""
        settings = default_settings()
        audio = self.audio()
        record_position(settings, audio, 3600.0, 7200.0)
        self.assertIsNone(saved_position(settings, audio, duration=100.0))

    def test_the_key_is_normalised_so_one_file_has_one_record(self) -> None:
        audio = self.audio()
        settings = default_settings()
        record_position(settings, audio, 600.0, 3600.0)
        variants = [str(audio), str(audio.resolve()), str(self.root / "." / audio.name)]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(saved_position(settings, variant), 600.0)
        self.assertEqual(position_key(audio), position_key(str(audio).upper()))

    def test_positions_survive_a_settings_round_trip(self) -> None:
        """The records are only useful if they are still there next launch."""
        config = self.root / "settings.json"
        audio = self.audio()
        settings = load_settings(config)
        record_position(settings, audio, 2832.0, 7200.0)
        save_settings(settings, config)
        reloaded = load_settings(config)
        self.assertEqual(saved_position(reloaded, audio), 2832.0)

    def test_a_damaged_positions_value_does_not_break_settings(self) -> None:
        config = self.root / "settings.json"
        config.write_text(
            '{"playback_positions": {"good": 12.5, "text": "nope", "bool": true, "none": null}}',
            encoding="utf-8",
        )
        settings = load_settings(config)
        self.assertEqual(settings["playback_positions"], {"good": 12.5})

    def test_positions_that_are_not_a_dictionary_are_replaced(self) -> None:
        config = self.root / "settings.json"
        config.write_text('{"playback_positions": ["wrong"]}', encoding="utf-8")
        settings = load_settings(config)
        self.assertEqual(settings["playback_positions"], {})

    def test_the_feature_is_on_by_default(self) -> None:
        self.assertTrue(default_settings()["remember_playback_position"])


if __name__ == "__main__":
    unittest.main()
