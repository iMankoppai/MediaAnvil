from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QShortcut, QKeySequence, QColor
from PySide6.QtWidgets import QLabel, QSlider, QListWidget, QListWidgetItem, QFileDialog, QAbstractItemView, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QStyledItemDelegate, QStyleOptionViewItem, QStyle
from .common import Page, row, button, ClickSlider, group, Columns, set_picture
from .design import icon
from sub2lrc.audio_preview import AudioPreviewPlayer, PlaybackState, load_audio_lyrics, current_lyric_index
from sub2lrc.audio_converter import SUPPORTED_INPUT_EXTENSIONS
from sub2lrc.audio_metadata import read_metadata


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
        file_card,file_body=group('')
        self.file_path=QLineEdit();self.file_path.setReadOnly(True);self.file_path.setPlaceholderText('选择或拖入本地音频文件')
        file_body.addWidget(row(self.file_path,button('选择音频文件…',self.choose,symbol='folder')));self.layout.addWidget(file_card)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(0,0,0,0);left_layout.setSpacing(16)
        track,track_layout=group('歌曲信息');left_layout.addWidget(track)
        self.title=QLabel('尚未选择音频');self.title.setWordWrap(True);self.title.setObjectName('sectionTitle')
        self.info=QLabel('选择一首音频，开始聆听');self.info.setWordWrap(True);self.info.setObjectName('muted')
        self.artwork=QLabel();self.artwork.setObjectName('artwork');self.artwork.setFixedSize(86,86);self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter);self.artwork.setPixmap(icon('music','#397bf3',38).pixmap(38,38))
        track_layout.addWidget(row(self.artwork,self.title));track_layout.addWidget(self.info)
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
        self.status=QLabel('等待载入音频');self.status.setObjectName('notice');player_layout.addWidget(self.status)
        left_layout.addStretch()
        lyric_card,lyric_layout=group('同步歌词')
        self.lyrics=LyricList();self.lyrics.setMouseTracking(True);self.lyrics.setMinimumHeight(350)
        self.lyrics.setItemDelegate(LyricItemDelegate(self.lyrics))
        self.lyrics.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        empty=QListWidgetItem('选择音频后，在这里查看同步歌词');empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter);empty.setFlags(Qt.ItemFlag.NoItemFlags);self.lyrics.addItem(empty)
        # Segoe UI Symbol contains lyric symbols such as ♡ and ♪.  Windows
        # automatically falls back to the Chinese UI font for CJK glyphs.
        self.lyrics.setStyleSheet('QListWidget { border:0; font-family:"Segoe UI Symbol"; font-size:17px; font-weight:600; color:#7c8eab; } QListWidget::item { border:0; outline:0; } QListWidget::item:focus { border:0; outline:0; } QListWidget::item:hover { background:#f4f7fd; } QListWidget::item:selected { color:#0877ff; background:#edf4ff; font-weight:700; }')
        self.lyrics.itemClicked.connect(self.lyric_clicked);lyric_layout.addWidget(self.lyrics,1)
        self.layout.addWidget(Columns(left,lyric_card,700),1)
        self.timer=QTimer(self);self.timer.setInterval(80);self.timer.timeout.connect(self.poll);self.timer.start()
        # Keep Space available when an import leaves focus on the sidebar or
        # window itself. A shortcut owned by this visible page becomes inactive
        # automatically when another page is selected.
        self.shortcut=QShortcut(QKeySequence('Space'),self);self.shortcut.setContext(Qt.ShortcutContext.WindowShortcut);self.shortcut.activated.connect(self.toggle)
    def choose(self):
        paths,_=QFileDialog.getOpenFileNames(self,self.app.t('选择音频'),'',self.app.t('音频 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus)'))
        if paths:self.receive([Path(p) for p in paths])
    def receive(self,paths):
        found=[p for p in paths if p.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS]
        if found:self.load(found[0])
        return len(found)
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
        self.title.setText((meta.title or path.stem) if meta else path.stem)
        self.info.setText(f'{meta.artist}  ·  {meta.info.format_label}  ·  {self.timestamp(player.duration)}' if meta else self.timestamp(player.duration))
        self.file_path.setText(str(path));self.file_path.setToolTip(str(path))
        if meta and meta.cover_data:set_picture(self.artwork,meta.cover_data,80)
        else:self.artwork.setPixmap(icon('music','#397bf3',38).pixmap(38,38))
        self.lyrics.clear()
        if timeline:
            spacer=QListWidgetItem('');spacer.setData(Qt.ItemDataRole.UserRole,'padding');spacer.setFlags(Qt.ItemFlag.NoItemFlags);self.lyrics.addItem(spacer)
        for line in timeline:
            item=QListWidgetItem(line.text or '♪');item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(QSize(1,max(44,28+24*max(1,len(line.text.splitlines())))));self.lyrics.addItem(item)
        if timeline:
            spacer=QListWidgetItem('');spacer.setFlags(Qt.ItemFlag.NoItemFlags);self.lyrics.addItem(spacer);self.lyrics.update_padding()
        if not timeline:self.lyrics.addItem(self.app.t('暂无同步歌词，可正常播放音频'))
        self.position.setRange(0,int(player.duration*1000))
        self.status.setText(self.app.t('音频与歌词已载入' if timeline else '音频已载入 · 暂无同步歌词'))
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
    def lyric_clicked(self,item):
        index=self.lyrics.row(item)-1
        if self.player and 0<=index<len(self.timeline):
            try:self.player.seek(self.timeline[index].time_seconds);self.poll()
            except Exception as exc:self.app.inform(str(exc))
    def volume_changed(self):
        if self.player:
            try:self.player.set_volume(self.volume.value())
            except Exception as exc:self.app.inform(str(exc))
    def close_player(self):
        self.timer.stop()
        if self.player:self.player.close()
