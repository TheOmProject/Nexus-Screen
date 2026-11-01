"""Move — X/Y jog wheel, Z keys, step distance, position, homing and bed-position
presets. Moves need the axis homed and an idle printer; Home never runs during a print."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QButtonGroup, QWidget

from nexus import theme
from nexus.moonraker.commands import XY_FEED, Z_FEED
from nexus.screens.addon_common import place_buttons
from nexus.widgets import icons
from nexus.widgets.buttons import JogKey, SmallButton
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.jog_wheel import JogWheel
from nexus.widgets.panels import ActionTile, Panel, SubScreen

STEPS = (0.1, 1, 5, 10, 25)
DEFAULT_STEP = 1          # selected in the reference
PRESET_MARGIN = 15.0      # mm inside the axis limits for the corner presets
PRESETS = [("Center", icons.crosshair), ("Front Left", icons.corner), ("Front Right", icons.corner),
           ("Back Left", icons.corner), ("Back Right", icons.corner)]


def preset_xy(name, th):
    (x0, y0, _), (x1, y1, _) = th["min"], th["max"]
    m = PRESET_MARGIN
    return {"Center": ((x0 + x1) / 2, (y0 + y1) / 2), "Front Left": (x0 + m, y0 + m),
            "Front Right": (x1 - m, y0 + m), "Back Left": (x0 + m, y1 - m), "Back Right": (x1 - m, y1 - m)}[name]


class PositionPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Position (mm)", parent)
        self.pos = None

    def set_pos(self, pos, homed):
        view = (tuple(round(v, 2) for v in pos), homed)
        if view != self.pos:
            self.pos = view
            self.update()

    def paint_body(self, p):
        if not self.pos:
            return
        pos, homed = self.pos
        w = (self.width() - 16 - 16) / 3
        for i, axis in enumerate("XYZ"):
            x = 8 + i * (w + 8)
            p.setFont(theme.font(theme.CAPTION, QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(QRectF(x + 4, 26, w, 16), Qt.AlignmentFlag.AlignVCenter, axis)
            box = QRectF(x, 44, w, 40)
            paint_panel(p, box, 5, top=QColor(8, 9, 11), bottom=QColor(16, 18, 21), border=QColor(52, 56, 62))
            p.setFont(theme.font(19, QFont.Weight.Bold))
            p.setPen(theme.FG if axis.lower() in homed else theme.MUTED)
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, f"{pos[i]:.2f}" if axis == "Z" else f"{pos[i]:.1f}")


class ZRocker(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.up = JogKey(icons.chevron_up, "Z+", self)
        self.down = JogKey(icons.chevron_down, "Z-", self)

    def resizeEvent(self, e):
        w, h = self.width(), self.height()
        self.up.setGeometry(8, 14, w - 16, h // 2 - 26)
        self.down.setGeometry(8, h // 2 + 12, w - 16, h // 2 - 26)
        super().resizeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        paint_panel(p, QRectF(0, 0, w, h), 12, top=QColor(40, 43, 48), bottom=QColor(16, 18, 21),
                    border=QColor(80, 85, 92))
        p.setPen(Qt.PenStyle.NoPen)
        for y in (5, h - 8):
            p.setBrush(QColor(255, 40, 30, 200))
            p.drawRoundedRect(QRectF(w / 2 - 16, y, 32, 3), 1.5, 1.5)
        p.setBrush(QColor(255, 40, 30, 60))
        p.drawRoundedRect(QRectF(w / 2 - 4, h / 2 - 16, 8, 32), 3, 3)
        p.setBrush(QColor(255, 48, 36))
        p.drawRoundedRect(QRectF(w / 2 - 1.5, h / 2 - 14, 3, 28), 1.5, 1.5)
        p.end()


class MoveScreen(SubScreen):
    TITLE = "Move"
    SUBTITLE = "Move axes, set distance and home"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.wheel = JogWheel(self)
        self.wheel.setGeometry(14, 52, 304, 304)
        self.wheel.jog.connect(self._jog)
        self.wheel.home.connect(lambda: self.ctl.run("home", axes=""))
        self.z = ZRocker(self)
        self.z.setGeometry(330, 60, 88, 290)
        self.z.up.clicked.connect(lambda: self._jog("Z", 1))
        self.z.down.clicked.connect(lambda: self._jog("Z", -1))
        self.step_panel = Panel("Step Distance (mm)", self)
        self.step_panel.setGeometry(428, 58, 364, 76)
        self.step_group = QButtonGroup(self)
        self.step_group.setExclusive(True)
        self.step_buttons = {}
        for s in STEPS:
            b = SmallButton(f"{s:g}", parent=self.step_panel, font_px=theme.BUTTON)
            self.step_group.addButton(b)
            self.step_buttons[s] = b
        place_buttons(list(self.step_buttons.values()), QRectF(8, 28, 348, 40), 5, 6)
        self.step_buttons[DEFAULT_STEP].setChecked(True)
        self.position = PositionPanel(self)
        self.position.setGeometry(428, 142, 364, 96)
        self.quick = Panel("Quick Move", self)
        self.quick.setGeometry(428, 246, 364, 104)
        self.home_btns = {}
        for label, axes in (("Home X", " X"), ("Home Y", " Y"), ("Home Z", " Z"), ("Home All", "")):
            b = ActionTile(icons.house, label, parent=self.quick)
            b.clicked.connect(lambda _=False, a=axes: self.ctl.run("home", axes=a))
            self.home_btns[label] = b
        place_buttons(list(self.home_btns.values()), QRectF(4, 22, 356, 78), 4, 0)
        self.presets = Panel("Presets", self)
        self.presets.setGeometry(8, 358, 784, 78)
        self.preset_btns = {}
        for name, icon in PRESETS:
            b = ActionTile(icon, name, parent=self.presets)
            b.clicked.connect(lambda _=False, n=name: self._goto(n))
            self.preset_btns[name] = b
        place_buttons(list(self.preset_btns.values()), QRectF(4, 22, 776, 52), 5, 0)
        self._data = {}

    def step(self):
        return next(s for s, b in self.step_buttons.items() if b.isChecked())

    def _jog(self, axis, direction):
        feed = Z_FEED if axis == "Z" else XY_FEED
        self.ctl.run("jog", axis=axis, distance=direction * self.step(), feed=feed)

    def _goto(self, name):
        th = self._data.get("toolhead")
        if th:
            x, y = preset_xy(name, th)
            self.ctl.run("move_to", x=round(x, 1), y=round(y, 1), feed=XY_FEED)

    def set_data(self, data):
        self._data = data
        th = data.get("toolhead") or {"homed": "", "pos": [0, 0, 0], "min": [0, 0, 0], "max": [0, 0, 0]}
        homed = th["homed"]
        jog_ok = self.ctl.can("jog", data)
        self.wheel.set_enabled_axes(jog_ok and "x" in homed, jog_ok and "y" in homed, self.ctl.can("home", data))
        self.z.up.setEnabled(jog_ok and "z" in homed)
        self.z.down.setEnabled(jog_ok and "z" in homed)
        self.position.set_pos(th["pos"], homed)
        home_ok = self.ctl.can("home", data)
        for b in self.home_btns.values():
            b.setEnabled(home_ok)
        move_ok = self.ctl.can("move_to", data) and "x" in homed and "y" in homed
        for b in self.preset_btns.values():
            b.setEnabled(move_ok)
