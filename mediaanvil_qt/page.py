"""Shared page header and file toolbar."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog, QBoxLayout)
from .design import icon


from .layouts import button, row
from .file_dialogs import dialog_category, dialog_initial_directory, dialog_filters, remember_dialog_selection, remember_dialog_filter


class Page(QWidget):
    def __init__(self, app, title, subtitle):
        super().__init__(); self.app = app; self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 18, 24, 18); self.layout.setSpacing(16)
        self.header = QWidget(); self.header_layout = QHBoxLayout(self.header); self.header_layout.setContentsMargins(0, 0, 0, 8); self.header_layout.setSpacing(14)
        name = {'音频预览':'music', '音频标签编辑':'tag', '歌词 / 字幕转换':'text',
                '音频格式转换':'convert', '图片格式转换':'image', '批量重命名':'rename', '设置':'settings'}.get(title, 'info')
        symbol = QLabel(); symbol.setObjectName('pageBadge');symbol.setAlignment(Qt.AlignmentFlag.AlignCenter);symbol.setPixmap(icon(name, '#0876ff', 30).pixmap(30, 30)); symbol.setFixedSize(56,56)
        self.header_layout.addWidget(symbol)
        symbol.hide()
        titles = QVBoxLayout(); titles.setSpacing(3)
        eyebrow=QLabel('MEDIA WORKSPACE');eyebrow.setObjectName('eyebrow');titles.addWidget(eyebrow)
        h = QLabel(title);h.setWordWrap(True); h.setObjectName('pageTitle'); titles.addWidget(h);self.page_title=h
        sub = QLabel(subtitle); sub.setWordWrap(True); sub.setObjectName('muted'); titles.addWidget(sub)
        self.header_layout.addLayout(titles, 1); self.layout.addWidget(self.header)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        direction=QBoxLayout.Direction.TopToBottom if self.width()<850 else QBoxLayout.Direction.LeftToRight
        if self.header_layout.direction()!=direction:self.header_layout.setDirection(direction)
    def file_toolbar(self, files):
        def choose():
            category=dialog_category(getattr(files,'empty_kind',''))
            supported=self.app.t('支持的文件') + ' (' + ' '.join('*'+x for x in sorted(files.extensions)) + ')'
            filters=dialog_filters(self,category,(supported,self.app.t('所有文件 (*)')))
            paths, chosen = QFileDialog.getOpenFileNames(self, self.app.t('选择文件'), dialog_initial_directory(self, category), filters)
            if paths:remember_dialog_selection(self, category, paths[0])
            remember_dialog_filter(self, category, chosen)
            files.add_paths(paths)
        files.choose_callback=choose
        toolbar = row(button('添加文件…', choose), button('添加文件夹…', lambda: self.app.choose_folder_for(self)),
                      button('移除选中', files.remove_checked), button('清空', files.clear))
        count = QLabel('0 个文件'); count.setObjectName('muted'); toolbar.layout().addWidget(count)
        toolbar.count_label=count
        files.filesChanged.connect(lambda: count.setText(self.app.t(f'{files.count()} 个文件')))
        return toolbar
    def output_default(self):
        s = self.app.settings
        return s['default_output_directory'] if s['default_output_location'] == 'custom' else ''
    def receive(self, paths): return 0

