"""Qt native window shell. Media work never runs in the GUI event loop."""
from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,QSize,QTimer
from PySide6.QtGui import QIcon,QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,
    QStackedWidget,QScrollArea,QProgressBar,QMessageBox,QDialog,QPlainTextEdit,
    QDialogButtonBox)
from core.settings import load_settings,settings_path,save_settings,last_load_warning
from core.tasks import TaskHistory,load_task_histories
from dataclasses import replace
from .task_execution import TaskExecutionMixin
from .task_history import TaskHistoryMixin
from .file_imports import FileImportMixin
from .common import resource,button,combo
from .design import Navigation, STYLE
from .documents import DocumentViewer
from .conversion import ConversionPage
from .join import JoinPage
from .preview import PreviewPage
from .metadata import MetadataPage
from .rename import RenamePage
from .settings import SettingsPage
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


class MainWindow(TaskExecutionMixin, TaskHistoryMixin, FileImportMixin, QMainWindow):
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
        self._worker=None;self._task_outcome=None;self._done=None;self._active_task_id=None;self._importing=False
        self.pending_tasks=[];self._finishing=False
        self.task_checkpoints={}
        self.queue_timer=QTimer(self);self.queue_timer.setSingleShot(True);self.queue_timer.timeout.connect(self.start_next_task)
        self.task_history_file=self.settings_file.parent/'task-history.json'
        self.task_histories=load_task_histories(self.task_history_file)
        self.task_history:TaskHistory|None=self.task_histories[-1] if self.task_histories else None
        self.task_flush_timer=QTimer(self);self.task_flush_timer.setSingleShot(True);self.task_flush_timer.setInterval(500)
        self.task_flush_timer.timeout.connect(self.flush_task_updates)
        central=QWidget();central.setObjectName('shell');layout=QHBoxLayout(central);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0);self.setCentralWidget(central)
        sidebar=QWidget();self.sidebar=sidebar;sidebar.setObjectName('sidebar');sidebar.setFixedWidth(224);left=QVBoxLayout(sidebar);left.setContentsMargins(12,14,12,8);left.setSpacing(12)
        brand_row=QHBoxLayout();brand_row.setContentsMargins(8,0,0,6);brand_row.setSpacing(10)
        logo=QLabel();logo.setPixmap(QIcon(str(resource('assets/qt/brand.svg'))).pixmap(36,36));brand_row.addWidget(logo)
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
        from .utility_pages import task_center,about_page
        self.pages['tasks']=task_center(self)
        self.pages['settings']=self.pages.pop('settings')
        self.update_task_page()
        self.pages['about']=about_page(self)
        labels=['音频预览','音频标签编辑','歌词 / 字幕转换','音频格式转换','图片格式转换','音频合并 / 分割','批量重命名','任务中心','设置','关于']
        self.keys=list(self.pages)
        for key,label in zip(self.keys,labels):
            page=self.pages[key];self.navigation.addItem(label)
            container=QWidget();body=QVBoxLayout(container);body.setContentsMargins(0,0,0,0);body.setSpacing(0)
            if hasattr(page,'footer'):
                page.layout.removeWidget(page.footer)
                page.footer.setObjectName('playerDock' if key=='preview' else 'actionFooter')
                page.footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
                page.footer.setContentsMargins(24,10,24,12)
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
        self.organizer_return=button('返回整理流程',self.open_organizer);self.organizer_return.hide();self.statusBar().addPermanentWidget(self.organizer_return)
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
        self.settings['language']=language;self.sidebar.setFixedWidth(244 if language=='en_US' else 224);apply_language(self,language)
        if language=='en_US':
            labels=('Audio Preview','Tag Editor','Lyrics / Subtitles','Audio Converter','Image Converter','Join / Split','Batch Rename','Task Center','Settings','About')
            for item,label in zip(self.navigation.buttons,labels):item.setText(label)
        for item in self.navigation.buttons:item.setStyleSheet('font-size:13px;' if language=='en_US' else '')
        self.update_task_page()
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
        if page is not None and self.preset_bar.parentWidget() is not page.header:
            self.statusBar().removeWidget(self.preset_bar)
            page.header_layout.addWidget(self.preset_bar)
    @staticmethod
    def preset_kind_matches(page,fields):
        if page is None:return False
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
        updated=dict(self.settings,task_presets=presets)
        try:save_settings(updated,self.settings_file)
        except Exception as exc:return self.inform(self.t('预设保存失败：')+str(exc))
        self.settings['task_presets']=presets
        self.refresh_preset_bar();self.preset_combo.setCurrentIndex(self.preset_combo.findText(name.strip()))
        self.statusBar().showMessage(self.t('预设已保存'))
    def delete_selected_preset(self):
        name=self.preset_combo.currentData() and self.preset_combo.currentText()
        if not name:return self.inform(self.t('请先选择要删除的预设。'))
        presets=dict(self.settings.get('task_presets',{}));presets.pop(name,None)
        updated=dict(self.settings,task_presets=presets)
        try:save_settings(updated,self.settings_file)
        except Exception as exc:return self.inform(self.t('预设删除失败：')+str(exc))
        self.settings['task_presets']=presets
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
        if self._finishing and self.pending_tasks:
            box.setWindowModality(Qt.WindowModality.NonModal);box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose);box.show()
        else:box.exec()
        return box
    def show_text(self,title,text):
        dialog=QDialog(self);dialog.setWindowTitle(self.t(title));dialog.resize(850,550);layout=QVBoxLayout(dialog)
        content=QPlainTextEdit(self.t(str(text)));content.setReadOnly(True);layout.addWidget(content)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        localize_dialog_buttons(dialog,self.document_language())
        if self._finishing and self.pending_tasks:
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose);dialog.show();return dialog
        dialog.exec()
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
    def open_organizer(self):
        if not getattr(self,'organizer',None):
            from .organizer import OrganizerDialog
            self.organizer=OrganizerDialog(self)
        self.organizer.show();self.organizer.raise_();self.organizer_return.show()
    def closeEvent(self,event):
        if self._worker or self._importing:
            event.ignore();self.inform(self.t('后台任务尚未完成，请完成后再关闭窗口。'));return
        self.pages['preview'].close_player()
        self.queue_timer.stop()
        for job in self.pending_tasks:
            history=next((h for h in self.task_histories if h.task_id==job.task_id),None)
            if history:self.store_task_history(replace(history,records=tuple(replace(r,state='已中断') for r in history.records)))
        self.pending_tasks=[]
        self.task_flush_timer.stop();self.persist_task_histories()
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
