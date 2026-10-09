from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QListWidget, QFileDialog, QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem, QStyle
from .preview_queue import PreviewQueueMixin, QUEUE_TAB as QUEUE_TAB
from .preview_lyrics import PreviewLyricsMixin
from .common import Page, dialog_initial_directory, remember_dialog_selection, dialog_filters, remember_dialog_filter
from .design import icon
from .player import realtime_player, prepare_playback_copy, release_playback_copy
from sub2lrc.audio_preview import AudioPreviewPlayer, PlaybackState, load_audio_lyrics, current_lyric_index
from sub2lrc.audio_converter import SUPPORTED_INPUT_EXTENSIONS
from sub2lrc.audio_metadata import read_metadata
from core.play_queue import PlayQueue
from core.playback_history import record_position, saved_position
from core.settings import save_settings


# Speeds offered in the preview page. atempo accepts 0.5-2.0 natively, so every
# option maps to a single filter instance; see AudioPreviewPlayer.set_speed.
SPEED_CHOICES = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
# Sleep timer lengths, in minutes. 23:59 is the largest the user asked for.
SLEEP_CHOICES = (1, 5, 10, 15, 30, 45, 60, 90, 120, 180, 240, 480, 720, 1439)
LYRIC_TAB = 0


class LyricList(QListWidget):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_padding()
        QTimer.singleShot(0,self.center_current)

    def center_current(self):
        if self.currentRow()>0:self.scrollToItem(self.currentItem(),QAbstractItemView.ScrollHint.PositionAtCenter)

    def update_padding(self):
        if self.count() >= 3 and self.item(0).data(Qt.ItemDataRole.UserRole) == 'padding':
            size = QSize(1, max(0, (self.viewport().height()-62)//2))
            self.item(0).setSizeHint(size); self.item(self.count()-1).setSizeHint(size)


class LyricItemDelegate(QStyledItemDelegate):
    """Keep selection colouring while suppressing the native focus rectangle."""
    def paint(self, painter, option, index):
        clean_option = QStyleOptionViewItem(option)
        clean_option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, clean_option, index)


class PreviewPage(PreviewQueueMixin, PreviewLyricsMixin, Page):
    def __init__(self,app):
        super().__init__(app,'音频预览','本地播放 · 同步歌词 · 点击歌词跳转')
        self.player=None;self.timeline=();self.path=None;self.active_line=None
        # The queue model is separate from the visible list so that ordering can
        # be reasoned about and tested without Qt.
        self.queue_tracks=PlayQueue()
        from .preview_layout import build_preview
        build_preview(self,app,LyricList,LyricItemDelegate,SPEED_CHOICES,SLEEP_CHOICES)
        self.timer=QTimer(self);self.timer.setInterval(80);self.timer.timeout.connect(self.poll);self.timer.start()
        self.sleep_timer=QTimer(self);self.sleep_timer.setSingleShot(True);self.sleep_timer.timeout.connect(self.sleep_finished)
        self.sleep.setCurrentIndex(0)
        for widget in (self.speed,self.repeat,self.sleep):
            widget.currentIndexChanged.connect(self.option_changed)
        self.auto_next.toggled.connect(self.option_changed)
        # Keep Space available when an import leaves focus on the sidebar or
        # window itself. A shortcut owned by this visible page becomes inactive
        # automatically when another page is selected.
        self.shortcut=QShortcut(QKeySequence('Space'),self);self.shortcut.setContext(Qt.ShortcutContext.WindowShortcut);self.shortcut.activated.connect(self.toggle)
    def choose(self):
        supported=self.app.t('音频 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus)')
        filters=dialog_filters(self,'audio',(supported,self.app.t('所有文件 (*)')))
        paths,chosen=QFileDialog.getOpenFileNames(self,self.app.t('选择音频'),dialog_initial_directory(self,'audio'),filters)
        if paths:
            remember_dialog_selection(self,'audio',paths[0]);remember_dialog_filter(self,'audio',chosen)
            self.receive([Path(p) for p in paths])
    def receive(self,paths):
        """Queue every supported file dropped in, and load one if nothing is playing.

        The first drop selects the first file; later drops extend the queue while
        whatever is already loaded keeps playing.
        """
        found=[p for p in paths if p.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS]
        if not found:return 0
        was_empty=not len(self.queue_tracks)
        self.queue_tracks.add(found)
        self.refresh_queue_list()
        if was_empty:
            self.load(self.queue_tracks.current)
        return len(found)
    def refresh_translated_text(self):
        """Rebuild text this page formats itself, after a language switch.

        ``apply_language`` walks widgets, so a label built from a count such as
        "Queue (8)" or "Last played to 47:12" is invisible to it and needs this
        hook. See i18n.apply_language.
        """
        self.queue_button.setText(self.app.t(f'队列 ({len(self.queue_tracks)})'))
        self.queue_tab_label()
        self.refresh_last_position()
        self.state_line.setText(self.state_text())
    def tab_changed(self,index):
        """The two right-hand views are mutually exclusive by construction."""
        self.state_line.setText(self.state_text())
    def resume_playback(self):
        """Play the current file from its own saved position."""
        if not self.player:return
        position=self.saved_position_for_current()
        if position is None:return self.restart_playback()
        try:
            self.player.seek(position);self.player.play();self.poll()
        except Exception as exc:self.app.inform(str(exc))
    def restart_playback(self):
        if not self.player:return
        try:
            self.player.seek(0.0);self.player.play();self.poll()
        except Exception as exc:self.app.inform(str(exc))
    def saved_position_for_current(self):
        if not self.path:return None
        duration=self.player.duration if self.player else 0.0
        return saved_position(self.app.settings,self.path,duration)
    def refresh_last_position(self):
        """Show the resume row only for a file that has its own record."""
        position=self.saved_position_for_current()
        if position is None:
            self.resume_row.hide();return
        self.resume_label.setText(self.app.t(f'上次播放至 {self.timestamp(position)}'))
        self.resume_row.show()
    def remember_position(self):
        """Store the current position under the rules in core.playback_history."""
        if not self.path or not self.player:return
        try:position=self.player.position
        except Exception:return
        if record_position(self.app.settings,self.path,position,self.player.duration):
            self.save_settings()
    def save_settings(self):
        try:save_settings(self.app.settings,self.app.settings_file)
        except Exception:pass
    def notice(self,text):
        """Show an event message, or hide the line when there is nothing to say."""
        if text:
            self.status.setText(self.app.t(text));self.status.show()
        else:
            self.status.clear();self.status.hide()
    def state_text(self):
        if not self.player:return self.app.t('等待载入音频')
        parts=[self.app.t('正在播放' if self.player and self.player.state==PlaybackState.PLAYING else '已暂停')]
        parts.append(f'{self.speed.currentData():g}×')
        parts.append(self.repeat.currentText())
        minutes=self.sleep.currentData()
        if minutes:parts.append(self.app.t(f'{minutes} 分钟后停止'))
        if self.queue_tracks.order=='shuffle':parts.append(self.app.t('随机播放'))
        return '  ·  '.join(parts)
    def load(self,path):
        external=self.app.settings['auto_load_same_name_lyrics'];prefer_embedded=self.app.settings['prefer_embedded_mp3_lyrics'];volume=self.volume.value()
        def work(report):
            player=AudioPreviewPlayer()
            try:
                player.load(path); player.set_volume(volume)
                lyrics=load_audio_lyrics(path,load_external=external,prefer_embedded=prefer_embedded)
                try: meta=read_metadata(path)
                except Exception: meta=None
                prepare_playback_copy(player,report)
                return path,player,lyrics,meta
            except Exception:player.close();release_playback_copy(player);raise
        self.app.run_task(work,self.loaded)
    def loaded(self,data):
        path,player,(source,timeline),meta=data
        if self.player:self.player.close()
        player=realtime_player(player,self)
        self.path=path;self.player=player;self.timeline=timeline;self.active_line=None
        # Keep the raw lyric text and its original timeline so an offset can be
        # applied, undone and re-applied without re-reading the file.
        self.lyric_source=source;self.base_timeline=timeline;self.applied_shift=0.0
        self.shift_save.setEnabled(bool(timeline))
        self._missing_reported=False;self._ticks=0
        self.title.setText((meta.title or path.stem) if meta else path.stem)
        self.info.setText(f'{meta.artist}  ·  {meta.info.format_label}  ·  {self.timestamp(player.duration)}' if meta else self.timestamp(player.duration))
        self.file_path.setText(str(path));self.file_path.setToolTip(str(path))
        self.artwork.set_artwork(meta.cover_data if meta else None,'♫')
        self.track_details.setText(f'{meta.album or "—"}\n{meta.info.format_label} · {self.timestamp(player.duration)}' if meta else self.timestamp(player.duration))
        self.refill_lyrics()
        self.position.setRange(0,int(player.duration*1000))
        self.notice(self.app.t('音频与歌词已载入' if timeline else '音频已载入 · 暂无同步歌词'))
        self.refresh_last_position()
        self.apply_speed()
        self.state_line.setText(self.state_text())
        self.poll()
    @staticmethod
    def timestamp(value):
        seconds=max(0,int(value));return f'{seconds//60:02d}:{seconds%60:02d}'
    def toggle(self):
        if not self.player:return
        try:
            if self.player.state==PlaybackState.PLAYING:self.player.pause()
            else:self.player.play()
        except Exception as exc:self.app.inform(str(exc))
        self.poll()
    def jump_by(self,seconds):
        if not self.player:return
        try:
            position=min(self.player.duration,max(0,self.player.position+seconds))
            self.player.seek(position);self.position.setValue(int(position*1000));self.update_display(position)
        except Exception as exc:self.app.inform(str(exc))
    def seek(self):
        if self.player:
            try:self.player.seek(self.position.value()/1000)
            except Exception as exc:self.app.inform(str(exc))
    def preview_seek(self,value):self.update_display(value/1000)
    def update_display(self,position):
        if not self.player:return
        self.time.setText(f'{self.timestamp(position)} / {self.timestamp(self.player.duration)}')
        index=current_lyric_index(self.timeline,position)
        if index!=self.active_line:
            self.active_line=index
            if index is not None:
                self.lyrics.setCurrentRow(index+1);self.lyrics.scrollToItem(self.lyrics.item(index+1),QAbstractItemView.ScrollHint.PositionAtCenter)
            else:
                self.lyrics.clearSelection();self.lyrics.setCurrentRow(-1)
    def poll(self):
        if self.player:
            if type(getattr(self.player,'last_error',None)) is str and self.player.last_error:
                self.notice(self.app.t('已切换至兼容播放：')+self.player.last_error);self.player.last_error=''
            self.play.setIcon(icon('pause' if self.player.state==PlaybackState.PLAYING else 'play','white',27))
        if self.player and not self.position.isSliderDown():
            position=self.player.position;self.position.setValue(int(position*1000));self.update_display(position)
        self.check_loaded_file()
        self.check_track_finished()
        self.remember_periodically()
    def check_track_finished(self):
        """Hand over to the queue when a file plays out.

        The player reports STOPPED at the end of the file, which is otherwise
        indistinguishable from a paused or never-started track; requiring the
        position to have reached the end tells them apart.
        """
        if not self.player or not self.path:return
        if self.player.state!=PlaybackState.STOPPED:return
        if self.player.duration<=0:return
        if self.player.position < self.player.duration-0.5:return
        if getattr(self,'_handling_end',False):return
        self._handling_end=True
        try:
            self.remember_position()
            self.play_next(automatic=True)
        finally:
            self._handling_end=False
    def remember_periodically(self):
        """Save the position every few seconds so a crash loses little."""
        self._ticks=getattr(self,'_ticks',0)+1
        if self._ticks%150:return
        if self.player and self.player.state==PlaybackState.PLAYING:
            self.remember_position()
    def check_loaded_file(self):
        """Warn once when the file behind the current player disappears."""
        self._ticks=getattr(self,'_ticks',0)+1
        if not self.path or self._ticks%25:return
        if Path(self.path).is_file():
            self._missing_reported=False;return
        if getattr(self,'_missing_reported',False):return
        self._missing_reported=True
        if self.player:
            try:self.player.pause()
            except Exception:pass
        self.play.setIcon(icon('play','white',27))
        self.notice(self.app.t('文件已被移动或删除，请重新选择音频'))
    def volume_changed(self):
        if self.player:
            if not hasattr(self.player,'media') and self.volume.isSliderDown():return
            try:self.player.set_volume(self.volume.value())
            except Exception as exc:self.app.inform(str(exc))
    def apply_speed(self):
        """Push the chosen speed to the player, keeping the position."""
        if not self.player:return
        try:self.player.set_speed(self.speed.currentData())
        except Exception as exc:self.app.inform(str(exc))
    def option_changed(self,*args):
        """React to a change in speed, repeat mode or the sleep timer."""
        self.apply_speed()
        self.update_sleep_timer()
        self.state_line.setText(self.state_text())
    def update_sleep_timer(self):
        """Arm, re-arm or cancel the sleep timer from the current selection."""
        minutes=self.sleep.currentData()
        self.sleep_timer.stop()
        if not minutes:
            return
        self.sleep_timer.start(int(minutes)*60*1000)
    def sleep_finished(self):
        """Pause playback when the sleep timer runs out."""
        if self.player:
            try:self.player.pause()
            except Exception:pass
        self.poll()
        self.sleep.setCurrentIndex(0)
        self.notice(self.app.t('定时关闭已生效，播放已暂停'))
    def close_current_player(self):
        """Release the loaded file without disturbing the queue."""
        if self.player:
            self.player.close();self.player=None
        self.sleep_timer.stop()
    def close_player(self):
        self.remember_position()
        self.save_settings()
        self.timer.stop();self.sleep_timer.stop()
        if self.player:self.player.close()
