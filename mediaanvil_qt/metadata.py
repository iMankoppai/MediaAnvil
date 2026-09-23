from pathlib import Path
from io import BytesIO
import tempfile
from uuid import uuid4
from PIL import Image
from PySide6.QtCore import Qt,QRect,QRectF,Signal,QTimer
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap
from PySide6.QtWidgets import (QLabel,QLineEdit,QPlainTextEdit,QFileDialog,QCheckBox,
    QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QSpinBox,QDoubleSpinBox,QDialogButtonBox,QWidget,QSizePolicy)
from .common import Page,button,row,form,combo,OutputPath,table,fill_table,group,Columns,dialog_initial_directory,remember_dialog_selection,dialog_filters,remember_dialog_filter
from .i18n import apply_language
from .services import EMBEDDABLE_LYRIC_EXTENSIONS,prepare_lyrics_for_embedding,tagged_destination,write_matches,batch_edit_tags,batch_shift_lyrics,batch_set_cover
from sub2lrc.audio_metadata import read_metadata,write_metadata,AudioMetadataChanges,export_metadata_cover,export_metadata_lyrics
from sub2lrc.converter import shift_lrc
from core.media_matcher import match_audio_file,scan_audio_folder,AUDIO_EXTENSIONS,COVER_EXTENSIONS


def equal_action_row(*actions):
    box=QWidget();layout=QHBoxLayout(box);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
    for action in actions:
        action.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);layout.addWidget(action,1)
    return box


class ResponsiveCover(QLabel):
    """Fit full-resolution artwork to all available preview space."""
    def __init__(self,parent=None):
        super().__init__('暂无封面',parent);self._source=QPixmap()
        self.setObjectName('coverPreview');self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(180,180);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
    def set_artwork(self,data,empty_text='暂无封面'):
        pixmap=QPixmap();pixmap.loadFromData(data or b'');self._source=pixmap
        if pixmap.isNull():self.clear();self.setText(empty_text)
        else:self.setText('')
        self._fit()
    def _fit(self):
        if self._source.isNull():return
        size=self.contentsRect().size()
        if size.width()>0 and size.height()>0:
            self.setPixmap(self._source.scaled(size,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):
        super().resizeEvent(event);self._fit()


class CropCanvas(QWidget):
    selectionChanged=Signal(int,int,int,int)
    def __init__(self,image,parent=None):
        super().__init__(parent);self.image=image;self._drag_start=None;self._drag_mode=None;self._drag_offset=(0,0)
        data=BytesIO();image.save(data,format='PNG');self.pixmap=QPixmap();self.pixmap.loadFromData(data.getvalue())
        self.selection=QRect(0,0,image.width,image.height)
        self.setMinimumSize(430,300);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
    def image_rect(self):
        if self.pixmap.isNull():return QRectF()
        scale=min(self.width()/self.image.width,self.height()/self.image.height)
        width=self.image.width*scale;height=self.image.height*scale
        return QRectF((self.width()-width)/2,(self.height()-height)/2,width,height)
    def _image_point(self,point):
        rect=self.image_rect()
        x=round((point.x()-rect.left())*self.image.width/rect.width())
        y=round((point.y()-rect.top())*self.image.height/rect.height())
        return max(0,min(self.image.width,x)),max(0,min(self.image.height,y))
    def set_selection(self,x,y,width,height,emit=False):
        x=max(0,min(int(x),self.image.width-1));y=max(0,min(int(y),self.image.height-1))
        width=max(1,min(int(width),self.image.width-x));height=max(1,min(int(height),self.image.height-y))
        self.selection=QRect(x,y,width,height);self.update()
        if emit:self.selectionChanged.emit(x,y,width,height)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        image_rect=self.image_rect();painter.drawPixmap(image_rect,self.pixmap,QRectF(self.pixmap.rect()))
        sx=image_rect.left()+self.selection.x()*image_rect.width()/self.image.width
        sy=image_rect.top()+self.selection.y()*image_rect.height()/self.image.height
        sw=self.selection.width()*image_rect.width()/self.image.width;sh=self.selection.height()*image_rect.height()/self.image.height
        crop=QRectF(sx,sy,sw,sh);shade=QColor(15,31,56,125);painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(shade)
        painter.drawRect(QRectF(image_rect.left(),image_rect.top(),image_rect.width(),max(0,crop.top()-image_rect.top())))
        painter.drawRect(QRectF(image_rect.left(),crop.bottom(),image_rect.width(),max(0,image_rect.bottom()-crop.bottom())))
        painter.drawRect(QRectF(image_rect.left(),crop.top(),max(0,crop.left()-image_rect.left()),crop.height()))
        painter.drawRect(QRectF(crop.right(),crop.top(),max(0,image_rect.right()-crop.right()),crop.height()))
        painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor('#2b70f3'),2));painter.drawRect(crop)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.image_rect().contains(event.position()):
            point=self._image_point(event.position());self._drag_start=point
            full=self.selection==QRect(0,0,self.image.width,self.image.height)
            if self.selection.contains(*point) and not full:
                self._drag_mode='move';self._drag_offset=(point[0]-self.selection.x(),point[1]-self.selection.y())
            else:self._drag_mode='resize';self.set_selection(*point,1,1,emit=True)
    def mouseMoveEvent(self,event):
        if self._drag_start is None:return
        x2,y2=self._image_point(event.position())
        if self._drag_mode=='move':
            width=self.selection.width();height=self.selection.height()
            x=max(0,min(self.image.width-width,x2-self._drag_offset[0]));y=max(0,min(self.image.height-height,y2-self._drag_offset[1]))
            self.set_selection(x,y,width,height,emit=True);return
        x1,y1=self._drag_start;left=min(x1,x2);top=min(y1,y2)
        self.set_selection(left,top,max(1,abs(x2-x1)),max(1,abs(y2-y1)),emit=True)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self._drag_start=None;self._drag_mode=None


class CropDialog(QDialog):
    def __init__(self,source,parent=None):
        super().__init__(parent);self.setWindowTitle('自由矩形裁剪封面');self.resize(720,620)
        with Image.open(source) as image:self.image=image.convert('RGB')
        layout=QVBoxLayout(self);instruction=QLabel('拖拽创建或移动矩形裁剪框，也可输入精确像素。');instruction.setObjectName('muted');layout.addWidget(instruction)
        self.canvas=CropCanvas(self.image);layout.addWidget(self.canvas,1)
        box,fields=group('裁剪区域（像素）');grid=QGridLayout();fields.addLayout(grid)
        self.x=QSpinBox();self.y=QSpinBox();self.width=QSpinBox();self.height=QSpinBox()
        self.x.setRange(0,self.image.width-1);self.y.setRange(0,self.image.height-1)
        self.width.setRange(1,self.image.width);self.height.setRange(1,self.image.height)
        self.width.setValue(self.image.width);self.height.setValue(self.image.height)
        for column,(label,control) in enumerate((('横向起点',self.x),('纵向起点',self.y),('宽度',self.width),('高度',self.height))):
            grid.addWidget(QLabel(label),0,column);grid.addWidget(control,1,column)
        layout.addWidget(box);self._syncing=False
        for control in (self.x,self.y,self.width,self.height):control.valueChanged.connect(self._fields_changed)
        self.canvas.selectionChanged.connect(self._canvas_changed)
        reset_button=button('恢复完整图片',self.reset_selection,symbol='undo')
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        buttons.addButton(reset_button,QDialogButtonBox.ButtonRole.ResetRole)
        language=getattr(getattr(parent,'app',None),'settings',{}).get('language','zh_CN')
        apply_language(self,language)
    def cropped(self):
        x,y,width,height=self.x.value(),self.y.value(),self.width.value(),self.height.value()
        return self.image.crop((x,y,x+width,y+height))
    def _fields_changed(self):
        if self._syncing:return
        self._syncing=True
        self.width.setMaximum(self.image.width-self.x.value());self.height.setMaximum(self.image.height-self.y.value())
        self.canvas.set_selection(self.x.value(),self.y.value(),self.width.value(),self.height.value());self._syncing=False
    def _canvas_changed(self,x,y,width,height):
        if self._syncing:return
        self._syncing=True
        self.x.setValue(x);self.y.setValue(y);self.width.setMaximum(self.image.width-x);self.height.setMaximum(self.image.height-y)
        self.width.setValue(width);self.height.setValue(height);self._syncing=False
    def reset_selection(self):
        self._canvas_changed(0,0,self.image.width,self.image.height);self.canvas.set_selection(0,0,self.image.width,self.image.height)


class MetadataPage(Page):
    def __init__(self,app):
        super().__init__(app,'音频标签编辑','编辑标签、歌词和封面；先预览，再保存。支持同目录智能匹配和文件夹批量写入。')
        self.path=None;self.state=None;self.lyric_path=None;self.cover_path=None
        self.temp=tempfile.TemporaryDirectory(prefix='mediaanvil-qt-cover-')
        file_card,file_body=group('');self.layout.addWidget(file_card)
        self.filename=QLineEdit();self.filename.setReadOnly(True);self.filename.setPlaceholderText('尚未选择音频')
        file_body.addWidget(row(self.filename,button('选择音频文件…',self.choose,symbol='folder')))
        self.details=QLabel('选择音频后显示格式、时长、码率与标签信息');self.details.setWordWrap(True);self.details.setObjectName('notice');file_body.addWidget(self.details)
        basic,fields=form('基本信息')
        self.title=QLineEdit();self.artist=QLineEdit();self.album=QLineEdit()
        self.track=QLineEdit();self.year=QLineEdit();self.genre=QLineEdit()
        self.title.setPlaceholderText('请输入歌名');self.artist.setPlaceholderText('请输入歌手');self.album.setPlaceholderText('请输入专辑')
        self.track.setPlaceholderText('如 3 或 3/12');self.year.setPlaceholderText('如 2024');self.genre.setPlaceholderText('如 流行 / Rock')
        fields.setRowWrapPolicy(fields.RowWrapPolicy.WrapAllRows)
        fields.addRow('歌名',self.title);fields.addRow('歌手',self.artist);fields.addRow('专辑',self.album)
        fields.addRow('曲目号',self.track);fields.addRow('年份',self.year);fields.addRow('流派',self.genre)
        lyric_card,lyric_layout=group('歌词')
        self.lyrics=QPlainTextEdit();self.lyrics.setReadOnly(True);self.lyrics.setPlaceholderText('尚未读取歌词');self.lyrics.setStyleSheet('QPlainTextEdit { font-family:"Segoe UI Symbol"; }');self.lyrics.setMinimumHeight(130);self.lyrics.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding);lyric_layout.addWidget(self.lyrics,1)
        self.import_lyrics_button=button('导入歌词 / 字幕…',self.import_lyrics,symbol='upload');self.export_lyrics_button=button('导出歌词…',lambda:self.export('lyrics'))
        self.lyric_actions=equal_action_row(self.import_lyrics_button,self.export_lyrics_button);self.lyric_actions.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);lyric_layout.addWidget(self.lyric_actions)
        self.remove_lyrics=QCheckBox('移除歌词（保存时生效）');self.remove_cover=QCheckBox('移除封面（保存时生效）')
        self.remove_lyrics.toggled.connect(lambda checked:self.clear_pending('lyrics') if checked else None)
        self.remove_cover.toggled.connect(lambda checked:self.clear_pending('cover') if checked else None)
        # The shift controls share the "remove lyrics" row so the lyrics and
        # artwork cards keep matching heights. Shifting only rewrites the
        # pending lyrics; nothing reaches the audio until the user saves.
        self.lyric_shift=QDoubleSpinBox();self.lyric_shift.setRange(0.0,3600.0);self.lyric_shift.setDecimals(2)
        self.lyric_shift.setSingleStep(0.5);self.lyric_shift.setValue(0.5);self.lyric_shift.setSuffix('秒')
        self.lyric_shift.setFixedWidth(92);self.lyric_shift.setToolTip('要调整的秒数')
        self.shift_direction=combo([('延后','later'),('提前','earlier')]);self.shift_direction.setFixedWidth(96)
        self.shift_button=button('应用',self.apply_lyric_shift);self.shift_button.setFixedWidth(50)
        # The shift controls need their own row (the import/export row is a
        # stretched equal-width group). The artwork card gets a matching empty
        # row so both cards keep the same height. Shifting only rewrites the
        # pending lyrics; nothing reaches the audio until the user saves.
        self.lyric_shift_row=row(self.lyric_shift,self.shift_direction,self.shift_button)
        lyric_layout.addWidget(self.lyric_shift_row)
        lyric_layout.addWidget(self.remove_lyrics)
        self.cover_spacer=QWidget();self.cover_spacer.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        # The row has no final height until the stylesheet has been applied, so
        # the spacer is matched once the event loop settles.
        QTimer.singleShot(0,self.sync_cover_spacer)
        cover_card,cover_layout=group('封面')
        self.cover=ResponsiveCover();cover_layout.addWidget(self.cover,1)
        self.import_cover_button=button('选择图片…',self.import_cover,symbol='image');self.export_cover_button=button('导出图片…',lambda:self.export('cover'))
        self.cover_actions=equal_action_row(self.import_cover_button,self.export_cover_button)
        self.cover_actions.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);cover_layout.addWidget(self.cover_actions)
        cover_layout.addWidget(self.remove_cover)
        cover_layout.addWidget(self.cover_spacer)
        media=Columns(lyric_card,cover_card,400);self.editor=Columns(basic,media,700);self.editor.box.setStretch(1,2)
        self.match_card,match_body=group('智能匹配关联文件');match_body.setContentsMargins(18,8,18,8)
        self.match_toggle=button('展开匹配区域',self.toggle_matches)
        heading=match_body.itemAt(0).widget();match_body.removeWidget(heading)
        self.match_header=QWidget();match_header_layout=QHBoxLayout(self.match_header);match_header_layout.setContentsMargins(0,0,0,0);match_header_layout.addWidget(heading);match_header_layout.addStretch();match_header_layout.addWidget(self.match_toggle);match_body.insertWidget(0,self.match_header)
        self.match_content=QWidget();matched=QVBoxLayout(self.match_content);matched.setContentsMargins(0,0,0,0);matched.setSpacing(8);match_body.addWidget(self.match_content)
        note=QLabel('自动查找同目录歌词与封面；多个候选需要手动选择。');note.setObjectName('muted');note.setWordWrap(False);self.match_note=note
        self.scan_button=button('扫描音乐文件夹…',self.scan_folder,symbol='folder')
        self.clear_matches_button=button('清空文件',self.clear_matches,symbol='trash');self.clear_matches_button.setProperty('danger',True);self.clear_matches_button.setEnabled(False)
        matched.addWidget(row(self.scan_button,self.clear_matches_button,note))
        self.matches=table(['音频','歌词候选','封面候选']);self.matches.setMinimumHeight(95);self.matches.setMaximumHeight(150);matched.addWidget(self.matches)
        self.lyric_match=combo([('不选择 / 保持原内容',None)]);self.cover_match=combo([('不选择 / 保持原内容',None)])
        matched.addWidget(row(QLabel('当前音频'),self.lyric_match,self.cover_match,button('应用到编辑',self.apply_match)))
        self.write_all=button('全部写入',self.batch_write,True);self.write_all.setEnabled(False)
        matched.addWidget(row(button('批量写入歌词',lambda:self.batch_write('lyrics')),button('批量写入封面',lambda:self.batch_write('cover')),self.write_all))
        # Batch tag editing: fill only the boxes you want applied, then write the
        # same values to every scanned file. Blank boxes are left untouched.
        # A grid rather than one long row: five labelled boxes plus the button
        # overflow a narrow window, and the page must never scroll sideways.
        # The fields occupy two rows of three columns and the buttons start on the
        # row below them. Putting a button on a row that already holds a field
        # makes the two overlap, which is what previously hid the track number.
        batch_fields=QWidget();batch_layout=QGridLayout(batch_fields)
        batch_layout.setContentsMargins(0,0,0,0);batch_layout.setHorizontalSpacing(8);batch_layout.setVerticalSpacing(6)
        self.batch_values={}
        for position,(key,label) in enumerate((('album','专辑'),('artist','歌手'),('year','年份'),
                                               ('track','曲目号'),('genre','流派'))):
            edit=QLineEdit();edit.setPlaceholderText(self.app.t(label))
            edit.setFixedWidth(110);edit.setClearButtonEnabled(True)
            self.batch_values[key]=edit
            column=position%3;grid_row=(position//3)*2
            batch_layout.addWidget(QLabel(self.app.t(label)),grid_row,column*2)
            batch_layout.addWidget(edit,grid_row,column*2+1)
        self.batch_apply=button('批量写入标签',self.apply_batch_tags,True);self.batch_apply.setEnabled(False)
        # Shifting every lyric at once is the batch form of the per-file offset on
        # the editor card: same direction, same seconds, applied to every scan.
        self.batch_shift_seconds=QDoubleSpinBox();self.batch_shift_seconds.setRange(0.0,3600.0)
        self.batch_shift_seconds.setDecimals(2);self.batch_shift_seconds.setSingleStep(0.5)
        self.batch_shift_seconds.setValue(0.5);self.batch_shift_seconds.setSuffix('秒')
        self.batch_shift_seconds.setFixedWidth(92);self.batch_shift_seconds.setToolTip('要调整的秒数')
        self.batch_shift_direction=combo([('延后','later'),('提前','earlier')]);self.batch_shift_direction.setFixedWidth(96)
        self.batch_shift=button('批量偏移歌词',self.apply_batch_shift,True);self.batch_shift.setEnabled(False)
        # One chosen image written to every scanned file, as opposed to the
        # matching write above, which pairs each track with the image beside it.
        # Both are kept: matching suits a folder of files that already have their
        # own artwork, this suits replacing the artwork of a whole album.
        self.batch_cover_path=QLabel('未选择封面图片');self.batch_cover_path.setObjectName('muted')
        self.batch_cover_choose=button('选择封面图片…',self.choose_batch_cover)
        self.batch_cover_apply=button('批量写入同一封面',self.apply_batch_cover,True)
        self.batch_cover_apply.setEnabled(False)
        batch_cover=row(self.batch_cover_choose,self.batch_cover_path,self.batch_cover_apply)
        batch_layout.addWidget(batch_cover,6,0,1,6)
        batch_actions=row(self.batch_apply,QLabel('歌词偏移'),self.batch_shift_seconds,
                          self.batch_shift_direction,self.batch_shift)
        batch_layout.addWidget(batch_actions,4,0,1,6)
        batch_layout.setColumnStretch(6,1)
        matched.addWidget(batch_fields)
        self.batch_fields_row=batch_fields
        self.match_content.hide()
        self.layout.addWidget(self.editor,1);self.layout.addWidget(self.match_card)
        self.mode=combo([('另存为（推荐）','save_as'),('覆盖原文件','overwrite')]);self.mode.setCurrentIndex(1 if app.settings['default_save_mode']=='overwrite' else 0)
        self.output=OutputPath(self.output_default())
        self.save_button=button('保存到音频',self.save,True)
        self.footer=row(QLabel('输出目录'),self.output,QLabel('保存方式'),self.mode);self.footer.layout().addWidget(button('取消修改',self.reset));self.footer.layout().addWidget(self.save_button);self.layout.addWidget(self.footer)
        self.match_rows=[]
    def toggle_matches(self):
        visible=not self.match_content.isVisible();self.match_content.setVisible(visible);self.match_toggle.setText(self.app.t('收起匹配区域' if visible else '展开匹配区域'))
        if visible:self.reveal_match_area()
    def reveal_match_area(self):
        """Bring the expanded matching card into view on long pages."""
        scroll=getattr(self,'scroll',None)
        if scroll is None:return
        QTimer.singleShot(0,lambda:self.scroll_to_match_area())
    def scroll_to_match_area(self):
        scroll=getattr(self,'scroll',None)
        if scroll is None or not self.match_card.isVisible():return
        bar=scroll.verticalScrollBar()
        if bar.maximum()<=0:return
        offset=self.match_card.mapTo(self,self.match_card.rect().topLeft()).y()
        bar.setValue(max(0,min(bar.maximum(),bar.value()+offset-self.layout.contentsMargins().top())))
    def clear_pending(self,kind):
        if kind=='lyrics':self.lyric_path=None
        else:self.cover_path=None
    def choose(self):
        supported=self.app.t('音频 (*.mp3 *.flac *.m4a *.ogg *.opus *.wav *.aac)')
        filters=dialog_filters(self,'audio',(supported,self.app.t('所有文件 (*)')))
        path,chosen=QFileDialog.getOpenFileName(self,self.app.t('选择音频'),dialog_initial_directory(self,'audio'),filters)
        if path:
            remember_dialog_selection(self,'audio',path);remember_dialog_filter(self,'audio',chosen);self.load(Path(path))
    def load(self,path,extras=()):
        def done(data):
            self.path=path;self.state,match=data;self.reset();self.populate_match(match)
            for extra in extras:
                if extra.suffix.lower() in EMBEDDABLE_LYRIC_EXTENSIONS:self.set_lyrics(extra)
                elif extra.suffix.lower() in COVER_EXTENSIONS:self.set_cover(extra)
        self.app.run_task(lambda report:(read_metadata(path),match_audio_file(path)),done)
    def reset(self):
        if not self.state:return
        s=self.state;self.lyric_path=self.cover_path=None;self.remove_lyrics.setChecked(False);self.remove_cover.setChecked(False)
        self.title.setText(s.title);self.artist.setText(s.artist);self.album.setText(s.album);self.track.setText(s.track);self.year.setText(s.year);self.genre.setText(getattr(s,'genre',''));self.lyrics.setPlainText(s.lyrics);self.cover.set_artwork(s.cover_data,self.app.t('暂无封面'))
        self.filename.setText(str(self.path));i=s.info
        if self.app.settings.get('language')=='en_US':
            self.details.setText(f'{i.format_label} · {i.duration_seconds:.1f} s · {i.bitrate_kbps} kbps · {i.sample_rate_hz} Hz · {i.channels} channels · {i.file_size_bytes/1024/1024:.2f} MB · {i.tag_count} tags' + ('' if s.writable else ' · Read only'))
        else:self.details.setText(f'{i.format_label} · {i.duration_seconds:.1f} 秒 · {i.bitrate_kbps} kbps · {i.sample_rate_hz} Hz · {i.channels} 声道 · {i.file_size_bytes/1024/1024:.2f} MB · {i.tag_count} 个标签' + ('' if s.writable else ' · 仅支持读取'))
    def candidates(self,box,paths):
        box.clear();box.addItem(self.app.t('不选择 / 保持原内容'),None)
        for path in paths:box.addItem(path.name,path)
        if len(paths)==1:box.setCurrentIndex(1)
        box.setToolTip(self.app.t('有多个候选时，请明确选择；未选择不会自动写入。'))
    def populate_match(self,match):
        self.candidates(self.lyric_match,match.lyric_candidates);self.candidates(self.cover_match,match.cover_candidates)
    def import_lyrics(self):
        supported=self.app.t('歌词 / 字幕 (*.lrc *.srt *.vtt)')
        filters=dialog_filters(self,'subtitle',(supported,self.app.t('所有文件 (*)')))
        path,chosen=QFileDialog.getOpenFileName(self,self.app.t('导入歌词 / 字幕'),dialog_initial_directory(self,'subtitle'),filters)
        if path:
            remember_dialog_selection(self,'subtitle',path);remember_dialog_filter(self,'subtitle',chosen);self.set_lyrics(Path(path))
    def set_lyrics(self,path):
        try:
            from sub2lrc.embedder import read_lrc
            prepared=prepare_lyrics_for_embedding(path,self.temp.name);text=read_lrc(prepared)
            self.lyrics.setPlainText(text);self.remove_lyrics.setChecked(False);self.lyric_path=prepared
        except Exception as exc:self.app.inform(str(exc))
    def sync_cover_spacer(self):
        """Match the artwork card's filler row to the lyrics shift row."""
        height=self.lyric_shift_row.height()
        if height and self.cover_spacer.height()!=height:self.cover_spacer.setFixedHeight(height)
    def resizeEvent(self,event):
        super().resizeEvent(event);self.sync_cover_spacer()
    def showEvent(self,event):
        super().showEvent(event);QTimer.singleShot(0,self.sync_cover_spacer)
    def apply_lyric_shift(self):
        """Apply the chosen direction and magnitude to the pending lyrics."""
        seconds=abs(self.lyric_shift.value())
        if self.shift_direction.currentData()=='earlier':seconds=-seconds
        self.shift_lyrics(seconds)
    def shift_lyrics(self,seconds):
        """Move the pending lyrics timeline without touching the audio yet."""
        if not seconds:return self.app.inform(self.app.t('请先设置偏移秒数。'))
        text=self.lyrics.toPlainText()
        if not text.strip():return self.app.inform(self.app.t('请先导入或载入歌词。'))
        try:moved=shift_lrc(text,seconds)
        except Exception as exc:return self.app.inform(str(exc))
        if moved==text:return self.app.inform(self.app.t('歌词中没有可调整的时间戳。'))
        try:
            target=Path(self.temp.name)/('shifted-'+uuid4().hex+'.lrc')
            target.write_text(moved,encoding='utf-8')
            self.lyrics.setPlainText(moved);self.lyric_path=target;self.remove_lyrics.setChecked(False)
        except OSError as exc:return self.app.inform(str(exc))
        self.app.statusBar().showMessage(self.app.t(f'歌词已偏移 {seconds:+.2f} 秒，保存后写入音频'))
    def import_cover(self):
        supported=self.app.t('图片 (*.png *.jpg *.jpeg *.webp *.bmp)')
        filters=dialog_filters(self,'image',(supported,self.app.t('所有文件 (*)')))
        path,chosen=QFileDialog.getOpenFileName(self,self.app.t('选择封面'),dialog_initial_directory(self,'image'),filters)
        if not path:return
        remember_dialog_selection(self,'image',path);remember_dialog_filter(self,'image',chosen)
        try:
            dialog=CropDialog(Path(path),self)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            target=Path(self.temp.name)/('cropped-'+uuid4().hex+'.png');dialog.cropped().save(target)
            self.set_cover(target)
        except Exception as exc:self.app.inform(str(exc))
    def set_cover(self,path):
        try:
            # Normalise formats unsupported by metadata adapters into a local PNG.
            with Image.open(path) as image:
                data=BytesIO();image.convert('RGBA').save(data,format='PNG')
            target=Path(self.temp.name)/('cover-'+uuid4().hex+'.png')
            target.write_bytes(data.getvalue());self.cover_path=target;self.remove_cover.setChecked(False);self.cover.set_artwork(data.getvalue())
        except Exception as exc:self.app.inform(str(exc))
    def crop(self):
        source=self.cover_path
        if not source and self.state and self.state.cover_data:
            source=Path(self.temp.name)/'original-cover';source.write_bytes(self.state.cover_data)
        if not source:return self.app.inform('请先选择封面或载入带封面的音频。')
        try:
            dialog=CropDialog(source,self)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                target=Path(self.temp.name)/'cropped.png';dialog.cropped().save(target);self.set_cover(target)
        except Exception as exc:self.app.inform(str(exc))
    def apply_match(self):
        if self.lyric_match.currentData():self.set_lyrics(self.lyric_match.currentData())
        if self.cover_match.currentData():self.set_cover(self.cover_match.currentData())
    def save(self):
        if not self.path or not self.state:return self.app.inform('请先选择音频。')
        if not self.state.writable:return self.app.inform('该格式当前只支持读取信息。')
        # Keyword arguments on purpose: this list has grown twice already, and a
        # positional call silently shifts every later field when one is inserted.
        path=self.path;changes=AudioMetadataChanges(
            title=self.title.text(),artist=self.artist.text(),album=self.album.text(),
            track=self.track.text(),year=self.year.text(),genre=self.genre.text(),
            lyrics_path=self.lyric_path,remove_lyrics=self.remove_lyrics.isChecked(),
            cover_path=self.cover_path,remove_cover=self.remove_cover.isChecked())
        overwrite=self.mode.currentData()=='overwrite';directory=self.output.text()
        def work(report):
            destination=None if overwrite else tagged_destination(path,directory)
            target=write_metadata(path,changes,destination)
            return target,read_metadata(target),match_audio_file(target)
        def done(result):
            self.path,self.state,match=result;self.reset();self.populate_match(match);self.app.inform('已保存：\n'+str(self.path))
        self.app.run_task(work,done)
    def export(self,kind):
        if not self.path:return self.app.inform('请先选择音频。')
        directory=QFileDialog.getExistingDirectory(self,self.app.t('选择导出文件夹'),dialog_initial_directory(self,'output'))
        if directory:
            remember_dialog_selection(self,'output',directory)
            path=self.path;function=export_metadata_lyrics if kind=='lyrics' else export_metadata_cover
            self.app.run_task(lambda report:function(path,directory),lambda output:self.app.inform('已导出：\n'+str(output)))
    def receive(self,paths):
        audio=[p for p in paths if p.suffix.lower() in AUDIO_EXTENSIONS]
        if audio:self.load(audio[0],[p for p in paths if p not in audio]);return 1
        for p in paths:
            if p.suffix.lower() in EMBEDDABLE_LYRIC_EXTENSIONS:self.set_lyrics(p)
            elif p.suffix.lower() in COVER_EXTENSIONS:self.set_cover(p)
        return sum(p.suffix.lower() in COVER_EXTENSIONS|EMBEDDABLE_LYRIC_EXTENSIONS for p in paths)
    def scan_folder(self):
        folder=QFileDialog.getExistingDirectory(self,self.app.t('扫描音乐文件夹'),dialog_initial_directory(self,'audio'))
        if folder:
            remember_dialog_selection(self,'audio',folder);self.scan(folder)
    def scan(self,folder):
        recursive=self.app.settings['include_subfolders']
        self.app.run_task(lambda report:scan_audio_folder(folder,include_subfolders=recursive,cancel_check=report.raise_if_cancelled),self.scanned)
    def scanned(self,matches):
        self.match_rows=list(matches);fill_table(self.matches,[(str(m.audio),'','') for m in matches])
        for i,m in enumerate(matches):
            for j,paths in ((1,m.lyric_candidates),(2,m.cover_candidates)):
                box=combo([]);self.candidates(box,paths);self.matches.setCellWidget(i,j,box)
        self.match_content.show();self.match_toggle.setText(self.app.t('收起匹配区域'));self.matches.show();self.write_all.setEnabled(bool(matches));self.batch_apply.setEnabled(bool(matches));self.batch_shift.setEnabled(bool(matches));self.batch_cover_apply.setEnabled(bool(matches));self.clear_matches_button.setEnabled(bool(matches));self.app.statusBar().showMessage(self.app.t(f'扫描完成：{len(matches)} 首音频'))
    def clear_matches(self):
        self.match_rows=[];self.matches.clearContents();self.matches.setRowCount(0)
        self.write_all.setEnabled(False);self.batch_apply.setEnabled(False);self.batch_shift.setEnabled(False);self.batch_cover_apply.setEnabled(False);self.clear_matches_button.setEnabled(False)
        self.app.statusBar().showMessage(self.app.t('已清空匹配文件列表'))
    def batch_write(self,kind=None):
        rows=tuple((m.audio,self.matches.cellWidget(i,1).currentData() if kind!='cover' else None,self.matches.cellWidget(i,2).currentData() if kind!='lyrics' else None) for i,m in enumerate(self.match_rows))
        if not rows:return
        overwrite=self.mode.currentData()=='overwrite';directory=self.output.text()
        self.app.run_task(lambda report:write_matches(rows,overwrite,directory,report),lambda lines:self.app.show_text('批量写入结果','\n'.join(lines)))
    def apply_batch_tags(self):
        """Write the filled tag boxes to every scanned file."""
        if not self.match_rows:return self.app.inform(self.app.t('请先扫描音乐文件夹。'))
        values={key:edit.text() for key,edit in self.batch_values.items()}
        if not any(text.strip() for text in values.values()):
            return self.app.inform(self.app.t('请至少填写一个要批量写入的标签。'))
        paths=[m.audio for m in self.match_rows]
        overwrite=self.mode.currentData()=='overwrite';directory=self.output.text()
        self.app.run_task(
            lambda report:batch_edit_tags(paths,values,overwrite,directory,report),
            lambda lines:self.app.show_text('批量标签结果','\n'.join(lines)))
    def apply_batch_shift(self):
        """Move the embedded lyrics of every scanned file by the same offset."""
        if not self.match_rows:return self.app.inform(self.app.t('请先扫描音乐文件夹。'))
        seconds=abs(self.batch_shift_seconds.value())
        if not seconds:return self.app.inform(self.app.t('请填写要调整的秒数。'))
        if self.batch_shift_direction.currentData()=='earlier':seconds=-seconds
        paths=[m.audio for m in self.match_rows]
        overwrite=self.mode.currentData()=='overwrite';directory=self.output.text()
        self.app.run_task(
            lambda report:batch_shift_lyrics(paths,seconds,overwrite,directory,report),
            lambda lines:self.app.show_text('批量歌词偏移结果','\n'.join(lines)))
    def choose_batch_cover(self):
        """Pick the single image that will be written to every scanned file."""
        start=dialog_initial_directory(self.app,'image')
        chosen,_=QFileDialog.getOpenFileName(self,self.app.t('选择封面图片'),start,
                                             'Images (*.jpg *.jpeg *.png *.webp *.bmp)')
        if not chosen:return
        remember_dialog_selection(self.app,'image',str(Path(chosen).parent))
        self.batch_cover=Path(chosen)
        self.batch_cover_path.setText(self.batch_cover.name)
        self.batch_cover_path.setToolTip(str(self.batch_cover))
    def apply_batch_cover(self):
        """Write the chosen image to every scanned file, replacing existing art."""
        if not self.match_rows:return self.app.inform(self.app.t('请先扫描音乐文件夹。'))
        cover=getattr(self,'batch_cover',None)
        if not cover or not Path(cover).is_file():
            return self.app.inform(self.app.t('请先选择封面图片。'))
        paths=[m.audio for m in self.match_rows]
        overwrite=self.mode.currentData()=='overwrite';directory=self.output.text()
        self.app.run_task(
            lambda report:batch_set_cover(paths,cover,overwrite,directory,report),
            lambda lines:self.app.show_text('批量封面结果','\n'.join(lines)))
