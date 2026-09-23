"""Remember where each audio file was left off.

The preview page resumes long recordings, so the position is stored per file
rather than only for the most recent one: a listener can leave several two-hour
files part-way through and come back to any of them.

Three rules decide what is worth remembering, and they exist to keep the feature
from becoming annoying:

* A short listen is not a position. Anything below :data:`MINIMUM_RESUME_SECONDS`
  is treated as sampling a file, so auditioning a folder leaves no trail.
* The tail of a file counts as finished. Within :data:`FINISHED_TAIL_SECONDS` of
  the end the recording is forgotten, so a file played to the end starts over
  instead of resuming on its last seconds.
* The whole feature can be switched off, in which case nothing is read or written.
"""

from __future__ import annotations

import os
from pathlib import Path

# Below this many seconds a listen is treated as sampling, not as progress.
MINIMUM_RESUME_SECONDS = 30.0
# Within this many seconds of the end the file counts as finished.
FINISHED_TAIL_SECONDS = 30.0
SETTING_ENABLED = "remember_playback_position"
SETTING_POSITIONS = "playback_positions"


def position_key(path: str | Path) -> str:
    """Return the key a file's position is stored under.

    The normalised absolute path is enough for the first version; a file that is
    moved loses its position, which is the accepted trade-off for not having to
    hash file contents.
    """
    return os.path.normcase(str(Path(path).resolve()))


def is_finished(position: float, duration: float) -> bool:
    """True when ``position`` is close enough to the end to count as played out."""
    if duration <= 0:
        return False
    return duration - position <= FINISHED_TAIL_SECONDS


def should_remember(position: float, duration: float) -> bool:
    """True when a position is worth storing for later resuming."""
    if duration <= 0:
        return False
    if position < MINIMUM_RESUME_SECONDS:
        return False
    return not is_finished(position, duration)


def saved_position(settings: dict, path: str | Path, duration: float = 0.0) -> float | None:
    """Return the stored position for ``path``, or ``None`` when there is none.

    A stored value that would now count as finished, or that lies beyond the end
    of the file, is ignored and reported as no position.
    """
    if not settings.get(SETTING_ENABLED, True):
        return None
    stored = (settings.get(SETTING_POSITIONS) or {}).get(position_key(path))
    if not isinstance(stored, (int, float)) or isinstance(stored, bool):
        return None
    position = float(stored)
    if position <= 0:
        return None
    if duration > 0 and position >= duration:
        return None
    if is_finished(position, duration):
        return None
    return position


def record_position(settings: dict, path: str | Path, position: float, duration: float) -> bool:
    """Store or clear the position for ``path`` in ``settings``.

    Returns whether a position is now stored. The caller owns persistence; this
    only edits the dictionary so it stays testable without touching disk.
    """
    positions = settings.setdefault(SETTING_POSITIONS, {})
    if not isinstance(positions, dict):
        positions = settings[SETTING_POSITIONS] = {}
    key = position_key(path)
    if not settings.get(SETTING_ENABLED, True) or not should_remember(position, duration):
        positions.pop(key, None)
        return False
    positions[key] = float(position)
    return True


def forget_position(settings: dict, path: str | Path) -> None:
    """Drop the stored position for one file."""
    positions = settings.get(SETTING_POSITIONS)
    if isinstance(positions, dict):
        positions.pop(position_key(path), None)


def clear_positions(settings: dict) -> None:
    """Drop every stored position, used when the feature is switched off."""
    settings[SETTING_POSITIONS] = {}


__all__ = [
    "FINISHED_TAIL_SECONDS",
    "MINIMUM_RESUME_SECONDS",
    "SETTING_ENABLED",
    "SETTING_POSITIONS",
    "clear_positions",
    "forget_position",
    "is_finished",
    "position_key",
    "record_position",
    "saved_position",
    "should_remember",
]
