"""Generate small, non-copyrighted tone fixtures for manual acceptance."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image
from sub2lrc.audio_converter import find_ffmpeg,_creation_flags
from sub2lrc.audio_metadata import write_metadata,AudioMetadataChanges


def create(directory):
    directory=Path(directory)
    if directory.exists():raise FileExistsError('Choose a new directory to preserve existing files.')
    directory.mkdir(parents=True)
    for number,frequency in ((1,440),(2,660)):
        path=directory/f'待整理{number}.mp3'
        subprocess.run([str(find_ffmpeg()),'-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
            '-i',f'sine=frequency={frequency}:sample_rate=44100','-af','volume=0.5','-t','10',
            '-codec:a','libmp3lame','-b:a','128k','-n',str(path)],check=True,creationflags=_creation_flags())
        write_metadata(path,AudioMetadataChanges(title=f'示例{number}'))
        Image.new('RGB',(240,240),(40,110,200) if number==1 else (70,160,110)).save(path.with_suffix('.png'))
        if number==1:
            path.with_suffix('.lrc').write_text('[ti:示例1]\n[00:00.00]验收开始\n[00:02.00]调整音量与倍速\n[00:05.00]观察歌词同步\n',encoding='utf-8-sig')
        else:
            path.with_name(path.name+'.vtt').write_text('WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n第二段测试音频\n\n00:00:02.000 --> 00:00:05.000\n双后缀字幕匹配\n\n00:00:05.000 --> 00:00:10.000\n检查处理结果\n',encoding='utf-8-sig')
    return directory


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args();print(create(args.directory))
