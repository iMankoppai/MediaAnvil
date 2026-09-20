"""Small, dependency-free live localisation layer for the Qt interface."""
from __future__ import annotations

import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QComboBox, QDialog, QLabel, QLineEdit,
    QListWidget, QMainWindow, QPlainTextEdit, QTableWidget, QWidget)


EN = {
    'MediaAnvil Qt — 多媒体工具箱': 'MediaAnvil Qt — Multimedia Toolbox',
    '音频预览': 'Audio Preview', '音频标签编辑': 'Audio Tag Editor',
    '歌词 / 字幕转换': 'Lyrics / Subtitle Converter', '音频格式转换': 'Audio Converter',
    '图片格式转换': 'Image Converter', '批量重命名': 'Batch Rename',
    '设置': 'Settings', '关于': 'About', '关于 MediaAnvil': 'About MediaAnvil',
    '本地播放 · 同步歌词 · 点击歌词跳转': 'Local playback · Synced lyrics · Click a line to seek',
    '编辑标签、歌词和封面；先预览，再保存。支持同目录智能匹配和文件夹批量写入。': 'Edit tags, lyrics and artwork; preview before saving. Supports smart matching and batch updates.',
    '批量转换 MP3、WAV、FLAC、M4A、AAC、OGG 等音频格式': 'Batch convert MP3, WAV, FLAC, M4A, AAC, OGG and more',
    '支持 JPG、PNG、WebP、BMP 批量互转': 'Batch convert JPG, PNG, WebP and BMP images',
    '支持 LRC、SRT、VTT 相互转换': 'Convert between LRC, SRT and VTT',
    '使用音频标签生成文件名；预览冲突后执行，可撤销最近一次重命名。': 'Generate filenames from audio tags, preview conflicts, and undo the latest batch.',
    '调整应用程序的常用选项': 'Adjust common application options',
    '让日常媒体整理更轻松': 'Make everyday media organisation easier',
    '一个简洁、离线的多媒体工具箱。\n\n播放音频、同步歌词，编辑标签与封面，整理文件名，\n以及完成音频、图片和歌词字幕的格式转换。\n\n媒体文件始终在本机处理，默认保留原文件。': 'A clean, offline multimedia toolbox.\n\nPlay audio with synced lyrics, edit tags and artwork, organise filenames,\nand convert audio, images, lyrics and subtitles.\n\nMedia files stay on this computer and source files are preserved by default.',
    '使用说明': 'User Guide', '第三方组件说明': 'Third-party Notices',
    '高效转换 · 让音频处理更简单  —': 'Efficient conversion · Simpler audio processing  —',
    '高效转换 · 让图片更好地使用  —': 'Efficient conversion · Images that work everywhere  —',
    '高效转换 · 让字幕与歌词更通用  —': 'Efficient conversion · More compatible lyrics and subtitles  —',
    '批量处理 · 让文件命更规范  —': 'Batch processing · Consistent filenames  —',

    '选择文件': 'Select Files', '选择音频文件': 'Select Audio Files', '选择图片': 'Select Images',
    '选择歌词 / 字幕文件': 'Select Lyrics / Subtitle Files', '选择或拖入本地音频文件': 'Select or drop a local audio file',
    '选择音频文件…': 'Choose Audio…', '添加文件…': 'Add Files…', '添加…': 'Add…',
    '添加文件': 'Add Files', '添加图片': 'Add Images', '移除': 'Remove', '移除选中': 'Remove Selected',
    '清空': 'Clear', '全选文件': 'Select All Files', '全选可重命名项': 'Select All Renameable Items',
    '添加文件夹…': 'Add Folder…', '移除选中的文件': 'Remove selected files', '清空文件列表': 'Clear file list',
    '移除已勾选的文件': 'Remove checked files',
    '可从资源管理器拖入文件或文件夹': 'Drag files or folders here from File Explorer',
    '点击添加文件 或 拖拽文件到此处': 'Click Add Files or drop files here',
    '点击添加图片 或 拖拽文件到此处': 'Click Add Images or drop files here',
    '支持 MP3、FLAC、M4A、WAV 等音频文件': 'Supports MP3, FLAC, M4A, WAV and more',
    '支持 .lrc、.srt、.vtt 等字幕文件': 'Supports .lrc, .srt and .vtt subtitle files',
    '支持 .mp3、.wav、.flac、.m4a、.aac、.ogg 等音频文件': 'Supports .mp3, .wav, .flac, .m4a, .aac and .ogg audio files',
    '支持 .jpg、.jpeg、.png、.webp、.bmp 等图片文件': 'Supports .jpg, .jpeg, .png, .webp and .bmp image files',
    '支持读取音频标签信息（MP3、FLAC、M4A、WAV 等）': 'Reads audio tags from MP3, FLAC, M4A, WAV and more',
    '支持 MP3、WAV、FLAC、M4A、AAC、OGG 等格式，可批量添加文件进行转换': 'Supports MP3, WAV, FLAC, M4A, AAC and OGG batch conversion',
    '支持 JPG、PNG、WebP、BMP 格式，可批量添加文件进行转换': 'Supports JPG, PNG, WebP and BMP batch conversion',
    '支持 LRC、SRT、VTT 格式，可批量添加文件进行转换': 'Supports LRC, SRT and VTT batch conversion',

    '转换设置': 'Conversion Settings', '设置输出格式及相关选项': 'Set the output format and related options',
    '输出格式': 'Output Format', '码率 / 质量': 'Bitrate / Quality', '比特率': 'Bitrate', '采样率': 'Sample Rate',
    '声道': 'Channels', '单声道': 'Mono', '立体声': 'Stereo', '保持原始': 'Keep Original',
    '保留音频标签': 'Preserve Audio Tags', '图片质量': 'Image Quality',
    '保持原始宽高；透明图片转为 JPG / BMP 时使用白色背景。': 'Keeps original dimensions; transparent images use a white background for JPG / BMP.',
    '高级设置：LRC 最后一句持续时间': 'Advanced: duration of final LRC line',
    '输出目录': 'Output Folder', '留空：保存到各源文件所在文件夹': 'Leave blank to save beside each source file',
    '浏览…': 'Browse…', '秒': 's', ' 秒': ' s',
    '转换完成后打开输出目录': 'Open output folder when finished', '开始批量转换': 'Start Batch Conversion',
    '转换完成': 'Conversion Results', '转换结果预览': 'Conversion Result Preview',
    '选择文件查看转换结果，支持另存为': 'Select a file to view its result or save a copy',
    '暂无转换记录': 'No conversion history', '选择转换结果': 'Select a conversion result',
    '结果另存为…': 'Save Result As…', '文件名': 'Filename', '格式': 'Format', '大小': 'Size', '状态': 'Status',
    '转换完成后，文件内容将在这里显示': 'Converted content will appear here',
    '转换完成后，文件将显示在这里': 'Converted files will appear here',
    '请选择左侧文件并进行转换': 'Select files on the left and start conversion',
    '选择转换结果查看预览': 'Select a result to preview it', '转换详情与失败原因': 'Conversion details and failure reasons',
    '打开所在位置': 'Open File Location', '再次转换': 'Convert Again', '转换失败': 'Conversion Failed',

    '歌曲信息': 'Track Information', '尚未选择音频': 'No audio selected', '选择一首音频，开始聆听': 'Select an audio file to begin',
    '播放控制': 'Playback Controls', '播放 / 暂停（空格）': 'Play / Pause (Space)',
    '后退 30 秒': 'Back 30 seconds', '前进 30 秒': 'Forward 30 seconds',
    '等待载入音频': 'Waiting for audio', '同步歌词': 'Synced Lyrics',
    '选择音频后，在这里查看同步歌词': 'Synced lyrics will appear here after selecting audio',
    '暂无同步歌词，可正常播放音频': 'No synced lyrics; audio playback is still available',

    '基本信息': 'Basic Information', '歌名': 'Title', '歌手': 'Artist', '专辑': 'Album',
    '请输入歌名': 'Enter title', '请输入歌手': 'Enter artist', '请输入专辑': 'Enter album',
    '歌词': 'Lyrics', '封面': 'Artwork', '尚未读取歌词': 'Lyrics not loaded', '暂无封面': 'No artwork',
    '导入 LRC…': 'Import LRC…', '导入歌词 / 字幕…': 'Import Lyrics / Subtitles…', '导出歌词…': 'Export Lyrics…', '选择图片…': 'Choose Image…', '导出图片…': 'Export Image…',
    '自由矩形裁剪封面': 'Free Crop Artwork',
    '拖拽创建或移动矩形裁剪框，也可输入精确像素。': 'Drag to create or move a crop rectangle, or enter exact pixel values.',
    '裁剪区域（像素）': 'Crop Area (pixels)', '横向起点': 'Left', '纵向起点': 'Top', '宽度': 'Width', '高度': 'Height',
    '恢复完整图片': 'Restore Full Image',
    '移除歌词（保存时生效）': 'Remove lyrics when saving', '移除封面（保存时生效）': 'Remove artwork when saving',
    '智能匹配关联文件': 'Smart File Matching', '展开匹配区域': 'Expand Matching Area', '收起匹配区域': 'Collapse Matching Area',
    '自动查找同目录歌词与封面；多个候选需要手动选择。': 'Find lyrics and artwork in the same folder; choose manually when multiple matches exist.',
    '扫描音乐文件夹…': 'Scan Music Folder…', '音频': 'Audio', '歌词候选': 'Lyrics Candidates', '封面候选': 'Artwork Candidates',
    '清空文件': 'Clear Files', '已清空匹配文件列表': 'Matching file list cleared',
    '不选择 / 保持原内容': 'None / Keep Existing', '当前音频': 'Current Audio', '应用到编辑': 'Apply to Editor',
    '有多个候选时，请明确选择；未选择不会自动写入。': 'When several matches exist, choose one explicitly; no selection changes nothing.',
    '批量写入歌词': 'Batch Write Lyrics', '批量写入封面': 'Batch Write Artwork', '全部写入': 'Write All',
    '另存为（推荐）': 'Save As', '覆盖原文件': 'Overwrite Source', '保存方式': 'Save Mode',
    '取消修改': 'Discard Changes', '保存到音频': 'Save to Audio',
    '选择音频后显示格式、时长、码率与标签信息': 'Format, duration, bitrate and tag details appear after selecting audio',

    '重命名规则': 'Rename Rules', '设置文件名模板，使用下方变量快速插入': 'Set a filename template and insert variables below',
    '重命名模板': 'Rename Template', '缺少字段时使用原文件名代替': 'Use original filename for missing fields',
    '包含子文件夹': 'Include Subfolders', '预览结果': 'Preview Results',
    '预览结果会根据规则自动更新': 'Preview results update from the rename rules', '刷新预览': 'Refresh Preview',
    '搜索文件名…': 'Search filenames…', '添加文件后，点击刷新预览': 'Add files, then refresh the preview',
    '选择': 'Select', '原文件名': 'Original Filename', '新文件名': 'New Filename',
    '撤销上次重命名': 'Undo Last Rename', '导出预览': 'Export Preview', '开始重命名': 'Start Renaming',

    '常规': 'General', '应用的基本行为设置': 'Basic application behaviour',
    '默认输出位置': 'Output Location', '跟随源文件': 'Source Folder', '指定文件夹': 'Custom Folder',
    '指定目录': 'Custom Folder', '选择默认输出文件夹': 'Choose a default output folder',
    '默认保存方式': 'Save Mode',
    '语言': 'Language', '简体中文': 'Chinese',
    '音频转换': 'Audio Conversion', '设置音频格式转换的默认参数': 'Default audio conversion parameters',
    '默认 MP3 码率': 'Default MP3 Bitrate', '默认 AAC / M4A 码率': 'Default AAC / M4A Bitrate',
    '默认保持原采样率': 'Keep Original Sample Rate', '默认保持原声道': 'Keep Original Channels',
    '保留音频元数据（标签信息）': 'Preserve Metadata',
    '图片转换': 'Image Conversion', '设置图片格式转换的默认参数': 'Default image conversion parameters',
    '默认 JPG 质量': 'Default JPG Quality', '默认 WebP 质量': 'Default WebP Quality',
    '保持原始尺寸': 'Keep Original Dimensions', '不缩放图片，输出与原图相同的尺寸': 'Do not resize; output uses the source dimensions',
    '歌词与预览': 'Lyrics & Preview', '设置歌词处理和音频预览的默认参数': 'Default lyrics and audio preview parameters',
    'LRC 最后一句持续时间': 'Final LRC Duration', '默认音量': 'Default Volume',
    '自动加载同名歌词': 'Auto-load Matching Lyrics',
    '优先使用 MP3 内嵌歌词': 'Prefer Embedded MP3 Lyrics',
    '文件扫描': 'File Scanning', '扫描文件时的默认行为': 'Default file scanning behaviour',
    'ⓘ  修改设置后将自动应用到后续任务': 'ⓘ  Changes automatically apply to subsequent tasks',
    '恢复默认设置': 'Restore Defaults', '保存设置': 'Save Settings',
    '就绪 · 可直接拖入文件或文件夹': 'Ready · Drop files or folders here', '就绪': 'Ready', '正在处理…': 'Processing…',
    '设置已保存并应用': 'Settings saved and applied', '当前任务仍在处理，请等待完成。': 'A task is still running. Please wait for it to finish.',
    '没有找到当前页面支持的文件。': 'No supported files were found for this page.',
    '后台任务尚未完成，请完成后再关闭窗口。': 'A background task is still running. Close the window after it finishes.',
    '结果显示失败：': 'Unable to display result: ', '处理失败：': 'Task failed: ',
    '音频与歌词已载入': 'Audio and lyrics loaded', '音频已载入 · 暂无同步歌词': 'Audio loaded · No synced lyrics',
    '已完成': 'Completed', '失败': 'Failed', '待预览': 'Pending Preview', '可重命名': 'Ready to Rename',
    '无需修改': 'No Change Needed', '缺少标签': 'Missing Tags', '无法读取': 'Unreadable', '文件名冲突': 'Filename Conflict',
    '请先添加并勾选要转换的文件。': 'Add and select at least one file to convert.',
    '请先选择一个转换成功的结果。': 'Select a successfully converted result first.',
    '请先添加音频。': 'Add audio files first.', '请先生成预览。': 'Generate a preview first.',
    '选择文件夹': 'Choose Folder', '选择输出文件夹': 'Choose Output Folder',
    '支持的文件': 'Supported Files', '此格式无编码参数': 'This format has no encoding parameter',
    '结果另存为': 'Save Result As', '完成时间：': 'Completed at: ',
    '选择音频': 'Choose Audio', '音频 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus)': 'Audio (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus)',
    '音频 (*.mp3 *.flac *.m4a *.ogg *.opus *.wav *.aac)': 'Audio (*.mp3 *.flac *.m4a *.ogg *.opus *.wav *.aac)',
    '导入歌词 / 字幕': 'Import Lyrics / Subtitles', '歌词 / 字幕 (*.lrc *.srt *.vtt)': 'Lyrics / Subtitles (*.lrc *.srt *.vtt)',
    '选择封面': 'Choose Artwork', '图片 (*.png *.jpg *.jpeg *.webp *.bmp)': 'Images (*.png *.jpg *.jpeg *.webp *.bmp)',
    '选择导出文件夹': 'Choose Export Folder', '扫描音乐文件夹': 'Scan Music Folder',
    '请先选择封面或载入带封面的音频。': 'Choose artwork or load an audio file with embedded artwork first.',
    '请先选择音频。': 'Choose an audio file first.', '该格式当前只支持读取信息。': 'This format is currently read-only.',
    '批量写入结果': 'Batch Write Results', '导出重命名预览': 'Export Rename Preview',
    '重命名结果': 'Rename Results', '撤销结果': 'Undo Results', '路径': 'Path', '说明': 'Details', '已勾选': 'Selected',
    '请选择自定义输出文件夹。': 'Choose a custom output folder.',
    '仅支持导入 LRC、SRT 或 VTT 歌词 / 字幕文件': 'Only LRC, SRT, and VTT lyrics or subtitle files can be imported.',
    '暂无封面 / 预览': 'No artwork / preview', '将文件拖放到这里': 'Drop files here',
    '或使用上方按钮添加文件与文件夹': 'Or use the buttons above to add files and folders',
    '可重命名（自动避让）': 'Ready to Rename (Conflict Avoided)',
    '文件名已经符合模板': 'Filename already matches the template',
    '批次内有多个文件生成了同名目标': 'Multiple files in this batch produce the same target name',
    '音频文件不存在或无法访问。': 'The audio file does not exist or cannot be accessed.',
    '源文件不存在或无法访问': 'The source file does not exist or cannot be accessed',
}

_current_language = 'zh_CN'


def set_current_language(language):
    global _current_language
    _current_language = language if language in ('zh_CN', 'en_US') else 'zh_CN'


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
