from pathlib import Path
import random
import tempfile
from uuid import uuid4
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QFileDialog, QAbstractItemView, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QDoubleSpinBox, QCheckBox, QStyledItemDelegate, QStyleOptionViewItem, QStyle
from .common import Page, row, button, combo, ClickSlider, group, Columns, SegmentedTabs, FileList, set_picture, dialog_initial_directory, remember_dialog_selection, dialog_filters, remember_dialog_filter
from .design import icon
from .services import tagged_destination
from sub2lrc.audio_preview import AudioPreviewPlayer, PlaybackState, load_audio_lyrics, current_lyric_index, shift_timeline
from sub2lrc.audio_converter import SUPPORTED_INPUT_EXTENSIONS
from sub2lrc.audio_metadata import read_metadata, write_metadata, AudioMetadataChanges
from sub2lrc.converter import cues_to_lrc, detect_format, parse_text, shift_cues, shift_lrc
from core.play_queue import PlayQueue
from core.playback_history import record_position, saved_position
from core.settings import save_settings


# Speeds offered in the preview page. atempo accepts 0.5-2.0 natively, so every
# option maps to a single filter instance; see AudioPreviewPlayer.set_speed.
SPEED_CHOICES = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
# Sleep timer lengths, in minutes. 23:59 is the largest the user asked for.
SLEEP_CHOICES = (1, 5, 10, 15, 30, 45, 60, 90, 120, 180, 240, 480, 720, 1439)
QUEUE_TAB = 1
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
            size = QSize(1, max(0, (self.viewport().height()-44)//2))
            self.item(0).setSizeHint(size); self.item(self.count()-1).setSizeHint(size)


class LyricItemDelegate(QStyledItemDelegate):
    """Keep selection colouring while suppressing the native focus rectangle."""
    def paint(self, painter, option, index):
        clean_option = QStyleOptionViewItem(option)
        clean_option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, clean_option, index)


class PreviewPage(Page):
    def __init__(self,app):
        super().__init__(app,'音频预览','本地播放 · 同步歌词 · 点击歌词跳转')
        self.player=None;self.timeline=();self.path=None;self.active_line=None
        # The queue model is separate from the visible list so that ordering can
        # be reasoned about and tested without Qt.
        self.queue_tracks=PlayQueue()
        file_card,file_body=group('')
        self.file_path=QLineEdit();self.file_path.setReadOnly(True);self.file_path.setPlaceholderText('选择或拖入本地音频文件')
        file_body.addWidget(row(self.file_path,button('选择音频文件…',self.choose,symbol='folder')));self.layout.addWidget(file_card)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(0,0,0,0);left_layout.setSpacing(16)
        track,track_layout=group('歌曲信息');left_layout.addWidget(track)
        self.title=QLabel('尚未选择音频');self.title.setWordWrap(True);self.title.setObjectName('sectionTitle')
        self.info=QLabel('选择一首音频，开始聆听');self.info.setWordWrap(True);self.info.setObjectName('muted')
        self.artwork=QLabel();self.artwork.setObjectName('artwork');self.artwork.setFixedSize(86,86);self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter);self.artwork.setPixmap(icon('music','#397bf3',38).pixmap(38,38))
        track_layout.addWidget(row(self.artwork,self.title));track_layout.addWidget(self.info)
        # Resume row. Shown only for a file that has its own saved position, so a
        # file that was never played does not advertise an empty "resume" action.
        self.resume_label=QLabel('')
        self.resume_button=button('继续播放',self.resume_playback,True)
        self.restart_button=button('从头播放',lambda:self.restart_playback())
        self.resume_row=row(self.resume_label,self.resume_button,self.restart_button)
        self.resume_row.hide()
        track_layout.addWidget(self.resume_row)
        player_card,player_layout=group('播放控制');left_layout.addWidget(player_card)
        self.skip_back=button('',lambda:self.jump_by(-30),symbol='previous');self.skip_back.setToolTip('后退 30 秒')
        self.skip_forward=button('',lambda:self.jump_by(30),symbol='next');self.skip_forward.setToolTip('前进 30 秒')
        self.play=button('',self.toggle,True,'play');self.play.setObjectName('roundPlay');self.play.setFixedSize(60,60);self.play.setIconSize(QSize(27,27));self.play.setToolTip('播放 / 暂停（空格）')
        for control in (self.skip_back,self.skip_forward):
            control.setObjectName('roundControl');control.setFixedSize(46,46);control.setAccessibleName(control.toolTip())
        controls=QWidget();controls_layout=QHBoxLayout(controls);controls_layout.setContentsMargins(0,0,0,0);controls_layout.setSpacing(10)
        controls_layout.addStretch();controls_layout.addWidget(self.skip_back);controls_layout.addWidget(self.play);controls_layout.addWidget(self.skip_forward);controls_layout.addStretch();player_layout.addWidget(controls)
        self.position=ClickSlider(Qt.Orientation.Horizontal);self.position.setMinimumHeight(24);self.position.setRange(0,0)
        self.position.sliderReleased.connect(self.seek);self.position.sliderMoved.connect(self.preview_seek)
        self.time=QLabel('00:00 / 00:00');self.time.setObjectName('muted')
        player_layout.addWidget(self.position);player_layout.addWidget(self.time)
        self.volume=ClickSlider(Qt.Orientation.Horizontal);self.volume.setMinimumHeight(24);self.volume.setRange(0,100);self.volume.setValue(app.settings['default_volume']);self.volume.sliderReleased.connect(self.volume_changed)
        volume_icon=QLabel();volume_icon.setPixmap(icon('volume').pixmap(22,22));player_layout.addWidget(row(volume_icon,self.volume))
        # Options row: speed, repeat mode, sleep timer and the queue toggle. These
        # sit under the transport controls, and the line above them summarises the
        # active combination so the current state is readable at a glance.
        self.speed=combo([(f'{value:g}×',value) for value in SPEED_CHOICES]);self.speed.setFixedWidth(96)
        self.speed.setToolTip('播放速度')
        # 1x is the middle of the list rather than its first entry; without this
        # the page would open at half speed.
        self.speed.setCurrentIndex(SPEED_CHOICES.index(1.0))
        self.repeat=combo([('不循环','once'),('单曲循环','repeat_one'),('列表循环','repeat_all')])
        self.repeat.setFixedWidth(120);self.repeat.setToolTip('播放结束后')
        self.sleep=combo([('不定时',0)]+[(f'{minutes} 分钟',minutes) for minutes in SLEEP_CHOICES])
        self.sleep.setFixedWidth(120);self.sleep.setToolTip('定时关闭')
        self.queue_button=button('队列 (0)',lambda:self.show_queue())
        self.queue_button.setToolTip('显示播放队列')
        self.options_row=row(self.speed,self.repeat,self.sleep,self.queue_button)
        player_layout.addWidget(self.options_row)
        # One line carries the playback state (playing/paused, speed, repeat, sleep
        # timer). The second line is reserved for messages about a specific event
        # and stays hidden when there is nothing to say, so the card normally shows
        # a single line rather than two competing ones.
        self.state_line=QLabel('等待载入音频');self.state_line.setObjectName('muted')
        player_layout.addWidget(self.state_line)
        self.status=QLabel('');self.status.setObjectName('notice');self.status.hide()
        player_layout.addWidget(self.status)
        left_layout.addStretch()
        # Right side: two mutually exclusive views. The lyric offset controls live
        # inside the lyric view, so they can never appear next to the play queue.
        lyric_card,lyric_layout=group('')
        self.lyrics=LyricList();self.lyrics.setMouseTracking(True);self.lyrics.setMinimumHeight(350)
        self.lyrics.setItemDelegate(LyricItemDelegate(self.lyrics))
        self.lyrics.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        empty=QListWidgetItem('选择音频后，在这里查看同步歌词');empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter);empty.setFlags(Qt.ItemFlag.NoItemFlags);self.lyrics.addItem(empty)
        # Segoe UI Symbol contains lyric symbols such as ♡ and ♪.  Windows
        # automatically falls back to the Chinese UI font for CJK glyphs.
        self.lyrics.setStyleSheet('QListWidget { border:0; font-family:"Segoe UI Symbol"; font-size:17px; font-weight:600; color:#7c8eab; } QListWidget::item { border:0; outline:0; } QListWidget::item:focus { border:0; outline:0; } QListWidget::item:hover { background:#f4f7fd; } QListWidget::item:selected { color:#0877ff; background:#edf4ff; font-weight:700; }')
        self.lyrics.itemClicked.connect(self.lyric_clicked)
        # Lyric timeline offset. Tuning it here is what the preview page is for:
        # the highlight follows the shift immediately so the user can listen and
        # adjust. Writing it back is optional, so the page stays read-only unless
        # the user explicitly saves.
        self.lyric_shift=QDoubleSpinBox();self.lyric_shift.setRange(0.0,3600.0);self.lyric_shift.setDecimals(2)
        self.lyric_shift.setSingleStep(0.5);self.lyric_shift.setValue(0.5);self.lyric_shift.setSuffix('秒')
        self.lyric_shift.setFixedWidth(92);self.lyric_shift.setToolTip('要调整的秒数')
        self.shift_direction=combo([('延后','later'),('提前','earlier')]);self.shift_direction.setFixedWidth(96)
        self.shift_apply=button('应用',self.apply_lyric_shift);self.shift_apply.setFixedWidth(50)
        self.shift_reset=button('重置',self.reset_lyric_shift);self.shift_reset.setFixedWidth(50)
        self.shift_save=button('保存到音频',self.save_shifted_lyrics,True)
        self.shift_save.setEnabled(False)
        self.shift_row=row(self.lyric_shift,self.shift_direction,self.shift_apply,self.shift_reset,self.shift_save)
        lyric_view=QWidget();lyric_view_layout=QVBoxLayout(lyric_view)
        lyric_view_layout.setContentsMargins(0,0,0,0);lyric_view_layout.setSpacing(10)
        lyric_view_layout.addWidget(self.lyrics,1);lyric_view_layout.addWidget(self.shift_row)
        queue_view=QWidget();queue_view_layout=QVBoxLayout(queue_view)
        queue_view_layout.setContentsMargins(0,0,0,0);queue_view_layout.setSpacing(10)
        self.queue_actions=row(button('添加文件',self.choose,symbol='folder'),
                               button('清空列表',self.clear_queue),
                               button('随机播放',self.toggle_shuffle))
        queue_view_layout.addWidget(self.queue_actions)
        self.queue=FileList(SUPPORTED_INPUT_EXTENSIONS,reorderable=True)
        self.queue.setMinimumHeight(350)
        self.queue.currentRowChanged.connect(self.queue_row_changed)
        self.queue.filesChanged.connect(self.queue_changed)
        queue_view_layout.addWidget(self.queue,1)
        self.auto_next=QCheckBox('播放结束后自动播放下一首');self.auto_next.setChecked(True)
        queue_view_layout.addWidget(self.auto_next)
        self.tabs=SegmentedTabs(['同步歌词','播放队列'],[lyric_view,queue_view],
                                trailing=QLabel('拖动可调整顺序'))
        self.tabs.changed.connect(self.tab_changed)
        lyric_layout.addWidget(self.tabs,1)
        self.layout.addWidget(Columns(left,lyric_card,700),1)
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
    def refresh_queue_list(self):
        """Mirror the queue model into the visible list.

        The row signal is blocked while the list is rebuilt: setting the current
        row would otherwise run the row handler, which loads the file a second
        time and restarts playback from the beginning.
        """
        tracks=self.queue_tracks
        self.queue.blockSignals(True)
        try:
            self.queue.clear()
            if tracks.entries:
                self.queue.add_paths(tracks.entries)
            if tracks.index>=0:
                self.queue.setCurrentRow(tracks.index)
        finally:
            self.queue.blockSignals(False)
        self.queue_button.setText(self.app.t(f'队列 ({len(tracks)})'))
        self.queue_tab_label()
    def queue_tab_label(self):
        """Keep the queue count on the tab, in either language.

        The count is a suffix rather than part of the label so that translating
        the label cannot drop it.
        """
        count=len(self.queue_tracks)
        self.tabs.set_suffix(f'({count})' if count else '')
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
    def show_queue(self):
        self.tabs.set_current_index(QUEUE_TAB)
    def tab_changed(self,index):
        """The two right-hand views are mutually exclusive by construction."""
        self.state_line.setText(self.state_text())
    def clear_queue(self):
        """Empty the queue and stop playback, since nothing is selected."""
        self.queue_tracks.clear()
        self.queue.blockSignals(True);self.queue.clear();self.queue.blockSignals(False)
        self.close_current_player()
        self.path=None
        self.queue_button.setText(self.app.t('队列 (0)'))
        self.queue_tab_label()
        self.state_line.setText('等待载入音频')
        self.title.setText('尚未选择音频');self.info.setText('选择一首音频，开始聆听')
        self.file_path.clear();self.resume_row.hide()
        self.timeline=();self.refill_lyrics();self.notice(self.app.t('等待载入音频'))
    def queue_changed(self):
        """Re-sync the model after the list is reordered or edited by dragging."""
        self.queue_tracks.entries=[Path(p) for p in self.queue.paths()]
        self.queue_tracks.index=self.queue.currentRow()
        self.refresh_last_position()
    def queue_row_changed(self,row):
        if row<0 or row>=len(self.queue_tracks):return
        if self.queue_tracks.index==row and self.path:return
        self.queue_tracks.select(row)
        self.load(self.queue_tracks.current)
    def toggle_shuffle(self):
        from core.play_queue import ORDER_IN_ORDER,ORDER_SHUFFLE
        shuffle=self.queue_tracks.order!=ORDER_SHUFFLE
        self.queue_tracks.set_order(ORDER_SHUFFLE if shuffle else ORDER_IN_ORDER,
                                    shuffle_seed=random.randrange(1<<30))
        self.notice(self.app.t('已开启随机播放' if shuffle else '已关闭随机播放'))
        self.state_line.setText(self.state_text())
    def pick_next(self,automatic=True):
        """The next file for the current repeat mode, or None when playback stops."""
        if automatic and not self.auto_next.isChecked():
            return None
        return self.queue_tracks.advance(mode=self.repeat.currentData(),automatic=automatic)
    def play_next(self,automatic=True):
        target=self.pick_next(automatic=automatic)
        if target is None:
            if automatic:self.notice(self.app.t('播放列表已结束'))
            return False
        self.refresh_queue_list()
        self.load(target)
        return True
    def play_previous(self):
        target=self.queue_tracks.rewind()
        if target is None:return False
        self.refresh_queue_list()
        self.load(target)
        return True
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
                return path,player,lyrics,meta
            except Exception:player.close();raise
        self.app.run_task(work,self.loaded)
    def loaded(self,data):
        path,player,(source,timeline),meta=data
        if self.player:self.player.close()
        self.path=path;self.player=player;self.timeline=timeline;self.active_line=None
        # Keep the raw lyric text and its original timeline so an offset can be
        # applied, undone and re-applied without re-reading the file.
        self.lyric_source=source;self.base_timeline=timeline;self.applied_shift=0.0
        self.shift_save.setEnabled(bool(timeline))
        self._missing_reported=False;self._ticks=0
        self.title.setText((meta.title or path.stem) if meta else path.stem)
        self.info.setText(f'{meta.artist}  ·  {meta.info.format_label}  ·  {self.timestamp(player.duration)}' if meta else self.timestamp(player.duration))
        self.file_path.setText(str(path));self.file_path.setToolTip(str(path))
        if meta and meta.cover_data:set_picture(self.artwork,meta.cover_data,80)
        else:self.artwork.setPixmap(icon('music','#397bf3',38).pixmap(38,38))
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
            item.setSizeHint(QSize(1,max(44,28+24*max(1,len(line.text.splitlines())))));self.lyrics.addItem(item)
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
        def work(report):
            text=self.shifted_lyric_text()
            with tempfile.TemporaryDirectory(prefix='mediaanvil-preview-') as temporary:
                lyrics=Path(temporary)/('shifted-'+uuid4().hex+'.lrc')
                lyrics.write_text(text,encoding='utf-8')
                target=tagged_destination(path)
                return write_metadata(path,AudioMetadataChanges(lyrics_path=lyrics),target)
        self.app.run_task(work,lambda target:self.app.inform('已另存为：\n'+str(target)))
    def volume_changed(self):
        if self.player:
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
