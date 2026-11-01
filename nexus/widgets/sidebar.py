"""Approved main-screen sidebar: NEXUS SCREEN wordmark + five section buttons."""
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QWidget

from nexus import theme
from nexus.widgets import icons
from nexus.widgets.glow_widget import paint_red_fill, red_glow

SECTIONS = [
    ("home", "Home", icons.home),
    ("print", "Print", icons.print_),
    ("filament", "Filament", icons.filament),
    ("control", "Control", icons.control),
    ("settings", "Settings", icons.gear),
]

LOGO_H = 50
ITEM_TOP = 56
ITEM_H = 68
ITEM_GAP = 4
ITEM_INSET = 4


class NavButton(QAbstractButton):
    def __init__(self, key, label, icon, parent=None):
        super().__init__(parent)
        self.key = key
        self._label = label
        self._icon = icon
        self._glow = 0.0
        self._anim = QPropertyAnimation(self, b"glow", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.BlankCursor)

    def _get_glow(self):
        return self._glow

    def _set_glow(self, v):
        self._glow = v
        self.update()

    glow = pyqtProperty(float, _get_glow, _set_glow)

    def set_active(self, active, animate=True):
        end = 1.0 if active else 0.0
        if self._glow == end and self._anim.state() != QPropertyAnimation.State.Running:
            return
        self._anim.stop()
        if not animate:
            self._set_glow(end)
            return
        self._anim.setStartValue(self._glow)
        self._anim.setEndValue(end)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        g = self._glow
        body = QRectF(ITEM_INSET, 0, w - 2 * ITEM_INSET, h)
        if g > 0.01:
            spread = 8
            halo = red_glow(int(body.width()), h, 7.0, spread, 0.85)
            p.setOpacity(g)
            p.drawPixmap(int(body.x()) - spread, -spread, halo)
            paint_red_fill(p, body, 7.0, 1.0)
            # bright left edge bar
            bar = QRectF(body.x(), body.y() + 2, 3.5, body.height() - 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 48, 32))
            p.drawRoundedRect(bar, 1.5, 1.5)
            p.setOpacity(1.0)
        elif self.isDown():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 18))
            p.drawRoundedRect(body, 7, 7)

        icon_c = QColor(theme.RED) if g > 0.5 else QColor(theme.FG_SOFT)
        if g > 0.5:
            icon_c = QColor(255, 58, 46)
        self._icon(p, QRectF(w / 2 - 12, 13, 24, 24), icon_c)
        p.setFont(theme.font(14, QFont.Weight.DemiBold if g > 0.5 else QFont.Weight.Medium))
        p.setPen(theme.FG if g > 0.5 else theme.FG_SOFT)
        p.drawText(QRectF(0, 42, w, 18), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self._label)
        p.end()


class Sidebar(QWidget):
    section_requested = pyqtSignal(str)

    def __init__(self, width, height, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.buttons = {}
        y = ITEM_TOP
        for key, label, icon in SECTIONS:
            btn = NavButton(key, label, icon, self)
            btn.setGeometry(0, y, width, ITEM_H)
            btn.clicked.connect(lambda _=False, k=key: self.section_requested.emit(k))
            self.buttons[key] = btn
            y += ITEM_H + ITEM_GAP

    def set_active(self, key, animate=True):
        for k, btn in self.buttons.items():
            btn.set_active(k == key, animate)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0.0, QColor(30, 33, 38, 150))
        g.setColorAt(1.0, QColor(18, 20, 24, 170))
        p.fillRect(QRectF(0, 0, w, h), g)
        p.setPen(QPen(QColor(46, 50, 57), 1.0))
        p.drawLine(w - 1, 0, w - 1, h)
        p.setPen(QPen(QColor(0, 0, 0, 160), 1.0))
        p.drawLine(w - 2, 0, w - 2, h)
        self._paint_wordmark(p, QRectF(0, 0, w, LOGO_H))
        p.end()

    def _paint_wordmark(self, p, r):
        # brushed-silver NEXUS over red SCREEN (as in the Fans / Move references)
        silver = QLinearGradient(0, r.y() + 8, 0, r.y() + 28)
        silver.setColorAt(0.0, QColor("#f2f4f7"))
        silver.setColorAt(0.55, QColor("#c9ced5"))
        silver.setColorAt(1.0, QColor("#9aa0a8"))
        p.setPen(QPen(silver, 1))
        p.setFont(theme.font(21, QFont.Weight.Bold, 0.6))
        p.drawText(QRectF(r.x(), r.y() + 6, r.width(), 22), Qt.AlignmentFlag.AlignCenter, "NEXUS")
        p.setPen(QColor(theme.RED))
        p.setFont(theme.font(13, QFont.Weight.DemiBold, 1.6))
        p.drawText(QRectF(r.x(), r.y() + 27, r.width(), 16), Qt.AlignmentFlag.AlignCenter, "SCREEN")
