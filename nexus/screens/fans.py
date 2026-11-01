"""Fans — one gauge card per fan Klipper reports. Part cooling (M106) and
fan_generic fans are adjustable; heater/controller/temperature fans are driven by
Klipper and shown read-only."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import Debounce, Stepper, grid, place_buttons
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.dial_gauge import DialGauge
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.panels import ActionTile, Panel, SubScreen

STEP = 0.10
PER_PAGE = 4


def fan_op(fan, speed):
    """(operation key, params) setting `fan` to `speed` (0..1), or None if not adjustable."""
    if fan["kind"] == "part":
        return "fan_part", {"value": round(speed * 255)}
    if fan["kind"] == "generic":
        return "fan_generic", {"fan": fan["param"], "speed": round(speed, 2)}
    return None


class FanCard(Panel):
    def __init__(self, ctl, parent=None):
        super().__init__("", parent)
        self.ctl = ctl
        self.fan = None
        self.pending = None
        self.gauge = DialGauge(icons.fan, self)
        self.debounce = Debounce(self)
        self.stepper = Stepper(self, self._step)

    def resizeEvent(self, e):
        w = self.width()
        self.gauge.setGeometry(int(w / 2 - 66), 52, 132, 132)
        self.stepper.place(10, self.height() - 48, w - 20, 36, key_w=42)
        super().resizeEvent(e)

    def set_fan(self, fan, data):
        self.fan = fan
        if not self.debounce.pending():
            self.pending = None
        speed = self.pending if self.pending is not None else fan["speed"]
        self.gauge.set_value(speed, None if fan["kind"] != "auto" else theme.RED_MID)
        op = fan_op(fan, speed)
        adjustable = op is not None
        self.stepper.setVisible(adjustable)
        if adjustable:
            ok = self.ctl.can(op[0], data)
            self.stepper.set(f"{round(speed * 100)}%", ok, speed > 0.001, speed < 0.999)
        self.update()

    def _step(self, d):
        base = self.pending if self.pending is not None else self.fan["speed"]
        self.pending = round(max(0.0, min(1.0, base + d * STEP)), 2)
        self.gauge.set_value(self.pending)
        self.stepper.set(f"{round(self.pending * 100)}%", True, self.pending > 0.001, self.pending < 0.999)
        key, params = fan_op(self.fan, self.pending)
        self.debounce(lambda k, prm: self.ctl.run(k, **prm), key, params)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        paint_panel(p, QRectF(0, 0, w, h), 7)
        f = self.fan
        if f:
            p.setFont(theme.font(theme.CARD, QFont.Weight.DemiBold))
            p.setPen(theme.FG)
            p.drawText(QRectF(12, 8, w - 24, 22), Qt.AlignmentFlag.AlignVCenter, f["name"])
            p.setFont(theme.font(theme.SMALL, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            p.drawText(QRectF(12, 28, w - 24, 16), Qt.AlignmentFlag.AlignVCenter, f["sub"])
            speed = self.pending if self.pending is not None else f["speed"]
            p.setFont(theme.font(smin(26), QFont.Weight.Bold))
            p.setPen(theme.FG)
            p.drawText(QRectF(0, sy(186), w, sy(30)), Qt.AlignmentFlag.AlignCenter, f"{round(speed * 100)}%")
            p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            auto = f["kind"] == "auto"
            p.drawText(QRectF(0, sy(214), w, sy(16)), Qt.AlignmentFlag.AlignCenter, "Automatic" if auto else "Target: 0-100%")
            if auto:
                p.setFont(theme.font(theme.BODY, QFont.Weight.DemiBold))
                p.setPen(theme.FG_SOFT)
                p.drawText(QRectF(sx(10), h - sy(48), w - sx(20), sy(36)), Qt.AlignmentFlag.AlignCenter, "Controlled by Klipper")
        p.end()


class FansScreen(SubScreen):
    TITLE = "Fans"
    SUBTITLE = "Control part, hotend, chamber and auxiliary fans"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.cards = [FanCard(ctl, self) for _ in range(PER_PAGE)]
        self.prev = SmallButton(icon=icons.back_arrow, parent=self, checkable=False)
        self.next = SmallButton(icon=icons.chevron, parent=self, checkable=False)
        self.prev.setGeometry(sx(700), sy(14), sx(40), sy(30))
        self.next.setGeometry(sx(748), sy(14), sx(40), sy(30))
        self.prev.clicked.connect(lambda: self._page(-1))
        self.next.clicked.connect(lambda: self._page(1))
        self.page = 0
        self.extra = Panel("Additional Controls", self)
        self.extra.setGeometry(sx(8), sy(354), sx(784), sy(82))
        self.all_off = ActionTile(icons.snowflake, "All Fans Off", "Adjustable fans to 0%", parent=self.extra)
        self.all_half = ActionTile(icons.fan, "All Fans 50%", "Adjustable fans to 50%", parent=self.extra)
        self.all_full = ActionTile(icons.fan, "All Fans 100%", "Adjustable fans to 100%", parent=self.extra)
        place_buttons([self.all_off, self.all_half, self.all_full], QRectF(sx(4), sy(22), sx(776), sy(56)), 3, 0)
        for btn, speed in ((self.all_off, 0.0), (self.all_half, 0.5), (self.all_full, 1.0)):
            btn.clicked.connect(lambda _=False, s=speed: self._set_all(s))
        self._data = {}

    def _page(self, d):
        self.page += d
        self.set_data(self._data)

    def _set_all(self, speed):
        ops = [fan_op(f, speed) for f in self._data.get("fans", [])]
        self.ctl.run_batch([op for op in ops if op])

    def set_data(self, data):
        self._data = data
        fans = data.get("fans") or []
        pages = max(1, (len(fans) + PER_PAGE - 1) // PER_PAGE)
        self.page = max(0, min(self.page, pages - 1))
        shown = fans[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]
        for b in (self.prev, self.next):
            b.setVisible(pages > 1)
        self.prev.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < pages - 1)
        cells = grid(QRectF(sx(8), sy(58), sx(784), sy(288)), PER_PAGE, PER_PAGE, sx(8))
        for i, card in enumerate(self.cards):
            if i < len(shown):
                card.setGeometry(cells[i].toRect())
                card.set_fan(shown[i], data)
                card.show()
            else:
                card.hide()
        ops = [fan_op(f, 0) for f in fans]
        any_ok = any(op and self.ctl.can(op[0], data) for op in ops)
        for b in (self.all_off, self.all_half, self.all_full):
            b.setEnabled(any_ok)
