"""Repeatable synthetic matching and long-audio waveform measurements."""
from __future__ import annotations

import array
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tracemalloc

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.media_matcher import DirectoryMatchIndex, _match_from_files
from sub2lrc.audio_converter import find_ffmpeg, _creation_flags
from sub2lrc.audio_join import audio_peaks


def measure(function):
    tracemalloc.start();started=time.perf_counter()
    result=function();elapsed=time.perf_counter()-started
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    return result,{'seconds':round(elapsed,4),'python_peak_mib':round(peak/1024/1024,3)}


def benchmark():
    report={}
    for count in (1000,10000):
        files=tuple(Path(f'song-{i:05d}{suffix}') for i in range(count) for suffix in ('.mp3','.lrc','.png'))
        audios=files[::3]
        def indexed():
            index=DirectoryMatchIndex(files)
            return tuple(index.match(audio) for audio in audios)
        matches,timing=measure(indexed)
        assert all(m.lyric and m.cover for m in matches)
        report[f'matching_{count}_indexed']=timing
        if count==1000:
            previous,old_timing=measure(lambda:tuple(_match_from_files(audio,files) for audio in audios))
            assert previous==matches
            report['matching_1000_previous']=old_timing
    ffmpeg=find_ffmpeg()
    with tempfile.TemporaryDirectory(prefix='mediaanvil-benchmark-') as temporary:
        source=Path(temporary)/'ten-minutes.flac';cache=Path(temporary)/'cache'
        subprocess.run([str(ffmpeg),'-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
                        '-i','anullsrc=r=8000:cl=mono','-t','600',str(source)],check=True,creationflags=_creation_flags())
        def previous_waveform():
            pcm=subprocess.run([str(ffmpeg),'-nostdin','-hide_banner','-loglevel','error','-i',str(source),
                                '-ac','1','-ar','8000','-f','s16le','pipe:1'],capture_output=True,check=True,creationflags=_creation_flags()).stdout
            samples=array.array('h');samples.frombytes(pcm)
            step=len(samples)/900
            return tuple(max((abs(v) for v in samples[int(i*step):int((i+1)*step)]),default=0)/32768 for i in range(900))
        previous,timing=measure(previous_waveform);report['waveform_600s_previous']=timing
        current,timing=measure(lambda:audio_peaks(source,cache_directory=cache));report['waveform_600s_streaming']=timing
        assert current[1]==previous
        cached,timing=measure(lambda:audio_peaks(source,cache_directory=cache));report['waveform_600s_cached']=timing
        assert cached==current
    return report


if __name__=='__main__':
    report=benchmark();output=ROOT/'.test-tools'/'upgrade-benchmark.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report,indent=2))
