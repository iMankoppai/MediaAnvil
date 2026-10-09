from dataclasses import replace
import csv
from core.tasks import TaskRecord
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox,QLineEdit,QLabel,QFileDialog,QHeaderView,QPushButton,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QSizePolicy
from .common import Page, FileList, button, row, combo, table, fill_table, StatusDelegate, Columns, dialog_initial_directory, remember_dialog_selection
from .conversion import step_group
from .design import icon
from core.audio_renamer import SUPPORTED_RENAME_EXTENSIONS,build_rename_plan,execute_rename_plan,undo_rename
from core.rename_history import RenameJournal


class RenamePage(Page):
    def __init__(self,app):
        super().__init__(app,'批量重命名','使用音频标签生成文件名；预览冲突后执行，可撤销最近一次重命名。')
        self.plan=None;self.journal=RenameJournal(app.settings_file.parent/'rename-history.json');self.records=self.journal.records()
        self.tagline=QLabel('批量处理 · 让文件命更规范  —');self.tagline.setObjectName('muted');self.tagline.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter);self.header_layout.addWidget(self.tagline)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(0,0,0,0);left_layout.setSpacing(10)
        source,source_layout,self.source_detail=step_group(1,'选择文件','支持读取音频标签信息（MP3、FLAC、M4A、WAV 等）');left_layout.addWidget(source)
        self.files=FileList(SUPPORTED_RENAME_EXTENSIONS);self.files.setMinimumHeight(0);self.files.setFixedHeight(28)
        self.files.empty_kind='rename';self.files.empty_title='点击添加文件 或 拖拽文件到此处';self.files.empty_hint='支持 MP3、FLAC、M4A、WAV 等音频文件'
        self.files.setStyleSheet('QListWidget { border:1px dashed #b9d4ff;border-radius:10px;background:#fbfdff; }')
        self.toolbar=self.file_toolbar(self.files);self.toolbar.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);toolbar_buttons=self.toolbar.findChildren(QPushButton)
        folder_button=toolbar_buttons.pop(1);self.toolbar.layout().removeWidget(folder_button);folder_button.setParent(None);folder_button.deleteLater()
        self.file_count=self.toolbar.count_label;self.toolbar.layout().removeWidget(self.file_count);self.toolbar.layout().takeAt(self.toolbar.layout().count()-1)
        for control,text,tip,symbol in zip(toolbar_buttons,('添加…','移除','清空'),('添加文件','移除已勾选的文件','清空文件列表'),('file','trash','trash')):
            control.setText(text);control.setToolTip(tip);control.setIcon(icon(symbol,'#df5265' if text=='清空' else '#397bf3',18));control.setIconSize(QSize(18,18));control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        for index in range(3):self.toolbar.layout().setStretch(index,1)
        source_layout.addWidget(self.toolbar);source_layout.addWidget(self.files,1)
        self.select_files=QCheckBox('全选文件');self.select_files.setChecked(True);self.select_files.toggled.connect(self.check_files)
        self.selection_row=QWidget();selection_layout=QHBoxLayout(self.selection_row);selection_layout.setContentsMargins(0,0,0,0);selection_layout.addWidget(self.select_files);selection_layout.addStretch();selection_layout.addWidget(self.file_count);source_layout.addWidget(self.selection_row)
        self.undo_button=button('撤销上次重命名',self.undo);self.undo_button.setEnabled(bool(self.records))
        rules,rules_layout,self.rules_detail=step_group(2,'重命名规则','设置文件名模板，使用下方变量快速插入');left_layout.addWidget(rules,1)
        fields=QFormLayout();fields.setContentsMargins(0,0,0,0);fields.setVerticalSpacing(8);fields.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow);rules_layout.addLayout(fields)
        self.template=combo(['{artist} - {title}','{track} - {title}','{album} - {track} - {title}','{year} - {artist} - {title}','{genre} - {title}']);self.template.setEditable(True);self.template.setMaximumWidth(16777215)
        fields.addRow('重命名模板',self.template)
        chips=[]
        for variable in ('{artist}','{title}','{album}','{track}','{year}','{genre}'):
            chip=button(variable,lambda checked=False,value=variable:self.template.lineEdit().insert(value));chip.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);chips.append(chip)
        self.chips_row=row(*chips);self.chips_row.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);rules_layout.addWidget(self.chips_row)
        self.fallback=QCheckBox('缺少字段时使用原文件名代替')
        self.include_subfolders=QCheckBox('包含子文件夹');self.include_subfolders.setChecked(app.settings['include_subfolders'])
        rules_layout.addWidget(self.fallback);rules_layout.addWidget(self.include_subfolders)
        preview,preview_layout,self.preview_detail=step_group(3,'预览结果','预览结果会根据规则自动更新')
        self.preview_button=button('',self.preview,symbol='convert');self.preview_button.setToolTip('刷新预览');preview.step_header.addWidget(self.preview_button,0,Qt.AlignmentFlag.AlignTop)
        self.search=QLineEdit();self.search.setPlaceholderText('搜索文件名…');self.search.setMaximumWidth(270);self.search.textChanged.connect(self.filter_rows)
        self.all_rows=QCheckBox('全选可重命名项');self.all_rows.setChecked(True);self.all_rows.toggled.connect(self.check_rows)
        self.count_label=QLabel('添加文件后，点击刷新预览');self.count_label.setObjectName('muted')
        self.preview_controls=row(self.all_rows,self.count_label,self.search);self.preview_controls.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);preview_layout.addWidget(self.preview_controls)
        self.table=table(['选择','#','原文件名','新文件名','状态'],virtual=True);self.table.setMinimumHeight(280)
        self.table.setItemDelegateForColumn(4,StatusDelegate(self.table))
        for col in (0,1,4):self.table.horizontalHeader().setSectionResizeMode(col,QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self.update_selection);preview_layout.addWidget(self.table,1)
        self.execute_button=button('开始重命名',self.execute,True,'play');self.execute_button.setEnabled(False)
        self.export_button=button('导出预览',self.export_preview,symbol='upload')
        actions=QWidget();actions.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);actions_layout=QHBoxLayout(actions);actions_layout.setContentsMargins(0,0,0,0);actions_layout.addWidget(self.undo_button);actions_layout.addStretch();actions_layout.addWidget(self.export_button);actions_layout.addWidget(self.execute_button);preview_layout.addWidget(actions)
        self.step_cards=(source,rules,preview);self.columns=Columns(left,preview,700);self.layout.addWidget(self.columns,1)
        self.files.filesChanged.connect(self.invalidate);self.template.currentTextChanged.connect(self.invalidate);self.fallback.toggled.connect(self.invalidate)
        from .tool_layouts import rename_layout
        rename_layout(self)
        self._layout_ready=True
    def current_preset_state(self):
        return {'kind':'rename','template':self.template.currentText(),'fallback_missing':self.fallback.isChecked()}
    def apply_preset(self,fields):
        if fields.get('template'):self.template.setCurrentText(fields['template'])
        if 'fallback_missing' in fields:self.fallback.setChecked(bool(fields['fallback_missing']))
    def receive(self,paths):return self.files.add_paths(paths)
    def check_files(self,checked):
        for i in range(self.files.count()):self.files.item(i).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    def remove_selected(self):
        selected={self.table.source_row(index.row()) for index in self.table.selectionModel().selectedRows()}
        remaining=[path for i,path in enumerate(self.files.paths()) if i not in selected]
        self.files.clear();self.files.add_paths(remaining)
    def invalidate(self,*args):
        self.plan=None;self.execute_button.setEnabled(False)
        fill_table(self.table,[('',i+1,p.name,'—',self.app.t('待预览')) for i,p in enumerate(self.files.paths())])
        self.count_label.setText(self.app.t(f'{self.files.count()} 个文件 · 点击刷新预览'));self.filter_rows()
    def filter_rows(self,*args):
        query=self.search.text().strip().casefold()
        for i in range(self.table.rowCount()):
            text=' '.join(self.table.item(i,c).text() for c in (2,3))
            self.table.setRowHidden(i,query not in text.casefold())
        self.table.commit_filter()
    def check_rows(self,checked):
        blocked=self.table.signalsBlocked();self.table.blockSignals(True);self.table.setUpdatesEnabled(False)
        try:
            for i in range(self.table.rowCount()):
                item=self.table.item(i,0)
                if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        finally:self.table.blockSignals(blocked);self.table.setUpdatesEnabled(True)
        self.update_selection()
    def selected_items(self):
        if not self.plan:return ()
        return tuple(item for i,item in enumerate(self.plan.items) if item.can_rename and self.table.item(i,0).checkState()==Qt.CheckState.Checked)
    def update_selection(self,*args):
        count=len(self.selected_items());self.execute_button.setEnabled(count>0)
        if self.plan:self.count_label.setText(self.app.t(f'{len(self.plan.items)} 项 · 已勾选 {count} 项'))
    def export_preview(self):
        if not self.plan:return self.app.inform(self.app.t('请先生成预览。'))
        default_name='rename-preview.csv' if self.app.settings.get('language')=='en_US' else '重命名预览.csv'
        default_path=str(Path(dialog_initial_directory(self,'output'))/default_name)
        path,_=QFileDialog.getSaveFileName(self,self.app.t('导出重命名预览'),default_path,'CSV (*.csv)')
        if path:
            remember_dialog_selection(self,'output',path)
            rows=[(i.source,i.original_name,i.new_name,i.status,i.message,i in self.selected_items()) for i in self.plan.items]
            def work(report):
                with open(path,'w',encoding='utf-8-sig',newline='') as stream:
                    writer=csv.writer(stream);writer.writerow([self.app.t(value) for value in ('路径','原文件名','新文件名','状态','说明','已勾选')]);writer.writerows(rows)
                return path
            self.app.run_task(work,lambda p:self.app.statusBar().showMessage(self.app.t('预览已导出：'+str(p))))
    def preview(self):
        paths=self.files.checked_paths();template=self.template.currentText();fallback=self.fallback.isChecked()
        if not paths:return self.app.inform(self.app.t('请先添加音频。'))
        def done(plan,task_id):
            if paths!=self.files.checked_paths() or template!=self.template.currentText() or fallback!=self.fallback.isChecked():
                self.app.statusBar().showMessage(self.app.t('文件或规则已变化，请重新预览。'));return
            self.previewed(plan)
        self.app.submit_task('preview',paths,self.current_preset_state(),
            lambda report:build_rename_plan(paths,template,fallback_missing=fallback,cancel_check=report.raise_if_cancelled),done)
    def previewed(self,plan):
        self.table.blockSignals(True)
        fill_table(self.table,[('',n+1,i.original_name,i.new_name,self.app.t(i.status)) for n,i in enumerate(plan.items)])
        self.plan=plan
        for n,item in enumerate(plan.items):
            check=self.table.item(n,0)
            if item.can_rename:check.setCheckState(Qt.CheckState.Checked if self.all_rows.isChecked() else Qt.CheckState.Unchecked)
            else:check.setFlags(Qt.ItemFlag.NoItemFlags)
            status=self.table.item(n,4);status.setForeground(QColor('#169763' if item.can_rename else '#c88032'));status.setToolTip(self.app.t(item.message))
        self.table.blockSignals(False);self.update_selection();self.filter_rows()
    def execute(self):
        if not self.plan:return
        selected=self.selected_items()
        if not selected:return
        plan=replace(self.plan,items=selected)
        parameters=self.current_preset_state()
        parameters['rename_plan']=[{'source':str(i.source),'target':str(i.target),
            'related':[(str(r.old_path),str(r.new_path)) for r in i.related]} for i in selected]
        targets={i.source:i.target for i in selected}
        targets.update({r.old_path:r.new_path for i in selected for r in i.related})
        def work(report):
            self.journal.begin()
            try:
                return execute_rename_plan(plan,cancel_check=report.raise_if_cancelled,before_move=self.journal.prepare,
                    after_move=lambda r:report.checkpoint(TaskRecord(r.old_path,'已完成',output=r.new_path)))
            finally:self.journal.finish()
        task_id=self.app.submit_task('rename',targets,parameters,work,
            lambda result,task_id:self.executed(result,parameters,task_id,targets))
        if task_id is None:return
        history=next(h for h in self.app.task_histories if h.task_id==task_id)
        self.app.store_task_history(replace(history,records=tuple(replace(r,output=targets[r.source]) for r in history.records)))
    def executed(self,result,parameters=None,task_id=None,targets=None):
        targets=targets if targets is not None else getattr(self,'_rename_targets',{})
        self.restore_recovery()
        records=[TaskRecord(item.source,'跳过',item.message) for item in getattr(result,'skipped',())]
        records += [TaskRecord(f.source,'失败',f.message,targets.get(f.source)) for f in result.failures]
        records += [TaskRecord(r.old_path,'已完成',output=r.new_path) for r in result.records+result.related_records if r.old_path not in {record.source for record in records}]
        recorded={r.source for r in records}
        records += [TaskRecord(p,'已中断','主音频未完成，关联文件未处理',t) for p,t in targets.items() if p not in recorded]
        self.app.record_task_history('rename',records,parameters,task_id)
        self.undo_button.setEnabled(bool(self.records))
        paths={r.old_path:r.new_path for r in result.records};current=[paths.get(p,p) for p in self.files.paths()]
        self.files.clear();self.files.add_paths(current);self.invalidate()
        self.app.show_text('重命名结果','\n'.join([f'完成：{r.old_path.name} → {r.new_path.name}' for r in result.records]+[f'完成：{r.old_path.name} → {r.new_path.name}' for r in result.related_records]+[f'跳过：{i.original_name} — {i.message or i.status}' for i in result.skipped]+[f'失败：{i.source.name} — {i.message}' for i in result.failures]))
    def undo(self):
        records=self.records
        if records:
            identities=self.journal.identities()
            self.app.run_task(lambda report:undo_rename(records,report.raise_if_cancelled,identities,self.journal.restored),self.undone)
    def restore_recovery(self):
        self.records=self.journal.records();self.undo_button.setEnabled(bool(self.records))
    def undone(self,result):
        self.restore_recovery()
        if getattr(self.app,'organizer',None):
            from core.tasks import TaskHistory
            self.app.organizer.follow_outputs(TaskHistory('rename',tuple(TaskRecord(r.new_path,'已完成',output=r.old_path) for r in result.records)))
        mapping={r.new_path:r.old_path for r in result.records};paths=[mapping.get(p,p) for p in self.files.paths()]
        self.files.clear();self.files.add_paths(paths);self.invalidate()
        self.app.show_text('撤销结果','\n'.join([f'恢复：{r.old_path}' for r in result.records]+[f'失败：{f.source} — {f.message}' for f in result.failures]))
    def resizeEvent(self,event):
        super().resizeEvent(event);self._update_responsive_layout()
    def showEvent(self,event):
        super().showEvent(event);self._update_responsive_layout();QTimer.singleShot(0,self._update_responsive_layout)
    def _update_responsive_layout(self):
        if not getattr(self,'_layout_ready',False):return
        viewport=getattr(self,'scroll',None);available=viewport.viewport().size() if viewport and viewport.viewport().width()>100 else self.size()
        roomy=available.width()>=850 and available.height()>=700;self._roomy=roomy;self.setMaximumHeight(16777215)
        self.files.setFixedHeight(170 if roomy else 28)
        for card in self.step_cards:card.step_badge.setFixedSize(32,32) if roomy else card.step_badge.setFixedSize(24,24)
        for detail in (self.source_detail,self.rules_detail,self.preview_detail):detail.setVisible(roomy)
        self.tagline.hide()
        labels=('添加文件','移除','清空') if roomy else ('添加…','移除','清空')
        for control,text in zip(self.toolbar.findChildren(QPushButton),labels):control.setText(self.app.t(text))
        if not roomy:self._refresh_compact_height();QTimer.singleShot(0,self._refresh_compact_height)
    def _refresh_compact_height(self):
        if getattr(self,'_roomy',False):return
        self.layout.activate();self.setMaximumHeight(self.sizeHint().height())
