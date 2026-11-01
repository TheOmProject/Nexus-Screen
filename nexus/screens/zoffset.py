"""Z Offset — the G-code Z offset (homing origin). Relative steps apply at once
(MOVE=1 only while printing); absolute presets ask first; Save applies the offset to
the probe and runs SAVE_CONFIG after confirmation."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import Stepper, enable, place_buttons
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.panels import ActionTile, Panel, SubScreen, Tile

ADJUST = (-0.05, -0.01, -0.005, 0.005, 0.01, 0.05)   # from the reference
PRESETS = (-1.5, -1.25, -1.0, -0.75, -0.5)            # from the reference
STEP = 0.01


def move_flag(state):
    return 1 if state == "printing" else 0  # never move a parked/idle toolhead


class CurrentPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Current Z Offset", parent)
        self.value = None

    def set_value(self, v):
        if v != self.value:
            self.value = v
            self.update()

    def paint_body(self, p):
        b = QRectF(8, 30, self.width() - 16, self.height() - 38)
        paint_panel(p, b, 6, top=QColor(8, 9, 11), bottom=QColor(16, 18, 21), border=QColor(52, 56, 62))
        p.setFont(theme.font(smin(38), QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(b.adjusted(0, -10, 0, -10), Qt.AlignmentFlag.AlignCenter,
                   "--" if self.value is None else f"{self.value:.3f} mm")
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(b.x(), b.bottom() - 34, b.width(), 18), Qt.AlignmentFlag.AlignCenter, "G-code offset")


class ZOffsetScreen(SubScreen):
    TITLE = "Z Offset"
    SUBTITLE = "Set the correct distance between nozzle and bed"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.current = CurrentPanel(self)
        self.current.setGeometry(sx(8), sy(58), sx(250), sy(250))
        self.adjust = Panel("Adjust Offset", self)
        self.adjust.setGeometry(sx(266), sy(58), sx(330), sy(250))
        self.adjust_btns = []
        for d in ADJUST:
            b = SmallButton(f"{d:+.3f}".rstrip("0").rstrip("."), parent=self.adjust, font_px=theme.BUTTON, checkable=False)
            b.clicked.connect(lambda _=False, v=d: self._adjust(v))
            self.adjust_btns.append(b)
        place_buttons(self.adjust_btns, QRectF(sx(10), sy(32), sx(310), sy(112)), 3, sx(8))
        self.stepper = Stepper(self.adjust, lambda d: self._adjust(d * STEP), font_px=theme.FIELD)
        self.stepper.place(sx(10), sy(168), sx(310), sy(64), key_w=sx(64))
        self.presets = Panel("Presets", self)
        self.presets.setGeometry(sx(604), sy(58), sx(188), sy(250))
        self.preset_tiles = []
        for v in PRESETS:
            t = Tile(self._preset_painter(v), self.presets)
            t.setCheckable(False)
            t.clicked.connect(lambda _=False, z=v: self._preset(z))
            self.preset_tiles.append(t)
        place_buttons(self.preset_tiles, QRectF(sx(4), sy(24), sx(180), sy(222)), 1, 0)
        self.actions = Panel("Actions", self)
        self.actions.setGeometry(sx(8), sy(316), sx(784), sy(120))
        self.save = ActionTile(icons.save, "Save Z Offset", "Apply to probe and save config", True, self.actions)
        self.reset = ActionTile(icons.refresh, "Reset Offset", "Set the offset to 0.000", parent=self.actions)
        place_buttons([self.save, self.reset], QRectF(sx(4), sy(26), sx(776), sy(88)), 2, 0)
        self.save.clicked.connect(lambda: self.ctl.confirm(
            "Save Z Offset?", "Applies the current offset to the probe (Z_OFFSET_APPLY_PROBE) and saves "
            "printer.cfg. Klipper restarts.", "Save & Restart", lambda: self.ctl.run("z_offset_save")))
        self.reset.clicked.connect(lambda: self._preset(0.0))  # absolute change: asks first, like the presets
        self._data = {}

    @staticmethod
    def _preset_painter(v):
        def paint(p, r, selected):
            p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
            p.setPen(theme.FG)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, f"{v:.3f}")
        return paint

    def _state(self):
        return self._data.get("state", "")

    def _adjust(self, delta):
        self.ctl.run("z_offset_adjust", delta=round(delta, 3), move=move_flag(self._state()))

    def _preset(self, z):
        cur = self._data.get("z_offset") or 0.0
        self.ctl.confirm(f"Set Z offset to {z:.3f} mm?",
                         f"Current offset is {cur:.3f} mm. A wrong offset can drive the nozzle into the bed.",
                         "Set Offset", lambda: self.ctl.run("z_offset_set", z=z, move=move_flag(self._state())))

    def set_data(self, data):
        self._data = data
        z = data.get("z_offset")
        self.current.set_value(z)
        ok = self.ctl.can("z_offset_adjust", data)
        for b in self.adjust_btns:
            b.setEnabled(ok)
        self.stepper.set("--" if z is None else f"{z:.3f} mm", ok)  # centre key is display-only
        for t, v in zip(self.preset_tiles, PRESETS):
            t.set_highlight(z is not None and abs(z - v) < 0.0005)
            t.setEnabled(self.ctl.can("z_offset_set", data))
        enable(self.ctl, data, [(self.save, "z_offset_save"), (self.reset, "z_offset_set")])
