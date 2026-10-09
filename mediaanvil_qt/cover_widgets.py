"""Responsive artwork display and rectangular cover-crop dialog."""
from io import BytesIO
from PIL import Image
from PySide6.QtCore import Qt,QRect,QRectF,Signal
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap
from PySide6.QtWidgets import (QLabel,QDialog,QVBoxLayout,QGridLayout,QSpinBox,QDialogButtonBox,QWidget,QSizePolicy)
from .layouts import button, group
from .i18n import apply_language


class ResponsiveCover(QLabel):
    """Fit full-resolution artwork to all available preview space."""
    def __init__(self,parent=None):
        super().__init__('暂无封面',parent);self._source=QPixmap()
        self.setObjectName('coverPreview');self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(180,180);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
    def set_artwork(self,data,empty_text='暂无封面'):
        pixmap=QPixmap();pixmap.loadFromData(data or b'');self._source=pixmap
        if pixmap.isNull():self.clear();self.setText(empty_text)
        else:self.setText('')
        self._fit()
    def _fit(self):
        if self._source.isNull():return
        size=self.contentsRect().size()
        if size.width()>0 and size.height()>0:
            self.setPixmap(self._source.scaled(size,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):
        super().resizeEvent(event);self._fit()


class CropCanvas(QWidget):
    selectionChanged=Signal(int,int,int,int)
    def __init__(self,image,parent=None):
        super().__init__(parent);self.image=image;self._drag_start=None;self._drag_mode=None;self._drag_offset=(0,0)
        data=BytesIO();image.save(data,format='PNG');self.pixmap=QPixmap();self.pixmap.loadFromData(data.getvalue())
        self.selection=QRect(0,0,image.width,image.height)
        self.setMinimumSize(430,300);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
    def image_rect(self):
        if self.pixmap.isNull():return QRectF()
        scale=min(self.width()/self.image.width,self.height()/self.image.height)
        width=self.image.width*scale;height=self.image.height*scale
        return QRectF((self.width()-width)/2,(self.height()-height)/2,width,height)
    def _image_point(self,point):
        rect=self.image_rect()
        x=round((point.x()-rect.left())*self.image.width/rect.width())
        y=round((point.y()-rect.top())*self.image.height/rect.height())
        return max(0,min(self.image.width,x)),max(0,min(self.image.height,y))
    def set_selection(self,x,y,width,height,emit=False):
        x=max(0,min(int(x),self.image.width-1));y=max(0,min(int(y),self.image.height-1))
        width=max(1,min(int(width),self.image.width-x));height=max(1,min(int(height),self.image.height-y))
        self.selection=QRect(x,y,width,height);self.update()
        if emit:self.selectionChanged.emit(x,y,width,height)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        image_rect=self.image_rect();painter.drawPixmap(image_rect,self.pixmap,QRectF(self.pixmap.rect()))
        sx=image_rect.left()+self.selection.x()*image_rect.width()/self.image.width
        sy=image_rect.top()+self.selection.y()*image_rect.height()/self.image.height
        sw=self.selection.width()*image_rect.width()/self.image.width;sh=self.selection.height()*image_rect.height()/self.image.height
        crop=QRectF(sx,sy,sw,sh);shade=QColor(15,31,56,125);painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(shade)
        painter.drawRect(QRectF(image_rect.left(),image_rect.top(),image_rect.width(),max(0,crop.top()-image_rect.top())))
        painter.drawRect(QRectF(image_rect.left(),crop.bottom(),image_rect.width(),max(0,image_rect.bottom()-crop.bottom())))
        painter.drawRect(QRectF(image_rect.left(),crop.top(),max(0,crop.left()-image_rect.left()),crop.height()))
        painter.drawRect(QRectF(crop.right(),crop.top(),max(0,image_rect.right()-crop.right()),crop.height()))
        painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor('#2b70f3'),2));painter.drawRect(crop)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.image_rect().contains(event.position()):
            point=self._image_point(event.position());self._drag_start=point
            full=self.selection==QRect(0,0,self.image.width,self.image.height)
            if self.selection.contains(*point) and not full:
                self._drag_mode='move';self._drag_offset=(point[0]-self.selection.x(),point[1]-self.selection.y())
            else:self._drag_mode='resize';self.set_selection(*point,1,1,emit=True)
    def mouseMoveEvent(self,event):
        if self._drag_start is None:return
        x2,y2=self._image_point(event.position())
        if self._drag_mode=='move':
            width=self.selection.width();height=self.selection.height()
            x=max(0,min(self.image.width-width,x2-self._drag_offset[0]));y=max(0,min(self.image.height-height,y2-self._drag_offset[1]))
            self.set_selection(x,y,width,height,emit=True);return
        x1,y1=self._drag_start;left=min(x1,x2);top=min(y1,y2)
        self.set_selection(left,top,max(1,abs(x2-x1)),max(1,abs(y2-y1)),emit=True)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self._drag_start=None;self._drag_mode=None


class CropDialog(QDialog):
    def __init__(self,source,parent=None):
        super().__init__(parent);self.setWindowTitle('自由矩形裁剪封面');self.resize(720,620)
        with Image.open(source) as image:self.image=image.convert('RGB')
        layout=QVBoxLayout(self);instruction=QLabel('拖拽创建或移动矩形裁剪框，也可输入精确像素。');instruction.setObjectName('muted');layout.addWidget(instruction)
        self.canvas=CropCanvas(self.image);layout.addWidget(self.canvas,1)
        box,fields=group('裁剪区域（像素）');grid=QGridLayout();fields.addLayout(grid)
        self.x=QSpinBox();self.y=QSpinBox();self.width=QSpinBox();self.height=QSpinBox()
        self.x.setRange(0,self.image.width-1);self.y.setRange(0,self.image.height-1)
        self.width.setRange(1,self.image.width);self.height.setRange(1,self.image.height)
        self.width.setValue(self.image.width);self.height.setValue(self.image.height)
        for column,(label,control) in enumerate((('横向起点',self.x),('纵向起点',self.y),('宽度',self.width),('高度',self.height))):
            grid.addWidget(QLabel(label),0,column);grid.addWidget(control,1,column)
        layout.addWidget(box);self._syncing=False
        for control in (self.x,self.y,self.width,self.height):control.valueChanged.connect(self._fields_changed)
        self.canvas.selectionChanged.connect(self._canvas_changed)
        reset_button=button('恢复完整图片',self.reset_selection,symbol='undo')
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        buttons.addButton(reset_button,QDialogButtonBox.ButtonRole.ResetRole)
        language=getattr(getattr(parent,'app',None),'settings',{}).get('language','zh_CN')
        apply_language(self,language)
    def cropped(self):
        x,y,width,height=self.x.value(),self.y.value(),self.width.value(),self.height.value()
        return self.image.crop((x,y,x+width,y+height))
    def _fields_changed(self):
        if self._syncing:return
        self._syncing=True
        self.width.setMaximum(self.image.width-self.x.value());self.height.setMaximum(self.image.height-self.y.value())
        self.canvas.set_selection(self.x.value(),self.y.value(),self.width.value(),self.height.value());self._syncing=False
    def _canvas_changed(self,x,y,width,height):
        if self._syncing:return
        self._syncing=True
        self.x.setValue(x);self.y.setValue(y);self.width.setMaximum(self.image.width-x);self.height.setMaximum(self.image.height-y)
        self.width.setValue(width);self.height.setValue(height);self._syncing=False
    def reset_selection(self):
        self._canvas_changed(0,0,self.image.width,self.image.height);self.canvas.set_selection(0,0,self.image.width,self.image.height)

