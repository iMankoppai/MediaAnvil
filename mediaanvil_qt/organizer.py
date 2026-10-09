"""A guided folder session reusing inspection, editing and rename pages."""
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QLabel
from .common import button, row, dialog_initial_directory, remember_dialog_selection
from .media_check import MediaCheckDialog
from .i18n import apply_language
from core.media_matcher import missing_media_check, check_audio_paths, match_audio_files, AUDIO_EXTENSIONS


class OrganizerDialog(MediaCheckDialog):
    def __init__(self,app):
        super().__init__(app)
        self.folder=None
        self.setWindowTitle('音乐整理流程')
        self.folder_label=QLabel('选择音乐文件夹，检查后勾选要整理的文件。');self.folder_label.setWordWrap(True)
        self.layout().insertWidget(0,self.folder_label)
        self.layout().insertWidget(1,row(button('1. 选择文件夹',self.choose_folder),
            button('2. 匹配歌词与封面',self.load_repairs),
            button('3. 预览标签修改',self.preview_tags),
            button('4. 预览重命名',self.load_rename)))
        self.repair.connect(lambda paths:self.load_repairs())
        self.edit.connect(self.edit_track)
        self.refresh.connect(self.recheck)
        apply_language(self,app.settings['language'])

    def choose_folder(self):
        folder=QFileDialog.getExistingDirectory(self,self.app.t('选择音乐文件夹'),dialog_initial_directory(self.app,'audio'))
        if folder:self.start_folder(Path(folder))

    def start_folder(self,folder):
        self.folder=Path(folder);remember_dialog_selection(self.app,'audio',folder)
        self.folder_label.setText(str(self.folder));self.selected.clear()
        recursive=self.app.settings['include_subfolders']
        self.app.submit_task('inspect',[],{'folder':str(folder)},
            lambda report:missing_media_check(folder,include_subfolders=recursive,cancel_check=report.raise_if_cancelled),
            lambda rows,task_id:self.inspected(rows))

    def inspected(self,rows):
        self.filter.setCurrentIndex(self.filter.findData('all'))
        self.set_rows(rows);self.selected.update(r.audio for r in rows);self.render_page()
        self.show();self.raise_();self.app.organizer_return.show()

    def paths(self):
        paths=self.selected_paths()
        if not paths:self.app.inform(self.app.t('请先勾选要整理的文件。'))
        return paths

    def load_repairs(self,preview=False):
        paths=self.paths()
        if not paths:return
        def done(matches,task_id):
            page=self.app.pages['editor'];page.scanned(matches)
            self.app.navigation.setCurrentRow(self.app.keys.index('editor'));page.reveal_match_area();self.hide()
            if preview:page.preview_batch_tags()
        self.app.submit_task('inspect',paths,{},lambda report:match_audio_files(paths,report.raise_if_cancelled),done)

    def preview_tags(self):self.load_repairs(preview=True)

    def load_rename(self):
        paths=self.paths()
        if not paths:return
        page=self.app.pages['renamer'];page.files.clear()
        self.app.navigation.setCurrentRow(self.app.keys.index('renamer'));self.hide()
        self.app.load_file_selection(page,paths,page.preview)

    def edit_track(self,path):
        self.hide();self.app.navigation.setCurrentRow(self.app.keys.index('editor'))
        self.app.pages['editor'].receive([path])

    def recheck(self):
        paths=tuple(r.audio for r in self.rows)
        if not paths:
            if self.folder:self.start_folder(self.folder)
            return
        selected=set(self.selected)
        def done(rows,task_id):
            self.set_rows(rows);self.selected=selected & {r.audio for r in rows};self.render_page();self.show()
        self.app.submit_task('inspect',paths,{},lambda report:check_audio_paths(paths,cancel_check=report.raise_if_cancelled),done)

    def follow_outputs(self,history):
        if history.kind not in ('tags','matches','cover','shift','rename'):return
        mapping={r.source:r.output for r in history.succeeded if r.output and r.output.suffix.lower() in AUDIO_EXTENSIONS}
        from dataclasses import replace
        self.rows=[replace(r,audio=mapping.get(r.audio,r.audio)) for r in self.rows]
        self.selected={mapping.get(p,p) for p in self.selected}
        self.set_rows(self.rows)
