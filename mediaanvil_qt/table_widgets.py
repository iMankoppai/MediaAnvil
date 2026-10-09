"""Table creation, row updates and display delegates."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (QAbstractItemView, QTableWidget, QTableWidgetItem, QHeaderView, QStyledItemDelegate)
from .i18n import tr


from .image_widgets import thumbnail


class StatusDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        source=str(index.data() or '')
        text=tr(source)
        # Callers may provide source text or already-localized display text.
        good=source in ('已完成',tr('已完成','en_US')) or source.startswith(('可重命名',tr('可重命名','en_US')))
        color=QColor('#178858' if good else '#c77736')
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=option.rect.adjusted(5,6,-5,-6)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#e1f6e9' if good else '#fff0e5'));painter.drawRoundedRect(rect,10,10)
        painter.setPen(color);painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,text);painter.restore()
    def sizeHint(self,option,index):return QSize(max(82,option.fontMetrics.horizontalAdvance(str(index.data()))+24),34)


class FileDelegate(QStyledItemDelegate):
    def initStyleOption(self,option,index):
        super().initStyleOption(option,index)
        path=Path(index.data())
        size=index.data(Qt.ItemDataRole.UserRole) or ''
        option.text=f'{path.name}    {size}    {path.suffix[1:].upper()}'
        if path.suffix.lower() in {'.jpg','.jpeg','.png','.webp','.bmp'}:option.icon=thumbnail(path)


class ThumbnailDelegate(QStyledItemDelegate):
    def initStyleOption(self,option,index):
        super().initStyleOption(option,index)
        path=index.data(Qt.ItemDataRole.UserRole)
        if path:option.icon=thumbnail(path)


def table(headers,virtual=False):
    if virtual:
        from .virtual_table import VirtualTable
        return VirtualTable(headers)
    t = QTableWidget(0, len(headers)); t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().hide(); return t


def fill_table(t, rows):
    blocked=t.signalsBlocked();t.blockSignals(True);t.setUpdatesEnabled(False)
    try:
        if hasattr(t,'reset_rows'):
            t.reset_rows(rows);return
        t.setRowCount(len(rows))
        for i, values in enumerate(rows):
            for j, value in enumerate(values):
                item = QTableWidgetItem(str(value)); item.setToolTip(str(value)); t.setItem(i, j, item)
    finally:t.blockSignals(blocked);t.setUpdatesEnabled(True)

