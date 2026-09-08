"""UI-independent jobs, with an explicit snapshot of all input settings."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from PIL import Image
from sub2lrc.audio_converter import convert_audio_batch
from sub2lrc.image_converter import convert_image_batch
from sub2lrc.converter import convert_content, convert_file, read_subtitle, unique_output_path
from sub2lrc.embedder import read_lrc
from sub2lrc.audio_metadata import AudioMetadataChanges, write_metadata


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


def collect_paths(paths, extensions, recursive=False):
    result = []; seen = set()
    for raw in paths:
        path = Path(raw)
        candidates = path.rglob('*') if path.is_dir() and recursive else path.iterdir() if path.is_dir() else (path,)
        for p in candidates:
            key = str(p.resolve()).casefold()
            if p.is_file() and p.suffix.lower() in extensions and key not in seen:
                seen.add(key); result.append(p)
    return tuple(result)


def tagged_destination(source, directory=''):
    source = Path(source); base = Path(directory) if directory else source.parent
    base.mkdir(parents=True, exist_ok=True)
    target = base / (source.stem + '_tagged' + source.suffix); index = 1
    while target.exists():
        target = base / (source.stem + f'_tagged_{index}' + source.suffix); index += 1
    return target


def convert_files(kind, paths, directory, settings, progress):
    lines = []; outputs = []
    for i, source in enumerate(paths):
        destination = Path(directory) if directory else source.parent
        def report(percent, text=''):
            progress((i + percent / 100) / len(paths) * 100, text or source.name)
        try:
            if kind == 'audio':
                result = convert_audio_batch([source], destination, settings,
                    progress=lambda p, n, total, percent, overall: report(percent))
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
        except Exception as exc: lines.append(f'失败：{source} — {exc}')
        report(100)
    return outputs, lines


def write_matches(rows, overwrite, directory, progress):
    lines = []
    for i, (audio, lyric, cover) in enumerate(rows):
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
        except Exception as exc: lines.append(f'失败：{audio.name} — {exc}')
        progress((i+1)/len(rows)*100, audio.name)
    return lines
