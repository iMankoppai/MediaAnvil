"""Shared buttons, card layouts, responsive columns and segmented tabs."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFormLayout, QFrame, QSizePolicy, QBoxLayout)
from .design import icon
from .i18n import tr, current_language as _current_language


def button(text, callback, primary=False, symbol=None):
    b = QPushButton(text)
    b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary: b.setProperty('primary', True)
    if symbol:b.setIcon(icon(symbol,'white' if primary else '#315cff',18))
    if text in ('清空','清空列表','移除歌词','移除封面'):b.setProperty('danger',True)
    b.clicked.connect(callback)
    return b


class ResponsiveRow(QWidget):
    """Let compact windows stack controls instead of clipping their labels."""
    def minimumSizeHint(self):
        size=super().minimumSizeHint();return QSize(0,size.height())
    def resizeEvent(self,event):
        super().resizeEvent(event)
        layout=self.layout()
        minimum=sum(max(item.widget().minimumWidth(),item.widget().minimumSizeHint().width()) for i in range(layout.count()) if (item:=layout.itemAt(i)).widget())
        minimum+=max(0,layout.count()-1)*layout.spacing()
        direction=QBoxLayout.Direction.TopToBottom if self.width()<minimum else QBoxLayout.Direction.LeftToRight
        if layout.direction()!=direction:layout.setDirection(direction)


def row(*widgets):
    box = ResponsiveRow(); layout = QHBoxLayout(box); layout.setContentsMargins(0, 0, 0, 0)
    expands = False
    for widget in widgets:
        flexible = bool(widget.sizePolicy().expandingDirections() & Qt.Orientation.Horizontal)
        layout.addWidget(widget, 1 if flexible else 0); expands |= flexible
    if not expands: layout.addStretch(1)
    return box


def combo(values):
    box = QComboBox(); box.setMaximumWidth(400)
    for value in values:
        if isinstance(value, tuple): box.addItem(*value)
        else: box.addItem(str(value), value)
    return box


def group(title):
    box = QFrame(); box.setObjectName('card'); layout = QVBoxLayout(box)
    layout.setContentsMargins(18, 16, 18, 16); layout.setSpacing(12)
    if title:
        heading = QLabel(title); heading.setObjectName('sectionTitle');heading.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed);layout.addWidget(heading)
    return box, layout


class SegmentedTabs(QWidget):
    """A row of mutually exclusive headings, each owning one stacked view.

    Two sibling panels are never shown at once, which is the point: the preview
    page's lyric calibration controls must not sit next to the play queue, or the
    user can adjust lyrics while looking at a list that has nothing to do with
    them. Uses QTabBar so it inherits the project's underline styling.
    """

    changed = Signal(int)

    def __init__(self, labels, views, *, trailing=None):
        super().__init__()
        from PySide6.QtWidgets import QTabBar, QStackedWidget
        self.bar = QTabBar(); self.bar.setDrawBase(False); self.bar.setExpanding(False)
        self.bar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stack = QStackedWidget()
        # Keep the Chinese source text so the labels can be re-translated later;
        # a QTabBar label is not a widget, so apply_language cannot reach it.
        self._sources = list(labels)
        self._suffix = ''
        for label in labels:
            self.bar.addTab(label)
        for view in views:
            self.stack.addWidget(view)
        self.bar.currentChanged.connect(self.stack.setCurrentIndex)
        self.bar.currentChanged.connect(self.changed.emit)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(8)
        header = QWidget(); header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0); header_layout.setSpacing(8)
        header_layout.addWidget(self.bar)
        if trailing is not None:
            header_layout.addWidget(trailing)
        header_layout.addStretch(1)
        layout.addWidget(header)
        layout.addWidget(self.stack, 1)
        self.header = header

    def set_tab_text(self, index, text):
        self.bar.setTabText(index, text)

    def refresh_translated_text(self):
        """Re-translate the tab labels after a language switch.

        apply_language walks widgets, and a QTabBar label is not a widget, so the
        labels have to be rebuilt here from their original Chinese source.
        """
        for index, source in enumerate(self._sources):
            text = tr(source, _current_language())
            if index == len(self._sources) - 1 and getattr(self, '_suffix', ''):
                text = f'{text} {self._suffix}'
            self.bar.setTabText(index, text)

    def set_suffix(self, text):
        """Text appended to the last tab, such as an item count."""
        self._suffix = text
        self.refresh_translated_text()

    def current_index(self):
        return self.bar.currentIndex()

    def set_current_index(self, index):
        self.bar.setCurrentIndex(index)

    def set_alignment_right(self):
        """Push a trailing widget to the far edge of the heading row."""
        layout = self.header.layout()
        layout.setStretch(layout.count() - 1, 1)


class Columns(QWidget):
    """Stack content on narrow windows without shrinking controls below usability."""
    def __init__(self, left, right, breakpoint=850):
        super().__init__(); self.breakpoint=breakpoint;self.box=QBoxLayout(QBoxLayout.Direction.LeftToRight,self)
        self.box.setContentsMargins(0,0,0,0);self.box.setSpacing(14)
        for pane in (left,right):
            pane.setMinimumWidth(0);pane.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Expanding)
        self.box.addWidget(left,1);self.box.addWidget(right,1)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        direction=QBoxLayout.Direction.TopToBottom if self.width()<self.breakpoint else QBoxLayout.Direction.LeftToRight
        if self.box.direction()!=direction:self.box.setDirection(direction)


def form(title):
    box, outer = group(title); layout = QFormLayout(); outer.addLayout(layout)
    layout.setHorizontalSpacing(24); layout.setVerticalSpacing(10)
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return box, layout

