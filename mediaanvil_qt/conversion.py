from pathlib import Path
import shutil
import time
from datetime import datetime
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QPlainTextEdit, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QHeaderView, QSizePolicy, QPushButton, QFrame
from .design import icon
from .common import Page, FileList, OutputPath, button, row, combo, group, Columns, table, fill_table, thumbnail, StatusDelegate
from .services import convert_files
from sub2lrc.audio_converter import FORMAT_SPECS, SUPPORTED_INPUT_EXTENSIONS, AudioConversionSettings
from sub2lrc.image_converter import IMAGE_FORMAT_SPECS, SUPPORTED_IMAGE_EXTENSIONS, ImageConversionSettings


def step_group(number, title, description):
    card=QFrame();card.setObjectName('card');body=QVBoxLayout(card)
    body.setContentsMargins(14,10,14,10);body.setSpacing(8)
    header=QWidget();header.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);header_row=QHBoxLayout(header);header_row.setContentsMargins(0,0,0,0);header_row.setSpacing(10)
    badge=QLabel(str(number));badge.setAlignment(Qt.AlignmentFlag.AlignCenter);badge.setFixedSize(32,32)
    badge.setStyleSheet('background:#e8f1ff;color:#2672f3;border-radius:16px;font-size:16px;font-weight:700;')
    header_row.addWidget(badge,0,Qt.AlignmentFlag.AlignTop)
    words=QVBoxLayout();words.setSpacing(2)
    heading=QLabel(title);heading.setObjectName('sectionTitle');words.addWidget(heading)
    detail=QLabel(description);detail.setObjectName('muted');detail.setWordWrap(True);detail.hide();words.addWidget(detail)
    header_row.addLayout(words,1);body.addWidget(header)
    card.step_badge=badge;card.step_header=header_row
    return card,body,detail


class ConversionPage(Page):
    def __init__(self, app, kind):
        self.kind=kind;self.last_outputs=[];self.records=[]
        title={'audio':'音频格式转换','image':'图片格式转换','subtitle':'歌词 / 字幕转换'}[kind]
        description={'audio':'批量转换 MP3、WAV、FLAC、M4A、AAC、OGG 等音频格式',
                     'image':'支持 JPG、PNG、WebP、BMP 批量互转',
                     'subtitle':'支持 LRC、SRT、VTT 相互转换'}[kind]
        super().__init__(app,title,description)
        self.tagline=QLabel({'audio':'高效转换 · 让音频处理更简单','image':'高效转换 · 让图片更好地使用','subtitle':'高效转换 · 让字幕与歌词更通用'}[kind]+'  —')
        self.tagline.setObjectName('muted');self.tagline.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.header_layout.addWidget(self.tagline)
        extensions=SUPPORTED_INPUT_EXTENSIONS if kind=='audio' else SUPPORTED_IMAGE_EXTENSIONS if kind=='image' else {'.lrc','.srt','.vtt'}
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(0,0,0,0);left_layout.setSpacing(10)
        source_title='选择'+('图片' if kind=='image' else '音频文件' if kind=='audio' else '歌词 / 字幕文件')
        source_description={'audio':'支持 MP3、WAV、FLAC、M4A、AAC、OGG 等格式，可批量添加文件进行转换',
                            'image':'支持 JPG、PNG、WebP、BMP 格式，可批量添加文件进行转换',
                            'subtitle':'支持 LRC、SRT、VTT 格式，可批量添加文件进行转换'}[kind]
        source,body,self.source_detail=step_group(1,source_title,source_description)
        left_layout.addWidget(source)
        self.files=FileList(extensions);self.files.setMinimumHeight(0);self.files.setFixedHeight(28)
        self.files.empty_kind=kind
        self.files.empty_title='点击添加'+('图片' if kind=='image' else '文件')+' 或 拖拽文件到此处'
        self.files.empty_hint={'audio':'支持 .mp3、.wav、.flac、.m4a、.aac、.ogg 等音频文件',
                               'image':'支持 .jpg、.jpeg、.png、.webp、.bmp 等图片文件',
                               'subtitle':'支持 .lrc、.srt、.vtt 等字幕文件'}[kind]
        self.files.setStyleSheet('QListWidget { border:1px dashed #b9d4ff;border-radius:10px;background:#fbfdff; }')
        self.toolbar=self.file_toolbar(self.files);self.toolbar.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        toolbar_buttons=self.toolbar.findChildren(QPushButton)
        folder_button=toolbar_buttons.pop(1);self.toolbar.layout().removeWidget(folder_button);folder_button.setParent(None);folder_button.deleteLater()
        self.file_count=self.toolbar.count_label;self.toolbar.layout().removeWidget(self.file_count)
        trailing=self.toolbar.layout().takeAt(self.toolbar.layout().count()-1)
        for control,text,tip,symbol in zip(toolbar_buttons,('添加…','移除','清空'),('添加文件','移除已勾选的文件','清空文件列表'),('file','trash','trash')):
            control.setText(text);control.setToolTip(tip)
            control.setIcon(icon(symbol,'#df5265' if text=='清空' else '#397bf3',18));control.setIconSize(QSize(18,18))
            control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        for index in range(len(toolbar_buttons)):self.toolbar.layout().setStretch(index,1)
        body.addWidget(self.toolbar);body.addWidget(self.files,1)
        self.select_all=QCheckBox('全选文件');self.select_all.setChecked(True)
        self.select_all.toggled.connect(self.check_all)
        self.selection_row=QWidget();selection_layout=QHBoxLayout(self.selection_row);selection_layout.setContentsMargins(0,0,0,0)
        selection_layout.addWidget(self.select_all);selection_layout.addStretch(1);selection_layout.addWidget(self.file_count);body.addWidget(self.selection_row)
        settings,settings_body,self.settings_detail=step_group(2,'转换设置','设置输出格式及相关选项');left_layout.addWidget(settings,1)
        grid=QGridLayout();grid.setHorizontalSpacing(12);grid.setVerticalSpacing(5);settings_body.addLayout(grid)
        specs=FORMAT_SPECS if kind=='audio' else IMAGE_FORMAT_SPECS if kind=='image' else None
        self.format=combo([(s.label,k) for k,s in specs.items()] if specs else ['LRC','SRT','VTT'])
        def field(label,control,r,c):
            row_index=r//2;label_column=c*2
            control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
            grid.addWidget(QLabel(label),row_index,label_column);grid.addWidget(control,row_index,label_column+1)
            grid.setColumnStretch(label_column+1,1)
        field('输出格式',self.format,0,0)
        if kind=='audio':
            self.parameter=combo([]);field('码率 / 质量',self.parameter,0,1)
            self.rate=combo([('保持原始',None),('44100 Hz',44100),('48000 Hz',48000),('96000 Hz',96000)])
            self.channels=combo([('保持原始',None),('单声道',1),('立体声',2)])
            field('采样率',self.rate,2,0);field('声道',self.channels,2,1)
            self.preserve=QCheckBox('保留音频标签');self.preserve.setChecked(app.settings['default_preserve_metadata'])
            settings_body.addWidget(self.preserve)
            self.format.currentIndexChanged.connect(self.update_parameter);self.update_parameter()
        elif kind=='image':
            self.quality=QSpinBox();self.quality.setRange(1,100);self.quality.setValue(app.settings['default_image_quality'])
            field('图片质量',self.quality,0,1)
            self.format.currentIndexChanged.connect(lambda:self.quality.setEnabled(IMAGE_FORMAT_SPECS[self.format.currentData()].supports_quality))
            note=QLabel('保持原始宽高；透明图片转为 JPG / BMP 时使用白色背景。');note.setWordWrap(True);note.setObjectName('notice');settings_body.addWidget(note)
        else:
            self.duration=QDoubleSpinBox();self.duration.setRange(.1,3600);self.duration.setValue(app.settings['subtitle_final_duration']);self.duration.setSuffix(' 秒')
            self.advanced=QCheckBox('高级设置：LRC 最后一句持续时间')
            settings_body.addWidget(self.advanced);settings_body.addWidget(self.duration);self.duration.hide();self.advanced.toggled.connect(self.duration.setVisible)
        self.output=OutputPath(self.output_default());settings_body.addWidget(row(QLabel('输出目录'),self.output))
        self.auto_open=QCheckBox('转换完成后打开输出目录');settings_body.addWidget(self.auto_open)
        self.start_button=button('开始批量转换',self.start,True,'convert')
        self.start_button.setMinimumHeight(32);self.start_button.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        settings_body.removeWidget(self.auto_open);settings_body.addWidget(row(self.auto_open,self.start_button))
        result_card,result_body,self.result_detail=step_group(3,'转换结果预览' if kind=='subtitle' else '转换完成','选择文件查看转换结果，支持另存为')
        self.step_cards=(source,settings,result_card)
        self.columns=Columns(left,result_card,700);self.layout.addWidget(self.columns,1)
        self.summary=QLabel('暂无转换记录');self.summary.setObjectName('muted');self.summary.hide();result_body.addWidget(self.summary)
        self.result_picker=combo([]);self.result_picker.setMaximumWidth(16777215);self.result_picker.currentIndexChanged.connect(self.show_result)
        self.result_picker.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);self.result_picker.setPlaceholderText('选择转换结果');self.result_picker.setEnabled(False)
        result_controls=row(self.result_picker,button('结果另存为…',self.save_result,symbol='upload'))
        result_controls.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);result_body.addWidget(result_controls)
        self.result_table=table(['文件名','格式','大小','状态'])
        self.result_table.setItemDelegateForColumn(3,StatusDelegate(self.result_table))
        self.result_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for col in (1,2,3):self.result_table.horizontalHeader().setSectionResizeMode(col,QHeaderView.ResizeMode.ResizeToContents)
        self.result_table.setMinimumHeight(130);self.result_table.currentCellChanged.connect(lambda r,*args:self.result_picker.setCurrentIndex(r) if r>=0 else None)
        if kind!='subtitle':result_body.addWidget(self.result_table,1)
        else:self.result_table.hide()
        self.empty=QWidget();empty_layout=QVBoxLayout(self.empty);empty_layout.addStretch()
        empty_icon=QLabel();empty_icon.setPixmap(icon('image' if kind=='image' else 'music' if kind=='audio' else 'file','#c3d4ed',76).pixmap(76,76));empty_layout.addWidget(empty_icon,0,Qt.AlignmentFlag.AlignCenter)
        empty_title=QLabel('暂无转换记录');empty_title.setObjectName('sectionTitle');empty_layout.addWidget(empty_title,0,Qt.AlignmentFlag.AlignCenter)
        empty_hint=QLabel('转换完成后，文件内容将在这里显示' if kind=='subtitle' else '转换完成后，文件将显示在这里');empty_hint.setObjectName('muted');empty_layout.addWidget(empty_hint,0,Qt.AlignmentFlag.AlignCenter)
        empty_more=QLabel('请选择左侧文件并进行转换');empty_more.setObjectName('muted');empty_layout.addWidget(empty_more,0,Qt.AlignmentFlag.AlignCenter);empty_layout.addStretch()
        result_body.addWidget(self.empty,1);self.result_table.hide()
        self.preview=QLabel('选择转换结果查看预览');self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setMinimumHeight(90)
        self.detail=QLabel('');self.detail.setWordWrap(True);self.detail.setObjectName('muted')
        if kind=='image':
            result_body.addWidget(self.preview);result_body.addWidget(self.detail);self.preview.hide();self.detail.hide()
        else:self.preview.hide();self.detail.hide()
        self.results=QPlainTextEdit();self.results.setReadOnly(True)
        if kind=='subtitle':self.results.setStyleSheet('QPlainTextEdit { font-family:"Segoe UI Symbol"; }')
        self.results.setPlaceholderText('转换完成后，文件内容将在这里显示' if kind=='subtitle' else '转换详情与失败原因')
        if kind=='subtitle':self.results.setMinimumHeight(190);result_body.addWidget(self.results,1);self.results.hide()
        else:self.results.setMaximumHeight(95);result_body.addWidget(self.results)
        if kind!='subtitle':self.results.hide()
        result_body.addWidget(row(button('打开所在位置',self.open_output,symbol='folder'),button('再次转换',self.reconvert,symbol='convert')))
        for control in self.findChildren(QPushButton):
            control.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)
        for control in self.toolbar.findChildren(QPushButton):control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.start_button.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self._layout_ready=True
    def receive(self,paths):return self.files.add_paths(paths)
    def check_all(self,checked):
        for i in range(self.files.count()):self.files.item(i).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    def update_parameter(self):
        spec=FORMAT_SPECS[self.format.currentData()];self.parameter.clear()
        for p in spec.parameter_options:self.parameter.addItem(str(p),p)
        default=self.app.settings['default_mp3_bitrate'] if spec.key=='mp3' else self.app.settings['default_aac_bitrate'] if spec.key in ('aac','m4a') else spec.default_parameter
        self.parameter.setCurrentIndex(max(0,self.parameter.findData(default)));self.parameter.setEnabled(bool(spec.parameter_options))
        self.parameter.setToolTip(self.app.t(spec.parameter_label or '此格式无编码参数'))
    def start(self):
        paths=self.files.checked_paths()
        if not paths:return self.app.inform(self.app.t('请先添加并勾选要转换的文件。'))
        self.convert_paths(paths)
    def convert_paths(self,paths):
        fmt=self.format.currentData()
        if self.kind=='audio':settings=AudioConversionSettings(fmt,self.parameter.currentData(),self.rate.currentData(),self.channels.currentData(),self.preserve.isChecked())
        elif self.kind=='image':settings=ImageConversionSettings(fmt,self.quality.value() if IMAGE_FORMAT_SPECS[fmt].supports_quality else None)
        else:settings=(fmt,self.duration.value())
        directory=self.output.text();kind=self.kind;self.started=time.monotonic()
        def work(report):
            records=[]
            for i,source in enumerate(paths):
                outputs,lines=convert_files(kind,[source],directory,settings,lambda p,t:report((i+p/100)/len(paths)*100,t))
                target=outputs[0] if outputs else None
                record=dict(source=source,path=target,message='\n'.join(lines),text='',size=target.stat().st_size if target else 0,dimensions='',finished=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                if target and kind=='subtitle':record['text']=target.read_text(encoding='utf-8-sig')
                if target and kind=='image':
                    from PIL import Image
                    with Image.open(target) as picture:record['dimensions']=f'{picture.width} × {picture.height}'
                records.append(record)
            return records
        self.app.run_task(work,self.completed)
    def completed(self,records):
        self.records=records;self.last_outputs=[r['path'] for r in records if r['path']]
        self.empty.hide();self.summary.show();self.result_picker.setEnabled(bool(records))
        if self.kind=='subtitle':self.results.show()
        else:self.result_table.show();self.results.show()
        if self.kind=='image':self.preview.show();self.detail.show()
        self.result_picker.blockSignals(True);self.result_picker.clear()
        for r in records:self.result_picker.addItem((r['path'] or r['source']).name,r['path'])
        self.result_picker.blockSignals(False)
        fill_table(self.result_table,[((r['path'] or r['source']).name,r['path'].suffix[1:].upper() if r['path'] else '—',f"{r['size']/1024:.1f} KB" if r['path'] else '—',self.app.t('已完成' if r['path'] else '失败')) for r in records])
        for i,r in enumerate(records):
            self.result_table.item(i,3).setForeground(QColor('#169763' if r['path'] else '#df5265'))
            self.result_table.item(i,0).setToolTip(r['message'])
            if self.kind=='image' and r['path']:self.result_table.item(i,0).setIcon(thumbnail(r['path']))
        self.summary.setObjectName('success' if len(self.last_outputs)==len(records) else 'notice')
        self.summary.setStyleSheet('');self.summary.style().unpolish(self.summary);self.summary.style().polish(self.summary)
        self.summary.setText(self.app.t(f'转换完成：成功 {len(self.last_outputs)} 个，失败 {len(records)-len(self.last_outputs)} 个 · 耗时 {time.monotonic()-self.started:.1f} 秒'))
        if self.kind!='subtitle':self.results.setPlainText(self.app.t('\n'.join(r['message'] for r in records)))
        if records:self.result_picker.setCurrentIndex(0);self.show_result(0);self.result_table.selectRow(0)
        if self.auto_open.isChecked():
            for directory in dict.fromkeys(p.parent for p in self.last_outputs):self.app.open_path(directory)
    def show_result(self,index):
        if not 0<=index<len(self.records):return
        self.result_table.blockSignals(True);self.result_table.selectRow(index);self.result_table.blockSignals(False)
        record=self.records[index];path=record['path']
        if self.kind=='subtitle':self.results.setPlainText(record['text'] if path else record['message'])
        if self.kind=='image':
            self.preview.clear()
            if path:
                self.preview.setPixmap(thumbnail(path,210).pixmap(210,150))
                self.detail.setText(f"{path.name}\n{record['size']/1024:.1f} KB · {record['dimensions']}\n{self.app.t('完成时间：')}{record['finished']}")
            else:self.preview.setText(self.app.t('转换失败'));self.detail.setText(self.app.t(record['message']))
    def current_record(self):
        index=self.result_picker.currentIndex()
        return self.records[index] if 0<=index<len(self.records) else None
    def open_output(self):
        record=self.current_record();path=record['path'] if record else None
        directory=path.parent if path else Path(self.output.text()) if self.output.text() else None
        if directory:self.app.open_path(directory)
    def save_result(self):
        record=self.current_record()
        if not record or not record['path']:return self.app.inform(self.app.t('请先选择一个转换成功的结果。'))
        source=record['path'];destination,_=QFileDialog.getSaveFileName(self,self.app.t('结果另存为'),str(source),f'{source.suffix.upper()} (*{source.suffix})')
        if destination:
            target=Path(destination)
            if target.resolve()==source.resolve():return
            self.app.run_task(lambda report:shutil.copy2(source,target),lambda path:self.app.statusBar().showMessage(self.app.t('已另存为：'+str(path))))
    def reconvert(self):
        record=self.current_record()
        if record:self.convert_paths([record['source']])
        else:self.start()
    def preview_text(self):
        record=self.current_record()
        if record:self.show_result(self.result_picker.currentIndex())
    def resizeEvent(self,event):
        super().resizeEvent(event)
        self._update_responsive_layout()
    def showEvent(self,event):
        super().showEvent(event);self._update_responsive_layout();QTimer.singleShot(0,self._update_responsive_layout)
    def _update_responsive_layout(self):
        if not getattr(self,'_layout_ready',False):return
        viewport=getattr(self,'scroll',None)
        available=viewport.viewport().size() if viewport and viewport.viewport().width()>100 else self.size()
        roomy=available.width()>=850 and available.height()>=600
        self._roomy=roomy;self.setMaximumHeight(16777215)
        expanded_height={'subtitle':170,'audio':170,'image':160}[self.kind]
        self.files.setFixedHeight(expanded_height if roomy else 28)
        for card in self.step_cards:
            card.step_badge.setFixedSize(32,32) if roomy else card.step_badge.setFixedSize(24,24)
        self.source_detail.hide()
        for detail in (self.settings_detail,self.result_detail):detail.setVisible(roomy)
        self.tagline.setVisible(available.width()>=900)
        long_labels=(('添加图片' if self.kind=='image' else '添加文件'),'移除','清空')
        short_labels=('添加…','移除','清空')
        for control,text in zip(self.toolbar.findChildren(QPushButton),long_labels if roomy else short_labels):control.setText(self.app.t(text))
        self.result_table.setMinimumHeight(190 if roomy else 130)
        self.results.setMinimumHeight(310 if roomy and self.kind=='subtitle' else 190 if self.kind=='subtitle' else 0)
        self.preview.setMinimumHeight(130 if roomy else 90)
        if not roomy:
            self._refresh_compact_height();QTimer.singleShot(0,self._refresh_compact_height)
    def _refresh_compact_height(self):
        if getattr(self,'_roomy',False):return
        self.layout.activate();self.setMaximumHeight(self.sizeHint().height())
