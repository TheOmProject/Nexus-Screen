"""Lighting — one card per LED object (neopixel/dotstar/led/pca*) Klipper reports:
on/off, brightness, colour; presets set every light's brightness."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton

from nexus import theme
from nexus.config import SCREEN_W, sx, sy, smin
from nexus.screens.addon_common import Debounce, Stepper, grid, place_buttons
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton, ToggleSwitch
from nexus.widgets.dial_gauge import DialGauge
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.panels import ActionTile, Panel, SubScreen

STEP = 0.10
PER_PAGE = 4
CARD_W = sx(190)
DOTS = ["#FFFFFF", "#FF2A22", "#FF7A1A", "#FFD21A", "#33D14F", "#14C8B4", "#2F9BFF", "#A04BFF"]
PRESETS = [("Off", "", 0.0), ("Low", "25%", 0.25), ("Medium", "50%", 0.50), ("High", "100%", 1.0)]


def split(colour):
    """(r, g, b) 0..1 -> (base colour with max channel 1, brightness)."""
    b = max(colour) if colour else 0.0
    if b <= 0.001:
        return (1.0, 1.0, 1.0), 0.0
    return tuple(c / b for c in colour), b


def hex_rgb(hx):
    c = QColor(hx)
    return (c.redF(), c.greenF(), c.blueF())


def led_params(light, base, brightness):
    r, g, b = (round(c * brightness, 3) for c in base)
    return {"led": light["led"], "r": r, "g": g, "b": b}


class ColourDot(QAbstractButton):
    def __init__(self, hx, parent=None):
        super().__init__(parent)
        self.hx = hx
        self.selected = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        rad = min(self.width(), self.height()) / 2 - 2
        if self.selected:
            p.setPen(QPen(QColor(theme.FG), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, rad, rad)
        p.setPen(QPen(QColor(0, 0, 0, 140), 1))
        p.setBrush(QColor(self.hx) if self.isEnabled() else QColor(self.hx).darker(250))
        p.drawEllipse(c, rad - 3, rad - 3)
        p.end()


class LightCard(Panel):
    def __init__(self, ctl, parent=None):
        super().__init__("", parent)
        self.ctl = ctl
        self.light = None
        self.base = (1.0, 1.0, 1.0)
        self.level = 0.0
        self.last_level = 1.0
        self.pending = False
        self.toggle = ToggleSwitch(self)
        self.gauge = DialGauge(icons.bulb, self)
        self.stepper = Stepper(self, self._step)
        self.dots = [ColourDot(hx, self) for hx in DOTS]
        self.custom = SmallButton("Custom Colour  ›", parent=self, font_px=theme.BUTTON, checkable=False)
        self.debounce = Debounce(self)
        self.toggle.clicked.connect(self._toggled)
        for d in self.dots:
            d.clicked.connect(lambda _=False, hx=d.hx: self._colour(hex_rgb(hx)))
        self.custom.clicked.connect(lambda: self.light and self.ctl.pick_colour(
            self.light["name"], QColor.fromRgbF(*self.base).name().upper(), lambda hx: self._colour(hex_rgb(hx))))

    def resizeEvent(self, e):
        w = self.width()
        self.toggle.setGeometry(w - sx(54), sy(12), sx(44), sy(22))
        self.gauge.setGeometry(int(w / 2 - smin(56)), sy(46), smin(112), smin(112))
        self.stepper.place(sx(10), sy(190), w - sx(20), sy(32), key_w=sx(40))
        for i, d in enumerate(self.dots):
            d.setGeometry(int(sx(10) + i * (w - sx(20)) / len(self.dots)), sy(226), int((w - sx(20)) / len(self.dots)), sy(24))
        self.custom.setGeometry(sx(10), sy(254), w - sx(20), sy(28))
        super().resizeEvent(e)

    def set_light(self, light, data):
        self.light = light
        if not self.debounce.pending():
            self.pending = False
            base, level = split(light["color"])
            if level > 0:
                self.base, self.last_level = base, level
            self.level = level
        ok = self.ctl.can("set_led", data)
        self._sync(ok)

    def _sync(self, ok):
        self.toggle.setChecked(self.level > 0.001)
        self.toggle.setEnabled(ok)
        self.gauge.set_value(self.level, QColor.fromRgbF(*self.base) if self.base != (1.0, 1.0, 1.0) else None)
        self.stepper.set(f"{round(self.level * 100)}%", ok, self.level > 0.001, self.level < 0.999)
        for d in self.dots:
            d.selected = QColor(d.hx).name() == QColor.fromRgbF(*self.base).name()
            d.setEnabled(ok)
            d.update()
        self.custom.setEnabled(ok)
        self.update()

    def _send(self):
        self.debounce(lambda prm: self.ctl.run("set_led", **prm), led_params(self.light, self.base, self.level))
        self._sync(True)

    def _step(self, d):
        self.level = round(max(0.0, min(1.0, self.level + d * STEP)), 2)
        if self.level > 0:
            self.last_level = self.level
        self._send()

    def _toggled(self):
        self.level = 0.0 if self.level > 0.001 else (self.last_level or 1.0)
        self._send()

    def _colour(self, rgb):
        self.base = split(rgb)[0]
        if self.level <= 0.001:
            self.level = self.last_level or 1.0
        self._send()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        paint_panel(p, QRectF(0, 0, w, self.height()), 7)
        if self.light:
            icons.bulb(p, QRectF(12, 12, 16, 20), QColor(theme.FG_SOFT))
            nf = theme.font(theme.LABEL, QFont.Weight.DemiBold)  # narrow card: name beside the switch
            p.setFont(nf)
            p.setPen(theme.FG)
            p.drawText(QRectF(34, 8, w - 94, 20), Qt.AlignmentFlag.AlignVCenter,
                       QFontMetricsF(nf).elidedText(self.light["name"], Qt.TextElideMode.ElideRight, w - 94))
            f = theme.font(theme.SMALL, QFont.Weight.Medium)
            p.setFont(f)
            p.setPen(theme.DIM)
            p.drawText(QRectF(34, 26, w - 94, 14), Qt.AlignmentFlag.AlignVCenter,
                       QFontMetricsF(f).elidedText(self.light["id"], Qt.TextElideMode.ElideRight, w - 94))
            p.setFont(theme.font(smin(24), QFont.Weight.Bold))
            p.setPen(theme.FG)
            p.drawText(QRectF(0, 158, w, 30), Qt.AlignmentFlag.AlignCenter, f"{round(self.level * 100)}%")
        p.end()


class LightingScreen(SubScreen):
    TITLE = "Lighting"
    SUBTITLE = "Control LED lights, brightness and colour"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.cards = [LightCard(ctl, self) for _ in range(PER_PAGE)]
        self.prev = SmallButton(icon=icons.back_arrow, parent=self, checkable=False)
        self.next = SmallButton(icon=icons.chevron, parent=self, checkable=False)
        self.prev.setGeometry(sx(700), sy(14), sx(40), sy(30))
        self.next.setGeometry(sx(748), sy(14), sx(40), sy(30))
        self.prev.clicked.connect(lambda: self._page(-1))
        self.next.clicked.connect(lambda: self._page(1))
        self.page = 0
        self.presets = Panel("Presets", self)
        self.presets.setGeometry(sx(8), sy(354), sx(784), sy(82))
        self.preset_btns = []
        for name, sub, level in PRESETS:
            b = ActionTile(icons.bulb, name, sub or "All lights off", parent=self.presets)
            b.clicked.connect(lambda _=False, lv=level: self._preset(lv))
            self.preset_btns.append(b)
        place_buttons(self.preset_btns, QRectF(sx(4), sy(22), sx(776), sy(56)), 4, 0)
        self._data = {}

    def _page(self, d):
        self.page += d
        self.set_data(self._data)

    def _preset(self, level):
        items = []
        for light in self._data.get("lights", []):
            items.append(("set_led", led_params(light, split(light["color"])[0], level)))
        self.ctl.run_batch(items)

    def set_data(self, data):
        self._data = data
        lights = data.get("lights") or []
        pages = max(1, (len(lights) + PER_PAGE - 1) // PER_PAGE)
        self.page = max(0, min(self.page, pages - 1))
        shown = lights[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]
        for b in (self.prev, self.next):
            b.setVisible(pages > 1)
        self.prev.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < pages - 1)
        n = len(shown)
        total = n * CARD_W + (n - 1) * 8 if n else 0
        x0 = sx(8) if n == PER_PAGE else (SCREEN_W - total) / 2  # fewer lights: centred row
        cells = grid(QRectF(sx(8), sy(58), sx(784), sy(288)), PER_PAGE, PER_PAGE, sx(8))
        for i, card in enumerate(self.cards):
            if i < n:
                r = cells[i] if n == PER_PAGE else QRectF(x0 + i * (CARD_W + sx(8)), sy(58), CARD_W, sy(288))
                card.setGeometry(r.toRect())
                card.set_light(shown[i], data)
                card.show()
            else:
                card.hide()
        ok = bool(lights) and self.ctl.can("set_led", data)
        for b in self.preset_btns:
            b.setEnabled(ok)
