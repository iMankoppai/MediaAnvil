"""Audit DLL provenance and require a successful frozen-app smoke test."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]


def binary_entries(value):
    if isinstance(value, (tuple, list)):
        if (len(value) == 3 and value[2] == 'BINARY'
                and isinstance(value[0], str) and isinstance(value[1], str)):
            yield value
        else:
            for child in value:
                yield from binary_entries(child)


def audit_sources(toc_path, allowed_roots):
    entries = binary_entries(ast.literal_eval(toc_path.read_text(encoding='utf8')))
    rejected = []
    for destination, source, _ in entries:
        path = Path(source).resolve()
        if not any(path.is_relative_to(base.resolve()) for base in allowed_roots):
            rejected.append(f'{destination}: {source}')
    if rejected:
        raise RuntimeError('Unexpected dependency source(s):\n' + '\n'.join(rejected))


def verify_release_documents(directory):
    """The user guide promises these files inside the release folder."""
    required = ('USER_GUIDE.md', 'USER_GUIDE.en.md', 'README-Qt.md', 'README-Qt.en.md',
                'LICENSE', 'THIRD_PARTY_NOTICES.md')
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise RuntimeError('Release folder is missing required document(s): ' + ', '.join(missing))
    licenses = directory / 'licenses/qt'
    if not licenses.is_dir() or not any(licenses.glob('*.txt')):
        raise RuntimeError('Release folder is missing licenses/qt license texts')


def verify():
    audit_sources(ROOT / 'build/MediaAnvilQt/Analysis-00.toc',
                  [Path(sys.base_prefix), Path(sys.prefix),
                   Path(os.environ['SystemRoot']), ROOT / 'vendor'])
    directory = ROOT / 'dist/MediaAnvilQt'
    verify_release_documents(directory)
    bundled_icu = tuple(directory.rglob('icu*.dll'))
    if bundled_icu:
        names = '\n'.join(str(path.relative_to(directory)) for path in bundled_icu)
        raise RuntimeError('ICU must be loaded from Windows, not bundled beside Qt6Core.dll:\n' + names)
    scratch = ROOT / '.test-tools/qt'
    scratch.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='frozen-check-', dir=scratch))
    environment = os.environ.copy()
    system_root = Path(os.environ['SystemRoot'])
    environment['PATH'] = os.pathsep.join((str(system_root / 'System32'), str(system_root)))
    try:
        completed = subprocess.run(
            [str(directory / 'MediaAnvilQt.exe'), '--smoke-test', str(output)],
            cwd=directory,
            env=environment,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Frozen Qt smoke test timed out; an error dialog may be blocking startup') from exc
    if completed.returncode != 0:
        error_file = output / 'error.txt'
        detail = error_file.read_text(encoding='utf8') if error_file.is_file() else 'no error report'
        raise RuntimeError(f'Frozen Qt smoke test failed with code {completed.returncode}: {detail}')
    report_file = output / 'report.json'
    if not report_file.is_file():
        raise RuntimeError('Frozen Qt smoke test did not create report.json')
    report = json.loads(report_file.read_text(encoding='utf8'))
    if not report.get('frozen') or len(report.get('audio_outputs', ())) != 1:
        raise RuntimeError(f'Frozen Qt smoke report is incomplete: {report}')

    source = output / 'smoke.wav'
    with wave.open(str(source), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b'\0\0' * 4000)
    ffmpeg = directory / '_internal' / 'ffmpeg.exe'
    target = output / 'ffmpeg-smoke.mp3'
    subprocess.run([str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(source),
                    '-codec:a', 'libmp3lame', '-b:a', '128k', str(target)], check=True, timeout=30)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError('Bundled FFmpeg did not create a valid output file')
    ffplay = directory / '_internal' / 'ffplay.exe'
    subprocess.run([str(ffplay), '-version'], check=True, timeout=15,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    print(f'Frozen Qt startup, in-app conversion and FFplay verified: {output}')


if __name__ == '__main__':
    verify()
