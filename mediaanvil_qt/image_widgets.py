"""Cover pictures and cached file thumbnails."""
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImageReader, QIcon
from .design import icon
from .i18n import tr


def set_picture(label, data, size=220):
    pix = QPixmap()
    if data: pix.loadFromData(data)
    if pix.isNull(): label.clear(); label.setText(tr('暂无封面 / 预览'))
    else: label.setPixmap(pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


def thumbnail(path, size=36):
    path=Path(path)
    try:stamp=(path.stat().st_mtime_ns,path.stat().st_size)
    except OSError:return icon('image')
    return _thumbnail(str(path),size,stamp)


@lru_cache(maxsize=256)
def _thumbnail(path,size,stamp):
    reader=QImageReader(str(path));reader.setAutoTransform(True)
    dimensions=reader.size()
    if dimensions.isValid():reader.setScaledSize(dimensions.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio))
    image=reader.read()
    return QIcon(QPixmap.fromImage(image)) if not image.isNull() else icon('image')

