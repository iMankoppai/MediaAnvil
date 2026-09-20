"""Qt native window shell. Media work never runs in the GUI event loop."""
from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,Slot,QSize
from PySide6.QtGui import QIcon,QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,
    QListWidget,QStackedWidget,QScrollArea,QProgressBar,QMessageBox,QDialog,QPlainTextEdit,
    QDialogButtonBox,QFileDialog)
from core.settings import load_settings,settings_path,save_settings,last_load_warning
from core.media_matcher import AUDIO_EXTENSIONS,LYRIC_EXTENSIONS,COVER_EXTENSIONS
from .common import resource,Worker,Page,button,group
from .design import Navigation, STYLE
from .conversion import ConversionPage
from .preview import PreviewPage
from .metadata import MetadataPage
from .rename import RenamePage
from .settings import SettingsPage
from .services import collect_paths
from .i18n import apply_language, tr
from . import __version__


DEFAULT_WINDOW_OUTER_PIXELS = QSize(1440, 900)
DEFAULT_WINDOW_MINIMUM = QSize(760, 480)


def default_window_size(available: QSize | None = None, frame_height: int = 30, device_pixel_ratio: float | None = None) -> tuple[int, int]:
    """Use a 1440×900 (16:10) outer size, scaling down proportionally when needed."""
    if available is None:
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry().size() if screen else DEFAULT_WINDOW_OUTER_PIXELS
        if device_pixel_ratio is None and screen:device_pixel_ratio = screen.devicePixelRatio()
    scale = device_pixel_ratio or 1.0
    target_width = DEFAULT_WINDOW_OUTER_PIXELS.width() / scale
    target_outer_height = DEFAULT_WINDOW_OUTER_PIXELS.height() / scale
    factor = min(1.0, round(available.width() * .90) / target_width, round(available.height() * .90) / target_outer_height)
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
        self.settings_file=Path(config_path) if config_path else settings_path().parent.parent/'MediaAnvilQt'/'settings.json'
        self.settings=load_settings(self.settings_file);warning=last_load_warning()
        self._worker=None;self._task_outcome=None;self._done=None
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
            'image':ConversionPage(self,'image'), 'renamer':RenamePage(self), 'settings':SettingsPage(self),
        }
        about=Page(self,'关于 MediaAnvil','让日常媒体整理更轻松')
        card,body=group(f'MediaAnvil  ·  v{__version__}');about.layout.addWidget(card)
        artwork=QLabel();artwork.setPixmap(self.windowIcon().pixmap(76,76));body.addWidget(artwork)
        text=QLabel('一个简洁、离线的多媒体工具箱。\n\n播放音频、同步歌词，编辑标签与封面，整理文件名，\n以及完成音频、图片和歌词字幕的格式转换。\n\n媒体文件始终在本机处理，默认保留原文件。');text.setWordWrap(True);body.addWidget(text)
        body.addWidget(button('使用说明',lambda:self.open_path(resource('USER_GUIDE.md'))),0,Qt.AlignmentFlag.AlignLeft)
        body.addWidget(button('第三方组件说明',lambda:self.open_path(resource('THIRD_PARTY_NOTICES.md'))),0,Qt.AlignmentFlag.AlignLeft);about.layout.addStretch();self.pages['about']=about
        labels=['音频预览','音频标签编辑','歌词 / 字幕转换','音频格式转换','图片格式转换','批量重命名','设置','关于']
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
        self.progress=QProgressBar();self.progress.setFixedWidth(230);self.progress.hide();self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage(warning or '就绪 · 可直接拖入文件或文件夹')
        self.setAcceptDrops(True);self.setStyleSheet(STYLE);self.apply_defaults();self.center_on_screen();self.set_language(self.settings['language'])
    def center_on_screen(self):
        screen=QApplication.primaryScreen()
        if screen is None:return
        frame=self.frameGeometry();frame.moveCenter(screen.availableGeometry().center());self.move(frame.topLeft())
    def show_page(self,index):
        self.stack.setCurrentIndex(index)
        page=self.pages[self.keys[index]]
        if hasattr(page,'_update_responsive_layout'):page._update_responsive_layout()
    @property
    def current_page(self):return self.pages[self.keys[self.stack.currentIndex()]]
    def t(self,text):return tr(text,self.settings.get('language','zh_CN'))
    def set_language(self,language):
        self.settings['language']=language;self.sidebar.setFixedWidth(204);apply_language(self,language)
        if language=='en_US':
            labels=('Audio Preview','Tag Editor','Lyrics / Subtitles','Audio Converter','Image Converter','Batch Rename','Settings','About')
            for item,label in zip(self.navigation.buttons,labels):item.setText(label)
        for item in self.navigation.buttons:item.setStyleSheet('font-size:13px;' if language=='en_US' else '')
        self.statusBar().showMessage(self.t('就绪 · 可直接拖入文件或文件夹'))
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
        self.centralWidget().setEnabled(False);self.progress.setRange(0,100);self.progress.setValue(0);self.progress.show();self.statusBar().showMessage(self.t('正在处理…'))
        self._worker.result.connect(self._result);self._worker.error.connect(self._error);self._worker.progress.connect(self._progress);self._worker.finished.connect(self._finished);self._worker.start()
    @Slot(object)
    def _result(self,value):self._task_outcome=(True,value)
    @Slot(str)
    def _error(self,value):self._task_outcome=(False,value)
    @Slot(float,str)
    def _progress(self,percent,text):self.progress.setValue(round(percent));self.statusBar().showMessage(self.t(text))
    @Slot()
    def _finished(self):
        worker=self._worker;done=self._done;outcome=self._task_outcome
        self._worker=None;self._done=None;worker.deleteLater();self.centralWidget().setEnabled(True);self.progress.hide();self.statusBar().showMessage(self.t('就绪'))
        if outcome:
            if outcome[0]:
                try:done(outcome[1])
                except Exception as exc:self.inform(self.t('结果显示失败：')+str(exc))
            else:self.inform(self.t('处理失败：')+outcome[1])
    def inform(self,text):QMessageBox.information(self,'MediaAnvil Qt',self.t(str(text)))
    def show_text(self,title,text):
        dialog=QDialog(self);dialog.setWindowTitle(self.t(title));dialog.resize(850,550);layout=QVBoxLayout(dialog)
        content=QPlainTextEdit(self.t(str(text)));content.setReadOnly(True);layout.addWidget(content)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.exec()
    def open_path(self,path):QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
    def choose_folder_for(self,page):
        folder=QFileDialog.getExistingDirectory(self,self.t('选择文件夹'))
        if folder:self.import_paths([Path(folder)],page)
    def import_paths(self,paths,page=None):
        page=page or self.current_page
        if not hasattr(page,'receive'):return
        extensions=page.files.extensions if hasattr(page,'files') else AUDIO_EXTENSIONS|LYRIC_EXTENSIONS|COVER_EXTENSIONS
        recursive=page.include_subfolders.isChecked() if hasattr(page,'include_subfolders') else self.settings['include_subfolders']
        def done(found):
            count=page.receive(found)
            if not count:self.inform(self.t('没有找到当前页面支持的文件。'))
            elif self._worker is None:self.statusBar().showMessage(self.t(f'已导入 {count} 个文件'))
        self.run_task(lambda report:collect_paths(paths,extensions,recursive),done)
    def dragEnterEvent(self,event):
        if self._worker is None and event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):event.acceptProposedAction()
        else:event.ignore()
    def dropEvent(self,event):
        if self._worker:return event.ignore()
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
