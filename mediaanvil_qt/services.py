"""UI-independent jobs, with an explicit snapshot of all input settings."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from PIL import Image
from sub2lrc.audio_converter import convert_audio_batch
from sub2lrc.image_converter import convert_image_batch
from sub2lrc.converter import convert_content, convert_file, read_subtitle, shift_lrc, unique_output_path
from sub2lrc.embedder import read_lrc
from sub2lrc.audio_metadata import AudioMetadataChanges, read_metadata, write_metadata
from core.tasks import TaskCancelled


EMBEDDABLE_LYRIC_EXTENSIONS=frozenset({'.lrc','.srt','.vtt'})


def prepare_lyrics_for_embedding(source,temporary_directory):
    """Return a validated LRC path, converting SRT/VTT without touching the source."""
    source=Path(source);suffix=source.suffix.lower()
    if suffix=='.lrc':
        read_lrc(source);return source
    if suffix not in EMBEDDABLE_LYRIC_EXTENSIONS:
        raise ValueError('仅支持导入 LRC、SRT 或 VTT 歌词 / 字幕文件')
    content=read_subtitle(source);converted=convert_content(content,suffix,'lrc')
    target=Path(temporary_directory)/('lyrics-'+uuid4().hex+'.lrc')
    target.write_text(converted,encoding='utf-8-sig');return target


def output_directory_problem(directory):
    """Return a reason string when a conversion cannot write to ``directory``.

    An empty value means "save beside each source file", which is always fine.
    """
    if not directory:
        return None
    target = Path(directory)
    if not target.exists():
        return '输出目录不存在或无法访问。'
    if not target.is_dir():
        return '输出目录不是一个文件夹。'
    probe = target / f'.mediaanvil-write-{uuid4().hex}.tmp'
    try:
        probe.write_bytes(b'')
    except OSError:
        return '输出目录不可写，请检查权限或换一个目录。'
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return None


def collect_paths(paths, extensions, recursive=False, cancel_check=None):
    result = []; seen = set()
    for raw in paths:
        if cancel_check: cancel_check()
        path = Path(raw)
        candidates = path.rglob('*') if path.is_dir() and recursive else path.iterdir() if path.is_dir() else (path,)
        for p in candidates:
            if cancel_check: cancel_check()
            key = str(p.resolve()).casefold()
            if p.is_file() and p.suffix.lower() in extensions and key not in seen:
                seen.add(key); result.append(p)
    return tuple(result)


def explain_rejected(paths, extensions, recursive=False):
    """Describe why nothing was imported, so the user sees the real reason."""
    items = [Path(raw) for raw in paths]
    missing = []; unsupported = {}
    for path in items:
        if path.is_file():
            if path.suffix.lower() not in extensions:
                key = path.suffix.lower() or path.name
                unsupported[key] = unsupported.get(key, 0) + 1
        elif path.is_dir():
            pattern = '**/*' if recursive else '*'
            for candidate in path.glob(pattern):
                if candidate.is_file() and candidate.suffix.lower() not in extensions:
                    key = candidate.suffix.lower() or candidate.name
                    unsupported[key] = unsupported.get(key, 0) + 1
        else:
            missing.append(path.name)
    return {'empty': not items, 'missing': tuple(missing), 'unsupported': unsupported}


def tagged_destination(source, directory=''):
    source = Path(source); base = Path(directory) if directory else source.parent
    base.mkdir(parents=True, exist_ok=True)
    target = base / (source.stem + '_tagged' + source.suffix); index = 1
    while target.exists():
        target = base / (source.stem + f'_tagged_{index}' + source.suffix); index += 1
    return target


def convert_files(kind, paths, directory, settings, progress, cancel_check=None, process_callback=None):
    lines = []; outputs = []
    for i, source in enumerate(paths):
        if cancel_check: cancel_check()
        destination = Path(directory) if directory else source.parent
        def report(percent, text=''):
            progress((i + percent / 100) / len(paths) * 100, text or source.name)
        try:
            if kind == 'audio':
                result = convert_audio_batch([source], destination, settings,
                    progress=lambda p, n, total, percent, overall: report(percent),
                    cancel_check=cancel_check, process_callback=process_callback)
                outputs.extend(result.outputs)
                lines.extend('完成：' + str(p) for p in result.outputs)
                lines.extend('失败：' + str(f.source) + ' — ' + f.message for f in result.failures)
            elif kind == 'image':
                result = convert_image_batch([source], destination, settings,
                    progress=lambda p, n, total, percent: report(percent))
                outputs.extend(o.destination for o in result.outputs)
                lines.extend('完成：' + str(o.destination) + ('（透明区域已填白）' if o.transparency_removed else '') for o in result.outputs)
                lines.extend('失败：' + str(f.source) + ' — ' + f.message for f in result.failures)
            else:
                fmt, duration = settings
                target = unique_output_path(destination, source, fmt)
                outputs.append(convert_file(source, target, fmt, duration))
                lines.append('完成：' + str(target))
        except TaskCancelled: raise
        except Exception as exc: lines.append(f'失败：{source} — {exc}')
        report(100)
    return outputs, lines


BATCH_EDITABLE_FIELDS = ('title', 'artist', 'album', 'track', 'year', 'genre')


def batch_edit_tags(audio_paths, values, overwrite, directory, progress):
    """Apply the same tag values to many files.

    ``values`` maps a field name to the text to write. Only non-empty entries are
    applied, so an untouched box never erases an existing tag, and each file is
    written independently: one failure is reported and the batch continues.
    """
    fields = {name: text.strip() for name, text in values.items()
              if name in BATCH_EDITABLE_FIELDS and text and text.strip()}
    if not fields:
        return ['跳过：没有填写任何要批量写入的字段。']
    lines = []
    total = len(audio_paths)
    for index, audio in enumerate(audio_paths):
        if hasattr(progress, 'raise_if_cancelled'):
            progress.raise_if_cancelled()
        try:
            target = None if overwrite else tagged_destination(audio, directory)
            output = write_metadata(audio, AudioMetadataChanges(**fields), target)
            lines.append(f'完成：{output}')
        except TaskCancelled:
            raise
        except Exception as exc:
            lines.append(f'失败：{audio.name} — {exc}')
        progress((index + 1) / total * 100, audio.name)
    return lines


def batch_shift_lyrics(audio_paths, seconds, overwrite, directory, progress):
    """Move the embedded lyrics of many files by the same number of seconds.

    Only files that actually carry lyrics are written; the rest are reported and
    skipped so a folder of instrumentals does not produce a wall of failures.
    The shift is applied to the text, so metadata lines such as ``[ti:]`` survive.
    """
    lines = []
    total = len(audio_paths)
    if not seconds:
        return ['跳过：偏移秒数为 0，没有需要调整的歌词。']
    for index, audio in enumerate(audio_paths):
        if hasattr(progress, 'raise_if_cancelled'):
            progress.raise_if_cancelled()
        try:
            state = read_metadata(audio)
            if not state.has_lyrics or not state.lyrics.strip():
                lines.append(f'跳过：{audio.name}（没有内嵌歌词）')
            else:
                shifted = shift_lrc(state.lyrics, seconds)
                if shifted == state.lyrics:
                    lines.append(f'跳过：{audio.name}（偏移后没有变化）')
                else:
                    target = None if overwrite else tagged_destination(audio, directory)
                    with TemporaryDirectory(prefix='mediaanvil-shift-') as temporary:
                        lyric = Path(temporary) / 'lyrics.lrc'
                        lyric.write_text(shifted, encoding='utf-8-sig')
                        output = write_metadata(audio, AudioMetadataChanges(lyrics_path=lyric), target)
                    lines.append(f'完成：{output}')
        except TaskCancelled:
            raise
        except Exception as exc:
            lines.append(f'失败：{audio.name} — {exc}')
        progress((index + 1) / total * 100, audio.name)
    return lines


def batch_set_cover(audio_paths, cover, overwrite, directory, progress):
    """Write one image as the artwork of many files.

    This is the counterpart to the per-file matching write: matching finds an
    image beside each track, while this puts a single chosen image on all of
    them, which is what replacing the artwork of a whole album needs.
    Formats the tag writer does not accept are converted through a temporary PNG.
    """
    cover = Path(cover)
    lines = []
    total = len(audio_paths)
    if not cover.is_file():
        return ['跳过：没有选择封面图片。']
    for index, audio in enumerate(audio_paths):
        if hasattr(progress, 'raise_if_cancelled'):
            progress.raise_if_cancelled()
        try:
            target = None if overwrite else tagged_destination(audio, directory)
            with TemporaryDirectory(prefix='mediaanvil-cover-') as temporary:
                image = cover
                if cover.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                    with Image.open(cover) as opened:
                        image = Path(temporary) / 'cover.png'
                        opened.convert('RGBA').save(image)
                output = write_metadata(audio, AudioMetadataChanges(cover_path=image), target)
            lines.append(f'完成：{output}')
        except TaskCancelled:
            raise
        except Exception as exc:
            lines.append(f'失败：{audio.name} — {exc}')
        progress((index + 1) / total * 100, audio.name)
    return lines


def write_matches(rows, overwrite, directory, progress):
    lines = []
    for i, (audio, lyric, cover) in enumerate(rows):
        if hasattr(progress, 'raise_if_cancelled'): progress.raise_if_cancelled()
        if not lyric and not cover:
            lines.append(f'跳过：{audio.name}（无已选关联文件）'); continue
        try:
            target = None if overwrite else tagged_destination(audio, directory)
            with TemporaryDirectory(prefix='mediaanvil-match-') as temporary:
                if lyric:lyric=prepare_lyrics_for_embedding(lyric,temporary)
                if cover and cover.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                    with Image.open(cover) as image:
                        cover = Path(temporary) / 'cover.png'
                        image.convert('RGBA').save(cover)
                output = write_metadata(audio, AudioMetadataChanges(lyrics_path=lyric, cover_path=cover), target)
            lines.append(f'完成：{output}')
        except TaskCancelled: raise
        except Exception as exc: lines.append(f'失败：{audio.name} — {exc}')
        progress((i+1)/len(rows)*100, audio.name)
    return lines
