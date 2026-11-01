"""Metallic X/Y jog wheel with a centre Home key (Move screen reference)."""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QConicalGradient, QFont, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget

from nexus import theme
from nexus.widgets import icons

# segment -> (axis, direction, label, angle of the segment centre in degrees, Qt convention)
SEGMENTS = {"y+": ("Y", 1, "Y+", 90), "x+": ("X", 1, "X+", 0), "y-": ("Y", -1, "Y-", 270), "x-": ("X", -1, "X-", 180)}


class JogWheel(QWidget):
    jog = pyqtSignal(str, int)
    home = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed = None
        self._enabled = {"X": True, "Y": True, "home": True}

    def set_enabled_axes(self, x, y, home):
        new = {"X": x, "Y": y, "home": home}
        if new != self._enabled:
            self._enabled = new
            self.update()

    def _geometry(self):
        size = min(self.width(), self.height())
        c = QPointF(self.width() / 2, self.height() / 2)
        return c, size / 2 - 6, size * 0.19

    def segment_at(self, pos):
        c, ro, ri = self._geometry()
        dx, dy = pos.x() - c.x(), c.y() - pos.y()
        r = math.hypot(dx, dy)
        if r <= ri:
            return "home"
        if r > ro:
            return None
        a = math.degrees(math.atan2(dy, dx)) % 360
        return min(SEGMENTS, key=lambda k: min(abs(a - SEGMENTS[k][3]), 360 - abs(a - SEGMENTS[k][3])))

    def _is_enabled(self, seg):
        return self._enabled["home"] if seg == "home" else self._enabled[SEGMENTS[seg][0]]

    def mousePressEvent(self, e):
        seg = self.segment_at(e.position())
        self._pressed = seg if seg and self._is_enabled(seg) else None
        self.update()

    def mouseReleaseEvent(self, e):
        seg, self._pressed = self._pressed, None
        self.update()
        if seg and self.segment_at(e.position()) == seg:
            if seg == "home":
                self.home.emit()
            else:
                self.jog.emit(SEGMENTS[seg][0], SEGMENTS[seg][1])

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c, ro, ri = self._geometry()
        # outer bezel
        bezel = QConicalGradient(c, 60)
        for pos, col in ((0, "#6b7078"), (0.25, "#d4d8de"), (0.5, "#51565e"), (0.75, "#b5bac2"), (1, "#6b7078")):
            bezel.setColorAt(pos, QColor(col))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bezel)
        p.drawEllipse(c, ro + 5, ro + 5)
        face = QRadialGradient(c, ro)
        face.setColorAt(0.4, QColor(52, 56, 62))
        face.setColorAt(1.0, QColor(24, 26, 30))
        p.setBrush(face)
        p.drawEllipse(c, ro, ro)
        # pressed segment highlight
        if self._pressed and self._pressed != "home":
            ang = SEGMENTS[self._pressed][3]
            p.setBrush(QColor(255, 40, 30, 70))
            p.drawPie(QRectF(c.x() - ro, c.y() - ro, 2 * ro, 2 * ro), int((ang - 45) * 16), 90 * 16)
        # segment dividers with red glow edges
        for k in range(4):
            a = math.radians(45 + 90 * k)
            p1 = QPointF(c.x() + ri * 1.25 * math.cos(a), c.y() - ri * 1.25 * math.sin(a))
            p2 = QPointF(c.x() + ro * math.cos(a), c.y() - ro * math.sin(a))
            p.setPen(QPen(QColor(255, 40, 30, 70), 5))
            p.drawLine(p1, p2)
            p.setPen(QPen(QColor(8, 9, 11), 2.5))
            p.drawLine(p1, p2)
        # labels + chevrons
        for key, (axis, _, label, ang) in SEGMENTS.items():
            on = self._enabled[axis]
            col = QColor(theme.FG) if on else QColor(theme.MUTED)
            a = math.radians(ang)
            mid = (ro + ri * 1.25) / 2
            cx, cy = c.x() + mid * math.cos(a), c.y() - mid * math.sin(a)
            p.save()
            p.translate(cx, cy)
            if axis == "Y":
                (icons.chevron_up if label == "Y+" else icons.chevron_down)(p, QRectF(-8, -15, 16, 9), col, 2.4)
            else:  # chevron above the label, pointing along the axis
                (icons.chevron if label == "X+" else icons.back_arrow)(p, QRectF(-4.5, -20, 9, 16), col)
            p.setFont(theme.font(theme.JOG, QFont.Weight.DemiBold))
            p.setPen(col)
            p.drawText(QRectF(-20, -2, 40, 20), Qt.AlignmentFlag.AlignCenter, label)
            p.restore()
        # centre home key with red ring
        on = self._enabled["home"]
        p.setPen(QPen(QColor(255, 40, 30, 90 if on else 30), 9))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, ri, ri)
        p.setPen(QPen(QColor(255, 42, 32) if on else QColor(90, 30, 26), 2.2))
        hub = QRadialGradient(c, ri)
        hub.setColorAt(0, QColor(70, 74, 80) if self._pressed != "home" else QColor(110, 20, 16))
        hub.setColorAt(1, QColor(26, 28, 32))
        p.setBrush(hub)
        p.drawEllipse(c, ri - 2, ri - 2)
        s = ri * 0.8
        icons.house(p, QRectF(c.x() - s / 2, c.y() - s / 2, s, s * 0.92), QColor(theme.FG) if on else QColor(theme.MUTED))
        p.end()
