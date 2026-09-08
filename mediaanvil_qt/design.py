"""Shared visual language: pale surfaces, line icons and standard Qt controls."""
import sys
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QByteArray, QRectF, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QCheckBox

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
}
PAGE_ICONS = ['music', 'tag', 'text', 'convert', 'image', 'rename', 'settings', 'info']


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
        color = '#2871f5' if self.isChecked() else '#c9d1dc'
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
        if index == 6: self.layout.addStretch(1)
        item = QPushButton(label); item.setObjectName('navItem'); item.setCheckable(True)
        item.setIcon(icon(PAGE_ICONS[index])); item.setIconSize(QSize(20, 20))
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.clicked.connect(lambda checked=False, i=index: self.setCurrentRow(i))
        self.buttons.append(item); self.layout.addWidget(item)
    def setCurrentRow(self, index):
        if not 0 <= index < len(self.buttons): return
        changed = self._current != index; self._current = index
        for i, item in enumerate(self.buttons):
            item.setChecked(i == index)
            item.setIcon(icon(PAGE_ICONS[i], '#246ef0' if i == index else '#43536d'))
        if changed: self.currentRowChanged.emit(index)
    def currentRow(self): return self._current


STYLE = '''
QWidget { font-family:"Microsoft YaHei UI"; font-size:13px; color:#27354e; }
QMainWindow, QWidget#shell { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #f8fbff,stop:0.5 #edf6ff,stop:1 #f5f9fe); }
QScrollArea, QScrollArea>QWidget>QWidget, QWidget#sidebar { background:transparent; border:none; }
QLabel { background:transparent; }
QLabel#pageTitle { font-size:23px; font-weight:700; color:#172641; }
QLabel#sectionTitle { font-size:16px; font-weight:600; color:#20304b; }
QLabel#trackTitle { font-size:22px; font-weight:650; color:#1b2a45; }
QLabel#brand { font-size:17px; font-weight:700; color:#15243f; }
QLabel#muted, QLabel#version { color:#8a98ad; font-size:12px; }
QLabel#iconBadge { background:#e8f0ff; border-radius:19px; }
QLabel#pageBadge { background:#e2efff; border-radius:14px; }
QLabel#success { background:#eaf8f1; color:#148957; padding:10px; border-radius:8px; }
QLabel#notice { background:#f0f6ff; color:#7288aa; padding:8px; border-radius:7px; }
QLabel#artwork { background:#eef4ff; border:1px solid #e5edfa; border-radius:14px; color:#8195b7; }
QLabel#coverPreview { background:transparent; border:0; color:#8195b7; }
QFrame#card { background:#ffffff; border:1px solid #edf1f7; border-radius:12px; }
QFrame#card QLineEdit, QFrame#card QComboBox, QFrame#card QSpinBox, QFrame#card QDoubleSpinBox { background:#f9fbfe; }
QFrame#card QListWidget, QFrame#card QPlainTextEdit, QFrame#card QTableWidget { background:#ffffff; }
QPushButton { background:#f9fbfe; border:1px solid #dfe6f0; border-radius:8px; padding:7px 13px; min-height:18px; }
QPushButton:hover { background:#edf3ff; border-color:#c8daf7; }
QPushButton:pressed { background:#e1ebfc; }
QPushButton:focus { border-color:#8ab0fb; }
QPushButton[primary="true"] { background:#2b70f3; color:white; border-color:#2b70f3; font-weight:600; }
QPushButton[primary="true"]:hover { background:#1b62e8; }
QPushButton[danger="true"] { color:#ee5365; background:#fff3f4; border-color:#ffdde2; }
QPushButton#roundControl { min-width:46px; max-width:46px; min-height:46px; max-height:46px; border-radius:23px; padding:0; background:#f0f5fd; border:0px solid transparent; }
QPushButton#roundControl:checked { background:#d9eaff; }
QPushButton#roundPlay { min-width:60px; max-width:60px; min-height:60px; max-height:60px; border-radius:30px; padding:0; background:#0877ff; border:0px solid transparent; }
QPushButton:disabled { color:#a0acbd; background:#f0f3f8; border-color:#e7edf4; }
QPushButton#navItem { background:transparent; border:0; border-left:2px solid transparent; border-radius:8px; text-align:left; padding:12px 14px; min-height:22px; font-size:15px; font-weight:600; }
QPushButton#navItem:hover { background:#e9f0fa; }
QPushButton#navItem:checked { background:#e2ecfc; color:#246ef0; border-left-color:#2a72fa; font-weight:700; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#f9fbfe; border:1px solid #e0e7f1; border-radius:7px; padding:5px 10px; min-height:20px; selection-background-color:#dbe8ff; selection-color:#234672; }
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus { border-color:#8ab0fb; }
QLineEdit:disabled,QComboBox:disabled,QSpinBox:disabled,QDoubleSpinBox:disabled { color:#a0acbd; background:#f1f4f9; }
QComboBox::drop-down { border:0; width:26px; }
QComboBox::down-arrow { image:url("@ASSETS@/chevron-down.svg"); width:12px; height:8px; }
QSpinBox::up-button,QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:22px; border:none; margin:2px 2px 0 0; }
QSpinBox::down-button,QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:22px; border:none; margin:0 2px 2px 0; }
QSpinBox::up-arrow,QDoubleSpinBox::up-arrow { image:url("@ASSETS@/chevron-up.svg"); width:10px; height:7px; }
QSpinBox::down-arrow,QDoubleSpinBox::down-arrow { image:url("@ASSETS@/chevron-down.svg"); width:10px; height:7px; }
QComboBox QAbstractItemView { border:1px solid #e0e7f1; background:white; selection-background-color:#e9f1ff; selection-color:#234672; padding:4px; }
QListWidget,QPlainTextEdit,QTableWidget { background:white; border:1px solid #e9eef5; border-radius:8px; selection-background-color:#e9f1ff; selection-color:#234672; padding:5px; }
QListWidget::item { padding:7px; border-radius:5px; }
QListWidget::item:hover { background:#f1f6ff; }
QHeaderView::section { background:#f7f9fd; color:#7a89a0; border:none; padding:10px 8px; font-weight:500; }
QTableWidget { gridline-color:#f0f3f8; }
QCheckBox { spacing:7px; min-height:23px; }
QCheckBox::indicator { width:15px; height:15px; }
QCheckBox::indicator:unchecked { border:1px solid #cbd6e5; border-radius:4px; background:white; }
QCheckBox::indicator:checked { border:1px solid #2b70f3; border-radius:4px; background:#2b70f3; image:url("@ASSETS@/check.svg"); }
QAbstractItemView::indicator { width:16px; height:16px; }
QAbstractItemView::indicator:unchecked { border:1px solid #cbd6e5; border-radius:4px; background:white; }
QAbstractItemView::indicator:checked { border:1px solid #2b70f3; border-radius:4px; background:#2b70f3; image:url("@ASSETS@/check.svg"); }
QTabWidget::pane { border:none; background:transparent; }
QTabBar::tab { color:#8391a6; padding:10px 18px; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#276eef; border-bottom-color:#2b70f3; }
QProgressBar { border:0; border-radius:4px; background:#e6edf8; text-align:center; color:#546988; }
QProgressBar::chunk { background:#397cf5; border-radius:4px; }
QSlider:horizontal { padding:0 8px; }
QSlider::groove:horizontal { height:5px; background:#e5ecf6; border-radius:2px; }
QSlider::sub-page:horizontal { background:#3a7bf4; border-radius:2px; }
QSlider::handle:horizontal { background:white; border:2px solid #397bf3; width:12px; height:12px; margin:-6px 0; border-radius:8px; }
QScrollBar:vertical { background:transparent; width:8px; margin:2px; }
QScrollBar::handle:vertical { background:#d3ddeb; border-radius:3px; min-height:30px; }
QScrollBar::handle:vertical:hover { background:#b9c9df; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QStatusBar { background:#f0f5fb; color:#8c9aaf; font-size:11px; }
QSplitter::handle { background:transparent; width:12px; }
QToolTip { background:#ffffff; color:#354761; border:1px solid #dce5f2; padding:6px; }
'''
STYLE = STYLE.replace('@ASSETS@', (Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets' / 'qt').as_posix())
