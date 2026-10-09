"""Audio waveform rendering and interactive selection, independent of decoding."""
from __future__ import annotations


from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QWidget,
    )


class WaveformView(QWidget):
    """Interactive waveform with a draggable selection range.

    The widget owns no audio state: callers set peaks/duration and read back
    ``selection_start``/``selection_end`` in seconds. Painting is cheap because
    only the cached peak list is redrawn.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.peaks: tuple[float, ...] = ()
        self.duration: float = 0.0
        self.selection_start = 0.0
        self.selection_end = 0.0
        self._drag_side = None  # None, 'start', 'end', 'move'
        self._press_time = 0.0
        self._press_start = 0.0
        self._press_end = 0.0
        self.selectionChanged = None  # optional callback(seconds_start, seconds_end)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # -- data ------------------------------------------------------------
    def set_audio(self, duration: float, peaks: tuple[float, ...]):
        self.duration = float(duration or 0.0)
        self.peaks = tuple(peaks)
        self.selection_start = 0.0
        self.selection_end = self.duration
        self.update()
        self._emit()

    def clear_audio(self):
        self.duration = 0.0; self.peaks = ()
        self.selection_start = 0.0; self.selection_end = 0.0
        self.update(); self._emit()

    def set_selection(self, start: float, end: float):
        self.selection_start = max(0.0, min(start, self.duration))
        self.selection_end = max(self.selection_start, min(end, self.duration))
        self.update(); self._emit()

    def _emit(self):
        if callable(self.selectionChanged):
            self.selectionChanged(self.selection_start, self.selection_end)

    # -- geometry --------------------------------------------------------
    def _time_at(self, x: float) -> float:
        width = max(1.0, self.width())
        return max(0.0, min(1.0, x / width)) * self.duration

    def _x_at(self, seconds: float) -> float:
        if self.duration <= 0: return 0.0
        return (seconds / self.duration) * self.width()

    # -- interaction -----------------------------------------------------
    def mousePressEvent(self, event):
        if self.duration <= 0: return
        position = event.position().x()
        time = self._time_at(position)
        start_x, end_x = self._x_at(self.selection_start), self._x_at(self.selection_end)
        edge = max(12, int(self.width() * 0.02))
        if abs(position - start_x) <= edge:
            self._drag_side = 'start'
        elif abs(position - end_x) <= edge:
            self._drag_side = 'end'
        elif start_x <= position <= end_x:
            self._drag_side = 'move'
            self._press_time = time
            self._press_start, self._press_end = self.selection_start, self.selection_end
        else:
            self._drag_side = 'start' if position < width_start(end_x, start_x) else 'end'
            self.set_selection(time, self.selection_end if self._drag_side == 'start' else time)
        self._press_time = time

    def mouseMoveEvent(self, event):
        if not self._drag_side or self.duration <= 0: return
        time = self._time_at(event.position().x())
        if self._drag_side == 'start':
            self.set_selection(min(time, self.selection_end), self.selection_end)
        elif self._drag_side == 'end':
            self.set_selection(self.selection_start, max(time, self.selection_start))
        else:
            delta = time - self._press_time
            span = self._press_end - self._press_start
            start = max(0.0, min(self._press_start + delta, self.duration - span))
            self.set_selection(start, start + span)

    def mouseReleaseEvent(self, event):
        self._drag_side = None

    # -- painting --------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 4.5, -0.5, -4.5)
        painter.setPen(QPen(QColor('#c8daf7'), 1))
        painter.setBrush(QColor('#f4f8ff'))
        painter.drawRoundedRect(rect, 8, 8)
        if not self.peaks or self.duration <= 0: return
        middle = rect.center().y()
        amplitude = rect.height() / 2 - 6
        bucket_width = rect.width() / len(self.peaks)
        start_x, end_x = self._x_at(self.selection_start), self._x_at(self.selection_end)
        for index, peak in enumerate(self.peaks):
            x = rect.left() + index * bucket_width
            height = max(1.0, peak * amplitude)
            inside = start_x <= x <= end_x
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#2b70f3' if inside else '#9fb7db'))
            painter.drawRect(QRectF(x, middle - height, max(1.0, bucket_width - 0.5), height * 2))
        painter.setPen(QPen(QColor('#246ef0'), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(start_x, rect.top()), QPointF(start_x, rect.bottom()))
        painter.drawLine(QPointF(end_x, rect.top()), QPointF(end_x, rect.bottom()))


def width_start(end_x: float, start_x: float) -> float:
    """Helper kept tiny: clicking left of the selection midpoint extends start."""
    return (start_x + end_x) / 2

