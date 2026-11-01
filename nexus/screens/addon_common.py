"""Pieces shared by the submenu screens (add-ons, Temperature, Fans, Lighting, Move)."""
from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from nexus import theme
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.overlays import COLOURS, MATERIAL_TEMPS
from nexus.widgets.panels import ActionTile, Panel, paint_rows

TEMP_STEP = 5


def fmt_temp(t):
    return "--" if t is None else f"{t:.0f}°C"  # Rajdhani's ° carries its own left gap


def colour_name(hex_colour):
    return next((n for n, hx in COLOURS if hx.upper() == (hex_colour or "").upper()), (hex_colour or "--").upper())


def default_temp(material, explicit=None):
    return explicit if explicit else MATERIAL_TEMPS.get((material or "").upper(), 0)


def grid(rect, n, cols, gap=6):
    """Cell rects for n items in `cols` columns filling `rect`."""
    rows = max(1, (n + cols - 1) // cols)
    cw = (rect.width() - gap * (cols - 1)) / cols
    ch = (rect.height() - gap * (rows - 1)) / rows
    return [QRectF(rect.x() + (i % cols) * (cw + gap), rect.y() + (i // cols) * (ch + gap), cw, ch)
            for i in range(n)]


def place_buttons(buttons, rect, cols, gap=6, pad=0):
    for b, r in zip(buttons, grid(rect, len(buttons), cols, gap)):
        b.setGeometry(r.adjusted(-pad, -pad, pad, pad).toRect())


def paint_number_band(p, r, text, active):
    band = QRectF(r.x() + 8, r.y() + 6, r.width() - 16, 18)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(210, 24, 18) if active else QColor(255, 255, 255, 14))
    p.drawRoundedRect(band, 3, 3)
    p.setFont(theme.font(theme.LABEL, QFont.Weight.Bold))
    p.setPen(theme.FG if active else theme.FG_SOFT)
    p.drawText(band, Qt.AlignmentFlag.AlignCenter, text)


def paint_status_dot(p, r, ok):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.GREEN if ok else theme.MUTED)
    p.drawEllipse(QRectF(r.x() + 9, r.bottom() - 17, 9, 9))


def paint_caption(p, r, line1, line2, y):
    p.setFont(theme.font(theme.BODY, QFont.Weight.DemiBold))
    p.setPen(theme.FG)
    p.drawText(QRectF(r.x(), y, r.width(), 15), Qt.AlignmentFlag.AlignCenter, line1)
    p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
    p.setPen(theme.FG_SOFT)
    p.drawText(QRectF(r.x(), y + 14, r.width(), 14), Qt.AlignmentFlag.AlignCenter, line2)


def enable(ctl, data, pairs):
    """pairs = [(button, operation_key)] → enabled only if the operation can run now."""
    for button, key in pairs:
        button.setEnabled(ctl.can(key, data))


class HeatPanel(Panel):
    """Temperature panel: Current, Target (− / +) and Set & Heat for one heater."""

    def __init__(self, ctl, parent=None):
        super().__init__("Temperature", parent)
        self.ctl = ctl
        self.heater = "extruder"
        self.current = None
        self.target = 0
        self.minus = SmallButton("-", parent=self, font_px=24, checkable=False)
        self.plus = SmallButton("+", parent=self, font_px=24, checkable=False)
        self.heat = ActionTile(icons.thermometer, "Set & Heat", primary=True, parent=self)
        self.minus.clicked.connect(lambda: self._step(-TEMP_STEP))
        self.plus.clicked.connect(lambda: self._step(TEMP_STEP))
        self.heat.clicked.connect(lambda: self.ctl.run("set_heater", heater=self.heater, target=float(self.target)))

    def resizeEvent(self, e):
        w, h = self.width(), self.height()
        self.minus.setGeometry(w - 92, 64, 40, 34)
        self.plus.setGeometry(w - 48, 64, 40, 34)
        self.heat.setGeometry(4, h - 68, w - 8, 62)
        super().resizeEvent(e)

    def set_heater(self, heater, target):
        self.heater, self.target = heater, int(target or 0)
        self.update()

    def set_data(self, data):
        cur = (data.get("heaters") or {}).get(self.heater)
        self.current = None if cur is None else cur[0]
        lo, hi = (data.get("limits") or {}).get(self.heater, (0, 0))
        self.minus.setEnabled(self.target > 0)
        self.plus.setEnabled(self.target + TEMP_STEP <= hi)
        self.heat.setEnabled(self.ctl.can("set_heater", data) and self.heater in (data.get("limits") or {}))
        self.update()

    def _step(self, d):
        self.target = max(0, self.target + d)
        self.ctl.refresh_controls()

    def paint_body(self, p):
        r = QRectF(8, 28, self.width() - 16, 70)
        paint_rows(p, r, [("Current", fmt_temp(self.current), None),
                          ("Target", fmt_temp(self.target) if self.target else "Off", None)], label_w=64)


class Debounce:
    """Run fn(*args) once, `ms` after the last call — −/+ bursts send one command."""

    def __init__(self, owner, ms=600):
        self._timer = QTimer(owner)
        self._timer.setSingleShot(True)
        self._timer.setInterval(ms)
        self._timer.timeout.connect(self._fire)
        self._call = None

    def __call__(self, fn, *args):
        self._call = (fn, args)
        self._timer.start()

    def pending(self):
        return self._timer.isActive()

    def _fire(self):
        if self._call:
            fn, args = self._call
            self._call = None
            fn(*args)


class Stepper:
    """− [value] + row. The centre key shows the value and may open the keypad."""

    def __init__(self, parent, on_step, on_value=None, font_px=theme.FIELD):
        self.minus = SmallButton("-", parent=parent, font_px=24, checkable=False)
        self.value = SmallButton("", parent=parent, font_px=font_px, checkable=False)
        self.plus = SmallButton("+", parent=parent, font_px=24, checkable=False)
        self.minus.clicked.connect(lambda: on_step(-1))
        self.plus.clicked.connect(lambda: on_step(1))
        if on_value:
            self.value.clicked.connect(on_value)

    def place(self, x, y, w, h, key_w=None):
        key_w = key_w or h + 6
        self.minus.setGeometry(int(x), int(y), key_w, h)
        self.value.setGeometry(int(x + key_w + 4), int(y), int(w - 2 * key_w - 8), h)
        self.plus.setGeometry(int(x + w - key_w), int(y), key_w, h)

    def set(self, text, enabled, minus_ok=True, plus_ok=True):
        if self.value._text != text:
            self.value._text = text
            self.value.update()
        self.value.setEnabled(enabled)
        self.minus.setEnabled(enabled and minus_ok)
        self.plus.setEnabled(enabled and plus_ok)

    def setVisible(self, visible):
        for b in (self.minus, self.value, self.plus):
            b.setVisible(visible)


def paint_bar(p, rect, fraction, colour):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(38, 41, 47))
    p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
    if fraction > 0:
        fill = QRectF(rect.x(), rect.y(), rect.width() * min(1.0, fraction), rect.height())
        p.setBrush(QColor(colour))
        p.drawRoundedRect(fill, rect.height() / 2, rect.height() / 2)
