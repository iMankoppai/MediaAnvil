"""TaskHistoryMixin: main-window behavior grouped by responsibility.

Uses the widgets and state initialized by MainWindow; owns no Qt object.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import replace
from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileDialog
from core.tasks import TaskHistory, TaskRecord, save_task_histories
from .table_widgets import fill_table
from .file_dialogs import dialog_initial_directory, remember_dialog_selection
from .i18n import tr


class TaskHistoryMixin:
    def persist_task_histories(self):
        try:save_task_histories(self.task_history_file,self.task_histories)
        except (OSError,ValueError) as exc:self.statusBar().showMessage(self.t('任务记录未能保存：')+str(exc))

    def flush_task_updates(self):
        updates=self.task_checkpoints;self.task_checkpoints={}
        if updates:
            histories=[]
            for history in self.task_histories:
                records=updates.get(history.task_id)
                if records:
                    known={r.source for r in history.records}
                    history=replace(history,records=tuple(records.get(r.source,r) for r in history.records)+tuple(r for p,r in records.items() if p not in known))
                    if self.task_history and self.task_history.task_id==history.task_id:self.task_history=history
                histories.append(history)
            self.task_histories=histories
        self.persist_task_histories();self.update_task_page()

    def store_task_history(self,history,immediate=True):
        self.task_histories=[history if h.task_id==history.task_id else h for h in self.task_histories]
        if not any(h.task_id==history.task_id for h in self.task_histories):self.task_histories.append(history)
        protected={j.task_id for j in self.pending_tasks}|{self._active_task_id}
        finished=[h.task_id for h in self.task_histories if h.task_id not in protected][-20:]
        self.task_histories=[h for h in self.task_histories if h.task_id in protected or h.task_id in finished];self.task_history=history
        if immediate:
            self.task_flush_timer.stop();self.flush_task_updates()
        elif not self.task_flush_timer.isActive():self.task_flush_timer.start()

    def begin_task_history(self,kind,paths,parameters):
        history=TaskHistory(kind,tuple(TaskRecord(Path(p),'等待') for p in paths),dict(parameters))
        self._active_task_id=history.task_id;self.store_task_history(history);return history.task_id

    @Slot(object)
    def checkpoint_task(self,record):
        if self._active_task_id:
            self.task_checkpoints.setdefault(self._active_task_id,{})[record.source]=record
            if not self.task_flush_timer.isActive():self.task_flush_timer.start()

    def finish_pending_records(self,state):
        if self.task_checkpoints:self.flush_task_updates()
        history=next((h for h in self.task_histories if h.task_id==self._active_task_id),None)
        if history and any(r.state in ('等待','处理中') for r in history.records):
            self.store_task_history(replace(history,records=tuple(replace(r,state=state) if r.state in ('等待','处理中') else r for r in history.records)))

    def record_task_history(self,kind,records,parameters=None,task_id=None):
        history=next((h for h in self.task_histories if h.task_id==task_id),None)
        self.store_task_history(replace(history,records=tuple(records)) if history else TaskHistory(kind,tuple(records),dict(parameters or {})))

    def select_task_history(self,index):
        task_id=self.task_picker.itemData(index)
        self.task_history=next((h for h in self.task_histories if h.task_id==task_id),None)
        self.task_page_number.blockSignals(True);self.task_page_number.setValue(1);self.task_page_number.blockSignals(False);self.update_task_page()

    def update_task_page(self,*args):
        history=self.task_history
        self.task_picker.blockSignals(True);self.task_picker.clear()
        names={'audio':'音频转换','image':'图片转换','subtitle':'歌词 / 字幕转换','rename':'批量重命名','preview':'预览修改',
               'tags':'批量标签','matches':'关联文件写入','cover':'封面写入','shift':'歌词偏移','join':'音频合并 / 分割','inspect':'媒体检查','report':'处理报告'}
        for h in reversed(self.task_histories):self.task_picker.addItem(h.created_at.replace('T',' ')+' · '+self.t(names.get(h.kind,h.kind)),h.task_id)
        self.task_picker._i18n_items=[self.task_picker.itemText(i) for i in range(self.task_picker.count())]
        if history:self.task_picker.setCurrentIndex(self.task_picker.findData(history.task_id))
        self.task_picker.blockSignals(False)
        if not history:
            self.task_kind.setText(self.t('暂无批量任务'));self.task_summary.setText(self.t('转换和重命名完成后，这里会显示每个文件的状态。'))
            self.task_table.setRowCount(0);self.task_retry.setEnabled(False);return
        kind=self.t(names.get(history.kind,history.kind))
        self.task_kind.setText(self.t('最近任务：')+kind)
        failed=len(history.failures)
        self.task_summary.setText(self.t(f'成功 {len(history.succeeded)} 个 · 失败 {failed} 个 · 未完成 {len(history.records)-len(history.succeeded)-failed} 个 · 时间 {history.created_at.replace("T"," ")}'))
        self.task_page_number.blockSignals(True);self.task_page_number.setMaximum(max(1,(len(history.records)+249)//250));self.task_page_number.blockSignals(False)
        self.task_page_number.setVisible(len(history.records)>250);self.task_page_number.setToolTip(self.t('页码'))
        start=(self.task_page_number.value()-1)*250;records=history.records[start:start+250]
        fill_table(self.task_table,[(r.source.name,self.t(r.state),self.t(r.message or '—'),str(r.output or '—')) for r in records])
        for row,record in enumerate(records):
            item=self.task_table.item(row,1)
            item.setForeground(QColor('#178858' if record.state=='已完成' else '#df5265' if record.failed else '#c77736'))
            item.setToolTip(self.t(record.message))
        self.task_retry.setEnabled(bool(history.retryable) and history.kind in ('audio','image','subtitle','rename','tags','matches','cover','shift','join'))

    def retry_failed(self):
        history=self.task_history
        if not history or not history.retryable:return self.inform(self.t('没有可重试的失败项。'))
        sources=[record.source for record in history.retryable]
        if history.kind in ('audio','image','subtitle'):self.pages[history.kind].convert_paths(sources,history.parameters or None)
        elif history.kind=='rename':
            page=self.pages['renamer'];page.apply_preset(history.parameters)
            if all(r.output for r in history.retryable):
                from core.audio_renamer import RenamePlan,RenamePlanItem,RenameRecord
                retry={r.source:r for r in history.retryable};related={};children=set()
                for entry in history.parameters.get('rename_plan',[]):
                    try:
                        source=Path(entry['source'])
                        if source not in retry:continue
                        companions=tuple(RenameRecord(Path(old),Path(new)) for old,new in entry.get('related',[]) if Path(old) in retry)
                        related[source]=companions;children.update(r.old_path for r in companions)
                    except (TypeError,ValueError,KeyError):continue
                plan=RenamePlan(tuple(RenamePlanItem(r.source,r.source.name,r.output,r.output.name,'可重命名',related=related.get(r.source,())) for r in history.retryable if r.source not in children),page.template.currentText(),page.fallback.isChecked())
                page.previewed(plan)
            else:page.files.clear();page.files.add_paths(sources);page.preview()
            self.navigation.setCurrentRow(self.keys.index('renamer'))
        elif history.kind in ('tags','matches','cover','shift'):self.pages['editor'].retry_batch(history)
        elif history.kind=='join':self.pages['join'].submit_parameters(sources,history.parameters)
        else:return self.inform(self.t('当前任务类型不支持重试。'))

    def open_task_output(self):
        if not self.task_history:return
        directories=dict.fromkeys(r.output.parent for r in self.task_history.succeeded if r.output)
        for directory in directories:self.open_path(directory)

    def check_task_outputs(self):
        if not self.task_history:return
        from core.task_reports import verify_outputs
        history=self.task_history
        paths=tuple(dict.fromkeys(r.output for r in history.succeeded if r.output))
        if not paths:return self.inform(self.t('当前任务没有可检查的结果。'))
        def done(records,task_id):
            self.record_task_history('inspect',records,task_id=task_id)
            self.show_text('结果检查','\n'.join(str(r.source)+' — '+self.t(r.state)+'：'+self.t(r.message) for r in records))
        self.submit_task('inspect',paths,{},lambda report:verify_outputs(history,report.raise_if_cancelled),done)

    def export_task_report(self):
        if not self.task_history:return
        from core.task_reports import export_report
        history=self.task_history
        path,_=QFileDialog.getSaveFileName(self,self.t('导出处理报告'),str(Path(dialog_initial_directory(self,'output'))/'MediaAnvil-report.csv'),'CSV (*.csv)')
        if path:
            remember_dialog_selection(self,'output',path)
            language=self.settings['language']
            self.submit_task('report',[],{},lambda report:export_report(history,path,lambda v:tr(v,language)),
                             lambda result,task_id:self.statusBar().showMessage(self.t('报告已导出：')+str(result)))

