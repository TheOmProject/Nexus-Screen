"""Temperature — heaters with − / value / + (value opens the keypad), presets,
PID tune / save / cooldown, and a status summary. Landscape adaptation of the
portrait reference."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QWidget

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import Debounce, Stepper, enable, grid, paint_bar, place_buttons
from nexus.widgets import icons
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.panels import ActionTile, Panel, SubScreen, Tile

STEP = 5
PRESETS = [("PLA", 220, 60), ("PETG", 230, 70), ("ABS", 240, 100), ("TPU", 210, 50)]  # from the reference
HEATERS = [("extruder", "Nozzle", icons.nozzle, "#ff2a22"),
           ("heater_bed", "Bed", icons.bed, "#ff8a1a"),
           ("chamber", "Chamber", icons.chamber, "#2f8bff")]


def _fmt(t):
    return "--" if t is None else f"{t:.0f}°C"


def available_heaters(data):
    """Heaters the printer actually has; the chamber only if it is a controllable heater."""
    out = []
    for key, label, icon, colour in HEATERS:
        if key == "chamber" and data.get("chamber_heater") != "chamber":
            continue
        if key in (data.get("heaters") or {}):
            out.append((key, label, icon, colour))
    return out


class HeaterCard(QWidget):
    def __init__(self, ctl, key, label, icon, colour, parent=None):
        super().__init__(parent)
        self.ctl, self.key, self.label, self.icon, self.colour = ctl, key, label, icon, QColor(colour)
        self.current = None
        self.target = None
        self.pending = None
        self.limits = (0.0, 0.0)
        self.debounce = Debounce(self)
        self.stepper = Stepper(self, self._step, lambda: self.ctl.open_keypad(self.key), font_px=theme.FIELD)

    def resizeEvent(self, e):
        self.stepper.place(10, self.height() - 46, self.width() - 20, 36, key_w=46)
        super().resizeEvent(e)

    def set_data(self, data):
        cur = (data.get("heaters") or {}).get(self.key) or (None, None)
        self.current, self.target = cur
        self.limits = (data.get("limits") or {}).get(self.key, (0.0, 0.0))
        if not self.debounce.pending():
            self.pending = None
        shown = self.pending if self.pending is not None else (self.target or 0)
        ok = self.ctl.can("set_heater", data)
        self.stepper.set(f"{shown:.0f}", ok, shown > 0, shown + STEP <= self.limits[1])
        self.update()

    def _step(self, d):
        base = self.pending if self.pending is not None else (self.target or 0)
        self.pending = max(0, min(self.limits[1], base + d * STEP))
        if 0 < self.pending < self.limits[0]:
            self.pending = self.limits[0]
        self.stepper.set(f"{self.pending:.0f}", True, self.pending > 0, self.pending + STEP <= self.limits[1])
        self.debounce(lambda t: self.ctl.run("set_heater", heater=self.key, target=float(t)), self.pending)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        paint_panel(p, QRectF(0, 0, w, h), 7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.colour)
        p.drawRoundedRect(QRectF(3, 8, 3.5, h - 16), 1.5, 1.5)
        self.icon(p, QRectF(16, 10, 22, 22), self.colour if self.key != "chamber" else QColor(theme.FG_SOFT))
        p.setFont(theme.font(theme.CARD, QFont.Weight.DemiBold))
        p.setPen(theme.FG)
        p.drawText(QRectF(46, 10, w - 56, 22), Qt.AlignmentFlag.AlignVCenter, self.label)
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(0, 36, w, 14), Qt.AlignmentFlag.AlignCenter, "Current")
        p.setFont(theme.font(smin(32), QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(0, 48, w, 38), Qt.AlignmentFlag.AlignCenter, _fmt(self.current))
        p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(0, 86, w, 16), Qt.AlignmentFlag.AlignCenter,
                   "Target: Off" if not self.target else f"Target: {_fmt(self.target)}")
        p.end()


class StatusPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Temperature Status", parent)
        self.rows = []

    def set_rows(self, rows):
        if rows != self.rows:
            self.rows = rows
            self.update()

    def paint_body(self, p):
        if not self.rows:
            return
        for r, (label, icon, colour, cur, target) in zip(grid(QRectF(8, 30, self.width() - 16, self.height() - 38),
                                                             len(self.rows), 1, 6), self.rows):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 8))
            p.drawRoundedRect(r, 5, 5)
            icon(p, QRectF(r.x() + 10, r.center().y() - 10, 20, 20), QColor(colour))
            p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
            p.setPen(theme.FG)
            p.drawText(QRectF(r.x() + 38, r.y(), 74, r.height()), Qt.AlignmentFlag.AlignVCenter, label)
            p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
            p.setPen(theme.FG_SOFT)
            p.drawText(QRectF(r.x() + 116, r.y(), 104, r.height()), Qt.AlignmentFlag.AlignVCenter,
                       f"{_fmt(cur)} / {_fmt(target) if target else 'Off'}")
            frac = (cur / target) if target else 0.0
            paint_bar(p, QRectF(r.x() + 224, r.center().y() - 4, r.width() - 280, 8), frac, colour)
            p.setPen(theme.DIM)
            p.drawText(QRectF(r.right() - 50, r.y(), 44, r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       f"{min(999, round(frac * 100))}%" if target else "--")


class TemperatureScreen(SubScreen):
    TITLE = "Temperature"
    SUBTITLE = "Monitor and control printer temperatures"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.cards = {key: HeaterCard(ctl, key, label, icon, colour, self) for key, label, icon, colour in HEATERS}
        self.presets = Panel("Presets", self)
        self.presets.setGeometry(sx(8), sy(224), sx(388), sy(100))
        self.preset_tiles = []
        for name, nozzle, bed in PRESETS:
            t = Tile(self._preset_painter(name, nozzle, bed), self.presets)
            t.setCheckable(False)
            t.clicked.connect(lambda _=False, n=nozzle, b=bed: self.ctl.run("preheat", nozzle=float(n), bed=float(b)))
            self.preset_tiles.append(t)
        place_buttons(self.preset_tiles, QRectF(sx(4), sy(24), sx(380), sy(72)), 4, 0)
        self.control = Panel("Temperature Control", self)
        self.control.setGeometry(sx(8), sy(332), sx(388), sy(104))
        self.pid = ActionTile(icons.thermometer, "Run PID Tune", parent=self.control, stacked=True)
        self.save = ActionTile(icons.save, "Save to Config", parent=self.control, stacked=True)
        self.cool = ActionTile(icons.snowflake, "Cooldown", parent=self.control, stacked=True)
        place_buttons([self.pid, self.save, self.cool], QRectF(sx(4), sy(24), sx(380), sy(76)), 3, 0)
        self.pid.clicked.connect(self.ctl.start_pid_tune)
        self.save.clicked.connect(self.ctl.confirm_save_config)
        self.cool.clicked.connect(lambda: self.ctl.run("heaters_off"))
        self.status = StatusPanel(self)
        self.status.setGeometry(sx(404), sy(224), sx(388), sy(212))
        self._data = {}

    @staticmethod
    def _preset_painter(name, nozzle, bed):
        def paint(p, r, selected):
            p.setFont(theme.font(theme.NAME, QFont.Weight.Bold))
            p.setPen(theme.FG)
            p.drawText(QRectF(r.x(), r.y() + 6, r.width(), 22), Qt.AlignmentFlag.AlignCenter, name)
            p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
            p.setPen(theme.FG_SOFT if selected else theme.DIM)
            p.drawText(QRectF(r.x(), r.y() + 30, r.width(), 18), Qt.AlignmentFlag.AlignCenter, f"({nozzle} / {bed})")
        return paint

    def set_data(self, data):
        self._data = data
        heaters = available_heaters(data)
        n = max(1, len(heaters))
        for key, card in self.cards.items():
            card.setVisible(any(h[0] == key for h in heaters))
        for (key, *_), r in zip(heaters, grid(QRectF(sx(8), sy(58), sx(784), sy(158)), n, n, sx(8))):
            self.cards[key].setGeometry(r.toRect())
            self.cards[key].set_data(data)
        nozzle_t = ((data.get("heaters") or {}).get("extruder") or (0, 0))[1]
        bed_t = ((data.get("heaters") or {}).get("heater_bed") or (0, 0))[1]
        for t, (name, nz, bd) in zip(self.preset_tiles, PRESETS):
            t.set_highlight(nozzle_t == nz and bed_t == bd)  # the preset matching the current targets
            t.setEnabled(self.ctl.can("preheat", data))
        enable(self.ctl, data, [(self.pid, "pid_tune"), (self.save, "save_config"), (self.cool, "heaters_off")])
        self.status.set_rows([(label, icon, colour, *((data.get("heaters") or {}).get(key) or (None, None)))
                              for key, label, icon, colour in heaters])
