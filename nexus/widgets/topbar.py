"""Minimal top bar: printer state on the left, temperatures and clock on the right."""
from datetime import datetime

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen

from nexus import theme
from nexus.widgets import icons
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.text import degree_width, draw_degrees

STATE_STYLE = {
    "standby":  (theme.GREEN, "Ready"),
    "ready":    (theme.GREEN, "Ready"),
    "complete": (theme.GREEN, "Complete"),
    "printing": (theme.RED, "Printing"),
    "paused":   (theme.AMBER, "Paused"),
    "cancelled": (theme.DIM, "Cancelled"),
    "error":    (theme.RED, "Error"),
    "offline":  (theme.MUTED, "Disconnected"),
}


def state_style(state):
    return STATE_STYLE.get(state, (theme.DIM, state.capitalize()))


class TopBar:
    """Painted directly by the main window so it never needs its own surface."""

    def __init__(self, owner, rect):
        self._owner = owner
        self.rect = rect
        self.boxed = False
        self._state = "offline"
        self._temps = (None, None, None)
        self._clock = datetime.now().strftime("%H:%M")
        self._timer = QTimer(owner)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._arm_clock()

    def _arm_clock(self):
        now = datetime.now()
        self._timer.start(max(250, (60 - now.second) * 1000 - now.microsecond // 1000 + 50))

    def _tick(self):
        text = datetime.now().strftime("%H:%M")
        if text != self._clock:
            self._clock = text
            self._owner.update(self.rect.toRect())
        self._arm_clock()

    def set_data(self, data):
        state = data["state"] if data.get("connected") else "offline"
        temps = tuple(None if t is None else round(t[0]) for t in
                      (data.get("nozzle"), data.get("bed"), data.get("chamber")))
        if (state, temps) != (self._state, self._temps):
            self._state, self._temps = state, temps
            self._owner.update(self.rect.toRect())

    def set_mode(self, rect, boxed):
        """Flat strip beside the sidebar, or boxed full-width bar on fullscreen screens."""
        self.rect, self.boxed = rect, boxed

    def _right_layout(self, tf):
        """Clock, separator and N/B/C readouts; `right` is the free edge left of the readouts."""
        r = self.rect
        clock_r = QRectF(r.right() - 66, r.top(), 52, r.height())
        sep_x = int(clock_r.left()) - 4
        temps = []
        right = sep_x - 14
        for tag, val in reversed(list(zip("NBC", self._temps))):
            text = f"{tag} {'--' if val is None else val}"
            tw = degree_width(tf, text)
            temps.append((QRectF(right - tw, r.top(), tw, r.height()), text))
            right -= tw + 14
        return clock_r, sep_x, temps, right

    def free_span(self):
        """(left, right) x of the empty stretch between the state label and the temperatures."""
        _, _, _, right = self._right_layout(theme.font(17, QFont.Weight.DemiBold))
        x = self.rect.left() + (30 if self.boxed else 21) + 26
        x += QFontMetricsF(theme.font(17, QFont.Weight.Medium)).horizontalAdvance("Printer") + 16 + 13
        x += QFontMetricsF(theme.font(17, QFont.Weight.DemiBold)).horizontalAdvance(state_style(self._state)[1])
        return x, right - (4 if self.boxed else 0)  # boxed: stay inside the left panel

    def paint(self, p):
        r = self.rect
        cy = r.center().y()
        tf = theme.font(17, QFont.Weight.DemiBold)

        # right-hand layout first so the boxed variant can size its panels
        clock_r, sep_x, temps, right = self._right_layout(tf)

        if self.boxed:
            box_l = QRectF(r.left() + 5, r.top() + 2, right - 5 - r.left(), r.height() - 4)
            box_r = QRectF(right + 7, r.top() + 2, r.right() - 7 - right, r.height() - 4)
            for box in (box_l, box_r):
                paint_panel(p, box, 4, top=QColor(20, 22, 26), bottom=QColor(11, 12, 15))
            x = r.left() + 30
        else:
            p.setPen(QPen(QColor(44, 48, 55), 1.0))
            p.drawLine(int(r.left()), int(r.bottom()), int(r.right()), int(r.bottom()))
            p.setPen(QPen(QColor(0, 0, 0, 170), 1.0))
            p.drawLine(int(r.left()), int(r.bottom()) + 1, int(r.right()), int(r.bottom()) + 1)
            x = r.left() + 21

        icons.printer(p, QRectF(x, cy - 8, 18, 16), QColor(theme.FG_SOFT))
        x += 26
        f = theme.font(17, QFont.Weight.Medium)
        p.setFont(f)
        fm = QFontMetricsF(f)
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(x, r.top(), 80, r.height()), Qt.AlignmentFlag.AlignVCenter, "Printer")
        x += fm.horizontalAdvance("Printer") + 16
        colour, label = state_style(self._state)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawEllipse(QRectF(x, cy - 3.5, 7, 7))
        x += 13
        p.setFont(theme.font(17, QFont.Weight.DemiBold))
        p.setPen(theme.FG)
        p.drawText(QRectF(x, r.top(), 160, r.height()), Qt.AlignmentFlag.AlignVCenter, label)

        # clock + separator
        p.setFont(theme.font(18, QFont.Weight.DemiBold))
        p.setPen(theme.FG)
        p.drawText(clock_r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self._clock)
        p.setPen(QPen(QColor(52, 57, 64), 1.0))
        p.drawLine(sep_x, int(r.top()) + 7, sep_x, int(r.bottom()) - 7)

        # N / B / C readouts, right-aligned against the separator
        p.setPen(theme.FG)
        for rect, text in temps:
            draw_degrees(p, rect, text, tf, Qt.AlignmentFlag.AlignLeft)
