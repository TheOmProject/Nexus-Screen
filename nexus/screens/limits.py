"""Limits — axis travel from the toolhead, homing positions from printer.cfg, endstop
states (Moonraker's query_endstops, refreshed on demand) and homing actions."""
from PyQt6.QtCore import QRectF

from nexus import theme
from nexus.screens.addon_common import enable, place_buttons
from nexus.widgets import icons
from nexus.widgets.panels import ActionTile, Panel, RowsPanel, SubScreen


class LimitsScreen(SubScreen):
    TITLE = "Limits"
    SUBTITLE = "View printer movement limits"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.axes = RowsPanel("Axis Limits", self, label_w=90)
        self.axes.setGeometry(8, 58, 290, 290)
        self.homing = RowsPanel("Homing Position", self, label_w=110)
        self.homing.setGeometry(306, 58, 486, 128)
        self.endstops = RowsPanel("Endstops", self, label_w=110)
        self.endstops.setGeometry(306, 194, 486, 154)
        self.actions = Panel("Actions", self)
        self.actions.setGeometry(8, 356, 784, 80)
        self.home_btns = {}
        for label, axes in (("Home All", ""), ("Home X", " X"), ("Home Y", " Y"), ("Home Z", " Z")):
            b = ActionTile(icons.house, label, primary=(axes == ""), parent=self.actions)
            b.clicked.connect(lambda _=False, a=axes: self.ctl.run("home", axes=a))
            self.home_btns[label] = b
        self.check = ActionTile(icons.refresh, "Check Endstops", parent=self.actions)
        self.check.clicked.connect(self.reload)
        place_buttons([*self.home_btns.values(), self.check], QRectF(4, 22, 776, 54), 5, 0)
        self._data = {}

    def showEvent(self, e):
        self.reload()
        super().showEvent(e)

    def reload(self):
        self.ctl.get_json("/printer/query_endstops/status", None, self._endstops, lambda: self._endstops(None))

    def _endstops(self, result):
        if not result:
            self.endstops.set_rows([("Status", "Not available", theme.DIM)])
            return
        self.endstops.set_rows([(k.replace("stepper_", "").upper() + " Endstop", v.capitalize(),
                                 theme.AMBER if v.lower() == "triggered" else theme.GREEN) for k, v in result.items()])

    def set_data(self, data):
        self._data = data
        th = data.get("toolhead") or {"min": [0, 0, 0], "max": [0, 0, 0]}
        rows = []
        for i, a in enumerate("XYZ"):
            rows += [(f"{a} (Min)", f"{th['min'][i]:g} mm", None), (f"{a} (Max)", f"{th['max'][i]:g} mm", None)]
        self.axes.set_rows(rows)
        hom = (data.get("config") or {}).get("homing") or {}
        self.homing.set_rows([(f"{a.upper()} Home", "-" if hom.get(a) is None else f"{hom[a]:g} mm", None) for a in "xyz"])
        enable(self.ctl, data, [(b, "home") for b in self.home_btns.values()])
