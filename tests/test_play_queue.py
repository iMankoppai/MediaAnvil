"""Ordering rules for the preview page's play queue."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.play_queue import ORDER_IN_ORDER, ORDER_SHUFFLE, PlayQueue


class PlayQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def files(self, count: int = 4) -> list[Path]:
        made = []
        for index in range(count):
            path = self.root / f"track-{index}.mp3"
            path.write_bytes(b"audio")
            made.append(path)
        return made

    def test_a_fresh_queue_selects_the_first_file(self) -> None:
        queue = PlayQueue(self.files(3))
        self.assertEqual(len(queue), 3)
        self.assertEqual(queue.index, 0)
        self.assertEqual(queue.current, self.root / "track-0.mp3")

    def test_an_empty_queue_has_no_current_file(self) -> None:
        queue = PlayQueue()
        self.assertEqual(len(queue), 0)
        self.assertIsNone(queue.current)
        self.assertIsNone(queue.next_index())
        self.assertIsNone(queue.previous_index())

    def test_adding_files_keeps_the_order_and_ignores_duplicates(self) -> None:
        first, second, third = self.files(3)
        queue = PlayQueue([first, second])
        self.assertEqual(queue.add([second, third]), 1, "a repeated path must not be queued twice")
        self.assertEqual(queue.entries, [first, second, third])
        self.assertEqual(queue.add([]), 0)

    def test_adding_the_first_files_selects_one(self) -> None:
        queue = PlayQueue()
        queue.add(self.files(2))
        self.assertEqual(queue.index, 0)
        self.assertIsNotNone(queue.current)

    def test_next_follows_the_list_and_stops_at_the_end(self) -> None:
        queue = PlayQueue(self.files(3))
        self.assertEqual(queue.advance(), self.root / "track-1.mp3")
        self.assertEqual(queue.advance(), self.root / "track-2.mp3")
        self.assertIsNone(queue.advance(), "the last file must not wrap in once mode")
        self.assertEqual(queue.current, self.root / "track-2.mp3")

    def test_repeat_all_wraps_to_the_first_file(self) -> None:
        queue = PlayQueue(self.files(2))
        queue.select(1)
        self.assertEqual(queue.advance(mode="repeat_all"), self.root / "track-0.mp3")

    def test_repeat_one_replays_the_same_file_but_manual_next_still_advances(self) -> None:
        """A Next button that does nothing would look broken to the user."""
        queue = PlayQueue(self.files(3))
        self.assertEqual(queue.advance(mode="repeat_one"), self.root / "track-0.mp3")
        self.assertEqual(queue.advance(mode="repeat_one", automatic=False), self.root / "track-1.mp3")

    def test_previous_walks_back_and_wraps(self) -> None:
        queue = PlayQueue(self.files(3))
        queue.select(1)
        self.assertEqual(queue.rewind(), self.root / "track-0.mp3")
        self.assertEqual(queue.rewind(), self.root / "track-2.mp3", "previous wraps from the first file")

    def test_shuffle_visits_every_file_exactly_once(self) -> None:
        queue = PlayQueue(self.files(6), order=ORDER_SHUFFLE, shuffle_seed=7)
        seen = []
        for _ in range(20):
            if queue.current is None:
                break
            seen.append(queue.current)
            if queue.advance() is None:
                break
        self.assertEqual(len(seen), 6, f"expected every file once, walked {[p.name for p in seen]}")
        self.assertEqual(len(set(seen)), 6, "shuffle must not repeat a file before the end")
        self.assertEqual(set(seen), set(self.files(6)))

    def test_shuffle_starts_from_the_selected_file_and_still_reaches_them_all(self) -> None:
        """Regression: the file before the selection used to be skipped.

        The shuffled order was rotated only by luck, so starting on index 0 of the
        permutation [4, 0, 5, 3, 1, 2] played 0, 5, 3, 1, 2 and never track 4.
        """
        files = self.files(6)
        for selected in range(6):
            with self.subTest(selected=selected):
                queue = PlayQueue(files, order=ORDER_SHUFFLE, shuffle_seed=7)
                queue.select(selected)
                seen = []
                for _ in range(20):
                    if queue.current is None:
                        break
                    seen.append(queue.current)
                    if queue.advance() is None:
                        break
                self.assertEqual(len(seen), 6, f"selected {selected}: walked {[p.name for p in seen]}")
                self.assertEqual(set(seen), set(files))
                self.assertEqual(seen[0], files[selected],
                                 "shuffle must begin with the file already selected")

    def test_every_shuffle_seed_reaches_every_file(self) -> None:
        files = self.files(5)
        for seed in range(25):
            with self.subTest(seed=seed):
                queue = PlayQueue(files, order=ORDER_SHUFFLE, shuffle_seed=seed)
                seen = []
                for _ in range(20):
                    if queue.current is None:
                        break
                    seen.append(queue.current)
                    if queue.advance() is None:
                        break
                self.assertEqual(set(seen), set(files), f"seed {seed} missed a file")

    def test_shuffle_is_stable_so_previous_returns_to_the_file_just_played(self) -> None:
        queue = PlayQueue(self.files(5), order=ORDER_SHUFFLE, shuffle_seed=3)
        first = queue.current
        second = queue.advance()
        self.assertEqual(queue.rewind(), first)
        self.assertEqual(queue.advance(), second, "the shuffle order must not change between calls")

    def test_shuffle_keeps_the_current_file_selected(self) -> None:
        queue = PlayQueue(self.files(5))
        queue.select(3)
        current = queue.current
        queue.set_order(ORDER_SHUFFLE, shuffle_seed=11)
        self.assertEqual(queue.current, current)

    def test_switching_back_to_in_order_restores_the_list_order(self) -> None:
        queue = PlayQueue(self.files(4), order=ORDER_SHUFFLE, shuffle_seed=5)
        queue.set_order(ORDER_IN_ORDER)
        self.assertEqual(queue.play_order, [0, 1, 2, 3])

    def test_removing_files_keeps_the_current_one_selected(self) -> None:
        queue = PlayQueue(self.files(4))
        queue.select(2)
        current = queue.current
        queue.remove([0])
        self.assertEqual(queue.current, current, "deleting an earlier file must not change the song")
        self.assertEqual(len(queue), 3)

    def test_removing_the_current_file_moves_to_a_neighbour(self) -> None:
        queue = PlayQueue(self.files(4))
        queue.select(3)
        queue.remove([3])
        self.assertEqual(queue.index, 2, "the selection must stay inside the list")
        self.assertIsNotNone(queue.current)

    def test_removing_everything_empties_the_queue(self) -> None:
        queue = PlayQueue(self.files(3))
        queue.remove([0, 1, 2])
        self.assertEqual(len(queue), 0)
        self.assertIsNone(queue.current)
        self.assertEqual(queue.index, -1)

    def test_clear_empties_the_queue(self) -> None:
        queue = PlayQueue(self.files(3))
        queue.clear()
        self.assertEqual(len(queue), 0)
        self.assertIsNone(queue.current)

    def test_moving_rows_reorders_them_and_keeps_the_current_file(self) -> None:
        queue = PlayQueue(self.files(4))
        queue.select(3)                      # track-3
        queue.move([3], 0)                   # send it to the front
        self.assertEqual(queue.entries[0], self.root / "track-3.mp3")
        self.assertEqual(queue.current, self.root / "track-3.mp3")
        self.assertEqual(queue.index, 0)

    def test_moving_a_block_keeps_its_internal_order(self) -> None:
        queue = PlayQueue(self.files(5))
        queue.move([1, 2], 4)
        names = [path.name for path in queue.entries]
        self.assertEqual(names, ["track-0.mp3", "track-3.mp3", "track-4.mp3",
                                 "track-1.mp3", "track-2.mp3"])

    def test_moving_out_of_range_is_clamped_rather_than_failing(self) -> None:
        queue = PlayQueue(self.files(3))
        queue.move([0], 99)
        self.assertEqual(queue.entries[-1], self.root / "track-0.mp3")
        queue.move([], 0)
        self.assertEqual(len(queue), 3, "an empty move must be a no-op")

    def test_selecting_by_path_and_index(self) -> None:
        queue = PlayQueue(self.files(3))
        self.assertEqual(queue.select(2), self.root / "track-2.mp3")
        self.assertEqual(queue.select_path(self.root / "track-1.mp3"), self.root / "track-1.mp3")
        self.assertIsNone(queue.select_path(self.root / "not-queued.mp3"))
        self.assertEqual(queue.select(99), self.root / "track-2.mp3", "index is clamped")
        self.assertEqual(queue.select(-5), self.root / "track-0.mp3")

    def test_playing_position_is_reported_for_the_queue_number(self) -> None:
        queue = PlayQueue(self.files(3))
        self.assertEqual(queue.position_of(self.root / "track-0.mp3"), 1)
        self.assertEqual(queue.position_of(self.root / "track-2.mp3"), 3)
        self.assertIsNone(queue.position_of(self.root / "absent.mp3"))

    def test_shuffled_play_order_is_reflected_in_the_displayed_number(self) -> None:
        queue = PlayQueue(self.files(4), order=ORDER_SHUFFLE, shuffle_seed=2)
        first_in_order = queue.play_order[0]
        path = queue.entries[first_in_order]
        self.assertEqual(queue.position_of(path), 1)

    def test_an_unknown_shuffle_seed_still_produces_a_valid_order(self) -> None:
        queue = PlayQueue(self.files(3), order="nonsense")
        self.assertEqual(queue.order, ORDER_IN_ORDER)
        self.assertEqual(queue.play_order, [0, 1, 2])

    def test_the_queue_only_accepts_files_it_was_given(self) -> None:
        """A dropped non-audio file is filtered by the page, not silently queued."""
        audio = self.files(1)
        queue = PlayQueue(audio)
        self.assertEqual(queue.entries, audio)


if __name__ == "__main__":
    unittest.main()
