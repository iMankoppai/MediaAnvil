"""Portable task reports; no media contents are exported."""
import csv
import io
from pathlib import Path
from .persistence import replace_file
import tempfile
import os
import json


def verify_outputs(history,cancel_check=None):
    """Check actual outputs on disk, including images and subtitle files."""
    from .tasks import TaskRecord,TaskCancelled
    from .media_matcher import AUDIO_EXTENSIONS
    records=[]
    for output in dict.fromkeys(r.output for r in history.succeeded if r.output):
        if cancel_check:cancel_check()
        try:
            if not output.is_file() or output.stat().st_size==0:raise ValueError('结果文件不存在或为空。')
            if output.suffix.lower() in AUDIO_EXTENSIONS:
                from sub2lrc.audio_join import audio_duration
                audio_duration(output)
            elif output.suffix.lower() in {'.jpg','.jpeg','.png','.webp','.bmp'}:
                from PIL import Image
                with Image.open(output) as image:image.verify()
            elif output.suffix.lower() in {'.lrc','.srt','.vtt'}:
                from sub2lrc.converter import read_subtitle,parse_text
                parse_text(read_subtitle(output),output.suffix.lower())
            else:
                with output.open('rb') as stream:stream.read(1)
            records.append(TaskRecord(output,'已完成','结果文件可读取',output))
        except TaskCancelled:raise
        except Exception as exc:records.append(TaskRecord(output,'失败',str(exc),output))
    return tuple(records)


def export_report(history,path,translate=lambda value:value):
    def cell(value):
        value=str(value)
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
    buffer=io.StringIO(newline='');writer=csv.writer(buffer)
    writer.writerow([translate(v) for v in ('任务','时间','路径','状态','说明','输出路径','参数')])
    for r in history.records:
        writer.writerow([cell(v) for v in (translate(history.kind),history.created_at,r.source,
            translate(r.state),translate(r.message),r.output or '',json.dumps(history.parameters,ensure_ascii=False))])
    path=Path(path);descriptor,name=tempfile.mkstemp(dir=path.parent,suffix='.csv.tmp')
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8-sig',newline='') as stream:
            stream.write(buffer.getvalue());stream.flush();os.fsync(stream.fileno())
        replace_file(temporary,path)
    finally:temporary.unlink(missing_ok=True)
    return path
