"""Conservative matching of audio files with nearby lyric and cover files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
import re
from typing import Callable, Iterable

from core.tasks import TaskCancelled


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
    source = source_stem.casefold()
    candidate = candidate_stem.casefold()
    suffix = audio_suffix.casefold()
    if suffix and candidate.endswith(suffix):
        candidate_without_suffix = candidate[:-len(suffix)]
        if candidate_without_suffix == source:
            return MatchPriority.FULL_AUDIO_NAME
        candidate = candidate_without_suffix
    if candidate == source:
        return MatchPriority.EXACT
    if _without_spaces(candidate) == _without_spaces(source):
        return MatchPriority.IGNORE_SPACES
    if _without_copy_suffix(candidate) == _without_copy_suffix(source):
        return MatchPriority.COPY_SUFFIX
    return None


def _best_candidates(source_stem: str, candidates: Iterable[Path], audio_suffix: str = "") -> tuple[tuple[Path, ...], MatchPriority | None]:
    scored: list[tuple[MatchPriority, Path]] = []
    best_priority: MatchPriority | None = None
    for candidate in candidates:
        priority = _priority(source_stem, candidate.stem, audio_suffix)
        if priority is None:
            continue
        if best_priority is None or priority < best_priority:
            best_priority = priority
            scored = [(priority, candidate)]
        elif priority == best_priority:
            scored.append((priority, candidate))
    if not scored:
        return (), None
    paths = tuple(
        path for _priority, path in sorted(
            scored,
            key=lambda item: (item[1].name.casefold(), str(item[1]).casefold()),
        )
    )
    return paths, best_priority


def _directory_files(directory: Path) -> tuple[Path, ...]:
    try:
        return tuple(sorted((item for item in directory.iterdir() if item.is_file()), key=lambda item: item.name.casefold()))
    except OSError:
        return ()


def _match_from_files(audio_path: Path, files: Iterable[Path]) -> MediaMatch:
    file_list = tuple(files)
    suffix = audio_path.suffix.casefold()
    audio_stem = audio_path.stem.casefold()
    lyric_candidates: list[Path] = []
    cover_candidates: list[Path] = []
    for candidate in file_list:
        candidate_suffix = candidate.suffix.casefold()
        if candidate_suffix in LYRIC_EXTENSIONS:
            lyric_candidates.append(candidate)
        elif candidate_suffix in COVER_EXTENSIONS:
            cover_candidates.append(candidate)
    lyrics, lyric_priority = _best_candidates(
        audio_stem, lyric_candidates, suffix,
    )
    covers, cover_priority = _best_candidates(
        audio_stem, cover_candidates, suffix,
    )
    return MediaMatch(audio_path, lyrics, covers, lyric_priority, cover_priority)


class DirectoryMatchIndex:
    """Index normalised stems once, retaining conservative priority scoring."""
    def __init__(self, files: Iterable[Path], cancel_check=None):
        self.names: dict[tuple[int, str], set[Path]] = {}
        for path in files:
            if cancel_check:cancel_check()
            if path.suffix.casefold() not in LYRIC_EXTENSIONS | COVER_EXTENSIONS:continue
            stem=path.stem.casefold();stems={stem}
            suffix=Path(stem).suffix
            if suffix in AUDIO_EXTENSIONS:stems.add(stem[:-len(suffix)])
            for name in stems:
                for level,key in enumerate((name,_without_spaces(name),_without_copy_suffix(name))):
                    self.names.setdefault((level,key),set()).add(path)

    @classmethod
    def from_directory(cls, directory: Path, cancel_check=None):
        return cls(_directory_files(directory),cancel_check)

    def candidates(self, stem: str) -> tuple[Path, ...]:
        stem=stem.casefold();paths=set()
        for level,key in enumerate((stem,_without_spaces(stem),_without_copy_suffix(stem))):
            paths.update(self.names.get((level,key),()))
        return tuple(sorted(paths,key=lambda p:(p.name.casefold(),str(p).casefold())))

    def match(self, audio: Path) -> MediaMatch:
        return _match_from_files(audio,self.candidates(audio.stem))


def match_audio_files(paths: Iterable[Path], cancel_check=None) -> tuple[MediaMatch, ...]:
    indexes={};matches=[]
    for path in map(Path,paths):
        if cancel_check:cancel_check()
        if path.parent not in indexes:indexes[path.parent]=DirectoryMatchIndex.from_directory(path.parent,cancel_check)
        matches.append(indexes[path.parent].match(path))
    return tuple(matches)


def matched_companions(
    audio: str | Path,
    suffixes: Iterable[str],
    directory: str | Path | None = None,
    index: DirectoryMatchIndex | None = None,
) -> tuple[Path, ...]:
    """Return same-name companion files safe enough to rename with the audio.

    Strong exact/full-name matches may all follow the audio. Weaker matches are
    used only when there is exactly one best candidate, so ambiguous copies are
    never renamed automatically.
    """
    audio_path = Path(audio)
    wanted = {suffix.casefold() for suffix in suffixes}
    search_directory = Path(directory) if directory is not None else audio_path.parent
    candidates = tuple(
        path for path in (index.candidates(audio_path.stem) if index else _directory_files(search_directory))
        if path.suffix.casefold() in wanted
    )
    strong = tuple(
        path for path in candidates
        if _priority(audio_path.stem, path.stem, audio_path.suffix)
        in {MatchPriority.FULL_AUDIO_NAME, MatchPriority.EXACT}
    )
    if strong:
        return tuple(sorted(strong, key=lambda path: (path.name.casefold(), str(path).casefold())))
    best, priority = _best_candidates(audio_path.stem, candidates, audio_path.suffix)
    if priority in {MatchPriority.IGNORE_SPACES, MatchPriority.COPY_SUFFIX} and len(best) == 1:
        return best
    return ()


def match_audio_file(audio: str | Path, directory: str | Path | None = None) -> MediaMatch:
    """Find conservative best matches in the audio's containing directory."""
    audio_path = Path(audio)
    search_directory = Path(directory) if directory is not None else audio_path.parent
    return DirectoryMatchIndex.from_directory(search_directory).match(audio_path)


def scan_audio_folder(
    folder: str | Path,
    *,
    include_subfolders: bool = False,
    cancel_check: Callable[[], None] | None = None,
) -> tuple[MediaMatch, ...]:
    """Scan a folder and match supported audio files, optionally recursively."""
    directory = Path(folder)
    if include_subfolders:
        try:
            files_by_directory: dict[Path, list[Path]] = {}
            for item in directory.rglob("*"):
                if cancel_check:
                    cancel_check()
                if item.is_file():
                    files_by_directory.setdefault(item.parent, []).append(item)
            for items in files_by_directory.values():
                items.sort(key=lambda item: item.name.casefold())
        except OSError:
            files_by_directory = {}
        audios = sorted(
            (path for items in files_by_directory.values() for path in items if path.suffix.casefold() in AUDIO_EXTENSIONS),
            key=lambda item: str(item).casefold(),
        )
        matches = []
        indexes={}
        for audio in audios:
            if cancel_check:
                cancel_check()
            if audio.parent not in indexes:indexes[audio.parent]=DirectoryMatchIndex(files_by_directory[audio.parent],cancel_check)
            matches.append(indexes[audio.parent].match(audio))
        return tuple(matches)
    else:
        files = _directory_files(directory)
    audios = tuple(path for path in files if path.suffix.casefold() in AUDIO_EXTENSIONS)
    matches = []
    index=DirectoryMatchIndex(files,cancel_check)
    for audio in audios:
        if cancel_check:
            cancel_check()
        matches.append(index.match(audio))
    return tuple(matches)


def missing_media_check(
    folder: str | Path,
    *,
    include_subfolders: bool = False,
    check_tags: bool = True,
    cancel_check: Callable[[], None] | None = None,
) -> tuple["MediaCheckRow", ...]:
    """Scan a folder and report what each audio file is missing.

    Lyrics and covers are checked with the same conservative matching rules as
    the smart-matching panel. Tag checks use the normal metadata reader, so an
    unreadable or read-only file is reported as a tag problem instead of being
    silently skipped.
    """
    directory = Path(folder)
    if not directory.is_dir():
        return ()
    matches = scan_audio_folder(directory, include_subfolders=include_subfolders, cancel_check=cancel_check)
    rows: list[MediaCheckRow] = []
    for match in matches:
        if cancel_check:
            cancel_check()
        missing_lyrics = not match.lyric_candidates
        missing_cover = not match.cover_candidates
        missing_tags: tuple[str, ...] = ()
        tag_error = ""
        if check_tags:
            try:
                from sub2lrc.audio_metadata import read_metadata
                state = read_metadata(match.audio)
                missing_lyrics=missing_lyrics and not getattr(state,'has_lyrics',False)
                missing_cover=missing_cover and not getattr(state,'has_cover',False)
                missing_tags = tuple(
                    field for field, value in (
                        ("title", state.title), ("artist", state.artist), ("album", state.album),
                    ) if not str(value or "").strip()
                )
            except TaskCancelled:
                raise
            except Exception as exc:
                missing_tags = ("tags",)
                tag_error = str(exc)
        rows.append(MediaCheckRow(
            audio=match.audio, missing_lyrics=missing_lyrics, missing_cover=missing_cover,
            missing_tags=missing_tags, tag_error=tag_error,
        ))
    return tuple(rows)


@dataclass(frozen=True)
class MediaCheckRow:
    """One audio file's missing-lyrics/cover/tags report."""

    audio: Path
    missing_lyrics: bool
    missing_cover: bool
    missing_tags: tuple[str, ...] = ()
    tag_error: str = ""

    @property
    def problems(self) -> tuple[str, ...]:
        found = []
        if self.missing_lyrics: found.append("lyrics")
        if self.missing_cover: found.append("cover")
        found.extend(self.missing_tags)
        return tuple(found)

    @property
    def has_problems(self) -> bool:
        return bool(self.problems)


# Clear aliases for callers that prefer “find” terminology.
find_associated_files = match_audio_file
match_folder = scan_audio_folder


__all__ = [
    "AUDIO_EXTENSIONS",
    "MediaCheckRow",
    "missing_media_check",
    "COVER_EXTENSIONS",
    "LYRIC_EXTENSIONS",
    "MatchPriority",
    "MediaMatch",
    "find_associated_files",
    "match_audio_file",
    "match_audio_files",
    "DirectoryMatchIndex",
    "match_folder",
    "matched_companions",
    "scan_audio_folder",
]
