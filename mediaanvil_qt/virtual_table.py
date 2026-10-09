"""Large result tables keep row data in a model, creating cells on demand."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import QTableView, QAbstractItemView, QHeaderView


class Cell:
    def __init__(self,table,row,column):self.table=table;self.r=row;self.c=column
    def text(self):return str(self.table.rows[self.r][self.c])
    def row(self):return self.r
    def column(self):return self.c
    def data(self,role):return self.table.values.get((self.r,self.c,int(role)))
    def setData(self,role,value):
        self.table.values[self.r,self.c,int(role)]=value
        visible=self.table.source_to_visible.get(self.r)
        if visible is not None:
            index=self.table.model().index(visible,self.c)
            self.table.model().dataChanged.emit(index,index,[int(role)])
        self.table.itemChanged.emit(self)
    def setText(self,value):
        self.table.rows[self.r][self.c]=str(value);self.setData(Qt.ItemDataRole.DisplayRole,str(value))
    def setToolTip(self,value):self.setData(Qt.ItemDataRole.ToolTipRole,str(value))
    def toolTip(self):return self.data(Qt.ItemDataRole.ToolTipRole) or self.text()
    def setForeground(self,value):self.setData(Qt.ItemDataRole.ForegroundRole,value)
    def setCheckState(self,value):self.setData(Qt.ItemDataRole.CheckStateRole,value)
    def checkState(self):return self.data(Qt.ItemDataRole.CheckStateRole) or Qt.CheckState.Unchecked
    def flags(self):return self.table.cell_flags.get((self.r,self.c),Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsUserCheckable)
    def setFlags(self,value):self.table.cell_flags[self.r,self.c]=value


class RowsModel(QAbstractTableModel):
    def __init__(self,table):super().__init__(table);self.table=table
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.table.visible_rows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.table.headers)
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():return None
        cell=self.table.item(self.table.source_row(index.row()),index.column())
        if role==Qt.ItemDataRole.DisplayRole:return cell.text()
        if role==Qt.ItemDataRole.ToolTipRole:return cell.toolTip()
        return cell.data(role)
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if role==Qt.ItemDataRole.DisplayRole and orientation==Qt.Orientation.Horizontal:return self.table.headers[section]
        return None
    def flags(self,index):
        if not index.isValid():return Qt.ItemFlag.NoItemFlags
        cell=self.table.item(self.table.source_row(index.row()),index.column());flags=cell.flags()
        if cell.data(Qt.ItemDataRole.CheckStateRole) is None:flags &= ~Qt.ItemFlag.ItemIsUserCheckable
        return flags
    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role!=Qt.ItemDataRole.CheckStateRole:return False
        self.table.item(self.table.source_row(index.row()),index.column()).setCheckState(Qt.CheckState(value));return True


class VirtualTable(QTableView):
    itemChanged=Signal(object)
    def __init__(self,headers):
        super().__init__();self.source_headers=list(headers);self.headers=list(headers)
        self.rows=[];self.values={};self.cell_flags={};self.hidden_rows=set();self.visible_rows=[];self.source_to_visible={};self.setModel(RowsModel(self))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.verticalHeader().hide()
    def reset_rows(self,rows):
        self.model().beginResetModel();self.rows=[list(r) for r in rows];self.values.clear();self.cell_flags.clear()
        self.hidden_rows.clear();self.visible_rows=list(range(len(self.rows)));self.source_to_visible={r:r for r in self.visible_rows}
        self.model().endResetModel()
    def source_row(self,row):return self.visible_rows[row]
    def setRowHidden(self,row,hidden):
        if hidden:self.hidden_rows.add(row)
        else:self.hidden_rows.discard(row)
    def isRowHidden(self,row):return row in self.hidden_rows
    def commit_filter(self):
        self.model().beginResetModel();self.visible_rows=[r for r in range(len(self.rows)) if r not in self.hidden_rows]
        self.source_to_visible={r:i for i,r in enumerate(self.visible_rows)};self.model().endResetModel()
    def rowCount(self):return len(self.rows)
    def columnCount(self):return len(self.headers)
    def item(self,row,column):
        return Cell(self,row,column) if 0<=row<len(self.rows) and 0<=column<len(self.headers) else None
    def setRowCount(self,count):self.reset_rows(self.rows[:count]+[['']*len(self.headers) for _ in range(max(0,count-len(self.rows)))])
    def clearContents(self):self.reset_rows([['']*len(self.headers) for _ in self.rows])
    def refresh_translated_text(self):
        from .i18n import tr,current_language
        self.headers=[tr(v,current_language()) for v in self.source_headers]
        self.model().headerDataChanged.emit(Qt.Orientation.Horizontal,0,len(self.headers)-1)
