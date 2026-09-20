"""Explicit packaging check, isolated from normal user settings and media."""
import json
import sys
import wave
from PySide6 import __version__ as qt_version
from PySide6.QtCore import QTimer
from sub2lrc.audio_converter import AudioConversionSettings, find_ffmpeg
from sub2lrc.audio_preview import find_ffplay
from .services import convert_files


def schedule_smoke(app, window, directory):
    directory.mkdir(parents=True, exist_ok=True)
    source=directory/'smoke.wav'
    with wave.open(str(source),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000)
        stream.writeframes(b'\0\0'*4000)

    def finished(result):
        outputs,lines=result
        report={'qt':qt_version,'frozen':bool(getattr(sys,'frozen',False)),
                'pages':window.keys,'tk_loaded':'tkinter' in sys.modules,
                'ffmpeg':str(find_ffmpeg()),'ffplay':str(find_ffplay()),
                'audio_outputs':[str(p) for p in outputs],'results':lines}
        window.navigation.setCurrentRow(window.keys.index('audio'))
        app.processEvents()
        window.grab().save(str(directory/'window.png'))
        (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        window.close()
        app.exit(0 if len(outputs)==1 and not report['tk_loaded'] else 1)

    def fail(message):
        (directory/'error.txt').write_text(message,encoding='utf8')
        app.exit(1)

    window.inform=fail
    def run_smoke_conversion():
        try:
            result = convert_files(
                'audio', [source], str(directory), AudioConversionSettings('mp3', 128), lambda *_: None,
            )
        except Exception as exc:
            fail(str(exc))
            return
        finished(result)

    # This is an executable startup check. Run the tiny conversion after the
    # event loop begins so the frozen process can deterministically exit; GUI
    # worker-thread behavior is covered by the Qt test suite.
    QTimer.singleShot(250, run_smoke_conversion)
