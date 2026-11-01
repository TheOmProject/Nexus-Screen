"""Painted touch buttons for the print controls."""
from PyQt6.QtCore import QElapsedTimer, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QWidget

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.widgets.glow_widget import paint_panel, panel_path, red_glow

GLOW = smin(7)


class ActionButton(QAbstractButton):
    """Large red-rimmed control (Pause / Resume / Stop / Home). Icon left of the label.

    The widget is GLOW px larger on every side than the visible button so the
    halo has room; callers position it with `place()`.
    """

    def __init__(self, icon, label, icon_size=(26, 26), parent=None, emphasis=True):
        super().__init__(parent)
        self._emphasis = emphasis  # False: dimmer rim and halo (Stop in the reference)
        self._icon = icon
        self._label = label
        self._icon_size = icon_size
        self.setCursor(Qt.CursorShape.BlankCursor)

    def place(self, x, y, w, h):
        self.setGeometry(x - GLOW, y - GLOW, w + 2 * GLOW, h + 2 * GLOW)

    def set_content(self, icon, label, icon_size=None):
        if (icon, label, icon_size or self._icon_size) != (self._icon, self._label, self._icon_size):
            self._icon, self._label = icon, label
            self._icon_size = icon_size or self._icon_size
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(GLOW, GLOW, self.width() - 2 * GLOW, self.height() - 2 * GLOW)
        on = self.isEnabled()
        if on:
            p.drawPixmap(0, 0, red_glow(int(r.width()), int(r.height()), 6.0, GLOW,
                                        0.75 if self._emphasis else 0.3))
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0.0, QColor(58, 10, 10) if not self.isDown() else QColor(110, 16, 14))
            g.setColorAt(1.0, QColor(22, 6, 6) if not self.isDown() else QColor(60, 8, 8))
            p.fillPath(panel_path(r, 6), g)
            p.setPen(QPen(QColor(255, 42, 32) if self._emphasis else QColor(150, 26, 20), 1.6))
        else:
            paint_panel(p, r, 6, top=QColor(24, 26, 30), bottom=QColor(15, 17, 20))
            p.setPen(QPen(QColor(52, 56, 62), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.8, 0.8, -0.8, -0.8), 6, 6)

        f = theme.font(smin(19), QFont.Weight.DemiBold)
        p.setFont(f)
        iw, ih = self._icon_size
        tw = p.fontMetrics().horizontalAdvance(self._label)
        gap = 18
        x = r.center().x() - (iw + gap + tw) / 2
        self._icon(p, QRectF(x, r.center().y() - ih / 2, iw, ih),
                   QColor(255, 36, 26) if on else QColor(theme.MUTED))
        p.setPen(theme.FG if on else theme.MUTED)
        p.drawText(QRectF(x + iw + gap, r.y(), tw + 4, r.height()), Qt.AlignmentFlag.AlignVCenter, self._label)
        p.end()


class SmallButton(QAbstractButton):
    """Compact neutral key: chevron (icon) or text, optional red 'selected' rim."""

    def __init__(self, text="", icon=None, parent=None, font_px=theme.BUTTON, checkable=None):
        super().__init__(parent)
        self._font_px = font_px
        self._text = text
        self._icon = icon
        self.setCheckable(bool(text) if checkable is None else checkable)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        on = self.isEnabled()
        sel = self.isChecked()
        top = QColor(30, 33, 38) if self.isDown() else QColor(19, 21, 25)
        paint_panel(p, r, 4, top=top, bottom=QColor(11, 12, 15), border=QColor(44, 48, 55))
        if sel:
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, QColor(70, 8, 8, 200))
            g.setColorAt(1, QColor(28, 4, 4, 200))
            p.fillPath(panel_path(r, 4), g)
            p.setPen(QPen(QColor(255, 42, 32) if on else QColor(110, 30, 26), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.7, 0.7, -0.7, -0.7), 4, 4)
        colour = QColor(theme.FG) if on else QColor(theme.MUTED)
        if self._icon:
            k = min(1.0, r.width() * 0.4 / 16)  # 16×9 chevron (approved Baby Step keys), smaller on tiny keys
            self._icon(p, QRectF(r.center().x() - 8 * k, r.center().y() - 4.5 * k, 16 * k, 9 * k), colour, 2.2)
        else:
            p.setFont(theme.font(self._font_px, QFont.Weight.DemiBold))
            p.setPen(colour)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


class BackButton(QAbstractButton):
    """'< Back' key at the top-left of submenu screens.

    The visible key (VISIBLE_W x VISIBLE_H) sits in the top bar; the widget is larger so the finger
    target reaches past it over non-interactive areas (status box edge, screen title)."""
    VISIBLE_W = sx(120)
    VISIBLE_H = sy(34)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.VISIBLE_W, self.VISIBLE_H)
        paint_panel(p, r, 6, top=QColor(34, 37, 42) if self.isDown() else QColor(22, 24, 28),
                    bottom=QColor(11, 12, 15))
        from nexus.widgets import icons
        icons.back_arrow(p, QRectF(16, r.center().y() - 10, 10, 20), QColor(theme.FG_SOFT), 2.6)
        p.setFont(theme.font(smin(22), QFont.Weight.DemiBold))
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(38, 0, r.width() - 40, r.height()), Qt.AlignmentFlag.AlignVCenter, "Back")
        p.end()


class EmergencyStopButton(QWidget):
    """Red EMERGENCY STOP key in the top bar. Fires after HOLD_MS of continuous press, with no dialog:
    a brief accidental touch, or sliding off the key, does nothing. The fill shows the hold progress.

    The widget is the full bar height (the finger target); the painted key is centred in it."""
    HOLD_MS = 500
    KEY_H = sy(28)
    triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(25)  # repaint only while held
        self._timer.timeout.connect(self._tick)
        self.progress = 0.0

    def holding(self):
        return self._timer.isActive()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._clock.start()
            self._timer.start()
            self._tick()

    def mouseMoveEvent(self, e):
        if self.holding() and not self.rect().contains(e.position().toPoint()):
            self._cancel()

    def mouseReleaseEvent(self, _):
        self._cancel()

    def hideEvent(self, _):
        self._cancel()

    def _cancel(self):
        self._timer.stop()
        if self.progress:
            self.progress = 0.0
            self.update()

    def _tick(self):
        self.progress = min(1.0, self._clock.elapsed() / self.HOLD_MS)
        self.update()
        if self.progress >= 1.0:
            self._timer.stop()
            self.triggered.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, (self.height() - self.KEY_H) / 2, self.width() - 2, self.KEY_H)
        paint_panel(p, r, 5, top=QColor(196, 30, 26), bottom=QColor(120, 12, 10), border=QColor(255, 96, 86),
                    alpha=255)
        if self.progress:
            p.save()
            p.setClipPath(panel_path(r, 5))
            p.fillRect(QRectF(r.left(), r.top(), r.width() * self.progress, r.height()), QColor(255, 70, 58))
            p.restore()
        p.setFont(theme.font(smin(15), QFont.Weight.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "STOPPING" if self.progress >= 1.0 else "EMERGENCY STOP")
        p.end()


class ToggleSwitch(QAbstractButton):
    """Red on/off switch (lighting cards)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        on = self.isChecked()
        enabled = self.isEnabled()
        p.setPen(QPen(QColor(255, 60, 45) if on and enabled else QColor(60, 64, 70), 1.2))
        p.setBrush(QColor(150, 14, 12) if on and enabled else QColor(24, 26, 30))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.right() - d - 3 if on else r.x() + 3
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(235, 237, 240) if enabled else QColor(110, 114, 120))
        p.drawEllipse(QRectF(x, r.y() + 3, d, d))
        p.end()


class JogKey(QAbstractButton):
    """Chevron + label key (Z+ / Z− on the Move screen)."""

    def __init__(self, icon, label, parent=None):
        super().__init__(parent)
        self._icon, self._label = icon, label

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        on = self.isEnabled()
        top = QColor(110, 18, 14) if self.isDown() else QColor(64, 68, 75)
        paint_panel(p, r, 8, top=top, bottom=QColor(28, 30, 35), border=QColor(90, 95, 103))
        col = QColor(theme.FG) if on else QColor(theme.MUTED)
        up = self._label.endswith("+")
        cy = r.center().y()
        self._icon(p, QRectF(r.center().x() - 11, cy - (18 if up else -6), 22, 12), col, 2.6)
        p.setFont(theme.font(theme.JOG_Z, QFont.Weight.DemiBold))
        p.setPen(col)
        p.drawText(QRectF(r.x(), cy - (0 if up else 24), r.width(), 22), Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()
