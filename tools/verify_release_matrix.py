"""Frozen startup and Qt layout checks at four scales and a Chinese path."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def verify(executable,output_directory):
    executable=Path(executable).resolve();output_directory=Path(output_directory).resolve()
    output_directory.mkdir(parents=True,exist_ok=True);reports=[]
    # Only copy the supplied release into new scratch space. Existing releases
    # and user media are never moved or modified.
    with tempfile.TemporaryDirectory(prefix='中文用户_媒体验收_',dir=output_directory) as temporary:
        copied=Path(temporary)/'中文路径'/'MediaAnvilQt'
        shutil.copytree(executable.parent,copied)
        environment=os.environ.copy();system=Path(os.environ['SystemRoot'])
        environment['PATH']=os.pathsep.join((str(system/'System32'),str(system)))
        for key in ('PYTHONHOME','PYTHONPATH','QT_PLUGIN_PATH','QML_IMPORT_PATH','QML2_IMPORT_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QT_SCREEN_SCALE_FACTORS','QT_FONT_DPI'):
            environment.pop(key,None)
        def run_case(scratch,factor):
            environment['QT_SCALE_FACTOR']=str(factor)
            subprocess.run([str(copied/executable.name),'--smoke-test',str(scratch)],
                cwd=copied,env=environment,check=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            return json.loads((scratch/'report.json').read_text(encoding='utf8'))
        baseline=run_case(output_directory/'baseline',1)
        native_scale=float(baseline['scale'])
        if native_scale<=0:raise RuntimeError('Invalid native display scale')
        for scale in (1,1.25,1.5,2):
            scratch=output_directory/'中文音频路径'/f'scale-{scale}'
            # QT_SCALE_FACTOR multiplies the native ratio. Calibrate so each
            # reported ratio equals the requested test scale on any host.
            report=run_case(scratch,scale/native_scale)
            if not report.get('frozen') or not report.get('multimedia_decode') or not report.get('layouts_ok') or abs(report.get('scale',0)-scale)>.01:
                raise RuntimeError(f'Frozen validation failed at scale {scale}: {report}')
            reports.append({'requested_scale':scale,**report})
    path=output_directory/'matrix-report.json';path.write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,default=Path('dist/MediaAnvilQt/MediaAnvilQt.exe'))
    parser.add_argument('--output-directory',type=Path,default=Path('.test-tools/release-matrix'))
    args=parser.parse_args();print(verify(args.executable,args.output_directory))
