"""FileImportMixin: main-window behavior grouped by responsibility.

Uses the widgets and state initialized by MainWindow; owns no Qt object.
"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QFileDialog
from core.media_matcher import AUDIO_EXTENSIONS, LYRIC_EXTENSIONS, COVER_EXTENSIONS
from .file_dialogs import dialog_category, dialog_initial_directory, remember_dialog_selection
from .services import collect_paths, explain_rejected


class FileImportMixin:
    def load_file_selection(self,page,paths,done=lambda:None):
        self._importing=True;page.setEnabled(False)
        def loaded(count):
            self._importing=False;page.setEnabled(True);done()
            if self.pending_tasks:self.queue_timer.start(0)
        page.files.add_paths_batched(paths,loaded)

    def choose_folder_for(self,page):
        category=dialog_category(getattr(page,'kind','audio'))
        folder=QFileDialog.getExistingDirectory(self,self.t('选择文件夹'),dialog_initial_directory(self,category))
        if folder:
            remember_dialog_selection(self,category,folder);self.import_paths([Path(folder)],page)

    def import_paths(self,paths,page=None):
        page=page or self.current_page
        if not hasattr(page,'receive'):return
        extensions=page.files.extensions if hasattr(page,'files') else AUDIO_EXTENSIONS|LYRIC_EXTENSIONS|COVER_EXTENSIONS
        recursive=page.include_subfolders.isChecked() if hasattr(page,'include_subfolders') else self.settings['include_subfolders']
        def done(found):
            if hasattr(page,'files') and len(found)>500:
                self._importing=True;page.setEnabled(False)
                def loaded(count):
                    self._importing=False;page.setEnabled(True)
                    self.statusBar().showMessage(self.t(f'已导入 {count} 个文件'))
                page.files.add_paths_batched(found,loaded);return
            count=page.receive(found)
            if not count:self.inform(self.import_failure_reason(paths,extensions,recursive))
            elif self._worker is None:self.statusBar().showMessage(self.t(f'已导入 {count} 个文件'))
        self.run_task(lambda report:collect_paths(paths,extensions,recursive,report.raise_if_cancelled),done)

    def import_failure_reason(self,paths,extensions,recursive):
        """Explain why an import produced nothing instead of a bare 'not found'."""
        detail=explain_rejected(paths,extensions,recursive)
        supported=' '.join('*'+value for value in sorted(extensions))
        if detail['empty']:
            return self.t('没有找到当前页面支持的文件。')
        if detail['missing'] and not detail['unsupported']:
            return self.t('文件不存在或无法访问：')+', '.join(detail['missing'][:3])
        unsupported=', '.join(f'{key} × {count}' for key,count in sorted(detail['unsupported'].items()))
        if unsupported:
            return self.t('没有找到当前页面支持的文件。')+'\n'+self.t('不支持的格式：')+unsupported+'\n'+self.t('当前支持：')+supported
        return self.t('没有找到当前页面支持的文件。')

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):event.acceptProposedAction()
        else:event.ignore()

    def dropEvent(self,event):
        paths=[Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.import_paths(paths);event.acceptProposedAction()

