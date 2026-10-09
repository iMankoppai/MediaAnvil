"""Tool-page composition shared by conversion and batch-operation workspaces."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget, QBoxLayout, QSizePolicy, QLabel, QGridLayout, QPushButton
from .layouts import button


class ActionFooter(QWidget):
    """Keep the path and action groups outside scrolling page content."""
    def __init__(self, left, right, breakpoint=900):
        super().__init__();self.breakpoint=breakpoint
        self.box=QBoxLayout(QBoxLayout.Direction.LeftToRight,self)
        self.box.setContentsMargins(0,0,0,0);self.box.setSpacing(12)
        self.box.addWidget(left,1);self.box.addWidget(right,1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        direction=QBoxLayout.Direction.TopToBottom if self.width()<self.breakpoint else QBoxLayout.Direction.LeftToRight
        if self.box.direction()!=direction:self.box.setDirection(direction)


class FooterActions(QWidget):
    """Wrap a fixed footer's action buttons into complete, readable rows."""
    def __init__(self,buttons,note=None,max_columns=4):
        super().__init__();self.buttons=buttons;self.note=note;self.max_columns=max_columns
        self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(8)
        if note:note.setWordWrap(True)
        self._columns=None;self._arrange(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
    def minimumSizeHint(self):
        size=super().minimumSizeHint();return QSize(0,size.height())
    def _arrange(self,columns):
        if self._columns==columns:return
        self._columns=columns
        while self.grid.count():self.grid.takeAt(0)
        if self.note:self.grid.addWidget(self.note,0,0,1,columns)
        for index,control in enumerate(self.buttons):
            self.grid.addWidget(control,1+index//columns,index%columns)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        required=max(button.minimumSizeHint().width() for button in self.buttons)+8
        self._arrange(max(1,min(self.max_columns,len(self.buttons),self.contentsRect().width()//max(1,required))))


def conversion_layout(page):
    output_row=page.output.parentWidget()
    action_row=page.start_button.parentWidget()
    page.step_cards[1].layout().removeWidget(output_row)
    page.step_cards[1].layout().removeWidget(action_row)
    page.footer=ActionFooter(output_row,action_row,1000)
    page.layout.addWidget(page.footer)
    page.tagline.hide()
    page.columns.box.setStretch(0,2);page.columns.box.setStretch(1,3)
    page.retry_button=button('重试失败项',lambda:page.convert_paths([r['source'] for r in page.records if not r['path']]),symbol='undo')
    page.retry_button.setEnabled(False)
    page.step_cards[2].layout().addWidget(page.retry_button)
    for card in page.step_cards:
        card.step_badge.hide()
        card.step_header.setSpacing(0)
    page.files.setStyleSheet('QListWidget { border:1px solid #e1e7f0; background:white; border-radius:7px; }')


def rename_layout(page):
    old_chips=page.chips_row
    rules=page.step_cards[1].layout();position=rules.indexOf(old_chips);rules.removeWidget(old_chips)
    page.chips_row=FooterActions(old_chips.findChildren(QPushButton),max_columns=3)
    old_chips.hide();rules.insertWidget(position,page.chips_row)
    actions=page.execute_button.parentWidget()
    page.step_cards[2].layout().removeWidget(actions)
    page.footer=actions;page.layout.addWidget(actions)
    page.export_button.setText('导出 CSV')
    page.columns.box.setStretch(0,2);page.columns.box.setStretch(1,4)
    page.tagline.hide()
    for card in page.step_cards:card.step_badge.hide()
    page.files.setStyleSheet('QListWidget { border:1px solid #e1e7f0; border-radius:7px; background:white; }')


def join_layout(page):
    page.tagline.hide()
    for card in (page.source_card,page.mode_card,page.output_card,page.result_card):
        card.step_badge.hide()
    page.files.setStyleSheet('QListWidget { border:1px solid #e1e7f0; border-radius:7px; background:white; }')
    left=page.columns.box.itemAt(0).widget().layout()
    right=page.columns.box.itemAt(1).widget().layout()
    for card in (page.mode_card,page.output_card):left.removeWidget(card)
    right.insertWidget(0,page.mode_card);right.insertWidget(1,page.output_card)
    page.columns.box.setStretch(0,1);page.columns.box.setStretch(1,2)
    for label in page.findChildren(QLabel):
        if label.objectName()=='muted':label.setWordWrap(True)
