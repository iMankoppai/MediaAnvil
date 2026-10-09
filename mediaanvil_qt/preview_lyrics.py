"""PreviewLyricsMixin: behavior using the state and controls owned by PreviewPage."""
from pathlib import Path
import tempfile
from uuid import uuid4
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QListWidgetItem
from .services import tagged_destination
from sub2lrc.audio_preview import shift_timeline
from sub2lrc.audio_metadata import write_metadata, AudioMetadataChanges
from sub2lrc.converter import cues_to_lrc, detect_format, parse_text, shift_cues, shift_lrc


class PreviewLyricsMixin:
    def lyric_clicked(self,item):
        index=self.lyrics.row(item)-1
        if self.player and 0<=index<len(self.timeline):
            try:self.player.seek(self.timeline[index].time_seconds);self.poll()
            except Exception as exc:self.app.inform(str(exc))

    def apply_lyric_shift(self):
        """Move the on-screen timeline by the chosen direction and magnitude."""
        seconds=abs(self.lyric_shift.value())
        if self.shift_direction.currentData()=='earlier':seconds=-seconds
        self.shift_lyrics(seconds)

    def shift_lyrics(self,seconds):
        """Re-render the lyric list at a new offset without touching the audio."""
        if not getattr(self,'base_timeline',None):return self.app.inform(self.app.t('请先载入带歌词的音频。'))
        if not seconds:return self.app.inform(self.app.t('请先设置偏移秒数。'))
        shifted=shift_timeline(self.base_timeline,seconds)
        self.applied_shift=seconds;self.timeline=shifted;self.active_line=None
        self.refill_lyrics()
        self.update_display(self.player.position if self.player else 0)
        self.notice(self.app.t(f'歌词已偏移 {seconds:+.2f} 秒（仅预览，未写入文件）'))

    def reset_lyric_shift(self):
        """Return the on-screen timeline to the file's original timing."""
        if not getattr(self,'base_timeline',None):return self.app.inform(self.app.t('请先载入带歌词的音频。'))
        self.applied_shift=0.0;self.timeline=self.base_timeline;self.active_line=None
        self.refill_lyrics();self.update_display(self.player.position if self.player else 0)
        self.notice(self.app.t('已恢复原始歌词时间轴'))

    def refill_lyrics(self):
        """Rebuild the lyric list for the current timeline, keeping the layout."""
        timeline=self.timeline
        self.lyrics.clear()
        if timeline:
            spacer=QListWidgetItem('');spacer.setData(Qt.ItemDataRole.UserRole,'padding');spacer.setFlags(Qt.ItemFlag.NoItemFlags);self.lyrics.addItem(spacer)
        for line in timeline:
            item=QListWidgetItem(line.text or '♪');item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(QSize(1,max(62,30+32*max(1,len(line.text.splitlines())))));self.lyrics.addItem(item)
        if timeline:
            spacer=QListWidgetItem('');spacer.setFlags(Qt.ItemFlag.NoItemFlags);self.lyrics.addItem(spacer);self.lyrics.update_padding()
        else:
            self.lyrics.addItem(self.app.t('暂无同步歌词，可正常播放音频'))

    def shifted_lyric_text(self):
        """Return the offset lyrics as LRC text ready to embed.

        LRC is rewritten in place so metadata lines such as ``[ti:]`` survive.
        SRT and VTT are re-rendered from shifted cues, which is the only correct
        way to move their ``-->`` ranges.
        """
        source=self.lyric_source
        try:kind=detect_format(self.path,source)
        except Exception:kind='lrc'
        if kind=='lrc':return shift_lrc(source,self.applied_shift)
        return cues_to_lrc(shift_cues(parse_text(source,kind),self.applied_shift))

    def save_shifted_lyrics(self):
        """Write the offset lyrics into the audio, keeping every other tag."""
        if not self.path or not getattr(self,'base_timeline',None):return self.app.inform(self.app.t('请先载入带歌词的音频。'))
        if not self.applied_shift:return self.app.inform(self.app.t('请先应用歌词偏移，再保存。'))
        path=self.path
        try:text=self.shifted_lyric_text()
        except Exception as exc:return self.app.inform(str(exc))
        def work(report):
            with tempfile.TemporaryDirectory(prefix='mediaanvil-preview-') as temporary:
                lyrics=Path(temporary)/('shifted-'+uuid4().hex+'.lrc')
                lyrics.write_text(text,encoding='utf-8')
                target=tagged_destination(path)
                return write_metadata(path,AudioMetadataChanges(lyrics_path=lyrics),target)
        self.app.run_task(work,lambda target:self.app.inform('已另存为：\n'+str(target)))

