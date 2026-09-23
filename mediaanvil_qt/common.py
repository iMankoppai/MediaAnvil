from __future__ import annotations
from pathlib import Path
import sys
from PySide6.QtCore import Qt, Signal, QThread, QRect, QSize, QStandardPaths, QEvent
from PySide6.QtGui import QPixmap, QPainter, QColor, QImageReader, QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QComboBox, QFormLayout, QListWidget,
    QAbstractItemView, QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QStyle, QStyleOptionSlider, QFrame, QSizePolicy, QBoxLayout, QListWidgetItem, QStyledItemDelegate)
from .design import icon
from .i18n import tr, current_language as _current_language


_DIALOG_SETTING_KEYS = {
    'audio': 'last_audio_directory',
    'image': 'last_image_directory',
    'subtitle': 'last_subtitle_directory',
    'output': 'last_output_directory',
}
_DIALOG_STANDARD_LOCATIONS = {
    'audio': QStandardPaths.StandardLocation.MusicLocation,
    'image': QStandardPaths.StandardLocation.PicturesLocation,
    'subtitle': QStandardPaths.StandardLocation.DocumentsLocation,
    'output': QStandardPaths.StandardLocation.DocumentsLocation,
}


def dialog_category(value):
    """Return the persisted directory category for a page or file-list kind."""
    return 'audio' if value in ('audio', 'rename', 'editor', 'preview') else value if value in _DIALOG_SETTING_KEYS else 'output'


def dialog_initial_directory(widget, category):
    """Choose a stable file-dialog start directory instead of the process cwd."""
    category = dialog_category(category)
    app = widget.window()
    saved = getattr(app, 'settings', {}).get(_DIALOG_SETTING_KEYS[category], '')
    if saved and Path(saved).is_dir():
        return str(Path(saved))
    fallback = QStandardPaths.writableLocation(_DIALOG_STANDARD_LOCATIONS[category])
    return fallback if fallback and Path(fallback).is_dir() else str(Path.home())


def remember_dialog_selection(widget, category, selection):
    """Remember the parent directory of a successful dialog selection."""
    if not selection:
        return
    category = dialog_category(category)
    selected = Path(selection)
    directory = selected if selected.is_dir() else selected.parent
    if directory.is_dir():
        app = widget.window()
        settings = getattr(app, 'settings', None)
        if settings is not None:
            settings[_DIALOG_SETTING_KEYS[category]] = str(directory.resolve())


_DIALOG_FILTER_KEYS = {
    'audio': 'last_audio_filter',
    'image': 'last_image_filter',
    'subtitle': 'last_subtitle_filter',
    'output': 'last_output_filter',
}


def dialog_filters(widget, category, filters):
    """Order file-dialog filters so the last used one is offered first.

    Windows shows the first entry of the filter list, and Qt's convenience
    dialog API cannot select an index, so remembering means reordering.
    """
    category = dialog_category(category)
    available = [value for value in filters if value]
    if len(available) < 2:
        return ';;'.join(available)
    saved = getattr(widget.window(), 'settings', {}).get(_DIALOG_FILTER_KEYS[category], '')
    if saved in available:
        available.insert(0, available.pop(available.index(saved)))
    return ';;'.join(available)


def remember_dialog_filter(widget, category, chosen):
    """Persist which filter the user actually used."""
    if not chosen:
        return
    category = dialog_category(category)
    settings = getattr(widget.window(), 'settings', None)
    if settings is not None:
        settings[_DIALOG_FILTER_KEYS[category]] = str(chosen)


def resource(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / name


def button(text, callback, primary=False, symbol=None):
    b = QPushButton(text)
    b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary: b.setProperty('primary', True)
    if symbol:b.setIcon(icon(symbol,'white' if primary else '#397bf3',18))
    if text in ('清空','清空列表','移除歌词','移除封面'):b.setProperty('danger',True)
    b.clicked.connect(callback)
    return b


def row(*widgets):
    box = QWidget(); layout = QHBoxLayout(box); layout.setContentsMargins(0, 0, 0, 0)
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


def set_picture(label, data, size=220):
    pix = QPixmap()
    if data: pix.loadFromData(data)
    if pix.isNull(): label.clear(); label.setText(tr('暂无封面 / 预览'))
    else: label.setPixmap(pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


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


def thumbnail(path, size=36):
    reader=QImageReader(str(path));reader.setAutoTransform(True)
    dimensions=reader.size()
    if dimensions.isValid():reader.setScaledSize(dimensions.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio))
    image=reader.read()
    return QIcon(QPixmap.fromImage(image)) if not image.isNull() else icon('image')


def file_size(size):
    return f'{size/1024/1024:.2f} MB' if size>=1024*1024 else f'{size/1024:.1f} KB' if size>=1024 else f'{size} B'


class StatusDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        text=tr(str(index.data() or ''))
        good=text in ('已完成','可重命名') or text.startswith('可重命名')
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
                self.item(index).setSelected(True);self.setCurrentRow(index)
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
        known = {str(p.resolve()).casefold() for p in self.paths()}; n = 0
        for path in map(Path, paths):
            key = str(path.resolve()).casefold()
            if path.is_file() and path.suffix.lower() in self.extensions and key not in known:
                item=QListWidgetItem(str(path));item.setToolTip(str(path));item.setCheckState(Qt.CheckState.Checked)
                try:item.setData(Qt.ItemDataRole.UserRole,file_size(path.stat().st_size))
                except OSError:pass
                item.setIcon(thumbnail(path) if path.suffix.lower() in {'.jpg','.jpeg','.png','.webp','.bmp'} else icon('music' if path.suffix.lower() not in {'.lrc','.srt','.vtt'} else 'text'))
                item.setSizeHint(QSize(1,46));self.addItem(item);known.add(key);n+=1
        if n: self.filesChanged.emit()
        return n
    def remove_selected(self):
        for item in self.selectedItems(): self.takeItem(self.row(item))
        self.filesChanged.emit()
    def remove_checked(self):
        checked=[index for index in range(self.count()) if self.item(index).checkState()==Qt.CheckState.Checked]
        rows=checked or [self.row(item) for item in self.selectedItems()]
        for index in sorted(set(rows),reverse=True):self.takeItem(index)
        if rows:self.filesChanged.emit()
    def clear(self): super().clear(); self.filesChanged.emit()


class Page(QWidget):
    def __init__(self, app, title, subtitle):
        super().__init__(); self.app = app; self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 12, 20, 16); self.layout.setSpacing(14)
        self.header = QWidget(); self.header_layout = QHBoxLayout(self.header); self.header_layout.setContentsMargins(0, 0, 0, 8); self.header_layout.setSpacing(14)
        name = {'音频预览':'music', '音频标签编辑':'tag', '歌词 / 字幕转换':'text',
                '音频格式转换':'convert', '图片格式转换':'image', '批量重命名':'rename', '设置':'settings'}.get(title, 'info')
        symbol = QLabel(); symbol.setObjectName('pageBadge');symbol.setAlignment(Qt.AlignmentFlag.AlignCenter);symbol.setPixmap(icon(name, '#0876ff', 30).pixmap(30, 30)); symbol.setFixedSize(56,56)
        self.header_layout.addWidget(symbol)
        titles = QVBoxLayout(); titles.setSpacing(3)
        h = QLabel(title); h.setObjectName('pageTitle'); titles.addWidget(h)
        sub = QLabel(subtitle); sub.setWordWrap(True); sub.setObjectName('muted'); titles.addWidget(sub)
        self.header_layout.addLayout(titles, 1); self.layout.addWidget(self.header)
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


class TaskReporter:
    """Callable progress reporter exposed to background jobs."""
    def __init__(self, signal, token):
        self._signal = signal; self._token = token
    @property
    def cancelled(self): return self._token.cancelled
    def __call__(self, percent, text=''):
        self.raise_if_cancelled(); self._signal.emit(float(percent), str(text))
    def raise_if_cancelled(self): self._token.raise_if_cancelled()
    def register_process(self, process): self._token.register_process(process)
    def unregister_process(self, process): self._token.unregister_process(process)


class Worker(QThread):
    result = Signal(object)
    error = Signal(str)
    cancelled = Signal()
    progress = Signal(float, str)
    def __init__(self, work, parent=None):
        from core.tasks import CancellationToken
        super().__init__(parent); self.work = work; self.token = CancellationToken()
    def request_cancel(self): self.token.cancel()
    def run(self):
        from core.tasks import TaskCancelled
        try: self.result.emit(self.work(TaskReporter(self.progress, self.token)))
        except TaskCancelled: self.cancelled.emit()
        except Exception as exc: self.error.emit(str(exc))


class ClickSlider(QSlider):
    """Seek to the clicked position instead of moving by a page step."""
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            option = QStyleOptionSlider(); self.initStyleOption(option)
            handle = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                                QStyle.SubControl.SC_SliderHandle, self)
            length = max(1, self.width() - handle.width())
            value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                round(event.position().x() - handle.width()/2), length, option.upsideDown)
            self.setValue(value)
            self.sliderMoved.emit(value)
        super().mousePressEvent(event)

    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End,
                           Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            self.sliderReleased.emit()


def table(headers):
    t = QTableWidget(0, len(headers)); t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().hide(); return t


def fill_table(t, rows):
    t.setRowCount(len(rows))
    for i, values in enumerate(rows):
        for j, value in enumerate(values):
            item = QTableWidgetItem(str(value)); item.setToolTip(str(value)); t.setItem(i, j, item)
