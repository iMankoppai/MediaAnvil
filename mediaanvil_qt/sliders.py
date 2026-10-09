"""Slider mouse and keyboard interaction for playback controls."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QSlider, QStyle, QStyleOptionSlider)


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

