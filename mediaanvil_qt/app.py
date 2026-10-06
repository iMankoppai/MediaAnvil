"""Qt native window shell. Media work never runs in the GUI event loop."""
from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,Slot,QSize,QTimer
from PySide6.QtGui import QIcon,QDesktopServices
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,
    QStackedWidget,QScrollArea,QProgressBar,QMessageBox,QDialog,QPlainTextEdit,
    QDialogButtonBox,QFileDialog,QHeaderView)
from core.settings import load_settings,settings_path,save_settings,last_load_warning
from core.media_matcher import AUDIO_EXTENSIONS,LYRIC_EXTENSIONS,COVER_EXTENSIONS
from core.tasks import TaskHistory
from datetime import datetime
from .common import resource,Worker,Page,button,group,table,fill_table,combo,dialog_category,dialog_initial_directory,remember_dialog_selection
from .design import Navigation, STYLE
from .documents import DocumentViewer
from .conversion import ConversionPage
from .join import JoinPage
from .preview import PreviewPage
from .metadata import MetadataPage
from .rename import RenamePage
from .settings import SettingsPage
from .services import collect_paths, explain_rejected
from .i18n import apply_language, localize_dialog_buttons, tr
from . import __version__


DEFAULT_WINDOW_OUTER_PIXELS = QSize(1440, 960)
DEFAULT_WINDOW_MINIMUM = QSize(760, 480)
# Keep a small margin so the frame never sits flush against a screen edge. The
# designed 1440x960 needs 94.1% of a 1080p desktop's usable height, so a 90%
# allowance would shrink it on the very displays it targets.
SCREEN_SAFETY_FRACTION = 0.95


def default_window_size(available: QSize | None = None, frame_height: int = 30, device_pixel_ratio: float | None = None) -> tuple[int, int]:
    """Use a 1440×960 (3:2) outer size, scaling down proportionally when needed."""
    if available is None:
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry().size() if screen else DEFAULT_WINDOW_OUTER_PIXELS
        if device_pixel_ratio is None and screen:device_pixel_ratio = screen.devicePixelRatio()
    scale = device_pixel_ratio or 1.0
    target_width = DEFAULT_WINDOW_OUTER_PIXELS.width() / scale
    target_outer_height = DEFAULT_WINDOW_OUTER_PIXELS.height() / scale
    factor = min(1.0, round(available.width() * SCREEN_SAFETY_FRACTION) / target_width,
                 round(available.height() * SCREEN_SAFETY_FRACTION) / target_outer_height)
    width = max(DEFAULT_WINDOW_MINIMUM.width(), round(target_width * factor))
    outer_height = max(DEFAULT_WINDOW_MINIMUM.height() + frame_height, round(target_outer_height * factor))
    return width, outer_height - frame_height


class MainWindow(QMainWindow):
    def __init__(self,config_path=None):
        super().__init__();self.setWindowTitle('MediaAnvil Qt — 多媒体工具箱');self.setMinimumSize(DEFAULT_WINDOW_MINIMUM);self.winId()
        margins=self.windowHandle().frameMargins() if self.windowHandle() else None
        frame_height=(margins.top()+margins.bottom()) if margins else 30
        screen=QApplication.primaryScreen()
        self.resize(*default_window_size(frame_height=frame_height,device_pixel_ratio=screen.devicePixelRatio() if screen else None))
        self.setWindowIcon(QIcon(str(resource('assets/mediaanvil-icon.png'))))
        # settings_path() already points at the MediaAnvilQt folder, so the
        # caller no longer rebuilds the path from its parts.
        self.settings_file=Path(config_path) if config_path else settings_path()
        self.settings=load_settings(self.settings_file);warning=last_load_warning()
        self._worker=None;self._task_outcome=None;self._done=None;self.task_history:TaskHistory|None=None
        central=QWidget();central.setObjectName('shell');layout=QHBoxLayout(central);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0);self.setCentralWidget(central)
        sidebar=QWidget();self.sidebar=sidebar;sidebar.setObjectName('sidebar');sidebar.setFixedWidth(204);left=QVBoxLayout(sidebar);left.setContentsMargins(14,10,8,14);left.setSpacing(20)
        brand_row=QHBoxLayout();brand_row.setContentsMargins(8,0,0,6);brand_row.setSpacing(10)
        logo=QLabel();logo.setPixmap(self.windowIcon().pixmap(34,34));brand_row.addWidget(logo)
        brand_text=QVBoxLayout();brand_text.setSpacing(1)
        brand=QLabel('MediaAnvil');brand.setObjectName('brand');brand_text.addWidget(brand)
        version=QLabel(f'v{__version__}');version.setObjectName('version');brand_text.addWidget(version)
        brand_row.addLayout(brand_text);brand_row.addStretch();left.addLayout(brand_row)
        self.navigation=Navigation();left.addWidget(self.navigation,1)
        layout.addWidget(sidebar);self.stack=QStackedWidget();layout.addWidget(self.stack,1)
        self.pages={
            'preview':PreviewPage(self), 'editor':MetadataPage(self),
            'subtitle':ConversionPage(self,'subtitle'), 'audio':ConversionPage(self,'audio'),
            'image':ConversionPage(self,'image'), 'join':JoinPage(self),
            'renamer':RenamePage(self), 'settings':SettingsPage(self),
        }
        task_page=Page(self,'任务中心','查看批量任务状态，失败项可单独重试')
        task_card,task_body=group('最近任务')
        self.task_kind=QLabel('暂无批量任务');self.task_kind.setObjectName('sectionTitle');task_body.addWidget(self.task_kind)
        self.task_summary=QLabel('转换和重命名完成后，这里会显示每个文件的状态。');self.task_summary.setObjectName('muted');self.task_summary.setWordWrap(True);task_body.addWidget(self.task_summary)
        self.task_retry=button('重试失败项',self.retry_failed,'task');self.task_retry.setEnabled(False);task_body.addWidget(self.task_retry,0,Qt.AlignmentFlag.AlignLeft)
        self.task_table=table(['文件','状态','说明']);self.task_table.setMinimumHeight(320)
        self.task_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for col in (1,2):self.task_table.horizontalHeader().setSectionResizeMode(col,QHeaderView.ResizeMode.ResizeToContents)
        task_body.addWidget(self.task_table,1)
        task_page.layout.addWidget(task_card);task_page.layout.addStretch()
        self.pages['tasks']=task_page
        about=Page(self,'关于 MediaAnvil','让日常媒体整理更轻松')
        card,body=group(f'MediaAnvil  ·  v{__version__}');about.layout.addWidget(card)
        artwork=QLabel();artwork.setPixmap(self.windowIcon().pixmap(76,76));body.addWidget(artwork)
        text=QLabel('一个简洁、离线的多媒体工具箱。\n\n播放音频、同步歌词，编辑标签与封面，整理文件名，\n以及完成音频、图片和歌词字幕的格式转换。\n\n媒体文件始终在本机处理，默认保留原文件。');text.setWordWrap(True);body.addWidget(text)
        body.addWidget(button('使用说明',lambda:self.show_document('使用说明','USER_GUIDE.md','USER_GUIDE.en.md')),0,Qt.AlignmentFlag.AlignLeft)
        body.addWidget(button('第三方组件说明',lambda:self.show_document('第三方组件说明','THIRD_PARTY_NOTICES.md')),0,Qt.AlignmentFlag.AlignLeft);about.layout.addStretch();self.pages['about']=about
        labels=['音频预览','音频标签编辑','歌词 / 字幕转换','音频格式转换','图片格式转换','音频合并 / 分割','批量重命名','任务中心','设置','关于']
        self.keys=list(self.pages)
        for key,label in zip(self.keys,labels):
            page=self.pages[key];self.navigation.addItem(label)
            container=QWidget();body=QVBoxLayout(container);body.setContentsMargins(0,0,0,0);body.setSpacing(0)
            if hasattr(page,'footer'):
                page.layout.removeWidget(page.footer)
                page.footer.setContentsMargins(20,8,20,12)
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page);body.addWidget(scroll,1)
            page.scroll=scroll
            if hasattr(page,'footer'):body.addWidget(page.footer)
            self.stack.addWidget(container)
        self.navigation.currentRowChanged.connect(self.show_page)
        self.navigation.setCurrentRow(self.keys.index('preview'))
        self.cancel_button=button('取消任务',self.cancel_task);self.cancel_button.hide();self.statusBar().addPermanentWidget(self.cancel_button)
        self.preset_bar=QWidget();preset_layout=QHBoxLayout(self.preset_bar);preset_layout.setContentsMargins(12,0,12,0);preset_layout.setSpacing(8)
        self.preset_combo=combo([]);self.preset_combo.currentIndexChanged.connect(self.apply_selected_preset)
        self.preset_save=button('保存预设',self.save_current_preset,symbol='save')
        self.preset_delete=button('删除',self.delete_selected_preset,symbol='trash')
        self.preset_bar.layout().addWidget(QLabel('预设'),0,Qt.AlignmentFlag.AlignLeft);self.preset_bar.layout().addWidget(self.preset_combo,1);self.preset_bar.layout().addWidget(self.preset_save,0,Qt.AlignmentFlag.AlignLeft);self.preset_bar.layout().addWidget(self.preset_delete,0,Qt.AlignmentFlag.AlignLeft)
        self.preset_bar.hide();self.statusBar().addPermanentWidget(self.preset_bar)
        self.progress=QProgressBar();self.progress.setFixedWidth(230);self.progress.hide();self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage(warning or '就绪 · 可直接拖入文件或文件夹')
        self.setAcceptDrops(True);self.setStyleSheet(STYLE);self.apply_defaults();self.center_on_screen();self.set_language(self.settings['language']);QTimer.singleShot(0,self.refresh_preset_bar)
    def center_on_screen(self):
        screen=QApplication.primaryScreen()
        if screen is None:return
        frame=self.frameGeometry();frame.moveCenter(screen.availableGeometry().center());self.move(frame.topLeft())
    def reset_scroll(self,page):
        """Entering a page starts at the top so navigation stays predictable."""
        scroll=getattr(page,'scroll',None)
        if scroll is not None:scroll.verticalScrollBar().setValue(0)
    @property
    def current_page(self):return self.pages[self.keys[self.stack.currentIndex()]]
    def t(self,text):return tr(text,self.settings.get('language','zh_CN'))
    def set_language(self,language):
        self.settings['language']=language;self.sidebar.setFixedWidth(204);apply_language(self,language)
        if language=='en_US':
            labels=('Audio Preview','Tag Editor','Lyrics / Subtitles','Audio Converter','Image Converter','Join / Split','Batch Rename','Task Center','Settings','About')
            for item,label in zip(self.navigation.buttons,labels):item.setText(label)
        for item in self.navigation.buttons:item.setStyleSheet('font-size:13px;' if language=='en_US' else '')
        self.statusBar().showMessage(self.t('就绪 · 可直接拖入文件或文件夹'))
    def preset_target_page(self):
        page=self.current_page
        return page if getattr(page,'kind',None) in ('audio','image','subtitle') or type(page).__name__=='RenamePage' else None
    def current_preset_state(self):
        page=self.preset_target_page()
        if type(page).__name__=='RenamePage':
            return {'kind':'rename','template':page.template.currentText(),'fallback_missing':page.fallback.isChecked()}
        return page.current_preset_state()
    def refresh_preset_bar(self):
        if not hasattr(self,'preset_combo'):return
        page=self.preset_target_page()
        self.preset_combo.blockSignals(True);self.preset_combo.clear()
        presets=self.settings.get('task_presets',{})
        matching={name:fields for name,fields in presets.items() if self.preset_kind_matches(page,fields)}
        for name in sorted(matching):self.preset_combo.addItem(name,matching[name])
        self.preset_combo.setCurrentIndex(-1);self.preset_combo.blockSignals(False)
        self.preset_bar.setVisible(page is not None)
    @staticmethod
    def preset_kind_matches(page,fields):
        if type(page).__name__=='RenamePage':return fields.get('kind')=='rename'
        return fields.get('kind')==page.kind
    def apply_selected_preset(self,index):
        fields=self.preset_combo.itemData(index)
        page=self.preset_target_page()
        if not fields or not page:return
        if fields.get('kind')=='rename':
            if fields.get('template'):page.template.setCurrentText(fields['template'])
            page.fallback.setChecked(bool(fields.get('fallback_missing')))
            return
        page.apply_preset(fields)
    def save_current_preset(self):
        page=self.preset_target_page()
        if not page:return self.inform(self.t('当前页面不支持预设。'))
        from PySide6.QtWidgets import QInputDialog
        name,ok=QInputDialog.getText(self,self.t('保存预设'),self.t('预设名称'),text=self.preset_combo.currentText())
        if not ok or not name.strip():return
        presets=dict(self.settings.get('task_presets',{}));presets[name.strip()]=self.current_preset_state()
        self.settings['task_presets']=presets
        try:save_settings(self.settings,self.app.settings_file)
        except Exception as exc:return self.inform(self.t('预设保存失败：')+str(exc))
        self.refresh_preset_bar();self.statusBar().showMessage(self.t('预设已保存'))
    def delete_selected_preset(self):
        name=self.preset_combo.currentData() and self.preset_combo.currentText()
        if not name:return self.inform(self.t('请先选择要删除的预设。'))
        presets=dict(self.settings.get('task_presets',{}));presets.pop(name,None)
        self.settings['task_presets']=presets
        try:save_settings(self.settings,self.app.settings_file)
        except Exception as exc:return self.inform(self.t('预设删除失败：')+str(exc))
        self.refresh_preset_bar();self.statusBar().showMessage(self.t('预设已删除'))
    def show_page(self,index):
        self.stack.setCurrentIndex(index)
        page=self.pages[self.keys[index]]
        if hasattr(page,'_update_responsive_layout'):page._update_responsive_layout()
        self.reset_scroll(page);self.refresh_preset_bar()
    def apply_defaults(self):
        s=self.settings
        for name in ('audio','image','subtitle'):
            page=self.pages[name];page.output.edit.setText(s['default_output_directory'] if s['default_output_location']=='custom' else '')
        audio=self.pages['audio'];audio.preserve.setChecked(s['default_preserve_metadata']);audio.update_parameter()
        audio.rate.setCurrentIndex(0 if s['default_keep_sample_rate'] else 2);audio.channels.setCurrentIndex(0 if s['default_keep_channels'] else 2)
        image=self.pages['image'];image.quality.setValue(s['default_webp_quality'] if image.format.currentData()=='webp' else s['default_image_quality'])
        self.pages['subtitle'].duration.setValue(s['subtitle_final_duration'])
        self.pages['preview'].volume.setValue(s['default_volume']);self.pages['preview'].volume_changed()
        self.pages['editor'].mode.setCurrentIndex(1 if s['default_save_mode']=='overwrite' else 0)
        self.pages['editor'].output.edit.setText(s['default_output_directory'] if s['default_output_location']=='custom' else '')
    def run_task(self,work,done):
        if self._worker:return self.inform(self.t('当前任务仍在处理，请等待完成。'))
        self._done=done;self._task_outcome=None;self._worker=Worker(work,self)
        self.progress.setRange(0,100);self.progress.setValue(0);self.progress.show();self.cancel_button.setEnabled(True);self.cancel_button.show();self.statusBar().showMessage(self.t('正在处理…'))
        self._worker.result.connect(self._result);self._worker.error.connect(self._error);self._worker.cancelled.connect(self._cancelled);self._worker.progress.connect(self._progress);self._worker.finished.connect(self._finished);self._worker.start()
    def cancel_task(self):
        if not self._worker:return
        self.cancel_button.setEnabled(False);self.statusBar().showMessage(self.t('正在取消…'));self._worker.request_cancel()
    @Slot(object)
    def _result(self,value):self._task_outcome=(True,value)
    @Slot(str)
    def _error(self,value):self._task_outcome=(False,value)
    @Slot()
    def _cancelled(self):self._task_outcome=(None,None)
    @Slot(float,str)
    def _progress(self,percent,text):self.progress.setValue(round(percent));self.statusBar().showMessage(self.t(text))
    @Slot()
    def _finished(self):
        worker=self._worker;done=self._done;outcome=self._task_outcome
        self._worker=None;self._done=None;worker.deleteLater();self.progress.hide();self.cancel_button.hide();self.statusBar().showMessage(self.t('任务已取消') if outcome and outcome[0] is None else self.t('就绪'))
        if outcome:
            if outcome[0] is True:
                try:done(outcome[1])
                except Exception as exc:self.inform(self.t('结果显示失败：')+str(exc))
            elif outcome[0] is False:self.inform(self.t('处理失败：')+outcome[1])
    def record_task_history(self,kind,records):
        self.task_history=TaskHistory(kind,tuple(records));self.update_task_page()
    def update_task_page(self):
        history=self.task_history
        if not history:
            self.task_kind.setText(self.t('暂无批量任务'));self.task_summary.setText(self.t('转换和重命名完成后，这里会显示每个文件的状态。'))
            self.task_table.setRowCount(0);self.task_retry.setEnabled(False);return
        kind={'audio':self.t('音频转换'),'image':self.t('图片转换'),'subtitle':self.t('歌词 / 字幕转换'),'rename':self.t('批量重命名')}.get(history.kind,history.kind)
        self.task_kind.setText(self.t('最近任务：')+kind)
        failed=len(history.failures)
        self.task_summary.setText(self.t(f'成功 {len(history.succeeded)} 个 · 失败 {failed} 个 · 时间 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'))
        fill_table(self.task_table,[(r.source.name,self.t(r.state),self.t(r.message or '—')) for r in history.records])
        for row,record in enumerate(history.records):
            item=self.task_table.item(row,1)
            item.setForeground(QColor('#178858' if not record.failed else '#df5265'))
            item.setToolTip(self.t(record.message))
        self.task_retry.setEnabled(bool(history.failures))
    def retry_failed(self):
        history=self.task_history
        if not history or not history.failures:return self.inform(self.t('没有可重试的失败项。'))
        sources=[record.source for record in history.failures]
        if history.kind in ('audio','image','subtitle'):self.pages[history.kind].convert_paths(sources)
        elif history.kind=='rename':self.pages['renamer'].files.clear();self.pages['renamer'].files.add_paths(sources);self.pages['renamer'].preview()
        else:return self.inform(self.t('当前任务类型不支持重试。'))
    def inform(self,text):self.show_message('MediaAnvil Qt',self.t(str(text)))
    def show_message(self,title,text,copy_allowed=True):
        """Message box whose details can be copied for a support report."""
        box=QMessageBox(self);box.setWindowTitle(title);box.setText(text)
        box.setIcon(QMessageBox.Icon.Information)
        copy_button=None
        if copy_allowed and str(text).strip():
            copy_button=box.addButton(self.t('复制详情'),QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        localize_dialog_buttons(box,self.document_language())
        if copy_button is not None:copy_button.clicked.connect(lambda:QApplication.clipboard().setText(str(text)))
        box.exec()
        return box
    def show_text(self,title,text):
        dialog=QDialog(self);dialog.setWindowTitle(self.t(title));dialog.resize(850,550);layout=QVBoxLayout(dialog)
        content=QPlainTextEdit(self.t(str(text)));content.setReadOnly(True);layout.addWidget(content)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        localize_dialog_buttons(dialog,self.document_language());dialog.exec()
    def document_language(self):
        return 'en_US' if self.settings.get('language')=='en_US' else 'zh_CN'
    def log_directory(self):
        """Local log folder beside the settings file; never uploaded anywhere."""
        return self.settings_file.parent/'logs'
    def open_log_directory(self):
        directory=self.log_directory()
        try:directory.mkdir(parents=True,exist_ok=True)
        except OSError as exc:return self.inform(self.t('无法创建日志目录：')+str(exc))
        self.open_path(directory)
        self.statusBar().showMessage(self.t('已打开日志目录'))
    def data_directory(self):
        """Folder holding settings.json; see data_directory on the settings page."""
        return self.settings_file.parent
    def open_data_directory(self):
        """Show the folder that holds the settings, logs and playback positions.

        Opening it is how a user finds or removes their own records; nothing here
        deletes anything on its own.
        """
        directory=self.data_directory()
        try:directory.mkdir(parents=True,exist_ok=True)
        except OSError as exc:return self.inform(self.t('无法创建数据目录：')+str(exc))
        self.open_path(directory)
        self.statusBar().showMessage(self.t('已打开数据目录'))
    def document_title(self,name):
        key={'USER_GUIDE.md':'使用说明','USER_GUIDE.en.md':'使用说明',
             'THIRD_PARTY_NOTICES.md':'第三方组件说明','README-Qt.md':'README','README-Qt.en.md':'README'}.get(name,name)
        return self.t(key)
    def resolve_document(self,url):
        """Resolve an in-document link to another bundled guide, never the filesystem."""
        name=Path(url.toLocalFile() or url.toString()).name
        if not name or Path(name).suffix.lower()!='.md':return None
        path=resource(name)
        if not path.is_file():return None
        try:text=path.read_text(encoding='utf-8')
        except (OSError,UnicodeError):return None
        return self.document_title(name),text
    def show_document(self,title,chinese_name,english_name=None):
        name=english_name if english_name and self.settings.get('language')=='en_US' else chinese_name
        path=resource(name)
        try:text=path.read_text(encoding='utf-8')
        except (OSError,UnicodeError) as exc:return self.inform(self.t('文档无法打开：')+str(exc))
        self.present_document(self.t(title),text)
    def present_document(self,title,markdown):
        viewer=DocumentViewer(title,markdown,self.document_language(),self.resolve_document,self);viewer.exec()
    def open_path(self,path):QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
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
    def closeEvent(self,event):
        if self._worker:
            event.ignore();self.inform(self.t('后台任务尚未完成，请完成后再关闭窗口。'));return
        self.pages['preview'].close_player()
        try:save_settings(self.settings,self.settings_file)
        except Exception as exc:self.inform('设置未能保存：'+str(exc))
        self.pages['editor'].temp.cleanup();super().closeEvent(event)


def main():
    import argparse
    parser=argparse.ArgumentParser(description='MediaAnvil Qt')
    parser.add_argument('--smoke-test',type=Path,help=argparse.SUPPRESS)
    options=parser.parse_args()
    app=QApplication(sys.argv);app.setApplicationName('MediaAnvilQt');app.setStyle('Fusion')
    window=MainWindow(options.smoke_test/'settings.json' if options.smoke_test else None);window.show()
    if options.smoke_test:
        from .smoke import schedule_smoke
        schedule_smoke(app,window,options.smoke_test)
    return app.exec()
