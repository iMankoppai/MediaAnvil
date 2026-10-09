"""TaskExecutionMixin: main-window behavior grouped by responsibility.

Uses the widgets and state initialized by MainWindow; owns no Qt object.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import replace
from copy import deepcopy
from PySide6.QtCore import Slot
from core.tasks import TaskHistory, TaskRecord
from .workers import Worker
from .table_widgets import fill_table
from .task_queue import QueuedTask


class TaskExecutionMixin:
    def run_task(self,work,done):
        if self._worker or self._importing:return self.inform(self.t('当前任务仍在处理，请等待完成。'))
        self._done=done;self._task_outcome=None;self._worker=Worker(work,self)
        self.progress.setRange(0,100);self.progress.setValue(0);self.progress.show();self.cancel_button.setEnabled(True);self.cancel_button.show();self.statusBar().showMessage(self.t('正在处理…'))
        self._worker.result.connect(self._result);self._worker.error.connect(self._error);self._worker.cancelled.connect(self._cancelled);self._worker.progress.connect(self._progress);self._worker.checkpoint.connect(self.checkpoint_task);self._worker.finished.connect(self._finished);self._worker.start()

    def submit_task(self,kind,paths,parameters,work,done):
        """Capture a job now; start only when earlier work and imports finish."""
        if len(self.pending_tasks)>=20:
            self.inform(self.t('待执行任务已达 20 个，请稍后再添加。'));return None
        history=TaskHistory(kind,tuple(TaskRecord(Path(p),'排队') for p in paths),deepcopy(parameters))
        self.pending_tasks.append(QueuedTask(history.task_id,kind,work,done))
        self.store_task_history(history);self.update_queue_table()
        self.statusBar().showMessage(self.t('任务已加入队列'))
        if not self._worker and not self._importing and not self._finishing:self.start_next_task()
        return history.task_id

    def start_next_task(self):
        if not self.pending_tasks:return
        if self._worker or self._importing or self._finishing:
            self.queue_timer.start(100);return
        job=self.pending_tasks.pop(0)
        history=next((h for h in self.task_histories if h.task_id==job.task_id),None)
        if history:
            self.store_task_history(replace(history,records=tuple(replace(r,state='等待') for r in history.records)))
        self._active_task_id=job.task_id;self.update_queue_table()
        self.run_task(job.work,lambda result:job.done(result,job.task_id))

    def update_queue_table(self):
        names={'audio':'音频转换','image':'图片转换','subtitle':'歌词 / 字幕转换','rename':'批量重命名',
               'tags':'批量标签','matches':'关联文件写入','cover':'封面写入','shift':'歌词偏移','join':'音频合并 / 分割'}
        histories={h.task_id:h for h in self.task_histories}
        fill_table(self.queue_table,[(self.t(names.get(j.kind,j.kind)),len(histories[j.task_id].records) if j.task_id in histories else 0) for j in self.pending_tasks])

    def move_queued_task(self,direction):
        index=self.queue_table.currentRow();target=index+direction
        if 0<=index<len(self.pending_tasks) and 0<=target<len(self.pending_tasks):
            self.pending_tasks[index],self.pending_tasks[target]=self.pending_tasks[target],self.pending_tasks[index]
            self.update_queue_table();self.queue_table.selectRow(target)

    def cancel_queued_task(self):
        index=self.queue_table.currentRow()
        if not 0<=index<len(self.pending_tasks):return
        job=self.pending_tasks.pop(index)
        history=next((h for h in self.task_histories if h.task_id==job.task_id),None)
        if history:self.store_task_history(replace(history,records=tuple(replace(r,state='已取消') for r in history.records)))
        self.update_queue_table()

    def cancel_task(self):
        if not self._worker:return
        self.cancel_button.setEnabled(False);self.statusBar().showMessage(self.t('正在取消…'));self._worker.request_cancel()

    @Slot(object)
    def _result(self,value):self._task_outcome=(True,value)

    @Slot(str)
    def _error(self,value):self._task_outcome=(False,value)

    @Slot()
    def _cancelled(self):
        self._task_outcome=(None,None);self.finish_pending_records('已取消')

    @Slot(float,str)
    def _progress(self,percent,text):self.progress.setValue(round(percent));self.statusBar().showMessage(self.t(text))

    @Slot()
    def _finished(self):
        self._finishing=True
        worker=self._worker;done=self._done;outcome=self._task_outcome
        self._worker=None;self._done=None;worker.deleteLater();self.progress.hide();self.cancel_button.hide();self.statusBar().showMessage(self.t('任务已取消') if outcome and outcome[0] is None else self.t('就绪'))
        if outcome:
            if outcome[0] is True:
                try:done(outcome[1])
                except Exception as exc:self.inform(self.t('结果显示失败：')+str(exc))
            elif outcome[0] is False:
                if self.task_checkpoints:self.flush_task_updates()
                history=next((h for h in self.task_histories if h.task_id==self._active_task_id),None)
                if history:self.store_task_history(replace(history,records=tuple(replace(r,state='失败',message=outcome[1]) if r.state in ('等待','处理中') else r for r in history.records)))
                self.inform(self.t('处理失败：')+outcome[1])
        self.finish_pending_records('已完成' if outcome and outcome[0] is True else '已中断')
        history=next((h for h in self.task_histories if h.task_id==self._active_task_id),None)
        if history and getattr(self,'organizer',None):self.organizer.follow_outputs(history)
        self._active_task_id=None
        if outcome and outcome[0] is not True:self.pages['renamer'].restore_recovery()
        self._finishing=False
        if self.pending_tasks:self.queue_timer.start(0)

