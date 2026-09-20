"""Audit DLL provenance and require a successful frozen-app smoke test."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
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


def verify():
    audit_sources(ROOT / 'build/MediaAnvilQt/Analysis-00.toc',
                  [Path(sys.base_prefix), Path(sys.prefix),
                   Path(os.environ['SystemRoot']), ROOT / 'vendor'])
    directory = ROOT / 'dist/MediaAnvilQt'
    scratch = ROOT / '.test-tools/qt'
    scratch.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='frozen-check-', dir=scratch))
    application = subprocess.Popen([str(directory / 'MediaAnvilQt.exe')], cwd=ROOT)
    try:
        time.sleep(3)
        if application.poll() is not None:
            raise RuntimeError(f'Frozen Qt application exited during startup with code {application.returncode}')
    finally:
        if application.poll() is None:
            application.terminate()
            application.wait(timeout=15)

    source = output / 'smoke.wav'
    with wave.open(str(source), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b'\0\0' * 4000)
    ffmpeg = directory / '_internal' / 'ffmpeg.exe'
    target = output / 'smoke.mp3'
    subprocess.run([str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(source),
                    '-codec:a', 'libmp3lame', '-b:a', '128k', str(target)], check=True, timeout=30)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError('Bundled FFmpeg did not create a valid output file')
    ffplay = directory / '_internal' / 'ffplay.exe'
    subprocess.run([str(ffplay), '-version'], check=True, timeout=15,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    print(f'Frozen Qt startup, FFmpeg conversion and FFplay verified: {output}')


if __name__ == '__main__':
    verify()
