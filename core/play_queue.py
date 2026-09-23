"""The preview page's play queue: what plays, in what order.

Kept separate from the page and from the player so the ordering rules can be
tested on their own. The queue holds paths only; reading tags and durations is
the page's job, because that can fail and must not break the ordering logic.
"""

from __future__ import annotations

import random
from pathlib import Path

ORDER_IN_ORDER = "in_order"
ORDER_SHUFFLE = "shuffle"
PLAYBACK_MODES = ("once", "repeat_one", "repeat_all")


class PlayQueue:
    """An ordered list of files with a current position.

    ``order`` decides what "next" means: in order it follows the list, shuffled it
    follows a stable permutation so that going back returns to the file just
    played rather than to a new random one.
    """

    def __init__(self, entries=None, *, order: str = ORDER_IN_ORDER,
                 shuffle_seed: int | None = None) -> None:
        self.entries: list[Path] = [Path(entry) for entry in (entries or ())]
        self.index = 0 if self.entries else -1
        self.order = order if order in (ORDER_IN_ORDER, ORDER_SHUFFLE) else ORDER_IN_ORDER
        self._seed = shuffle_seed
        self._shuffled: list[int] = []
        self._rebuild_shuffle()

    # -- contents -----------------------------------------------------------
    def _rebuild_shuffle(self) -> None:
        """Build the shuffled order, rotated so the current file plays first.

        Without the rotation the walk starts wherever the current file happens to
        sit in the permutation, and every file before it would never be reached:
        with order [4, 0, 5, 3, 1, 2] and index 0, playback ran 0 -> 5 -> 3 -> 1
        -> 2 and track 4 was silently skipped for the whole session.
        """
        indexes = list(range(len(self.entries)))
        if self.order == ORDER_SHUFFLE:
            random.Random(self._seed).shuffle(indexes)
            if 0 <= self.index < len(self.entries):
                place = indexes.index(self.index)
                indexes = indexes[place:] + indexes[:place]
        self._shuffled = indexes

    def add(self, paths) -> int:
        """Append paths, ignoring ones already queued. Returns how many were new."""
        known = set(self.entries)
        added = 0
        for raw in paths:
            path = Path(raw)
            if path in known:
                continue
            known.add(path)
            self.entries.append(path)
            added += 1
        if added:
            if self.index < 0:
                self.index = 0
            self._rebuild_shuffle()
        return added

    def remove(self, indexes) -> None:
        """Drop the given indexes, keeping the current file selected if it stays."""
        current = self.current
        for index in sorted({int(i) for i in indexes}, reverse=True):
            if 0 <= index < len(self.entries):
                del self.entries[index]
        self._rebuild_shuffle()
        if not self.entries:
            self.index = -1
            return
        if current is not None and current in self.entries:
            self.index = self.entries.index(current)
        else:
            self.index = min(self.index, len(self.entries) - 1)
        self.index = max(0, self.index)

    def clear(self) -> None:
        self.entries.clear()
        self.index = -1
        self._shuffled = []

    def move(self, rows, before_index) -> None:
        """Reorder rows so they sit together at ``before_index``.

        Mirrors the file lists elsewhere in the program: the moved rows keep their
        relative order, and the current file stays selected afterwards.
        """
        rows = sorted({int(row) for row in rows if 0 <= int(row) < len(self.entries)})
        if not rows:
            return
        current = self.current
        moving = [self.entries[row] for row in rows]
        remaining = [entry for i, entry in enumerate(self.entries) if i not in set(rows)]
        target = max(0, min(int(before_index), len(remaining)))
        self.entries = remaining[:target] + moving + remaining[target:]
        self._rebuild_shuffle()
        if current is not None and current in self.entries:
            self.index = self.entries.index(current)
        else:
            self.index = max(0, min(self.index, len(self.entries) - 1))

    # -- selection ----------------------------------------------------------
    @property
    def current(self) -> Path | None:
        if 0 <= self.index < len(self.entries):
            return self.entries[self.index]
        return None

    def select(self, index: int) -> Path | None:
        if not self.entries:
            self.index = -1
            return None
        self.index = max(0, min(int(index), len(self.entries) - 1))
        # The shuffled order is anchored on the current file, so changing the
        # selection has to rebuild it; otherwise the new current file can sit
        # mid-permutation and the files ahead of it are never reached.
        self._rebuild_shuffle()
        return self.current

    def select_path(self, path) -> Path | None:
        target = Path(path)
        if target in self.entries:
            self.index = self.entries.index(target)
            self._rebuild_shuffle()
            return self.current
        return None

    # -- ordering -----------------------------------------------------------
    @property
    def play_order(self) -> list[int]:
        """The indexes in the sequence they will play."""
        if self.order == ORDER_SHUFFLE:
            return list(self._shuffled)
        return list(range(len(self.entries)))

    def next_index(self, *, mode: str = "once", automatic: bool = True) -> int | None:
        """Return the index to play next, or ``None`` when playback should stop.

        ``automatic`` marks the end of a file; a manual Next always advances even
        in repeat-one, because otherwise the control would appear broken.
        """
        if not self.entries:
            return None
        if mode == "repeat_one" and automatic:
            return self.index
        order = self.play_order
        if not order:
            return None
        try:
            place = order.index(self.index)
        except ValueError:
            return order[0]
        if place + 1 < len(order):
            return order[place + 1]
        if mode == "repeat_all":
            return order[0]
        return None

    def previous_index(self) -> int | None:
        if not self.entries:
            return None
        order = self.play_order
        try:
            place = order.index(self.index)
        except ValueError:
            return order[0]
        if place - 1 >= 0:
            return order[place - 1]
        return order[-1] if len(order) > 1 else order[0]

    def advance(self, *, mode: str = "once", automatic: bool = True) -> Path | None:
        target = self.next_index(mode=mode, automatic=automatic)
        if target is None:
            return None
        self.index = target
        return self.current

    def rewind(self) -> Path | None:
        target = self.previous_index()
        if target is None:
            return None
        self.index = target
        return self.current

    # -- presentation -------------------------------------------------------
    def set_order(self, order: str, *, shuffle_seed: int | None = None) -> None:
        current = self.current
        self.order = order if order in (ORDER_IN_ORDER, ORDER_SHUFFLE) else ORDER_IN_ORDER
        if shuffle_seed is not None:
            self._seed = shuffle_seed
        self._rebuild_shuffle()
        if current is not None and current in self.entries:
            self.index = self.entries.index(current)

    def position_of(self, path) -> int | None:
        """The 1-based place a file occupies in the play order, for display."""
        target = Path(path)
        if target not in self.entries:
            return None
        order = self.play_order
        try:
            return order.index(self.entries.index(target)) + 1
        except ValueError:
            return None

    def __len__(self) -> int:
        return len(self.entries)


__all__ = ["ORDER_IN_ORDER", "ORDER_SHUFFLE", "PLAYBACK_MODES", "PlayQueue"]
