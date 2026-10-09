"""Qt playback controls use the decoder's clock and keep the stream alive."""
from PySide6.QtCore import QUrl
from sub2lrc.audio_preview import PlaybackState, AudioPreviewError, MIN_SPEED, MAX_SPEED


class QtAudioPreviewPlayer:
    def __init__(self,prepared,parent=None):
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        self.source=prepared.source;self.duration=prepared.duration
        self.volume=prepared.volume;self.speed=prepared.speed
        self.fallback=prepared;self.compatibility=False;self.last_error='';self._closed=False
        self._state=PlaybackState.STOPPED;self._ended=False;self._pending_position=None
        self.media=QMediaPlayer(parent);self.audio=QAudioOutput(self.media)
        self.audio.setVolume(self.volume/100);self.media.setAudioOutput(self.audio)
        self.media.setPitchCompensation(True)
        self.media.errorOccurred.connect(self._error)
        self.media.mediaStatusChanged.connect(self._status)
        self.media.setSource(QUrl.fromLocalFile(str(getattr(prepared,'qt_source',self.source).resolve())))

    @property
    def state(self):return self.fallback.state if self.compatibility else self._state

    @property
    def position(self):
        if self.compatibility:return self.fallback.position
        if self._ended:return self.duration
        if self._pending_position is not None:return self._pending_position
        return min(self.duration,max(0,self.media.position()/1000))

    def _status(self,status):
        from PySide6.QtMultimedia import QMediaPlayer
        if self.compatibility or self._closed:return
        if status==QMediaPlayer.MediaStatus.EndOfMedia:
            self._ended=True;self._state=PlaybackState.STOPPED
        elif status in (QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia):
            if self._pending_position is not None:
                position=self._pending_position;self._pending_position=None
                self.media.setPosition(round(position*1000))

    def _error(self,*args):
        if self.compatibility or self._closed:return
        position=self.position;state=self._state
        self.last_error=self.media.errorString()
        self.compatibility=True;self.media.stop()
        if hasattr(self.fallback,'qt_source'):self.fallback.source=self.fallback.qt_source
        self.fallback.set_volume(self.volume);self.fallback.set_speed(self.speed);self.fallback.seek(position)
        if state in (PlaybackState.PLAYING,PlaybackState.PAUSED):
            try:
                self.fallback.play()
                if state==PlaybackState.PAUSED:self.fallback.pause()
            except AudioPreviewError as exc:self.last_error=str(exc)

    def play(self):
        if self.compatibility:return self.fallback.play()
        if self._ended or self.position>=self.duration:self.seek(0)
        self._state=PlaybackState.PLAYING;self.media.play()

    def pause(self):
        if self.compatibility:return self.fallback.pause()
        if self._state!=PlaybackState.PLAYING:return
        self._state=PlaybackState.PAUSED;self.media.pause()

    def stop(self):
        if self.compatibility:return self.fallback.stop()
        self._state=PlaybackState.STOPPED;self._ended=False;self._pending_position=None;self.media.stop();self.media.setPosition(0)

    def seek(self,position):
        target=min(self.duration,max(0,float(position)))
        if self.compatibility:return self.fallback.seek(target)
        from PySide6.QtMultimedia import QMediaPlayer
        self._ended=False
        self._pending_position=target if self.media.mediaStatus() in (QMediaPlayer.MediaStatus.LoadingMedia,QMediaPlayer.MediaStatus.NoMedia) else None
        self.media.setPosition(round(target*1000))

    def set_volume(self,volume):
        if not 0<=volume<=100:raise AudioPreviewError('音量必须在 0 到 100 之间。')
        self.volume=volume
        if self.compatibility:self.fallback.set_volume(volume)
        else:self.audio.setVolume(volume/100)

    def set_speed(self,speed):
        speed=float(speed)
        if not MIN_SPEED<=speed<=MAX_SPEED:raise AudioPreviewError('播放速度超出支持范围。')
        self.speed=speed
        if self.compatibility:return self.fallback.set_speed(speed)
        from PySide6.QtMultimedia import QMediaPlayer
        if speed!=1 and self.media.pitchCompensationAvailability()==QMediaPlayer.PitchCompensationAvailability.Unavailable:
            self._error();return
        self.media.setPlaybackRate(speed)

    def close(self):
        if self._closed:return
        self._closed=True;self._state=PlaybackState.STOPPED
        self.fallback.close();self.media.stop();self.media.setSource(QUrl());self.media.deleteLater()
        # Flush this object's destruction before removing the scratch media.
        # Merely waiting on the GUI thread prevents deleteLater from running.
        from PySide6.QtCore import QCoreApplication,QEvent
        QCoreApplication.sendPostedEvents(self.media,QEvent.Type.DeferredDelete)
        release_playback_copy(self.fallback)


def prepare_playback_copy(prepared,report):
    """Use scratch media so playback never locks the editable original."""
    import tempfile
    from pathlib import Path
    try:__import__('PySide6.QtMultimedia')
    except ImportError:return
    temporary=tempfile.TemporaryDirectory(prefix='mediaanvil-playback-')
    target=Path(temporary.name)/('audio'+prepared.source.suffix)
    try:
        with prepared.source.open('rb') as source,target.open('wb') as output:
            while data:=source.read(1024*1024):
                report.raise_if_cancelled();output.write(data)
    except BaseException:
        temporary.cleanup();raise
    prepared.qt_directory=temporary;prepared.qt_source=target


def release_playback_copy(prepared):
    temporary=getattr(prepared,'qt_directory',None)
    if temporary:
        import time
        for attempt in range(5):
            try:temporary.cleanup();return
            except PermissionError:
                if attempt==4:raise
                time.sleep(.025*2**attempt)


def realtime_player(prepared,parent=None):
    from sub2lrc.audio_preview import AudioPreviewPlayer
    if not isinstance(prepared,AudioPreviewPlayer):return prepared
    try:return QtAudioPreviewPlayer(prepared,parent)
    except ImportError:return prepared
