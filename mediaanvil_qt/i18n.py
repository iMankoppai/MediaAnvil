"""Small, dependency-free live localisation layer for the Qt interface."""
from __future__ import annotations

import re
from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QComboBox, QDialog,
    QDialogButtonBox, QLabel, QLineEdit, QListWidget, QMainWindow, QPlainTextEdit, QTableWidget, QWidget)


from .translations_en import EN as EN


_current_language = 'zh_CN'
_translator = None

# Qt ships its own catalogue for standard dialog buttons. Loading it keeps
# "Close"/"Cancel"/"OK" consistent with the selected language instead of
# falling back to Qt's built-in English source strings.
_QT_CATALOGUES = {'zh_CN': 'zh_CN', 'en_US': 'en'}
_STANDARD_BUTTON_TEXT = {
    'zh_CN': {
        QDialogButtonBox.StandardButton.Ok: '确定', QDialogButtonBox.StandardButton.Cancel: '取消',
        QDialogButtonBox.StandardButton.Close: '关闭', QDialogButtonBox.StandardButton.Save: '保存',
        QDialogButtonBox.StandardButton.Open: '打开', QDialogButtonBox.StandardButton.Yes: '是',
        QDialogButtonBox.StandardButton.No: '否', QDialogButtonBox.StandardButton.Apply: '应用',
        QDialogButtonBox.StandardButton.Reset: '重置', QDialogButtonBox.StandardButton.Discard: '放弃',
        QDialogButtonBox.StandardButton.Help: '帮助',
    },
    'en_US': {
        QDialogButtonBox.StandardButton.Ok: 'OK', QDialogButtonBox.StandardButton.Cancel: 'Cancel',
        QDialogButtonBox.StandardButton.Close: 'Close', QDialogButtonBox.StandardButton.Save: 'Save',
        QDialogButtonBox.StandardButton.Open: 'Open', QDialogButtonBox.StandardButton.Yes: 'Yes',
        QDialogButtonBox.StandardButton.No: 'No', QDialogButtonBox.StandardButton.Apply: 'Apply',
        QDialogButtonBox.StandardButton.Reset: 'Reset', QDialogButtonBox.StandardButton.Discard: 'Discard',
        QDialogButtonBox.StandardButton.Help: 'Help',
    },
}


def set_current_language(language):
    global _current_language
    _current_language = language if language in ('zh_CN', 'en_US') else 'zh_CN'


def current_language():
    """The language in effect, for code that must format its own text."""
    return _current_language


def install_standard_translations(app, language):
    """Load Qt's bundled catalogue so standard buttons follow the interface language."""
    global _translator
    if app is None:
        return False
    if _translator is not None:
        app.removeTranslator(_translator)
        _translator = None
    catalogue = _QT_CATALOGUES.get(language)
    if not catalogue:
        return False
    translator = QTranslator()
    if not translator.load(f'qtbase_{catalogue}', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        return False
    app.installTranslator(translator)
    _translator = translator
    return True


def localize_dialog_buttons(root, language):
    """Pin standard button text so it always matches the selected language."""
    labels = _STANDARD_BUTTON_TEXT.get(language) or _STANDARD_BUTTON_TEXT['en_US']
    for box in root.findChildren(QDialogButtonBox):
        for standard, text in labels.items():
            control = box.button(standard)
            if control is not None:
                control.setText(text)


def tr(text, language=None):
    """Translate an exact UI string and a few common dynamic status patterns."""
    value = str(text)
    language = language or _current_language
    if language != 'en_US':
        return value
    if value in EN:
        return EN[value]
    if '\n' in value:
        return '\n'.join(tr(line, language) for line in value.split('\n'))
    patterns = (
        (r'^检查完成：(\d+) 个文件，(\d+) 个完整，(\d+) 个存在缺失。$',r'Check complete: \1 files, \2 complete, \3 with missing items.'),
        (r'^成功 (\d+) 个 · 失败 (\d+) 个 · 未完成 (\d+) 个 · 时间 (.*)$',r'\1 succeeded · \2 failed · \3 unfinished · Time \4'),
        (r'^共 (\d+) 项 · 每页 200 项$',r'\1 items · 200 per page'),
        (r'^(\d+) 个文件$', r'\1 files'),
        (r'^已导入 (\d+) 个文件$', r'Imported \1 files'),
        (r'^扫描完成：(\d+) 首音频$', r'Scan complete: \1 audio files'),
        (r'^转换完成：成功 (\d+) 个，失败 (\d+) 个 · 耗时 ([\d.]+) 秒$', r'Complete: \1 succeeded, \2 failed · \3 s'),
        (r'^(\d+) 个文件 · 点击刷新预览$', r'\1 files · Refresh to preview'),
        (r'^(\d+) 项 · 已勾选 (\d+) 项$', r'\1 items · \2 selected'),
        (r'^完成：(.*)（透明区域已填白）$', r'Completed: \1 (transparent areas filled with white)'),
        (r'^跳过：(.*)（无已选关联文件）$', r'Skipped: \1 (no associated file selected)'),
        (r'^完成：(.*)$', r'Completed: \1'),
        (r'^失败：(.*)$', r'Failed: \1'),
        (r'^跳过：(.*)$', r'Skipped: \1'),
        (r'^恢复：(.*)$', r'Restored: \1'),
        (r'^已保存：(.*)$', r'Saved: \1'),
        (r'^已导出：(.*)$', r'Exported: \1'),
        (r'^已另存为：(.*)$', r'Saved as: \1'),
        (r'^预览已导出：(.*)$', r'Preview exported: \1'),
        (r'^设置未能保存：(.*)$', r'Unable to save settings: \1'),
        (r'^保存失败：(.*)$', r'Save failed: \1'),
        (r'^缺少字段：(.*)$', r'Missing fields: \1'),
        (r'^歌词已偏移 (.*) 秒，保存后写入音频$', r'Lyrics shifted by \1 s; saved to the audio afterwards'),
        (r'^将合并 (\d+) 个文件，按列表顺序拼接（可拖动或上移/下移调整）$', r'Joining \1 files in list order (drag or use Move Up/Down to reorder)'),
        (r'^歌词已偏移 (.*) 秒（仅预览，未写入文件）$', r'Lyrics shifted by \1 s (preview only; nothing written)'),
        (r'^队列 \((\d+)\)$', r'Queue (\1)'),
        (r'^播放队列 \((\d+)\)$', r'Queue (\1)'),
        (r'^(\d+) 分钟$', r'\1 min'),
        (r'^(\d+) 分钟后停止$', r'stops in \1 min'),
        (r'^上次播放至 (.*)$', r'Last played to \1'),
    )
    for pattern, replacement in patterns:
        if re.match(pattern, value):
            return re.sub(pattern, replacement, value)
    return value


def _source(obj, key, value):
    store = getattr(obj, '_i18n_sources', None)
    if store is None:
        store = {}; obj._i18n_sources = store
    if key not in store:
        store[key] = value
    return store[key]


def apply_language(root: QWidget, language: str):
    """Apply language live while retaining original Chinese source strings."""
    set_current_language(language)
    install_standard_translations(QApplication.instance(), language)
    widgets = [root, *root.findChildren(QWidget)]
    for widget in widgets:
        if isinstance(widget, (QMainWindow, QDialog)):
            widget.setWindowTitle(tr(_source(widget, 'windowTitle', widget.windowTitle()), language))
        if isinstance(widget, (QLabel, QAbstractButton)):
            widget.setText(tr(_source(widget, 'text', widget.text()), language))
        if isinstance(widget, (QLineEdit, QPlainTextEdit)):
            original = _source(widget, 'placeholder', widget.placeholderText())
            widget.setPlaceholderText(tr(original, language))
        if isinstance(widget, QAbstractSpinBox):
            prefix = _source(widget, 'prefix', widget.prefix()); suffix = _source(widget, 'suffix', widget.suffix())
            widget.setPrefix(tr(prefix, language)); widget.setSuffix(tr(suffix, language))
        tooltip = widget.toolTip()
        if tooltip or getattr(widget, '_i18n_sources', {}).get('tooltip'):
            widget.setToolTip(tr(_source(widget, 'tooltip', tooltip), language))
        if isinstance(widget, QComboBox):
            original = _source(widget, 'placeholder', widget.placeholderText())
            widget.setPlaceholderText(tr(original, language))
            sources = getattr(widget, '_i18n_items', None)
            if sources is None or len(sources) != widget.count():
                sources = [widget.itemText(i) for i in range(widget.count())]; widget._i18n_items = sources
            for index, source in enumerate(sources):
                widget.setItemText(index, tr(source, language))
        if isinstance(widget, QTableWidget):
            sources = getattr(widget, '_i18n_headers', None)
            if sources is None:
                sources = [widget.horizontalHeaderItem(i).text() if widget.horizontalHeaderItem(i) else '' for i in range(widget.columnCount())]
                widget._i18n_headers = sources
            for index, source in enumerate(sources):
                if widget.horizontalHeaderItem(index): widget.horizontalHeaderItem(index).setText(tr(source, language))
        if isinstance(widget, QListWidget):
            sources = getattr(widget, '_i18n_list_items', None)
            if sources is None or len(sources) != widget.count():
                sources = [widget.item(i).text() for i in range(widget.count())]; widget._i18n_list_items = sources
            for index, source in enumerate(sources):
                widget.item(index).setText(tr(source, language))
        for name in ('empty_title', 'empty_hint'):
            if hasattr(widget, name):
                source = _source(widget, name, getattr(widget, name)); setattr(widget, name, tr(source, language))
        widget.update()
    # Text the pages build themselves, such as "Queue (8)", is not reachable by
    # walking widgets, so each page may expose a refresh hook for it.
    for widget in widgets:
        hook = getattr(widget, 'refresh_translated_text', None)
        if callable(hook):
            hook()
    localize_dialog_buttons(root, language)
