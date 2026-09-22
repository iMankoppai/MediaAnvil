"""Offline, read-only Markdown reader for the bundled guides.

The viewer deliberately never opens a browser, never follows a network link and
never writes to disk: it only renders text that already ships with the
application and links between those bundled documents.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSplitter, QTextBrowser, QVBoxLayout,
    QWidget)

from .i18n import localize_dialog_buttons, tr

_NETWORK_SCHEMES = ('http', 'https', 'ftp', 'ftps', 'mailto')


def document_outline(document):
    """Return ``(level, text, block position)`` for every Markdown heading."""
    rows = []
    block = document.firstBlock()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        text = block.text().strip()
        if level and text:
            rows.append((level, text, block.position()))
        block = block.next()
    return rows


class DocumentViewer(QDialog):
    """Read-only Markdown window with an outline and in-document search."""

    def __init__(self, title, markdown, language='zh_CN', resolver=None, parent=None):
        super().__init__(parent)
        self.language = language
        self.resolver = resolver
        self.outline_rows = []
        self.setWindowTitle(title)
        self.resize(940, 640)
        self.setMinimumSize(560, 400)
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._outline_panel())
        splitter.addWidget(self._content_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([230, 710])
        layout.addWidget(splitter, 1)
        layout.addWidget(self._footer())
        self.set_markdown(markdown)
        localize_dialog_buttons(self, language)

    # ---- construction -------------------------------------------------
    def _outline_panel(self):
        panel = QWidget()
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 8, 0)
        column.setSpacing(6)
        caption = QLabel(tr('目录', self.language))
        caption.setObjectName('sectionTitle')
        column.addWidget(caption)
        self.outline = QListWidget()
        self.outline.setMinimumWidth(150)
        self.outline.currentRowChanged.connect(self._outline_activated)
        column.addWidget(self.outline, 1)
        self.outline_panel = panel
        return panel

    def _content_panel(self):
        panel = QWidget()
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        self.browser.setReadOnly(True)
        self.browser.anchorClicked.connect(self._link_clicked)
        self.browser.verticalScrollBar().valueChanged.connect(self._sync_outline)
        column.addWidget(self.browser, 1)
        return panel

    def _footer(self):
        footer = QWidget()
        row = QHBoxLayout(footer)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('在文档中查找…', self.language))
        self.search.setMaximumWidth(280)
        self.search.returnPressed.connect(self.find_next)
        self.search.textChanged.connect(lambda _text: self.status.clear())
        previous = QPushButton(tr('上一个', self.language))
        following = QPushButton(tr('下一个', self.language))
        previous.clicked.connect(self.find_previous)
        following.clicked.connect(self.find_next)
        self.status = QLabel('')
        self.status.setObjectName('muted')
        row.addWidget(self.search)
        row.addWidget(previous)
        row.addWidget(following)
        row.addWidget(self.status, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        row.addWidget(self.buttons)
        return footer

    # ---- content ------------------------------------------------------
    def set_markdown(self, markdown):
        self.markdown = markdown or ''
        self.browser.setMarkdown(self.markdown)
        self._build_outline()

    def _build_outline(self):
        self.outline.blockSignals(True)
        self.outline.clear()
        self.outline_rows = document_outline(self.browser.document())
        for level, text, _position in self.outline_rows:
            item = QListWidgetItem(('    ' * max(0, level - 1)) + text)
            item.setData(Qt.ItemDataRole.UserRole, text)
            self.outline.addItem(item)
        self.outline.blockSignals(False)
        self.outline_panel.setVisible(bool(self.outline_rows))

    def _outline_activated(self, row):
        if row < 0 or row >= len(self.outline_rows):
            return
        position = self.outline_rows[row][2]
        block = self.browser.document().findBlock(position)
        if block.isValid():
            self.browser.setTextCursor(QTextCursor(block))
            self.browser.ensureCursorVisible()

    def _sync_outline(self, *_args):
        if not self.outline_rows:
            return
        cursor = self.browser.cursorForPosition(QPoint(6, 6))
        current = 0
        for index, (_level, _text, position) in enumerate(self.outline_rows):
            if position <= cursor.block().position():
                current = index
            else:
                break
        self.outline.blockSignals(True)
        self.outline.setCurrentRow(current)
        self.outline.blockSignals(False)

    # ---- search -------------------------------------------------------
    def find_next(self):
        self._find(backward=False)

    def find_previous(self):
        self._find(backward=True)

    def _find(self, backward):
        needle = self.search.text()
        if not needle:
            self.status.clear()
            return
        flags = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
        if not self.browser.find(needle, flags):
            self.status.setText(tr('未找到匹配内容', self.language))

    # ---- links --------------------------------------------------------
    def _link_clicked(self, url):
        target = url.toString()
        if url.scheme().lower() in _NETWORK_SCHEMES:
            # Never reach the network: keep the address available for the user.
            QApplication.clipboard().setText(target)
            self.status.setText(tr('已复制链接，未打开网络地址', self.language))
            return
        document = self.resolver(url) if self.resolver else None
        if document is not None:
            title, markdown = document
            self.setWindowTitle(title)
            self.search.clear()
            self.status.clear()
            self.set_markdown(markdown)
            self.browser.verticalScrollBar().setValue(0)
            return
        name = Path(url.toLocalFile() or target).name or target
        QApplication.clipboard().setText(target)
        self.status.setText(tr('已复制链接，未自动打开：', self.language) + name)
