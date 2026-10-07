"""Selectable media inspection results feeding the existing repair tools."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QCheckBox, QSpinBox, QHeaderView

from .common import button, combo, row, table, fill_table
from .i18n import apply_language


class MediaCheckDialog(QDialog):
    repair = Signal(object)
    edit = Signal(object)
    refresh = Signal()

    def __init__(self, app):
        super().__init__(app);self.app=app;self.rows=[];self.selected=set();self.visible=[];self.page_rows=[]
        self.setWindowTitle('媒体检查结果');self.resize(900,560);self.setMinimumSize(650,420)
        layout=QVBoxLayout(self)
        self.summary=QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.filter=combo([('存在缺失','problems'),('全部文件','all'),('缺歌词','lyrics'),('缺封面','cover'),
                           ('缺标题','title'),('缺歌手','artist'),('缺专辑','album'),('标签不可读','tags')])
        self.filter.setMinimumWidth(180)
        self.search=QLineEdit();self.search.setPlaceholderText('搜索文件名…')
        self.select_all=QCheckBox('全选当前结果')
        layout.addWidget(row(self.filter,self.search,self.select_all))
        self.table=table(['选择','文件','缺失项','路径']);layout.addWidget(self.table,1)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.page_number=QSpinBox();self.page_number.setMinimum(1);self.page_number.setMaximum(1)
        self.page_label=QLabel()
        layout.addWidget(row(QLabel('页码'),self.page_number,self.page_label))
        self.page_number.valueChanged.connect(self.render_page)
        self.repair_button=button('将勾选文件载入批量修复',self.choose_repair,True)
        self.edit_button=button('编辑当前音频',self.choose_edit)
        self.refresh_button=button('重新检查',self.refresh.emit)
        layout.addWidget(row(self.repair_button,self.edit_button,self.refresh_button,button('关闭',self.hide)))
        self.filter.currentIndexChanged.connect(self.filter_rows);self.search.textChanged.connect(self.filter_rows)
        self.select_all.toggled.connect(self.select_visible)
        self.table.itemChanged.connect(self.selection_changed);self.table.currentCellChanged.connect(self.update_actions)
        self.table.cellDoubleClicked.connect(lambda r,c:self.choose_edit())
        apply_language(self,app.settings['language'])

    def set_rows(self, rows):
        self.rows=list(rows);self.selected.intersection_update(r.audio for r in rows);self.filter_rows()
        complete=sum(not r.has_problems for r in self.rows)
        self.summary.setText(self.app.t(f'检查完成：{len(rows)} 个文件，{complete} 个完整，{len(rows)-complete} 个存在缺失。'))

    def refresh_translated_text(self):
        page=self.page_number.value();self.set_rows(self.rows);self.page_number.setValue(page)

    def render_page(self,*args):
        start=(self.page_number.value()-1)*200;self.page_rows=self.visible[start:start+200]
        self.table.blockSignals(True)
        labels={'lyrics':'缺歌词','cover':'缺封面','title':'缺标题','artist':'缺歌手','album':'缺专辑','tags':'标签不可读'}
        fill_table(self.table,[('',r.audio.name,'、'.join(self.app.t(labels[p]) for p in r.problems) or self.app.t('完整'),str(r.audio)) for r in self.page_rows])
        for i,r in enumerate(self.page_rows):
            self.table.item(i,0).setCheckState(Qt.CheckState.Checked if r.audio in self.selected else Qt.CheckState.Unchecked)
            self.table.item(i,2).setToolTip(r.tag_error or self.table.item(i,2).text())
        self.table.blockSignals(False);self.update_actions()
        self.page_label.setText(self.app.t(f'共 {len(self.visible)} 项 · 每页 200 项'))

    def filter_rows(self,*args):
        choice=self.filter.currentData();query=self.search.text().strip().casefold()
        self.visible=[r for r in self.rows if (choice=='all' or choice=='problems' and r.has_problems or choice in r.problems) and query in str(r.audio).casefold()]
        self.page_number.blockSignals(True);self.page_number.setMaximum(max(1,(len(self.visible)+199)//200));self.page_number.setValue(1);self.page_number.blockSignals(False)
        self.select_all.blockSignals(True);self.select_all.setChecked(False);self.select_all.blockSignals(False)
        self.render_page()

    def selected_paths(self):
        return tuple(r.audio for r in self.visible if r.audio in self.selected)

    def select_visible(self,checked):
        if checked:self.selected.update(r.audio for r in self.visible)
        else:self.selected.difference_update(r.audio for r in self.visible)
        self.render_page()

    def selection_changed(self,item):
        if item.column()==0 and item.row()<len(self.page_rows):
            path=self.page_rows[item.row()].audio
            if item.checkState()==Qt.CheckState.Checked:self.selected.add(path)
            else:self.selected.discard(path)
        self.update_actions()

    def update_actions(self,*args):
        self.repair_button.setEnabled(bool(self.selected_paths()))
        current=self.table.currentRow();self.edit_button.setEnabled(0<=current<len(self.page_rows))

    def choose_repair(self):
        paths=self.selected_paths()
        if paths:self.repair.emit(paths)

    def choose_edit(self):
        i=self.table.currentRow()
        if 0<=i<len(self.page_rows):self.edit.emit(self.page_rows[i].audio)
