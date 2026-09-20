"""Plan and execute safe, tag-based audio file renames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import string
from typing import Callable, Iterable

from sub2lrc.audio_metadata import AudioMetadataError, read_metadata


SUPPORTED_RENAME_EXTENSIONS = frozenset({".mp3", ".flac", ".m4a", ".ogg", ".opus"})
ALLOWED_TEMPLATE_FIELDS = frozenset({"artist", "title", "album", "track", "year"})
INVALID_FILENAME_CHARS = frozenset('<>:/\\|?*"')
_COPY_SUFFIX = re.compile(r"\s+")
_TRACK_NUMBER = re.compile(r"^\s*(\d+)")
_YEAR_NUMBER = re.compile(r"(\d{4})")


class AudioRenameError(ValueError):
    """Raised for invalid templates or unsafe rename requests."""


class RenameTemplateError(AudioRenameError):
    """Raised when a template contains unsupported syntax or fields."""


class MissingRenameFieldError(AudioRenameError):
    """Raised when a required tag field is empty."""

    def __init__(self, fields: Iterable[str]) -> None:
        self.fields = tuple(fields)
        super().__init__(f"缺少字段：{'、'.join(self.fields)}")


@dataclass(frozen=True)
class RenameFields:
    source: Path
    original_name: str
    extension: str
    artist: str = ""
    title: str = ""
    album: str = ""
    track: str = ""
    year: str = ""

    @property
    def original_stem(self) -> str:
        return Path(self.original_name).stem


@dataclass(frozen=True)
class RenamePlanItem:
    source: Path
    original_name: str
    target: Path | None
    new_name: str
    status: str
    message: str = ""
    fields: RenameFields | None = None

    @property
    def can_rename(self) -> bool:
        return self.target is not None and self.status.startswith("可重命名")


@dataclass(frozen=True)
class RenamePlan:
    items: tuple[RenamePlanItem, ...]
    template: str
    fallback_missing: bool = False

    @property
    def ready_count(self) -> int:
        return sum(item.can_rename for item in self.items)

    @property
    def blocked_count(self) -> int:
        return len(self.items) - self.ready_count


@dataclass(frozen=True)
class RenameRecord:
    old_path: Path
    new_path: Path


@dataclass(frozen=True)
class RenameFailure:
    source: Path
    message: str


@dataclass(frozen=True)
class RenameExecutionResult:
    records: tuple[RenameRecord, ...]
    skipped: tuple[RenamePlanItem, ...]
    failures: tuple[RenameFailure, ...]

    @property
    def success_count(self) -> int:
        return len(self.records)


@dataclass(frozen=True)
class UndoResult:
    records: tuple[RenameRecord, ...]
    failures: tuple[RenameFailure, ...]


def _clean_text(value: object | None) -> str:
    return str(value or "").strip()


def _track_value(value: object | None) -> str:
    raw = _clean_text(value)
    match = _TRACK_NUMBER.match(raw)
    if not match:
        return ""
    number = int(match.group(1))
    return f"{number:02d}"


def _year_value(value: object | None) -> str:
    raw = _clean_text(value)
    match = _YEAR_NUMBER.search(raw)
    return match.group(1) if match else raw


def read_rename_fields(file: str | Path) -> RenameFields:
    """Read fields through MediaAnvil's existing unified metadata API."""
    path = Path(file)
    if path.suffix.casefold() not in SUPPORTED_RENAME_EXTENSIONS:
        raise AudioRenameError("该音频格式暂不支持根据标签自动重命名。")
    if not path.is_file():
        raise AudioRenameError("音频文件不存在或无法访问。")
    try:
        metadata = read_metadata(path)
    except (OSError, AudioMetadataError) as exc:
        raise AudioRenameError(f"读取标签失败：{exc}") from exc
    return RenameFields(
        source=path,
        original_name=path.name,
        extension=path.suffix,
        artist=_clean_text(getattr(metadata, "artist", "")),
        title=_clean_text(getattr(metadata, "title", "")),
        album=_clean_text(getattr(metadata, "album", "")),
        track=_track_value(getattr(metadata, "track", "")),
        year=_year_value(getattr(metadata, "year", "")),
    )


def scan_audio_files(folder: str | Path, *, include_subfolders: bool = False) -> tuple[Path, ...]:
    """Collect supported tag-bearing audio files from a folder."""
    directory = Path(folder)
    if not directory.is_dir():
        return ()
    try:
        iterator = directory.rglob("*") if include_subfolders else directory.iterdir()
        return tuple(sorted(
            (path for path in iterator if path.is_file() and path.suffix.casefold() in SUPPORTED_RENAME_EXTENSIONS),
            key=lambda path: str(path).casefold(),
        ))
    except OSError:
        return ()


def validate_template(template: str) -> tuple[str, ...]:
    """Validate a simple ``str.format`` template and return used fields."""
    if not template.strip():
        raise RenameTemplateError("重命名模板不能为空。")
    fields: list[str] = []
    formatter = string.Formatter()
    try:
        parsed = tuple(formatter.parse(template))
    except ValueError as exc:
        raise RenameTemplateError(f"模板格式错误：{exc}") from exc
    for _literal, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if not field_name or not field_name.isidentifier() or field_name not in ALLOWED_TEMPLATE_FIELDS:
            raise RenameTemplateError(f"模板包含未知变量：{{{field_name or ''}}}")
        if format_spec or conversion:
            raise RenameTemplateError("模板变量不支持格式化参数或转换标记。")
        fields.append(field_name)
    return tuple(dict.fromkeys(fields))


def sanitize_filename(value: str) -> str:
    """Make a Windows-safe filename stem without changing its extension."""
    cleaned = "".join(" " if character in INVALID_FILENAME_CHARS or ord(character) < 32 else character for character in value)
    cleaned = _COPY_SUFFIX.sub(" ", cleaned).strip().rstrip(".").rstrip()
    return cleaned


def _field_values(fields: RenameFields) -> dict[str, str]:
    return {
        "artist": fields.artist,
        "title": fields.title,
        "album": fields.album,
        "track": fields.track,
        "year": fields.year,
    }


def render_filename_template(
    template: str,
    fields: RenameFields,
    *,
    fallback_missing: bool = False,
    max_length: int = 240,
) -> str:
    """Render and sanitize a filename, including the original extension."""
    used_fields = validate_template(template)
    values = _field_values(fields)
    missing = tuple(field for field in used_fields if not values[field])
    if missing and not fallback_missing:
        raise MissingRenameFieldError(missing)
    if missing and fallback_missing:
        for field in missing:
            values[field] = fields.original_stem
    try:
        stem = template.format_map(values)
    except (KeyError, ValueError) as exc:
        raise RenameTemplateError(f"模板渲染失败：{exc}") from exc
    stem = sanitize_filename(stem)
    if not stem:
        raise AudioRenameError("生成的文件名为空。")
    extension = fields.extension
    allowed_stem_length = max(1, max_length - len(extension))
    stem = stem[:allowed_stem_length].rstrip(" .")
    if not stem:
        raise AudioRenameError("生成的文件名为空。")
    return f"{stem}{extension}"


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve()).casefold()
    except OSError:
        return str(path.absolute()).casefold()


def _unique_destination(directory: Path, filename: str, source: Path, reserved: set[str]) -> tuple[Path, bool]:
    candidate = directory / filename
    stem = candidate.stem
    extension = candidate.suffix
    avoided = False
    index = 1
    while candidate.exists() or _path_key(candidate) in reserved or _path_key(candidate) == _path_key(source):
        candidate = directory / f"{stem}_{index}{extension}"
        index += 1
        avoided = True
    return candidate, avoided


def detect_conflicts(items: Iterable[RenamePlanItem]) -> dict[str, tuple[RenamePlanItem, ...]]:
    """Return targets shared by two or more planned items."""
    grouped: dict[str, list[RenamePlanItem]] = {}
    for item in items:
        if item.target is not None:
            grouped.setdefault(_path_key(item.target), []).append(item)
    return {key: tuple(value) for key, value in grouped.items() if len(value) > 1}


def build_rename_plan(
    files: Iterable[str | Path],
    template: str = "{artist} - {title}",
    *,
    fallback_missing: bool = False,
) -> RenamePlan:
    """Read tags and build a preview-only plan without renaming anything."""
    validate_template(template)
    unique_files: list[Path] = []
    seen: set[str] = set()
    for raw_file in files:
        path = Path(raw_file)
        key = _path_key(path)
        if key not in seen:
            seen.add(key)
            unique_files.append(path)

    provisional: list[RenamePlanItem] = []
    for path in unique_files:
        try:
            fields = read_rename_fields(path)
            new_name = render_filename_template(template, fields, fallback_missing=fallback_missing)
        except MissingRenameFieldError as exc:
            provisional.append(RenamePlanItem(path, path.name, None, "—", "缺少标签", str(exc)))
        except (AudioRenameError, OSError) as exc:
            provisional.append(RenamePlanItem(path, path.name, None, "—", "无法读取", str(exc)))
        else:
            target = path.parent / new_name
            if _path_key(target) == _path_key(path):
                provisional.append(RenamePlanItem(path, path.name, target, new_name, "无需修改", "文件名已经符合模板", fields))
            else:
                provisional.append(RenamePlanItem(path, path.name, target, new_name, "可重命名", "", fields))

    conflicts = detect_conflicts(provisional)
    conflict_keys = set(conflicts)
    reserved: set[str] = set()
    planned: list[RenamePlanItem] = []
    for item in provisional:
        if item.target is None:
            planned.append(item)
            continue
        key = _path_key(item.target)
        if key in conflict_keys:
            planned.append(RenamePlanItem(item.source, item.original_name, item.target, item.new_name, "文件名冲突", "批次内有多个文件生成了同名目标", item.fields))
            continue
        if item.status == "无需修改":
            planned.append(item)
            reserved.add(_path_key(item.source))
            continue
        target, avoided = _unique_destination(item.source.parent, item.new_name, item.source, reserved)
        status = "可重命名（自动避让）" if avoided else "可重命名"
        message = "目标文件已存在，已生成安全的新文件名" if avoided else ""
        reserved.add(_path_key(target))
        planned.append(RenamePlanItem(item.source, item.original_name, target, target.name, status, message, item.fields))
    return RenamePlan(tuple(planned), template, fallback_missing)


def execute_rename_plan(
    plan: RenamePlan,
    on_item: Callable[[RenamePlanItem, str], None] | None = None,
) -> RenameExecutionResult:
    """Execute only approved plan items; one filesystem error never aborts the batch."""
    records: list[RenameRecord] = []
    skipped: list[RenamePlanItem] = []
    failures: list[RenameFailure] = []
    for item in plan.items:
        if not item.can_rename:
            skipped.append(item)
            if on_item:
                on_item(item, "跳过")
            continue
        assert item.target is not None
        try:
            if not item.source.is_file():
                raise OSError("源文件不存在或无法访问")
            if item.target.exists():
                raise OSError("目标文件已存在，未覆盖")
            item.source.rename(item.target)
        except (OSError, ValueError) as exc:
            failures.append(RenameFailure(item.source, str(exc)))
            if on_item:
                on_item(item, "失败")
            continue
        record = RenameRecord(item.source, item.target)
        records.append(record)
        if on_item:
            on_item(item, "已完成")
    return RenameExecutionResult(tuple(records), tuple(skipped), tuple(failures))


def undo_rename(records: Iterable[RenameRecord]) -> UndoResult:
    """Undo the latest batch only when both paths are still safe to use."""
    restored: list[RenameRecord] = []
    failures: list[RenameFailure] = []
    for record in reversed(tuple(records)):
        try:
            if not record.new_path.is_file():
                raise OSError("新文件名不存在")
            if record.old_path.exists():
                raise OSError("原文件名已被其他文件占用")
            record.new_path.rename(record.old_path)
        except OSError as exc:
            failures.append(RenameFailure(record.new_path, str(exc)))
            continue
        restored.append(record)
    return UndoResult(tuple(restored), tuple(failures))


__all__ = [
    "ALLOWED_TEMPLATE_FIELDS",
    "AudioRenameError",
    "MissingRenameFieldError",
    "RenameExecutionResult",
    "RenameFailure",
    "RenameFields",
    "RenamePlan",
    "RenamePlanItem",
    "RenameRecord",
    "RenameTemplateError",
    "SUPPORTED_RENAME_EXTENSIONS",
    "UndoResult",
    "build_rename_plan",
    "detect_conflicts",
    "execute_rename_plan",
    "read_rename_fields",
    "render_filename_template",
    "scan_audio_files",
    "sanitize_filename",
    "undo_rename",
    "validate_template",
]
