"""Output directory control and selectable, reorderable file lists."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QRect, QSize, QEvent, QTimer, QItemSelectionModel
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QFileDialog, QListWidget,
    QAbstractItemView, QSizePolicy, QListWidgetItem)
from .design import icon
from .i18n import tr


from .file_dialogs import dialog_initial_directory, remember_dialog_selection
from .layouts import button
from .table_widgets import FileDelegate


class OutputPath(QWidget):
    def __init__(self, text=''):
        super().__init__(); layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(text); self.edit.setPlaceholderText('留空：保存到各源文件所在文件夹')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.edit); layout.addWidget(button('浏览…', self.choose))
    def choose(self):
        path = QFileDialog.getExistingDirectory(self, tr('选择输出文件夹'), dialog_initial_directory(self, 'output'))
        if path:
            remember_dialog_selection(self, 'output', path); self.edit.setText(path)
    def text(self): return self.edit.text().strip()


def file_size(size):
    return f'{size/1024/1024:.2f} MB' if size>=1024*1024 else f'{size/1024:.1f} KB' if size>=1024 else f'{size} B'


class FileList(QListWidget):
    filesChanged = Signal()
    def sizeHint(self):return QSize(360,150)
    def __init__(self, extensions, reorderable=False):
        super().__init__(); self.extensions = frozenset(extensions)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setMinimumHeight(125); self.setToolTip('可从资源管理器拖入文件或文件夹')
        self._empty_icon = icon('upload', '#9fb7db', 30)
        self.setItemDelegate(FileDelegate(self));self.setIconSize(QSize(32,32))
        self.itemChanged.connect(lambda item:self.filesChanged.emit())
        self.choose_callback=None
        # Reordering is opt-in because only the join page cares about list order.
        # The whole window already accepts files dropped from Explorer, so this
        # list must claim internal drags only and let external URL drops fall
        # through to the window, or dropping a file onto the list would stop
        # working.
        self.reorderable=reorderable
        if reorderable:
            self.setDragEnabled(True);self.setAcceptDrops(True)
            # InternalMove is what makes Qt treat a drag from this list as a
            # reorder rather than a copy.
            self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            self.setDropIndicatorShown(True)
            self.setDefaultDropAction(Qt.DropAction.MoveAction)
            self.setToolTip('拖动条目可调整顺序；也可从资源管理器拖入文件或文件夹')
            # In InternalMove mode Qt's own item-view drag handling claims URL
            # drops before dragEnterEvent is consulted, which would stop files
            # being dropped onto the list from Explorer. A viewport filter sees
            # the event first and hands anything carrying URLs back to the
            # window-level handler.
            self.viewport().installEventFilter(self)
    def eventFilter(self,watched,event):
        # In InternalMove mode Qt's own item-view drag handling claims URL drops
        # before dragEnterEvent is consulted, which would stop files being dropped
        # onto the list from Explorer. Refusing the event here, before Qt's
        # handler sees it, leaves the drop to the window-level importer.
        if watched is self.viewport() and event.type() in (
                QEvent.Type.DragEnter,QEvent.Type.DragMove,QEvent.Type.Drop):
            if event.mimeData().hasUrls():
                event.setAccepted(False)
                return True
        return super().eventFilter(watched,event)
    def _is_internal_drag(self,event):
        return self.reorderable and not event.mimeData().hasUrls()
    def dragEnterEvent(self,event):
        if self._is_internal_drag(event):event.acceptProposedAction()
        else:event.ignore()
    def dragMoveEvent(self,event):
        if self._is_internal_drag(event):event.acceptProposedAction()
        else:event.ignore()
    def dropEvent(self,event):
        if not self._is_internal_drag(event):return event.ignore()
        rows=sorted(self.row(item) for item in self.selectedItems())
        if not rows:return event.ignore()
        index=self.indexAt(event.position().toPoint())
        # Dropping onto a row inserts before it, or after it when the indicator
        # says the pointer is below the row's midpoint.
        before=self.count() if not index.isValid() else index.row()
        if index.isValid() and self.dropIndicatorPosition()==QAbstractItemView.DropIndicatorPosition.BelowItem:
            before=index.row()+1
        self.move_rows(rows,before)
        event.acceptProposedAction()
    def move_rows(self,rows,before_index):
        """Move ``rows`` together so they sit immediately before ``before_index``.

        ``before_index`` is an index in the list *as it looks now*; the moved rows
        are taken out first and re-inserted at the gap in front of that row, so
        ``before_index=count()`` appends at the end. Rows keep their original
        relative order and stay selected, so a second move continues from the new
        position.

        Expressing the destination as "before row N" rather than as a final index
        keeps the arithmetic in one place: an insertion point in the shortened
        list is just the number of rows that stay and currently precede N.

        The entries are rebuilt from their stored data rather than moved with
        ``takeItem``: under PySide6 the item returned by ``takeItem`` is already
        owned by Python and re-adding it produces empty rows, so the list is
        captured, cleared and repopulated instead.
        """
        chosen=sorted(set(rows))
        if not chosen:return False
        count=self.count()
        if any(position<0 or position>=count for position in chosen):return False
        chosen_set=set(chosen)
        snapshot=[self._entry(index) for index in range(count)]
        moved=[snapshot[position] for position in chosen]
        remaining=[(index,entry) for index,entry in enumerate(snapshot) if index not in chosen_set]
        insert_at=sum(1 for index,_entry in remaining if index<before_index)
        entries=[entry for _index,entry in remaining]
        for offset,entry in enumerate(moved):entries.insert(insert_at+offset,entry)
        self.clear()
        for entry in entries:self._add_entry(entry)
        self.clearSelection()
        for entry in entries:
            if entry in moved:self._select_entry(entry)
        self.filesChanged.emit()
        return True
    def _entry(self,index):
        """Capture everything needed to rebuild one row."""
        item=self.item(index)
        return {'path':item.text(),'checked':item.checkState(),
                'size':item.data(Qt.ItemDataRole.UserRole),'tip':item.toolTip(),
                'icon':item.icon()}
    def _add_entry(self,entry):
        item=QListWidgetItem(entry['path'])
        item.setToolTip(entry['tip'] or entry['path'])
        item.setCheckState(entry['checked'])
        if entry['size'] is not None:item.setData(Qt.ItemDataRole.UserRole,entry['size'])
        if not entry['icon'].isNull():item.setIcon(entry['icon'])
        item.setSizeHint(QSize(1,46))
        self.addItem(item)
        return item
    def _select_entry(self,entry):
        for index in range(self.count()):
            if self.item(index).text()==entry['path']:
                item=self.item(index)
                self.setCurrentItem(item,QItemSelectionModel.SelectionFlag.NoUpdate)
                item.setSelected(True)
                return
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if not self.count() and event.button()==Qt.MouseButton.LeftButton and self.choose_callback:self.choose_callback()
    def checked_paths(self):
        return tuple(Path(self.item(i).text()) for i in range(self.count()) if self.item(i).checkState()==Qt.CheckState.Checked)
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count(): return
        painter = QPainter(self.viewport()); width = self.viewport().width(); height = self.viewport().height()
        kind=getattr(self,'empty_kind','')
        if kind:
            icon_name='image' if kind=='image' else 'music' if kind=='audio' else 'file'
            icon_size=46 if height>=120 else 22
            top=max(4,(height-(106 if height>=120 else icon_size))//2)
            icon(icon_name,'#b8c8df',icon_size).paint(painter,(width-icon_size)//2,top,icon_size,icon_size)
            if height>=120:
                painter.setPen(QColor('#3c4d68'))
                painter.drawText(QRect(8,top+56,width-16,24),Qt.AlignmentFlag.AlignCenter,tr(getattr(self,'empty_title','点击添加文件 或 拖拽文件到此处')))
                painter.setPen(QColor('#66758b'))
                painter.drawText(QRect(8,top+82,width-16,22),Qt.AlignmentFlag.AlignCenter,tr(getattr(self,'empty_hint','')))
            return
        top = max(8, (height - 86)//2)
        self._empty_icon.paint(painter, (width-30)//2, top, 30, 30)
        painter.setPen(QColor('#586f92'))
        painter.drawText(QRect(8, top+40, width-16, 22), Qt.AlignmentFlag.AlignCenter, tr('将文件拖放到这里'))
        painter.setPen(QColor('#66758b'))
        painter.drawText(QRect(8, top+64, width-16, 20), Qt.AlignmentFlag.AlignCenter, tr('或使用上方按钮添加文件与文件夹'))
    def paths(self): return tuple(Path(self.item(i).text()) for i in range(self.count()))
    def add_paths(self, paths):
        return self._insert_paths(paths,{str(p).casefold() for p in self.paths()})
    def _insert_paths(self,paths,known):
        n = 0
        was_blocked = self.signalsBlocked()
        self.blockSignals(True);self.setUpdatesEnabled(False)
        music_icon=icon('music');text_icon=icon('text')
        try:
            for path in map(Path, paths):
                key = str(path).casefold()
                if path.is_file() and path.suffix.lower() in self.extensions and key not in known:
                    item=QListWidgetItem(str(path));item.setToolTip(str(path));item.setCheckState(Qt.CheckState.Checked)
                    try:item.setData(Qt.ItemDataRole.UserRole,file_size(path.stat().st_size))
                    except OSError:pass
                    if path.suffix.lower() not in {'.jpg','.jpeg','.png','.webp','.bmp'}:item.setIcon(text_icon if path.suffix.lower() in {'.lrc','.srt','.vtt'} else music_icon)
                    item.setSizeHint(QSize(1,46));self.addItem(item);known.add(key);n+=1
        finally:
            self.setUpdatesEnabled(True)
            if not was_blocked:
                self.blockSignals(False)
        if n and not was_blocked: self.filesChanged.emit()
        return n
    def add_paths_batched(self,paths,done):
        paths=tuple(paths);known={str(p).casefold() for p in self.paths()};position=0;count=0
        def batch():
            nonlocal position,count
            blocked=self.signalsBlocked();self.blockSignals(True)
            try:count+=self._insert_paths(paths[position:position+200],known)
            finally:self.blockSignals(blocked)
            position+=200
            if position<len(paths):QTimer.singleShot(0,self,batch)
            else:
                if count and not blocked:self.filesChanged.emit()
                done(count)
        QTimer.singleShot(0,self,batch)
    def remove_selected(self):
        for item in self.selectedItems(): self.takeItem(self.row(item))
        self.filesChanged.emit()
    def remove_checked(self):
        checked=[index for index in range(self.count()) if self.item(index).checkState()==Qt.CheckState.Checked]
        rows=checked or [self.row(item) for item in self.selectedItems()]
        for index in sorted(set(rows),reverse=True):self.takeItem(index)
        if rows:self.filesChanged.emit()
    def clear(self): super().clear(); self.filesChanged.emit()

