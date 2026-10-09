"""Task-center and About layouts, independent of task scheduling and persistence."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QSpinBox, QHeaderView
from .page import Page
from .layouts import group, row, button, combo, Columns
from .table_widgets import table
from .common import resource
from . import __version__


def task_center(app):
    page=Page(app,'任务中心','查看批量任务进度，重试未完成的文件')
    queued,queued_body=group('待执行任务')
    app.queue_table=table(['任务','文件数']);app.queue_table.setMaximumHeight(120)
    app.queue_table.setMinimumHeight(80);queued_body.addWidget(app.queue_table)
    queued_body.addWidget(row(button('上移待执行任务',lambda:app.move_queued_task(-1)),
        button('下移待执行任务',lambda:app.move_queued_task(1)),button('取消待执行任务',app.cancel_queued_task)))
    page.layout.addWidget(queued)
    history,body=group('任务记录')
    app.task_picker=combo([]);app.task_picker.currentIndexChanged.connect(app.select_task_history);body.addWidget(app.task_picker)
    app.task_kind=QLabel('暂无批量任务');app.task_kind.setObjectName('muted');body.addWidget(app.task_kind)
    app.task_summary=QLabel('转换和重命名完成后，这里会显示每个文件的状态。')
    app.task_summary.setWordWrap(True);app.task_summary.setObjectName('notice');body.addWidget(app.task_summary)
    app.task_table=table(['文件','状态','说明','输出路径']);app.task_table.setMinimumHeight(200)
    app.task_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
    for col in (1,2):app.task_table.horizontalHeader().setSectionResizeMode(col,QHeaderView.ResizeMode.ResizeToContents)
    body.addWidget(app.task_table,1)
    app.task_page_number=QSpinBox();app.task_page_number.setRange(1,1)
    app.task_page_number.valueChanged.connect(app.update_task_page);body.addWidget(app.task_page_number)
    app.task_retry=button('重试未完成项',app.retry_failed,True,'undo');app.task_retry.setEnabled(False)
    body.addWidget(row(app.task_retry,button('打开结果位置',app.open_task_output,symbol='folder'),
        button('重新检查结果',app.check_task_outputs,symbol='convert'),button('导出处理报告',app.export_task_report,symbol='file')))
    page.layout.addWidget(history,1)
    page.header_layout.addWidget(button('整理音乐文件夹…',app.open_organizer,symbol='folder'))
    return page


def about_page(app):
    page=Page(app,'关于 MediaAnvil','让日常媒体整理更轻松')
    card,body=group('')
    identity,identity_body=group('')
    identity.setStyleSheet('QFrame#card { border:0; }')
    mark=QLabel();mark.setPixmap(QIcon(str(resource('assets/qt/brand.svg'))).pixmap(96,96))
    identity_body.addWidget(mark,0,Qt.AlignmentFlag.AlignCenter)
    name=QLabel('MediaAnvil');name.setObjectName('pageTitle');identity_body.addWidget(name,0,Qt.AlignmentFlag.AlignCenter)
    version=QLabel(f'v{__version__}');version.setObjectName('muted');identity_body.addWidget(version,0,Qt.AlignmentFlag.AlignCenter)
    caption=QLabel('离线多媒体工具箱');caption.setObjectName('muted');identity_body.addWidget(caption,0,Qt.AlignmentFlag.AlignCenter)
    text=QLabel('播放音频、同步歌词，编辑标签与封面，整理文件名，\n以及完成音频、图片和歌词字幕的格式转换。\n\n媒体文件始终在本机处理，默认保留原文件。')
    text.setWordWrap(True);text.setStyleSheet('font-size:16px;')
    identity_row=Columns(identity,text,700);identity_row.box.setStretch(0,1);identity_row.box.setStretch(1,2)
    body.addStretch(1);body.addWidget(identity_row);body.addStretch(1)
    guide=button('使用说明',lambda:app.show_document('使用说明','USER_GUIDE.md','USER_GUIDE.en.md'),symbol='folder')
    notices=button('第三方组件说明',lambda:app.show_document('第三方组件说明','THIRD_PARTY_NOTICES.md'),symbol='file')
    for action in (guide,notices):
        action.setMinimumHeight(34);body.addWidget(action)
    local=QLabel('●  本地处理 · 无需上传媒体文件');local.setObjectName('notice');body.addWidget(local)
    page.layout.addWidget(card,1)
    return page
