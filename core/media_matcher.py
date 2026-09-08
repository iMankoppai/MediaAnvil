"""Conservative matching of audio files with nearby lyric and cover files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
import re
from typing import Iterable


AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus"})
LYRIC_EXTENSIONS = frozenset({".lrc", ".srt", ".vtt", ".txt"})
COVER_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})


class MatchPriority(IntEnum):
    """Lower values are stronger matching rules."""

    FULL_AUDIO_NAME = 0
    EXACT = 1
    IGNORE_SPACES = 2
    COPY_SUFFIX = 3


_COPY_SUFFIX = re.compile(
    r"(?:\s*[-_]\s*(?:副本|copy)(?:\s*\d+)?|\s*[（(]\s*\d+\s*[）)])$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MediaMatch:
    """Best nearby lyric and cover candidates for one audio file.

    More than one candidate is deliberately retained at the best priority so
    the UI can ask the user to choose instead of silently guessing.
    """

    audio: Path
    lyric_candidates: tuple[Path, ...] = ()
    cover_candidates: tuple[Path, ...] = ()
    lyric_priority: MatchPriority | None = None
    cover_priority: MatchPriority | None = None

    @property
    def lyric(self) -> Path | None:
        return self.lyric_candidates[0] if len(self.lyric_candidates) == 1 else None

    @property
    def cover(self) -> Path | None:
        return self.cover_candidates[0] if len(self.cover_candidates) == 1 else None

    @property
    def lyric_ambiguous(self) -> bool:
        return len(self.lyric_candidates) > 1

    @property
    def cover_ambiguous(self) -> bool:
        return len(self.cover_candidates) > 1

    @property
    def has_matches(self) -> bool:
        return bool(self.lyric_candidates or self.cover_candidates)


def _casefold(value: str) -> str:
    return value.casefold()


def _without_spaces(value: str) -> str:
    return "".join(character for character in value if not character.isspace())


def _without_copy_suffix(value: str) -> str:
    return _COPY_SUFFIX.sub("", value).rstrip()


def _priority(source_stem: str, candidate_stem: str, audio_suffix: str = "") -> MatchPriority | None:
    source = _casefold(source_stem)
    candidate = _casefold(candidate_stem)
    suffix = _casefold(audio_suffix)
    if suffix and candidate.endswith(suffix) and candidate[:-len(suffix)] == source:
        return MatchPriority.FULL_AUDIO_NAME
    if suffix and candidate.endswith(suffix):
        candidate = candidate[:-len(suffix)]
    if candidate == source:
        return MatchPriority.EXACT
    if _without_spaces(candidate) == _without_spaces(source):
        return MatchPriority.IGNORE_SPACES
    if _casefold(_without_copy_suffix(candidate)) == _casefold(_without_copy_suffix(source)):
        return MatchPriority.COPY_SUFFIX
    return None


def _best_candidates(source_stem: str, candidates: Iterable[Path], audio_suffix: str = "") -> tuple[tuple[Path, ...], MatchPriority | None]:
    scored: list[tuple[MatchPriority, Path]] = []
    for candidate in candidates:
        priority = _priority(source_stem, candidate.stem, audio_suffix)
        if priority is not None:
            scored.append((priority, candidate))
    if not scored:
        return (), None
    best_priority = min(priority for priority, _path in scored)
    paths = tuple(
        path for priority, path in sorted(
            scored,
            key=lambda item: (item[0], item[1].name.casefold(), str(item[1]).casefold()),
        ) if priority == best_priority
    )
    return paths, best_priority


def _directory_files(directory: Path) -> tuple[Path, ...]:
    try:
        return tuple(sorted((item for item in directory.iterdir() if item.is_file()), key=lambda item: item.name.casefold()))
    except OSError:
        return ()


def _match_from_files(audio_path: Path, files: Iterable[Path]) -> MediaMatch:
    file_list = tuple(files)
    lyrics, lyric_priority = _best_candidates(
        audio_path.stem,
        (path for path in file_list if path.suffix.casefold() in LYRIC_EXTENSIONS),
        audio_path.suffix,
    )
    covers, cover_priority = _best_candidates(
        audio_path.stem,
        (path for path in file_list if path.suffix.casefold() in COVER_EXTENSIONS),
        audio_path.suffix,
    )
    return MediaMatch(audio_path, lyrics, covers, lyric_priority, cover_priority)


def match_audio_file(audio: str | Path, directory: str | Path | None = None) -> MediaMatch:
    """Find conservative best matches in the audio's containing directory."""
    audio_path = Path(audio)
    search_directory = Path(directory) if directory is not None else audio_path.parent
    files = _directory_files(search_directory)
    return _match_from_files(audio_path, files)


def scan_audio_folder(folder: str | Path, *, include_subfolders: bool = False) -> tuple[MediaMatch, ...]:
    """Scan a folder and match supported audio files, optionally recursively."""
    directory = Path(folder)
    if include_subfolders:
        try:
            files = tuple(sorted((item for item in directory.rglob("*") if item.is_file()), key=lambda item: str(item).casefold()))
        except OSError:
            files = ()
    else:
        files = _directory_files(directory)
    audios = tuple(path for path in files if path.suffix.casefold() in AUDIO_EXTENSIONS)
    if include_subfolders:
        # Keep matching local to each audio file's own directory.  A recursive
        # scan should discover nested albums without mixing same-named files
        # from sibling folders.
        return tuple(
            _match_from_files(audio, (candidate for candidate in files if candidate.parent == audio.parent))
            for audio in audios
        )
    return tuple(_match_from_files(audio, files) for audio in audios)


# Clear aliases for callers that prefer “find” terminology.
find_associated_files = match_audio_file
match_folder = scan_audio_folder


__all__ = [
    "AUDIO_EXTENSIONS",
    "COVER_EXTENSIONS",
    "LYRIC_EXTENSIONS",
    "MatchPriority",
    "MediaMatch",
    "find_associated_files",
    "match_audio_file",
    "match_folder",
    "scan_audio_folder",
]
