"""Audio join and split page: merge several files, or cut one into pieces."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel,
    QRadioButton, QButtonGroup, QSpinBox, QVBoxLayout, QWidget, QSizePolicy,
    )

from .waveform import WaveformView as WaveformView, width_start as width_start
from .common import (Page, FileList, OutputPath, button, row, combo, Columns, table,
    fill_table)
from .conversion import step_group
from sub2lrc.audio_converter import FORMAT_SPECS, SUPPORTED_INPUT_EXTENSIONS
from sub2lrc.audio_join import (AudioPolish, MAX_FADE_SECONDS, SplitPlan, audio_duration,
    audio_peaks, merge_audio, plan_equal_parts, plan_fixed_length, split_audio)


class JoinPage(Page):
    """Three modes: join many files, split one file, or crop a selected range."""

    def __init__(self, app):
        super().__init__(app, '音频合并 / 分割 / 裁剪', '把多段音频接成一条、切成多段，或按波形裁剪出一段；输出为新文件，不改动源文件。')
        self.tagline = QLabel('批量处理 · 拼接、切分与波形裁剪  —')
        self.tagline.setObjectName('muted')
        self.tagline.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.header_layout.addWidget(self.tagline)

        left = QWidget(); left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0); left_layout.setSpacing(10)

        source, body, self.source_detail = step_group(1, '选择音频文件', '支持 MP3、WAV、FLAC、M4A、AAC、OGG 等格式')
        self.source_card = source
        left_layout.addWidget(source)
        self.files = FileList(SUPPORTED_INPUT_EXTENSIONS, reorderable=True)
        self.files.empty_kind = 'audio'
        self.files.empty_title = '点击添加文件 或 拖拽文件到此处'
        self.files.empty_hint = '合并需要至少两个文件；分割只需一个'
        self.files.setStyleSheet('QListWidget { border:1px dashed #b9d4ff;border-radius:10px;background:#fbfdff; }')
        self.toolbar = self.file_toolbar(self.files)
        self.toolbar.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        body.addWidget(self.toolbar); body.addWidget(self.files, 1)
        self.select_all = QCheckBox('全选文件'); self.select_all.setChecked(True)
        self.select_all.toggled.connect(self.check_all)
        self.selection_row = QWidget(); selection = QHBoxLayout(self.selection_row)
        selection.setContentsMargins(0, 0, 0, 0)
        selection.addWidget(self.select_all)
        # Dragging is the quick way to reorder; these buttons are the accessible
        # one, and they work when the list is too short to drop onto precisely.
        self.move_up_button = button('上移', lambda: self.move_selection(-1))
        self.move_down_button = button('下移', lambda: self.move_selection(1))
        self.move_up_button.setToolTip('把选中的文件向上移动一位')
        self.move_down_button.setToolTip('把选中的文件向下移动一位')
        selection.addWidget(self.move_up_button); selection.addWidget(self.move_down_button)
        selection.addStretch(1)
        selection.addWidget(self.toolbar.count_label); body.addWidget(self.selection_row)

        mode_card, mode_body, self.mode_detail = step_group(2, '处理方式', '合并多段音频、把一段切成多段，或按波形裁剪出一段')
        self.mode_card = mode_card
        left_layout.addWidget(mode_card)
        self.mode_buttons = {}
        mode_row = QWidget(); mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0); mode_layout.setSpacing(16)
        self.mode_group = QButtonGroup(self)
        for index, (key, label) in enumerate((('merge', '合并为一个文件'), ('split', '分割为多个文件'), ('crop', '裁剪选中片段'))):
            option = QRadioButton(label); option.setChecked(index == 0)
            self.mode_group.addButton(option, index)
            self.mode_buttons[key] = option; mode_layout.addWidget(option)
        mode_layout.addStretch(1); mode_body.addWidget(mode_row)
        self.mode_group.idToggled.connect(self.mode_changed)

        # Crop mode shows a waveform for the first checked file. Peaks are
        # decoded once per file in the background and cached until it changes.
        self.crop_start_edit = QDoubleSpinBox(); self.crop_start_edit.setRange(0.0, 36000.0)
        self.crop_start_edit.setDecimals(2); self.crop_start_edit.setSuffix(' 秒'); self.crop_start_edit.setFixedWidth(110)
        self.crop_end_edit = QDoubleSpinBox(); self.crop_end_edit.setRange(0.0, 36000.0)
        self.crop_end_edit.setDecimals(2); self.crop_end_edit.setSuffix(' 秒'); self.crop_end_edit.setFixedWidth(110)
        crop_options = QWidget(); crop_layout = QVBoxLayout(crop_options)
        crop_layout.setContentsMargins(0, 0, 0, 0); crop_layout.setSpacing(8)
        self.waveform = WaveformView()
        self.waveform.selectionChanged = self.crop_selection_changed
        crop_layout.addWidget(self.waveform)
        crop_row = row(QLabel('开始'), self.crop_start_edit, QLabel('结束'), self.crop_end_edit,
                       button('试听选区', self.preview_crop, symbol='play'),
                       button('清除选区', self.clear_crop_selection, symbol='undo'))
        crop_layout.addWidget(crop_row)
        self.crop_note = QLabel('拖动波形上的虚线选择起止时间；导出时写入新文件。')
        self.crop_note.setObjectName('muted')
        crop_layout.addWidget(row(self.crop_note,button('重新生成波形',self.reload_waveform,symbol='convert')))
        self.crop_options = crop_options
        mode_body.addWidget(crop_options)

        self.split_options = QWidget(); split_layout = QVBoxLayout(self.split_options)
        split_layout.setContentsMargins(0, 0, 0, 0); split_layout.setSpacing(8)
        self.split_mode = combo([('按段数等分', 'parts'), ('按每段时长', 'length')])
        self.split_mode.setMaximumWidth(180)
        self.split_parts = QSpinBox(); self.split_parts.setRange(2, 200); self.split_parts.setValue(2)
        self.split_parts.setFixedWidth(90)
        self.split_length = QDoubleSpinBox(); self.split_length.setRange(0.5, 3600.0)
        self.split_length.setDecimals(1); self.split_length.setValue(30.0)
        self.split_length.setSuffix(' 秒'); self.split_length.setFixedWidth(110)
        split_layout.addWidget(row(QLabel('分段方式'), self.split_mode, QLabel('段数'), self.split_parts,
                                   QLabel('每段'), self.split_length))
        self.duration_note = QLabel('选择文件后显示时长')
        self.duration_note.setObjectName('muted')
        split_layout.addWidget(self.duration_note)
        mode_body.addWidget(self.split_options)
        self.split_mode.currentIndexChanged.connect(self.split_mode_changed)
        self.split_mode_changed()

        output_card, output_body, self.output_detail = step_group(3, '输出设置', '输出为新文件，源文件保持不变')
        self.output_card = output_card
        left_layout.addWidget(output_card)
        self.format = combo([(spec.label, key) for key, spec in FORMAT_SPECS.items()])
        self.format.setFixedWidth(120)
        self.output = OutputPath()
        output_body.addWidget(row(QLabel('输出格式'), self.format, QLabel('输出目录'), self.output))
        # Optional polish. Both default to off so an untouched page behaves
        # exactly as before; nothing is applied unless the user asks for it.
        self.fade_enabled = QCheckBox('淡入淡出')
        self.fade_seconds = QDoubleSpinBox(); self.fade_seconds.setRange(0.1, MAX_FADE_SECONDS)
        self.fade_seconds.setDecimals(1); self.fade_seconds.setSingleStep(0.5)
        self.fade_seconds.setValue(2.0); self.fade_seconds.setSuffix(' 秒')
        self.fade_seconds.setFixedWidth(110); self.fade_seconds.setEnabled(False)
        self.fade_seconds.setToolTip('音频开头淡入、结尾淡出的时长')
        self.normalize = QCheckBox('音量标准化')
        self.normalize.setToolTip('按 EBU R128 把各段响度调整到一致，适合拼接音量不同的录音')
        self.fade_enabled.toggled.connect(self.fade_seconds.setEnabled)
        polish_row = row(self.fade_enabled, self.fade_seconds, self.normalize)
        self.polish_row = polish_row
        output_body.addWidget(polish_row)
        self.fast_export=QCheckBox('快速导出（兼容时免重编码）')
        self.fast_export.setToolTip('快速模式按音频帧切分，切点可能有轻微偏差；格式不兼容或启用音效时自动使用精确模式。')
        output_body.addWidget(self.fast_export)
        self.polish_note = QLabel('两项默认关闭；勾选后仅作用于新生成的文件。')
        self.polish_note.setObjectName('muted')
        output_body.addWidget(self.polish_note)

        right = QWidget(); right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0); right_layout.setSpacing(10)
        result, result_body, self.result_detail = step_group(4, '处理结果', '显示本次生成的每一个文件')
        self.result_card = result
        right_layout.addWidget(result)
        self.result_table = table(['文件名', '格式', '大小'])
        self.result_table.setMinimumHeight(220)
        result_body.addWidget(self.result_table, 1)
        self.status = QLabel('尚未开始')
        self.status.setObjectName('notice'); result_body.addWidget(self.status)
        right_layout.addStretch(1)
        self.columns = Columns(left, right, 760)
        self.layout.addWidget(self.columns, 1)

        self.start_button = button('开始处理', self.start, True, 'play')
        self.footer = row(self.start_button)
        self.layout.addWidget(self.footer)
        # The default-checked button emits no toggle signal, so the initial
        # label and option visibility are applied explicitly here.
        from .tool_layouts import join_layout
        join_layout(self)
        self.mode_changed()
        self.files.filesChanged.connect(self.refresh_waveform_source)
        self._wave_source = None
        self._layout_ready = True

    # ---- state ---------------------------------------------------------
    def current_mode(self):
        return {0: 'merge', 1: 'split', 2: 'crop'}.get(self.mode_group.checkedId(), 'merge')

    def mode_changed(self, *_args):
        mode = self.current_mode()
        self.split_options.setVisible(mode == 'split')
        self.crop_options.setVisible(mode == 'crop')
        self.start_button.setText(self.app.t({'merge': '开始合并', 'split': '开始分割', 'crop': '导出选区'}[mode]))
        if mode == 'crop':
            self.refresh_waveform_source()
        self.update_duration_note()

    def refresh_waveform_source(self, *_args):
        """Load peaks for the first checked file when crop mode is active."""
        if self.current_mode() != 'crop': return
        paths = self.files.checked_paths()
        source = paths[0] if paths else None
        if source == self._wave_source: return
        if self.app._importing:
            QTimer.singleShot(50,self,self.refresh_waveform_source);return
        if self.app._worker:
            if getattr(self,'_wave_waiting_worker',None) is not self.app._worker:
                self._wave_waiting_worker=self.app._worker
                self.app._worker.finished.connect(lambda:QTimer.singleShot(0,self,self.refresh_waveform_source))
            return
        self._wave_source = source
        if source is None:
            self.waveform.clear_audio(); self.crop_note.setText(self.app.t('选择一个音频文件后显示波形。')); return
        self.crop_note.setText(self.app.t('正在生成波形…'))
        def work(report):
            return audio_peaks(source,cancel_check=report.raise_if_cancelled,
                               process_callback=report.register_process,
                               cache_directory=self.app.settings_file.parent/'waveforms')
        def done(result):
            if self._wave_source != source: return
            duration, peaks = result
            self.waveform.set_audio(duration, peaks)
            self.crop_start_edit.setMaximum(max(0.0, duration))
            self.crop_end_edit.setMaximum(max(0.0, duration))
            self.crop_note.setText(self.app.t('拖动波形上的虚线选择起止时间；导出时写入新文件。'))
        self.app.run_task(work, done)
        if self.app._worker:self.app._worker.cancelled.connect(self.waveform_cancelled)

    def waveform_cancelled(self):
        self._wave_source=None;self.crop_note.setText(self.app.t('波形生成已取消，点击重新生成。'))
        self.waveform.clear_audio()
    def reload_waveform(self):
        if self.app._worker or self.app._importing:return self.app.inform(self.app.t('当前任务仍在处理，请等待完成。'))
        self._wave_source=None;self.refresh_waveform_source()

    def crop_selection_changed(self, start, end):
        self.crop_start_edit.blockSignals(True); self.crop_start_edit.setValue(start); self.crop_start_edit.blockSignals(False)
        self.crop_end_edit.blockSignals(True); self.crop_end_edit.setValue(end); self.crop_end_edit.blockSignals(False)

    def clear_crop_selection(self):
        self.waveform.set_selection(0.0, self.waveform.duration)

    def preview_crop(self):
        """Audition the current selection with FFplay; never touches files."""
        if self.waveform.duration <= 0: return self.app.inform(self.app.t('请先选择音频文件。'))
        start, end = self.waveform.selection_start, self.waveform.selection_end
        if end - start < 0.05: return self.app.inform(self.app.t('选区太短，请先拖宽选区。'))
        from sub2lrc.audio_preview import find_ffplay
        from sub2lrc.audio_converter import _creation_flags
        import subprocess
        command = [str(find_ffplay()), '-nodisp', '-autoexit', '-hide_banner', '-loglevel', 'error',
                   '-ss', f'{start:.3f}', '-t', f'{end - start:.3f}', str(self._wave_source)]
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=_creation_flags())

    def split_mode_changed(self, *_args):
        by_parts = self.split_mode.currentData() == 'parts'
        self.split_parts.setVisible(by_parts); self.split_length.setVisible(not by_parts)
        self.update_duration_note()

    def update_duration_note(self):
        paths = self.files.checked_paths()
        mode = self.current_mode()
        if not paths:
            self.duration_note.setText(self.app.t('选择文件后显示时长'))
            return
        if mode == 'merge':
            self.duration_note.setText(self.app.t(f'将合并 {len(paths)} 个文件，按列表顺序拼接（可拖动或上移/下移调整）'))
        elif mode == 'crop':
            self.duration_note.setText(self.app.t('裁剪只处理列表中的第一个文件'))
        else:
            self.duration_note.setText(self.app.t('分割只处理列表中的第一个文件'))

    def receive(self, paths):
        return self.files.add_paths(paths)

    def move_selection(self, direction):
        """Move the selected rows one place up or down, keeping them together."""
        rows=sorted(self.files.row(item) for item in self.files.selectedItems())
        if not rows:
            return self.app.inform(self.app.t('请先在列表中选择要调整顺序的文件。'))
        # "Before row N" in the current list: one above the block for an upward
        # move, and the row just past the block for a downward move.
        before=rows[0]-1 if direction<0 else rows[-1]+2
        if before<0:return
        if direction>0 and rows[-1]>=self.files.count()-1:return
        if self.files.move_rows(rows,before):self.update_duration_note()

    def check_all(self, checked):
        for index in range(self.files.count()):
            self.files.item(index).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    # ---- work ----------------------------------------------------------
    def current_polish(self):
        """Snapshot the optional fade / normalisation choices for the worker."""
        fade = self.fade_seconds.value() if self.fade_enabled.isChecked() else 0.0
        return AudioPolish(fade_seconds=fade, normalize=self.normalize.isChecked())

    def start(self):
        paths = self.files.checked_paths()
        if not paths:
            return self.app.inform(self.app.t('请先添加并勾选要处理的文件。'))
        parameters={'mode':self.current_mode(),'format':self.format.currentData(),'output_directory':self.output.text(),
            'fade':self.current_polish().fade_seconds,'normalize':self.current_polish().normalize,
            'fast':self.fast_export.isChecked(),'split_mode':self.split_mode.currentData(),
            'parts':self.split_parts.value(),'length':self.split_length.value(),
            'start':self.waveform.selection_start,'end':self.waveform.selection_end}
        self.submit_parameters(paths,parameters)

    def submit_parameters(self,paths,parameters):
        paths=tuple(Path(p) for p in paths)
        output_format=parameters['format'];directory=parameters.get('output_directory','')
        polish=AudioPolish(fade_seconds=parameters.get('fade',0),normalize=parameters.get('normalize',False))
        fast=parameters.get('fast',False);mode=parameters['mode']
        try:
            polish.validate()
        except Exception as exc:
            return self.app.inform(str(exc))
        if mode == 'merge':
            if len(paths) < 2:
                return self.app.inform(self.app.t('合并至少需要两个音频文件。'))
            sources = list(paths)
            self.app.submit_task('join',sources,parameters,
                lambda report: [merge_audio(sources, output_format, directory, report,
                                            polish=polish,fast=fast,
                                            cancel_check=report.raise_if_cancelled,
                                            process_callback=report.register_process)],
                lambda outputs,task_id:self.finished(outputs,task_id,sources))
            return
        source = paths[0]
        if mode == 'crop':
            start,end=parameters['start'],parameters['end']
            if end - start < 0.05:
                return self.app.inform(self.app.t('选区太短，请先拖宽选区。'))
            plans = (SplitPlan(start, end - start),)
        else:
            by_parts=parameters['split_mode']=='parts';parts=parameters['parts'];length=parameters['length']
            def work(report):
                report(0, source.name)
                total = audio_duration(source)
                plan_list = plan_equal_parts(total, parts) if by_parts else plan_fixed_length(total, length)
                return list(split_audio(source, plan_list, output_format, directory, report,
                                        polish=polish,fast=fast,
                                        cancel_check=report.raise_if_cancelled,
                                        process_callback=report.register_process))
            self.app.submit_task('join',[source],parameters,work,lambda outputs,task_id:self.finished(outputs,task_id,[source]))
            return
        def crop_work(report):
            report(0, source.name)
            return list(split_audio(source, plans, output_format, directory, report,
                                    polish=polish,fast=fast,
                                    cancel_check=report.raise_if_cancelled,
                                    process_callback=report.register_process))
        self.app.submit_task('join',[source],parameters,crop_work,lambda outputs,task_id:self.finished(outputs,task_id,[source]))

    def finished(self, outputs,task_id=None,sources=()):
        outputs = [Path(path) for path in outputs]
        if task_id:
            from core.tasks import TaskRecord
            records=[TaskRecord(source,'已完成',output=outputs[0]) for source in sources] if len(sources)>1 else [TaskRecord(sources[0],'已完成',output=p) for p in outputs]
            self.app.record_task_history('join',records,task_id=task_id)
        self.last_outputs = outputs
        rows = []
        for path in outputs:
            try: size = f'{path.stat().st_size / 1024:.1f} KB'
            except OSError: size = '—'
            rows.append((path.name, path.suffix[1:].upper(), size))
        fill_table(self.result_table, rows)
        self.status.setText(self.app.t(f'完成：共生成 {len(outputs)} 个文件'))
        self.app.statusBar().showMessage(self.app.t(f'完成：共生成 {len(outputs)} 个文件'))
        self.log_task(len(outputs))

    def log_task(self, produced):
        """Record counts only, matching the other task pages."""
        from core.task_log import record_task
        record_task(f'join:{self.current_mode()}', self.files.count(), produced, (),
                    directory=self.app.log_directory())

    # ---- layout --------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event); self._update_responsive_layout()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_responsive_layout(); QTimer.singleShot(0, self._update_responsive_layout)

    def _update_responsive_layout(self):
        if not getattr(self, '_layout_ready', False): return
        viewport = getattr(self, 'scroll', None)
        available = viewport.viewport().size() if viewport and viewport.viewport().width() > 100 else self.size()
        roomy = available.width() >= 900 and available.height() >= 600
        self._roomy = roomy; self.setMaximumHeight(16777215)
        self.files.setFixedHeight(170 if roomy else 28)
        for card in (self.source_card, self.mode_card, self.output_card, self.result_card):
            card.step_badge.setFixedSize(32, 32) if roomy else card.step_badge.setFixedSize(24, 24)
        for detail in (self.source_detail, self.mode_detail, self.output_detail, self.result_detail):
            detail.setVisible(roomy)
        self.tagline.hide()
