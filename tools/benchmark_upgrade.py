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
import argparse
from threading import Event, Thread
from process_memory import process_tree_mib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.media_matcher import DirectoryMatchIndex, _match_from_files
from sub2lrc.audio_converter import find_ffmpeg, _creation_flags
from sub2lrc.audio_join import audio_peaks


def measure(function):
    stopped=Event();memory=[]
    def sample():
        while not stopped.is_set():
            value=process_tree_mib()
            if value is not None:memory.append(value)
            stopped.wait(.1)
    sampler=Thread(target=sample,daemon=True);sampler.start()
    tracemalloc.start();started=time.perf_counter()
    try:
        result=function();elapsed=time.perf_counter()-started
        _,peak=tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop();stopped.set();sampler.join(timeout=2)
    return result,{'seconds':round(elapsed,4),'python_peak_mib':round(peak/1024/1024,3),
        'process_tree_peak_mib':round(max(memory),3) if memory else None,'memory_sample_interval_ms':100}


def benchmark(extended=False,audios=(),work_directory=None,skip_legacy=False):
    report={}
    for count in (1000,10000):
        files=tuple(Path(f'song-{i:05d}{suffix}') for i in range(count) for suffix in ('.mp3','.lrc','.png'))
        matching_audios=files[::3]
        def indexed():
            index=DirectoryMatchIndex(files)
            return tuple(index.match(audio) for audio in matching_audios)
        matches,timing=measure(indexed)
        assert all(m.lyric and m.cover for m in matches)
        report[f'matching_{count}_indexed']=timing
        if count==1000 and not skip_legacy:
            previous,old_timing=measure(lambda:tuple(_match_from_files(audio,files) for audio in matching_audios))
            assert previous==matches
            report['matching_1000_previous']=old_timing
    ffmpeg=find_ffmpeg()
    with tempfile.TemporaryDirectory(prefix='mediaanvil-benchmark-',dir=work_directory) as temporary:
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
        if extended:
            for name,seconds,rate,channels in (('stereo_music',600,44100,2),('long_podcast_surrogate',1800,16000,1)):
                generated=Path(temporary)/(name+'.flac')
                subprocess.run([str(ffmpeg),'-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
                    '-i',f'sine=frequency=330:sample_rate={rate}','-t',str(seconds),'-ac',str(channels),str(generated)],check=True,creationflags=_creation_flags())
                _,timing=measure(lambda:audio_peaks(generated,cache_directory=cache))
                report[name]={'synthetic':True,'seconds_of_audio':seconds,'sample_rate':rate,'channels':channels,**timing}
            broken=Path(temporary)/'corrupt.flac';broken.write_bytes(b'broken media')
            try:audio_peaks(broken)
            except ValueError as exc:report['corrupt_media']={'rejected':True,'message':str(exc)}
            else:raise AssertionError('Corrupt media was accepted')
        for audio in audios:
            try:
                _,timing=measure(lambda:audio_peaks(audio,cache_directory=cache))
                report['input:'+Path(audio).name]={'synthetic':False,**timing}
            except ValueError as exc:report['input:'+Path(audio).name]={'error':str(exc)}
        from PySide6.QtWidgets import QApplication
        from mediaanvil_qt.virtual_table import VirtualTable
        qt=QApplication.instance() or QApplication([])
        view=VirtualTable(['文件','状态']);rows=[(f'{i}.mp3','已完成') for i in range(10000)]
        _,timing=measure(lambda:view.reset_rows(rows));qt.processEvents()
        assert view.rowCount()==10000
        report['table_10000_rows']=timing;view.close()
        def filter_rows():
            for i in range(view.rowCount()):view.setRowHidden(i,'9999' not in view.item(i,0).text())
            view.commit_filter();return view.model().rowCount()
        visible,timing=measure(filter_rows);assert visible==1
        report['table_10000_filter']=timing
        report['work_directory']=str(Path(temporary).parent)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extended',action='store_true',help='Include non-silent stereo and 30-minute signals')
    parser.add_argument('--skip-legacy',action='store_true',help='Skip the slow historical matching implementation')
    parser.add_argument('--audio',type=Path,action='append',default=[],help='Measure existing audio read-only; repeat for multiple files')
    parser.add_argument('--work-directory',type=Path,help='Existing scratch directory, e.g. a different test disk')
    parser.add_argument('--output',type=Path,default=ROOT/'.test-tools'/'upgrade-benchmark.json')
    args=parser.parse_args()
    report=benchmark(args.extended,args.audio,args.work_directory,args.skip_legacy);output=args.output;output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report,indent=2))
