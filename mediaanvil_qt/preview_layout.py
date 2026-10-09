"""Preview workspace and fixed transport dock; playback behavior stays in PreviewPage."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QListWidgetItem, QCheckBox, QDoubleSpinBox, QSizePolicy)
from .layouts import button, row, combo, group, Columns, SegmentedTabs
from .file_widgets import FileList
from .sliders import ClickSlider
from .cover_widgets import ResponsiveCover
from .design import icon
from sub2lrc.audio_converter import SUPPORTED_INPUT_EXTENSIONS


class TransportDock(QWidget):
    """Keep transport groups usable when the available window width changes."""
    def __init__(self, position, time, volume, transport, options):
        super().__init__()
        self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0)
        self.grid.setHorizontalSpacing(16);self.grid.setVerticalSpacing(6)
        self.seek_row=row(position,time);self.grid.addWidget(self.seek_row,0,0,1,3)
        self.groups=(volume,transport,options);self._wide=None
        self._arrange(False)

    def _arrange(self,wide):
        if wide==self._wide:return
        self._wide=wide
        for widget in self.groups:self.grid.removeWidget(widget)
        for column,widget in enumerate(self.groups):
            self.grid.addWidget(widget,1 if wide else column+1,column if wide else 0,1,1 if wide else 3)
        for column in range(3):self.grid.setColumnStretch(column,(2 if column==2 else 1) if wide else 0)

    def resizeEvent(self,event):
        super().resizeEvent(event);self._arrange(self.width()>=800)


def build_preview(page, app, lyric_list, lyric_delegate, speeds, sleep_choices):
    page.file_path=QLineEdit();page.file_path.setReadOnly(True)
    page.file_path.setPlaceholderText('选择或拖入本地音频文件')
    file_card,file_body=group('');file_body.setContentsMargins(12,10,12,10)
    file_body.addWidget(row(page.file_path,button('添加音频',page.choose,True,'folder')))
    page.layout.addWidget(file_card)

    track,track_body=group('')
    page.artwork=ResponsiveCover();page.artwork.setObjectName('artwork')
    page.artwork.setMinimumSize(180,180);page.artwork.setMaximumHeight(320)
    page.artwork.set_artwork(None,'♫')
    track_body.addWidget(page.artwork,1)
    page.title=QLabel('尚未选择音频');page.title.setWordWrap(True);page.title.setObjectName('trackTitle')
    page.info=QLabel('选择一首音频，开始聆听');page.info.setWordWrap(True);page.info.setObjectName('muted')
    track_body.addWidget(page.title);track_body.addWidget(page.info)
    heading=QLabel('歌曲信息');heading.setObjectName('sectionTitle');track_body.addWidget(heading)
    page.track_details=QLabel('选择音频后显示专辑、格式与文件信息');page.track_details.setWordWrap(True)
    page.track_details.setObjectName('muted');track_body.addWidget(page.track_details)
    page.resume_label=QLabel('');page.resume_label.setObjectName('muted')
    page.resume_button=button('继续播放',page.resume_playback,True)
    page.restart_button=button('从头播放',page.restart_playback)
    page.resume_row=row(page.resume_label,page.resume_button,page.restart_button)
    page.resume_row.hide();track_body.addWidget(page.resume_row)

    lyric_card,lyric_body=group('')
    page.lyrics=lyric_list();page.lyrics.setMouseTracking(True);page.lyrics.setMinimumHeight(260)
    page.lyrics.setItemDelegate(lyric_delegate(page.lyrics))
    page.lyrics.setVerticalScrollMode(page.lyrics.ScrollMode.ScrollPerPixel)
    page.lyrics.setStyleSheet('QListWidget { border:0; font-family:"Microsoft YaHei UI","Segoe UI Symbol"; font-size:22px; font-weight:600; color:#718098; } QListWidget::item { border:0; padding:14px 8px; outline:0; } QListWidget::item:focus { border:0; outline:0; } QListWidget::item:hover { background:#f4f7fd; } QListWidget::item:selected { color:#315cff; background:#edf2ff; font-weight:700; }')
    empty=QListWidgetItem('选择音频后，在这里查看同步歌词');empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    empty.setFlags(Qt.ItemFlag.NoItemFlags);page.lyrics.addItem(empty)
    page.lyrics.itemClicked.connect(page.lyric_clicked)
    lyric_view=QWidget();lyrics=QVBoxLayout(lyric_view);lyrics.setContentsMargins(0,0,0,0)
    lyrics.addWidget(page.lyrics,1)
    calibration,calibration_body=group('歌词校准')
    calibration.setStyleSheet('QFrame#card { border:0; border-top:1px solid #e5eaf3; border-radius:0; }')
    calibration_body.setContentsMargins(0,10,0,0)
    hint=QLabel('调整仅用于预览，保存后写入音频');hint.setObjectName('muted');hint.setWordWrap(True)
    calibration_body.addWidget(hint)
    page.lyric_shift=QDoubleSpinBox();page.lyric_shift.setRange(0,3600);page.lyric_shift.setDecimals(2)
    page.lyric_shift.setSingleStep(.5);page.lyric_shift.setValue(.5);page.lyric_shift.setSuffix(' 秒')
    page.lyric_shift.setFixedWidth(108);page.lyric_shift.setToolTip('要调整的秒数')
    page.shift_direction=combo([('延后','later'),('提前','earlier')]);page.shift_direction.setFixedWidth(100)
    page.shift_apply=button('应用',page.apply_lyric_shift);page.shift_reset=button('重置',page.reset_lyric_shift)
    page.shift_save=button('保存到音频',page.save_shifted_lyrics,True);page.shift_save.setEnabled(False)
    page.shift_row=row(page.lyric_shift,page.shift_direction,page.shift_apply,page.shift_reset,page.shift_save)
    calibration_body.addWidget(page.shift_row)
    page.status=QLabel('');page.status.setObjectName('muted');page.status.setWordWrap(True);page.status.hide()
    calibration_body.addWidget(page.status);lyrics.addWidget(calibration)
    queue_view=QWidget();queue=QVBoxLayout(queue_view);queue.setContentsMargins(0,0,0,0)
    page.queue_actions=row(button('添加文件',page.choose,symbol='folder'),button('清空列表',page.clear_queue),button('随机播放',page.toggle_shuffle))
    queue.addWidget(page.queue_actions)
    page.queue=FileList(SUPPORTED_INPUT_EXTENSIONS,reorderable=True);page.queue.setMinimumHeight(260)
    page.queue.currentRowChanged.connect(page.queue_row_changed);page.queue.filesChanged.connect(page.queue_changed)
    queue.addWidget(page.queue,1)
    page.auto_next=QCheckBox('播放结束后自动播放下一首');page.auto_next.setChecked(True);queue.addWidget(page.auto_next)
    page.tabs=SegmentedTabs(['同步歌词','播放队列'],[lyric_view,queue_view],trailing=QLabel('点击歌词可跳转'))
    page.tabs.changed.connect(page.tab_changed);lyric_body.addWidget(page.tabs,1)
    page.columns=Columns(track,lyric_card,720);page.columns.box.setStretch(0,2);page.columns.box.setStretch(1,3)
    page.layout.addWidget(page.columns,1)

    page.position=ClickSlider(Qt.Orientation.Horizontal);page.position.setRange(0,0)
    page.position.setMinimumHeight(24)
    page.position.sliderReleased.connect(page.seek);page.position.sliderMoved.connect(page.preview_seek)
    page.time=QLabel('00:00 / 00:00');page.time.setObjectName('muted')
    page.volume=ClickSlider(Qt.Orientation.Horizontal);page.volume.setRange(0,100);page.volume.setValue(app.settings['default_volume'])
    page.volume.setMinimumHeight(24)
    page.volume.setMinimumWidth(60);page.volume.setMaximumWidth(160)
    page.volume.valueChanged.connect(page.volume_changed);page.volume.sliderReleased.connect(page.volume_changed)
    speaker=QLabel();speaker.setPixmap(icon('volume').pixmap(20,20));volume=row(speaker,page.volume)
    page.skip_back=button('',lambda:page.jump_by(-30),symbol='previous');page.skip_back.setToolTip('后退 30 秒')
    page.skip_forward=button('',lambda:page.jump_by(30),symbol='next');page.skip_forward.setToolTip('前进 30 秒')
    for control in (page.skip_back,page.skip_forward):
        control.setObjectName('roundControl');control.setFixedSize(38,38);control.setAccessibleName(control.toolTip())
    page.play=button('',page.toggle,True,'play');page.play.setObjectName('roundPlay')
    page.play.setFixedSize(54,54);page.play.setIconSize(QSize(27,27));page.play.setToolTip('播放 / 暂停（空格）')
    transport=QWidget();transport_row=QHBoxLayout(transport);transport_row.setContentsMargins(0,0,0,0)
    transport_row.addStretch()
    for control in (page.skip_back,page.play,page.skip_forward):transport_row.addWidget(control)
    transport_row.addStretch()
    page.speed=combo([(f'{value:g}×',value) for value in speeds]);page.speed.setCurrentIndex(speeds.index(1.0));page.speed.setFixedWidth(82);page.speed.setToolTip('播放速度')
    page.repeat=combo([('不循环','once'),('单曲循环','repeat_one'),('列表循环','repeat_all')]);page.repeat.setMinimumWidth(100);page.repeat.setToolTip('播放结束后')
    page.sleep=combo([('不定时',0)]+[(f'{minutes} 分钟',minutes) for minutes in sleep_choices]);page.sleep.setMinimumWidth(104);page.sleep.setToolTip('定时关闭')
    page.queue_button=button('队列 (0)',page.show_queue);page.queue_button.setToolTip('显示播放队列')
    page.options_row=row(page.speed,page.repeat,page.sleep,page.queue_button)
    page.footer=TransportDock(page.position,page.time,volume,transport,page.options_row)
    page.footer.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
    page.layout.addWidget(page.footer)
    page.state_line=QLabel('等待载入音频');page.state_line.setObjectName('muted');track_body.addWidget(page.state_line)
