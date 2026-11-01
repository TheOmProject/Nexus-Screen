"""StealthChanger (klipper-toolchanger) Dashboard and Controls. Tools come from the
toolchanger object; nothing is fixed to T0–T4."""
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QButtonGroup

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import (HeatPanel, colour_name, default_temp, enable, fmt_temp, grid, paint_caption,
                                        paint_number_band, paint_status_dot, place_buttons)
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.panels import ActionTile, Panel, RowsPanel, SubScreen, Tile, paint_rows


class _ToolSelection:
    """Selected tool name shared by both StealthChanger screens."""
    name = None


def _tools(data):
    sc = data.get("stealthchanger") or {}
    return sc, sc.get("details", [])


def _active(data):
    sc, tools = _tools(data)
    a = sc.get("active")
    return tools[a] if a is not None and a < len(tools) else None


def _selected(data):
    sc, tools = _tools(data)
    names = [t["name"] for t in tools]
    if _ToolSelection.name not in names:
        act = _active(data)
        _ToolSelection.name = act["name"] if act else (names[0] if names else None)
    return next((t for t in tools if t["name"] == _ToolSelection.name), None)


def _heater(data, tool):
    return (data.get("heaters") or {}).get(tool["extruder"]) if tool else None


class StealthChangerDashboard(SubScreen):
    requires = "stealthchanger"
    TITLE = "StealthChanger Dashboard"
    SUBTITLE = "View toolhead status, tools and system information"
    manage = pyqtSignal()

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.status = RowsPanel("System Status", self, label_w=96)
        self.status.setGeometry(sx(8), sy(58), sx(196), sy(250))
        self.heads = Panel("Toolheads", self)
        self.heads.setGeometry(sx(212), sy(58), sx(580), sy(250))
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.tiles = []
        self.active = Panel("Active Tool", self)
        self.active.setGeometry(sx(8), sy(316), sx(250), sy(120))
        self.active.paint_body = self._paint_active
        self.temps = Panel("Temperatures", self)
        self.temps.setGeometry(sx(266), sy(316), sx(370), sy(120))
        self.temps.paint_body = self._paint_temps
        self.tools = Panel("Tools", self)
        self.tools.setGeometry(sx(644), sy(316), sx(148), sy(120))
        self.manage_btn = ActionTile(icons.gear, "Manage", "Tool controls", parent=self.tools)
        self.manage_btn.setGeometry(sx(4), sy(26), sx(140), sy(88))
        self.manage_btn.clicked.connect(self.manage)
        self._data = {}

    def _select_tile(self, i):
        _, tools = _tools(self._data)
        if i < len(tools):
            _ToolSelection.name = tools[i]["name"]
        self.set_data(self._data)

    def set_data(self, data):
        self._data = data
        sc, tools = _tools(data)
        sel = _selected(data)
        while len(self.tiles) < len(tools):
            t = Tile(lambda p, r, s: None, self.heads)
            t.clicked.connect(lambda _=False, i=len(self.tiles): self._select_tile(i))
            self.group.addButton(t)
            self.tiles.append(t)
        n = len(tools)
        cols = n if n <= 5 else 4
        rows = max(1, (n + cols - 1) // cols)
        height = 220 if rows > 1 else 170
        cells = grid(QRectF(6, 24 + (220 - height) / 2, 568, height), max(n, 1), max(cols, 1), 0)
        for i, t in enumerate(self.tiles):
            if i < n:
                t.setGeometry(cells[i].toRect())
                t.set_painter(self._tile_painter(tools[i], _heater(data, tools[i])))
                t.setChecked(tools[i] is sel)
                t.show()
            else:
                t.hide()
        act = _active(data)
        state = (sc.get("status") or "--").capitalize()
        bad = sc.get("status") in ("error",)
        self.status.set_rows([
            ("State", state, theme.RED if bad else theme.GREEN),
            ("Active Tool", act["name"] if act else "None", None),
            ("Tools Detected", str(n), None),
            ("Material", act["material"] if act else "--", None),
            ("Errors", "Yes" if bad else "None", theme.RED if bad else theme.GREEN),
        ])
        self.manage_btn.setEnabled(bool(tools))
        self.active.update()
        self.temps.update()

    @staticmethod
    def _tile_painter(tool, heater):
        def paint(p, r, selected):
            paint_number_band(p, r, tool["name"], selected)
            h = min(r.height() - 70, 64.0)
            icons.toolhead(p, QRectF(r.center().x() - h * 0.38, r.y() + 32, h * 0.76, h), QColor(tool["color"]))
            paint_caption(p, r, tool["material"], fmt_temp(heater[0] if heater else None), r.bottom() - 32)
            paint_status_dot(p, r, True)
        return paint

    def _paint_active(self, p):
        act = _active(self._data)
        b = self.active.body()
        if not act:
            p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, "No tool active")
            return
        icons.toolhead(p, QRectF(b.x() + 14, b.y() + 8, 46, 62), QColor(act["color"]))
        p.setFont(theme.font(smin(22), QFont.Weight.Bold))
        p.setPen(theme.RED)
        p.drawText(QRectF(b.x() + 82, b.y() + 8, 140, 28), Qt.AlignmentFlag.AlignVCenter, act["name"])
        p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
        p.setPen(theme.FG_SOFT)
        heater = _heater(self._data, act)
        p.drawText(QRectF(b.x() + 82, b.y() + 38, 150, 20), Qt.AlignmentFlag.AlignVCenter,
                   f"{act['material']}  {fmt_temp(heater[0] if heater else None)}")
        paint_status_dot(p, QRectF(b.x() + 74, b.y(), 100, b.height() - 4), True)
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(b.x() + 98, b.bottom() - 22, 140, 18), Qt.AlignmentFlag.AlignVCenter, "Mounted")

    def _paint_temps(self, p):
        d = self._data
        act = _active(d)
        cells = [("Nozzle", _heater(d, act) or d.get("nozzle")), ("Chamber", d.get("chamber")), ("Bed", d.get("bed"))]
        for r, (label, val) in zip(grid(self.temps.body(), 3, 3, 6), cells):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 8))
            p.drawRoundedRect(r, 5, 5)
            p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            p.drawText(QRectF(r.x(), r.y() + 6, r.width(), 16), Qt.AlignmentFlag.AlignCenter, label)
            p.setFont(theme.font(smin(22), QFont.Weight.Bold))
            p.setPen(theme.FG)
            p.drawText(QRectF(r.x(), r.y() + 24, r.width(), 28), Qt.AlignmentFlag.AlignCenter,
                       fmt_temp(val[0] if val else None))
            p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            target = val[1] if val else None
            p.drawText(QRectF(r.x(), r.y() + 54, r.width(), 16), Qt.AlignmentFlag.AlignCenter,
                       "Target Off" if not target else f"Target {target:.0f}°C")


class ToolDetail(Panel):
    def __init__(self, ctl, parent=None):
        super().__init__("Tool", parent)
        self.ctl = ctl
        self.tool = None
        self.heater = None
        self.colour_btn = SmallButton("Colour", parent=self, font_px=theme.BUTTON, checkable=False)
        self.material_btn = SmallButton("Material", parent=self, font_px=theme.BUTTON, checkable=False)
        self.colour_btn.setGeometry(sx(10), sy(166), sx(96), sy(30))
        self.material_btn.setGeometry(sx(10), sy(202), sx(96), sy(30))
        self.colour_btn.clicked.connect(
            lambda: self.tool and self.ctl.pick_colour(self.tool["name"], self.tool["color"],
                                                       lambda c: self.ctl.set_tool_meta(self.tool["name"], color=c)))
        self.material_btn.clicked.connect(
            lambda: self.tool and self.ctl.pick_material(self.tool["name"], self.tool["material"],
                                                         lambda m: self.ctl.set_tool_meta(self.tool["name"], material=m)))

    def set_tool(self, tool, heater, data):
        self.tool, self.heater = tool, heater
        self.title = f"Tool {tool['name']} - {tool['material']}" if tool else "Tool"
        ok = bool(tool) and self.ctl.can_edit_metadata(data)
        self.colour_btn.setEnabled(ok)
        self.material_btn.setEnabled(ok)
        self.update()

    def paint_body(self, p):
        t = self.tool
        if not t:
            return
        icons.toolhead(p, QRectF(26, 40, 66, 100), QColor(t["color"]))
        r = QRectF(116, 30, self.width() - 124, self.height() - 38)
        h = self.heater
        paint_rows(p, r, [
            ("Material", t["material"], None),
            ("Colour", colour_name(t["color"]), t["color"]),
            ("Target Temp", fmt_temp(default_temp(t["material"])), None),
            ("Status", t["state"], theme.GREEN if t["state"] == "Active" else None),
            ("Nozzle Temp", "--" if not h else f"{h[0]:.0f} / {h[1]:.0f}°C", None),
        ], label_w=110)


class StealthChangerControls(SubScreen):
    requires = "stealthchanger"
    TITLE = "StealthChanger Controls"
    SUBTITLE = "Change tools and manage toolhead filament"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.select = Panel("Select Tool", self)
        self.select.setGeometry(sx(8), sy(58), sx(150), sy(250))
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons = []
        self.detail = ToolDetail(ctl, self)
        self.detail.setGeometry(sx(166), sy(58), sx(400), sy(250))
        self.heat = HeatPanel(ctl, self)
        self.heat.setGeometry(sx(574), sy(58), sx(218), sy(250))
        self.actions = Panel("Tool Actions", self)
        self.actions.setGeometry(sx(8), sy(316), sx(784), sy(120))
        a = self.actions
        self.select_btn = ActionTile(icons.check, "Select Tool", "Activate this tool", True, a)
        self.park = ActionTile(icons.house, "Park Tool", "Return tool to dock", parent=a)
        self.init = ActionTile(icons.swap, "Initialize", "Initialize toolchanger", parent=a)
        self.refresh = ActionTile(icons.refresh, "Refresh Status", "Re-read tool state", parent=a)
        place_buttons([self.select_btn, self.park, self.init, self.refresh], QRectF(sx(4), sy(26), sx(776), sy(88)), 4, 0)
        self.select_btn.clicked.connect(self._select_tool)
        self.park.clicked.connect(lambda: self.ctl.run("tool_park"))
        self.init.clicked.connect(lambda: self.ctl.run("tc_initialize"))
        self.refresh.clicked.connect(self.ctl.request_refresh)
        self._data = {}
        self._heat_for = None

    def _select_tool(self):
        t = _selected(self._data)
        if t:
            self.ctl.run("tool_select", number=t["number"])

    def _choose(self, name):
        _ToolSelection.name = name
        self.set_data(self._data)

    def set_data(self, data):
        self._data = data
        _, tools = _tools(data)
        sel = _selected(data)
        while len(self.tool_buttons) < len(tools):
            b = SmallButton("", parent=self.select, font_px=smin(17), checkable=True)
            self.tool_group.addButton(b)
            self.tool_buttons.append(b)
        for b, t in zip(self.tool_buttons, tools):
            b._text = t["name"]
            try:
                b.clicked.disconnect()
            except TypeError:
                pass
            b.clicked.connect(lambda _=False, n=t["name"]: self._choose(n))
            b.setChecked(t is sel)
            b.show()
        for b in self.tool_buttons[len(tools):]:
            b.hide()
        place_buttons(self.tool_buttons[:len(tools)], QRectF(sx(8), sy(28), sx(134), sy(214)), 2, sx(6))
        self.detail.set_tool(sel, _heater(data, sel), data)
        if sel and (sel["name"], sel["material"]) != self._heat_for:  # re-derive on tool or material change
            self._heat_for = (sel["name"], sel["material"])
            self.heat.set_heater(sel["extruder"], default_temp(sel["material"]))
        self.heat.set_data(data)
        enable(self.ctl, data, [(self.select_btn, "tool_select"), (self.park, "tool_park"),
                                (self.init, "tc_initialize")])
        act = _active(data)
        self.select_btn.setEnabled(self.select_btn.isEnabled() and bool(sel) and sel is not act)
        self.park.setEnabled(self.park.isEnabled() and act is not None)
        self.refresh.setEnabled(bool(data.get("connected")))
