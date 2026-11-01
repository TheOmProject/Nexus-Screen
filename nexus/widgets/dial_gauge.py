"""Circular 0–100 % gauge (fans, lights): dark track, red value arc with glow,
metallic hub with an icon. The static layers are cached per size."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QConicalGradient, QPainter, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QWidget

from nexus import theme

START, SPAN = 225, -270  # degrees: from lower-left, clockwise to lower-right
_bg_cache = {}


def _background(size):
    px = _bg_cache.get(size)
    if px is not None:
        return px
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QPointF(size / 2, size / 2)
    r = size / 2
    rim = QRadialGradient(c, r)
    rim.setColorAt(0.80, QColor(10, 11, 13))
    rim.setColorAt(0.93, QColor(30, 33, 38))
    rim.setColorAt(1.00, QColor(8, 9, 11))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(rim)
    p.drawEllipse(c, r - 1, r - 1)
    track = QRectF(size * 0.12, size * 0.12, size * 0.76, size * 0.76)
    p.setPen(QPen(QColor(32, 35, 40), size * 0.075, cap=Qt.PenCapStyle.FlatCap))
    p.drawArc(track, START * 16, SPAN * 16)
    hub = QConicalGradient(c, 45)
    for pos, col in ((0.0, "#5a5f67"), (0.25, "#c9ced5"), (0.5, "#4a4f57"), (0.75, "#b9bec6"), (1.0, "#5a5f67")):
        hub.setColorAt(pos, QColor(col))
    p.setPen(QPen(QColor(10, 11, 13), 2))
    p.setBrush(QColor(20, 22, 26))
    p.drawEllipse(c, r * 0.56, r * 0.56)
    p.setBrush(hub)
    p.drawEllipse(c, r * 0.44, r * 0.44)
    p.setBrush(QColor(28, 30, 35))
    p.drawEllipse(c, r * 0.38, r * 0.38)
    p.end()
    _bg_cache[size] = px
    return px


class DialGauge(QWidget):
    def __init__(self, icon, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._value = 0.0
        self._colour = QColor(theme.RED)

    def set_value(self, value, colour=None):
        value = max(0.0, min(1.0, value))
        colour = QColor(colour) if colour else QColor(theme.RED)
        if (value, colour.rgb()) != (self._value, self._colour.rgb()):
            self._value, self._colour = value, colour
            self.update()

    def paintEvent(self, _):
        size = min(self.width(), self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy = (self.width() - size) / 2, (self.height() - size) / 2
        p.translate(ox, oy)
        p.drawPixmap(0, 0, _background(size))
        if self._value > 0.001:
            track = QRectF(size * 0.12, size * 0.12, size * 0.76, size * 0.76)
            span = int(SPAN * self._value * 16)
            glow = QColor(self._colour)
            for w, a in ((0.16, 40), (0.11, 70)):
                glow.setAlpha(a)
                p.setPen(QPen(glow, size * w, cap=Qt.PenCapStyle.FlatCap))
                p.drawArc(track, START * 16, span)
            p.setPen(QPen(self._colour, size * 0.075, cap=Qt.PenCapStyle.FlatCap))
            p.drawArc(track, START * 16, span)
        s = size * 0.36
        self._icon(p, QRectF(size / 2 - s / 2, size / 2 - s / 2, s, s), QColor(theme.FG_SOFT))
        p.end()
