"""Extruder — temperature, extrude / retract with distance and speed, status, flow rate
(M221), pressure advance and the extruder fan (read-only, Klipper-controlled)."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import place_buttons
from nexus.screens.extrusion import ExtruderStatus, NozzlePanel
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.panels import ActionTile, Panel, SubScreen

DISTANCES = (1, 5, 10, 25, 50, 100)   # "+" cycles, as in the reference
SPEEDS = (1, 2, 5, 10, 15)
DEFAULT_DISTANCE, DEFAULT_SPEED = 10, 5


def _next(options, value, cap=None):
    allowed = [o for o in options if cap is None or o <= cap] or [options[0]]
    later = [o for o in allowed if o > value]
    return later[0] if later else allowed[0]


class MoveColumn:
    """Distance / speed rows and the action button for Extrude or Retract."""

    def __init__(self, panel, x, title, icon, primary, on_go):
        self.title, self.x = title, x
        self.distance, self.speed = DEFAULT_DISTANCE, DEFAULT_SPEED
        self.dist_val = SmallButton("", parent=panel, font_px=theme.BUTTON, checkable=False)
        self.dist_plus = SmallButton("+", parent=panel, font_px=22, checkable=False)
        self.speed_val = SmallButton("", parent=panel, font_px=theme.BUTTON, checkable=False)
        self.speed_plus = SmallButton("+", parent=panel, font_px=22, checkable=False)
        self.go = ActionTile(icon, title, parent=panel, primary=primary)
        for b in (self.dist_val, self.dist_plus):
            b.clicked.connect(lambda: self._cycle("distance"))
        for b in (self.speed_val, self.speed_plus):
            b.clicked.connect(lambda: self._cycle("speed"))
        self.go.clicked.connect(lambda: on_go(self.distance, self.speed))
        self.dist_val.setGeometry(sx(x + 70), sy(52), sx(82), sy(36))
        self.dist_plus.setGeometry(sx(x + 156), sy(52), sx(36), sy(36))
        self.speed_val.setGeometry(sx(x + 70), sy(94), sx(82), sy(36))
        self.speed_plus.setGeometry(sx(x + 156), sy(94), sx(36), sy(36))
        self.go.setGeometry(sx(x), sy(140), sx(196), sy(66))
        self.cap = None
        self.refresh = lambda: None

    def _cycle(self, which):
        if which == "distance":
            self.distance = _next(DISTANCES, self.distance)
        else:
            self.speed = _next(SPEEDS, self.speed, self.cap)
        self.refresh()

    def sync(self, enabled, cap):
        self.cap = cap
        allowed = [o for o in SPEEDS if o <= cap] or [SPEEDS[0]]
        if self.speed not in allowed:
            self.speed = allowed[-1]
        self.dist_val._text = f"{self.distance} mm"
        self.speed_val._text = f"{self.speed} mm/s"
        for b in (self.dist_val, self.dist_plus, self.speed_val, self.speed_plus):
            b.setEnabled(enabled)
            b.update()

    def paint(self, p):
        p.setFont(theme.font(theme.LABEL, QFont.Weight.DemiBold))
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(sx(self.x), sy(28), sx(196), sy(20)), Qt.AlignmentFlag.AlignCenter, self.title)
        p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(sx(self.x), sy(52), sx(66), sy(36)), Qt.AlignmentFlag.AlignVCenter, "Distance")
        p.drawText(QRectF(sx(self.x), sy(94), sx(66), sy(36)), Qt.AlignmentFlag.AlignVCenter, "Speed")


class ExtrudePanel(Panel):
    def __init__(self, ctl, parent=None):
        super().__init__("Extrude / Retract", parent)
        job = ctl.filament_job
        self.extrude = MoveColumn(self, 8, "Extrude", icons.advance, True,
                                  lambda d, s: job.start("Extruding", d, s))
        self.retract = MoveColumn(self, 210, "Retract", icons.retract, False,
                                  lambda d, s: job.start("Retracting", -d, s))

    def paint_body(self, p):
        self.extrude.paint(p)
        self.retract.paint(p)
        p.setPen(QColor(theme.DIVIDER))
        p.drawLine(sx(205), sy(32), sx(205), self.height() - sy(12))


class ExtruderScreen(SubScreen):
    TITLE = "Extruder"
    SUBTITLE = "Control extruder motor, temperature and flow"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.temp = NozzlePanel(ctl, self)
        self.temp.setGeometry(sx(8), sy(58), sx(190), sy(240))
        self.moves = ExtrudePanel(ctl, self)
        self.moves.setGeometry(sx(206), sy(58), sx(414), sy(240))
        for col in (self.moves.extrude, self.moves.retract):
            col.refresh = lambda: self.set_data(self._data)
        self.status = ExtruderStatus(self)
        self.status.setGeometry(sx(628), sy(58), sx(164), sy(240))
        self.extra = Panel("Additional Controls", self)
        self.extra.setGeometry(sx(8), sy(306), sx(784), sy(130))
        self.extra.paint_body = self._paint_fan
        self.flow = ActionTile(icons.gear, "Flow Rate", "--", parent=self.extra)
        self.pa = ActionTile(icons.mesh_grid, "Pressure Advance", "--", parent=self.extra)
        place_buttons([self.flow, self.pa], QRectF(sx(4), sy(28), sx(520), sy(96)), 2, 0)
        self.flow.clicked.connect(self._edit_flow)
        self.pa.clicked.connect(self._edit_pa)
        ctl.filament_job.changed.connect(lambda: self.set_data(self.ctl._data))
        self._data = {}

    def _edit_flow(self):
        cur = ((self._data.get("extruder") or {}).get("flow") or 1.0) * 100
        self.ctl.edit_value("Flow Rate", "%", cur, 50, 150, 3, 0,
                            lambda v: self.ctl.run("flow_rate", percent=round(v)))

    def _edit_pa(self):
        cur = (self._data.get("extruder") or {}).get("pa") or 0.0
        self.ctl.edit_value("Pressure Advance", "", cur, 0.0, 1.0, 1, 3,
                            lambda v: self.ctl.run("pressure_advance", value=v))

    def _hotend_fan(self):
        return next((f for f in self._data.get("fans") or [] if f["id"].startswith("heater_fan ")), None)

    def _paint_fan(self, p):
        r = QRectF(sx(536), sy(32), sx(240), sy(88))
        icons.fan(p, QRectF(r.x() + sx(8), r.center().y() - sy(16), smin(32), smin(32)), QColor(theme.FG_SOFT))
        fan = self._hotend_fan()
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
        p.setPen(theme.FG)
        p.drawText(QRectF(r.x() + sx(52), r.y() + sy(16), sx(180), sy(22)), Qt.AlignmentFlag.AlignVCenter, "Extruder Fan")
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        text = "Not detected" if fan is None else (
            f"Automatic · {round(fan['speed'] * 100)}%" if fan["speed"] > 0 else "Automatic · OFF")
        p.drawText(QRectF(r.x() + sx(52), r.y() + sy(40), sx(180), sy(18)), Qt.AlignmentFlag.AlignVCenter, text)

    def set_data(self, data):
        self._data = data
        job = self.ctl.filament_job
        self.temp.set_data(data)
        self.status.set_data(data, job)
        ext = data.get("extruder") or {}
        cap = (data.get("extruder_cfg") or {}).get("max_speed", 10.0)
        can = self.ctl.can("extrude", data) and not job.busy() and ext.get("can_extrude", False)
        for col in (self.moves.extrude, self.moves.retract):
            col.sync(not job.busy(), cap)
            col.go.setEnabled(can)
        self.flow._subtitle = "--" if ext.get("flow") is None else f"{ext['flow'] * 100:.0f} %"
        self.pa._subtitle = "--" if ext.get("pa") is None else f"{ext['pa']:.3f}"
        self.flow.setEnabled(self.ctl.can("flow_rate", data))
        self.pa.setEnabled(self.ctl.can("pressure_advance", data))
        for b in (self.flow, self.pa):
            b.update()
        self.extra.update()
