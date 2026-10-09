"""Shared visual language: pale surfaces, line icons and standard Qt controls."""
from functools import lru_cache
from PySide6.QtCore import Qt, QSize, QByteArray, QRectF, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QCheckBox, QLabel

ICONS = {
    'music': '<path d="M9 18V5l11-2v13M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2.5"/><ellipse cx="17" cy="16" rx="3" ry="2.5"/>',
    'tag': '<path d="M3 4h8l10 10-7 7L3 10Z"/><circle cx="7.5" cy="8" r="1"/>',
    'text': '<path d="m5 20 7-17 7 17M8 13h8"/>',
    'convert': '<path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/>',
    'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m4 17 5-5 4 4 3-4 5 5"/>',
    'rename': '<path d="m14 4 6 6M4 20l5-1L21 7l-4-4L5 15Z"/>',
    'settings': '<path d="m9 3 1-1h4l1 3 3 1 3-1 2 4-2 2v3l2 2-2 4-3-1-3 1-1 3h-4l-1-3-3-1-3 1-2-4 2-2v-3L1 9l2-4 3 1 3-1Z" transform="translate(1 0) scale(.92)"/><circle cx="12" cy="12" r="3.5"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.2"/>',
    'folder': '<path d="M3 7V4h7l2 3h9v13H3ZM3 10h18"/>',
    'list': '<path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"/>',
    'search': '<circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6"/>',
    'upload': '<path d="M4 16v5h16v-5M12 16V3m-5 5 5-5 5 5"/>',
    'file': '<path d="M6 2h8l5 5v15H6Z"/><path d="M14 2v6h5"/>',
    'trash': '<path d="M4 7h16M9 3h6l1 4M7 7l1 14h8l1-14M10 11v6M14 11v6"/>',
    'play': '<path d="m9 4 12 8-12 8Z"/>',
    'pause': '<path d="M8 5v14M16 5v14"/>',
    'stop': '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    'previous':'<path d="M5 5v14m14-14L7 12l12 7Z"/>',
    'next':'<path d="M19 5v14M5 5l12 7-12 7Z"/>',
    'shuffle':'<path d="M3 6h3c5 0 7 12 12 12h3m-4-4 4 4-4 4M3 18h3c2 0 4-3 6-6s4-6 6-6h3m-4-4 4 4-4 4"/>',
    'volume':'<path d="M3 9h4l5-5v16l-5-5H3Zm13-1c3 2 3 6 0 8m3-11c5 4 5 10 0 14"/>',
    'undo':'<path d="M9 7H4v-5M4 7c2-3 5-4 8-4a9 9 0 1 1-8 13"/>',
    'save':'<path d="M4 3h13l3 3v15H4Z"/><path d="M8 3v6h8V3M8 21v-7h8v7"/>',
    'crop':'<path d="M7 3v14a4 4 0 0 0 4 4h10M3 7h14a4 4 0 0 1 4 4v10"/>',
    'task':'<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3" cy="6" r=".6"/><circle cx="3" cy="12" r=".6"/><circle cx="3" cy="18" r=".6"/>',
}
PAGE_ICONS = ['music', 'tag', 'text', 'convert', 'image', 'shuffle', 'rename', 'task', 'settings', 'info']
# The stretch sits above this entry so the navigation keeps its footer group.
NAVIGATION_STRETCH_INDEX = 7


@lru_cache(maxsize=128)
def icon(name, color='#43536d', size=22):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(name, ICONS["list"])}</svg>'
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


class Toggle(QCheckBox):
    """A keyboard-accessible checkbox painted as a compact switch."""
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setAccessibleName(text); self.setFixedSize(44, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def hitButton(self, point): return self.rect().contains(point)
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = '#315cff' if self.isChecked() else '#c9d1dc'
        if not self.isEnabled(): color = '#dce3ec'
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(1, 3, 42, 22), 11, 11)
        painter.setBrush(QColor('white')); painter.drawEllipse(QRectF(24 if self.isChecked() else 4, 6, 16, 16))
        if self.hasFocus():
            painter.setPen(QPen(QColor('#6c99e8'), 1, Qt.PenStyle.DotLine)); painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(0.5, .5, 43, 25), 6, 6)


class Navigation(QWidget):
    currentRowChanged = Signal(int)
    def __init__(self):
        super().__init__(); self.buttons = []; self._current = -1
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.layout.setSpacing(5)
    def addItem(self, label):
        index = len(self.buttons)
        item = QPushButton(label); item.setObjectName('navItem'); item.setCheckable(True)
        item.setIcon(icon(PAGE_ICONS[index])); item.setIconSize(QSize(20, 20))
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.clicked.connect(lambda checked=False, i=index: self.setCurrentRow(i))
        self.buttons.append(item); self.layout.addWidget(item)
        if index == 9:self.arrange_groups()
    def arrange_groups(self):
        while self.layout.count():self.layout.takeAt(0)
        for heading,indices in (('工作空间',(0,1,6)),('格式处理',(2,3,4,5)),('',(7,))):
            if heading:
                caption=QLabel(heading);caption.setObjectName('navHeading');self.layout.addWidget(caption)
            for index in indices:self.layout.addWidget(self.buttons[index])
        self.layout.addStretch(1)
        for index in (8,9):self.layout.addWidget(self.buttons[index])
        self.local_status=QLabel('●  本地处理');self.local_status.setObjectName('localStatus')
        self.layout.addWidget(self.local_status)
    def setCurrentRow(self, index):
        if not 0 <= index < len(self.buttons): return
        changed = self._current != index; self._current = index
        for i, item in enumerate(self.buttons):
            item.setChecked(i == index)
            item.setIcon(icon(PAGE_ICONS[i], '#315cff' if i == index else '#192338'))
        if changed: self.currentRowChanged.emit(index)
    def currentRow(self): return self._current


from .theme import STYLE as STYLE
