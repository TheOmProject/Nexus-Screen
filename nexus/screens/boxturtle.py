"""BoxTurtle (AFC) Dashboard and Controls. Lane count comes from AFC; nothing is fixed."""
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QButtonGroup

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.moonraker.commands import LANE_MOVE_MM
from nexus.screens.addon_common import (HeatPanel, colour_name, default_temp, enable, fmt_temp, grid, paint_caption,
                                        paint_number_band, paint_status_dot, place_buttons)
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.panels import ActionTile, Panel, RowsPanel, SubScreen, Tile, paint_rows

MAX_TILES = 12  # 3 rows of 4; more lanes page with ‹ ›


def _lane_label(lane):
    return f"{lane['material'] or '--'}  {fmt_temp(default_temp(lane['material'], lane.get('temp')))}"


class _LaneSelection:
    """Selected lane id shared by both BoxTurtle screens."""
    lane_id = None


def _lanes(data):
    bt = data.get("boxturtle") or {}
    return bt, bt.get("lanes", [])


def _selected(data):
    bt, lanes = _lanes(data)
    ids = [l["id"] for l in lanes]
    if _LaneSelection.lane_id not in ids:
        _LaneSelection.lane_id = bt.get("current") if bt.get("current") in ids else (ids[0] if ids else None)
    return next((l for l in lanes if l["id"] == _LaneSelection.lane_id), None)


class BoxTurtleDashboard(SubScreen):
    requires = "boxturtle"
    TITLE = "BoxTurtle Dashboard"
    SUBTITLE = "View filament status, lanes and active tool"
    manage = pyqtSignal()

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.status = RowsPanel("System Status", self, label_w=92)
        self.status.setGeometry(sx(8), sy(58), sx(196), sy(250))
        self.lanes_panel = Panel("Filament Lanes", self)
        self.lanes_panel.setGeometry(sx(212), sy(58), sx(580), sy(250))
        self.prev = SmallButton(icon=icons.back_arrow, parent=self.lanes_panel, checkable=False)
        self.next = SmallButton(icon=icons.chevron, parent=self.lanes_panel, checkable=False)
        self.prev.setGeometry(sx(496), sy(3), sx(36), sy(20))
        self.next.setGeometry(sx(536), sy(3), sx(36), sy(20))
        self.prev.clicked.connect(lambda: self._page(-1))
        self.next.clicked.connect(lambda: self._page(1))
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.tiles = []
        self._page_no = 0
        self.active = Panel("Active Tool", self)
        self.active.setGeometry(sx(8), sy(316), sx(300), sy(120))
        self.active.paint_body = self._paint_active
        self.runout = Panel("Runout Lane", self)
        self.runout.setGeometry(sx(316), sy(316), sx(170), sy(120))
        self.runout.paint_body = self._paint_runout
        self.tools = Panel("Tools", self)
        self.tools.setGeometry(sx(494), sy(316), sx(298), sy(120))
        self.load = ActionTile(icons.load, "Load", parent=self.tools)
        self.unload = ActionTile(icons.unload, "Unload", parent=self.tools)
        self.manage_btn = ActionTile(icons.gear, "Manage", parent=self.tools)
        place_buttons([self.load, self.unload, self.manage_btn], QRectF(sx(4), sy(26), sx(290), sy(88)), 3, 0)
        self.load.clicked.connect(lambda: self._lane_op("lane_load"))
        self.unload.clicked.connect(lambda: self._lane_op("lane_unload"))
        self.manage_btn.clicked.connect(self.manage)
        self._data = {}

    def _lane_op(self, key):
        lane = _selected(self._data)
        if lane:
            self.ctl.run(key, lane=lane["id"])

    def _page(self, d):
        self._page_no += d
        self.set_data(self._data)

    def _ensure_tiles(self, n):
        while len(self.tiles) < n:
            t = Tile(lambda p, r, s: None, self.lanes_panel)
            t.clicked.connect(lambda _=False, i=len(self.tiles): self._select_tile(i))
            self.group.addButton(t)
            self.tiles.append(t)

    def _select_tile(self, i):
        _, lanes = _lanes(self._data)
        idx = self._page_no * MAX_TILES + i
        if idx < len(lanes):
            _LaneSelection.lane_id = lanes[idx]["id"]
        self.set_data(self._data)

    def set_data(self, data):
        self._data = data
        bt, lanes = _lanes(data)
        sel = _selected(data)
        pages = max(1, (len(lanes) + MAX_TILES - 1) // MAX_TILES)
        self._page_no = max(0, min(self._page_no, pages - 1))
        self.prev.setVisible(pages > 1)
        self.next.setVisible(pages > 1)
        self.prev.setEnabled(self._page_no > 0)
        self.next.setEnabled(self._page_no < pages - 1)
        shown = lanes[self._page_no * MAX_TILES:(self._page_no + 1) * MAX_TILES]
        self._ensure_tiles(len(shown))
        cols = 4
        cells = grid(QRectF(sx(6), sy(24), sx(568), sy(220)), max(len(shown), 1), cols, 0)
        for i, t in enumerate(self.tiles):
            if i < len(shown):
                lane = shown[i]
                t.setGeometry(cells[i].toRect())
                t.set_painter(self._tile_painter(lane, lane["id"] == bt.get("current")))
                t.setChecked(lane is sel)
                t.show()
            else:
                t.hide()
        loaded = sum(1 for l in lanes if l["loaded"])
        current = next((l for l in lanes if l["id"] == bt.get("current")), None)
        self.status.set_rows([
            ("State", bt.get("state", "--"), theme.RED if bt.get("error") else theme.GREEN),
            ("Active Lane", current["name"] if current else "None", None),
            ("Filament", (current or {}).get("material") or "--", None),
            ("Lanes Loaded", f"{loaded} / {len(lanes)}", None),
            ("Buffer", (current or {}).get("buffer") or "--", None),
            ("Errors", "Yes" if bt.get("error") else "None", theme.RED if bt.get("error") else theme.GREEN),
        ])
        enable(self.ctl, data, [(self.load, "lane_load"), (self.unload, "lane_unload")])
        self.load.setEnabled(self.load.isEnabled() and bool(sel) and sel["loaded"] and not sel["tool_loaded"])
        self.unload.setEnabled(self.unload.isEnabled() and bool(sel) and sel["tool_loaded"])
        self.active.update()
        self.runout.update()

    @staticmethod
    def _tile_painter(lane, in_tool):
        def paint(p, r, selected):
            paint_number_band(p, r, lane["name"], selected)
            s = min(r.width() * 0.5, r.height() - 66)
            icons.spool_side(p, QRectF(r.center().x() - s / 2, r.y() + 30, s, s * 0.82),
                             QColor(lane["color"]) if lane["loaded"] else QColor(theme.MUTED))
            paint_caption(p, r, lane["material"] or "Empty",
                          fmt_temp(default_temp(lane["material"], lane.get("temp"))), r.bottom() - 32)
            paint_status_dot(p, r, lane["loaded"])
            if in_tool:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(theme.GREEN)
                cx, cy = r.right() - 13, r.bottom() - 12.5  # diamond = lane is in the toolhead
                p.drawPolygon([QPointF(cx, cy - 5), QPointF(cx + 5, cy), QPointF(cx, cy + 5), QPointF(cx - 5, cy)])
        return paint

    def _paint_active(self, p):
        bt, lanes = _lanes(self._data)
        lane = next((l for l in lanes if l["id"] == bt.get("current")), None)
        b = self.active.body()
        if not lane:
            p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, "No lane loaded")
            return
        icons.spool_side(p, QRectF(b.x() + sx(6), b.y() + sy(14), sx(72), sy(58)), QColor(lane["color"]))
        p.setFont(theme.font(smin(20), QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(b.x() + sx(96), b.y() + sy(10), sx(180), sy(26)), Qt.AlignmentFlag.AlignVCenter, f"Lane {lane['name']}")
        p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(b.x() + sx(96), b.y() + sy(38), sx(180), sy(20)), Qt.AlignmentFlag.AlignVCenter, _lane_label(lane))
        paint_status_dot(p, QRectF(b.x() + sx(88), b.y(), sx(100), b.height() - sy(4)), True)
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(b.x() + sx(112), b.bottom() - sy(22), sx(160), sy(18)), Qt.AlignmentFlag.AlignVCenter, "Loaded to toolhead")

    def _paint_runout(self, p):
        bt, lanes = _lanes(self._data)
        cur = next((l for l in lanes if l["id"] == bt.get("current")), None)
        nxt = next((l for l in lanes if cur and l["id"] == cur.get("runout")), None)
        b = self.runout.body()
        if not nxt:
            p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, "None set")
            return
        icons.spool_side(p, QRectF(b.x() + sx(4), b.y() + sy(18), sx(56), sy(46)), QColor(nxt["color"]))
        p.setFont(theme.font(smin(18), QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(b.x() + sx(68), b.y() + sy(14), sx(90), sy(24)), Qt.AlignmentFlag.AlignVCenter, f"Lane {nxt['name']}")
        p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(b.x() + sx(68), b.y() + sy(40), sx(90), sy(20)), Qt.AlignmentFlag.AlignVCenter, nxt["material"] or "--")


class LaneDetail(Panel):
    def __init__(self, ctl, parent=None):
        super().__init__("Lane", parent)
        self.ctl = ctl
        self.lane = None
        self.colour_btn = SmallButton("Colour", parent=self, font_px=theme.BUTTON, checkable=False)
        self.material_btn = SmallButton("Material", parent=self, font_px=theme.BUTTON, checkable=False)
        self.colour_btn.setGeometry(sx(10), sy(114), sx(96), sy(30))
        self.material_btn.setGeometry(sx(10), sy(150), sx(96), sy(30))
        self.colour_btn.clicked.connect(
            lambda: self.lane and self.ctl.pick_colour(f"Lane {self.lane['name']}", self.lane["color"],
                                                       lambda c: self.ctl.run("lane_color", lane=self.lane["id"], color=c)))
        self.material_btn.clicked.connect(
            lambda: self.lane and self.ctl.pick_material(f"Lane {self.lane['name']}", self.lane["material"],
                                                         lambda m: self.ctl.run("lane_material", lane=self.lane["id"], material=m)))

    def set_lane(self, lane, data):
        self.lane = lane
        self.title = f"Lane {lane['name']} - {lane['material'] or 'Empty'}" if lane else "Lane"
        enable(self.ctl, data, [(self.colour_btn, "lane_color"), (self.material_btn, "lane_material")])
        self.update()

    def paint_body(self, p):
        lane = self.lane
        if not lane:
            return
        icons.spool_side(p, QRectF(sx(18), sy(34), sx(82), sy(70)), QColor(lane["color"]) if lane["loaded"] else QColor(theme.MUTED))
        r = QRectF(sx(116), sy(30), self.width() - sx(124), self.height() - sy(38))
        paint_rows(p, r, [
            ("Material", lane["material"] or "--", None),
            ("Colour", colour_name(lane["color"]), lane["color"]),
            ("Target Temp", fmt_temp(default_temp(lane["material"], lane.get("temp"))), None),
            ("Status", "In Toolhead" if lane["tool_loaded"] else ("Loaded" if lane["loaded"] else "Empty"),
             theme.GREEN if lane["loaded"] else theme.DIM),
            ("Filament Sensor", "Present" if lane["sensor"] else "Empty", theme.GREEN if lane["sensor"] else theme.DIM),
        ], label_w=118)


class BoxTurtleControls(SubScreen):
    requires = "boxturtle"
    TITLE = "BoxTurtle Controls"
    SUBTITLE = "Load, unload and manage filament lanes"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.select = Panel("Select Lane", self)
        self.select.setGeometry(sx(8), sy(58), sx(150), sy(190))
        self.lane_group = QButtonGroup(self)
        self.lane_group.setExclusive(True)
        self.lane_buttons = []
        self.detail = LaneDetail(ctl, self)
        self.detail.setGeometry(sx(166), sy(58), sx(400), sy(190))
        self.heat = HeatPanel(ctl, self)
        self.heat.setGeometry(sx(574), sy(58), sx(218), sy(190))
        self.actions = Panel("Filament Actions", self)
        self.actions.setGeometry(sx(8), sy(256), sx(784), sy(88))
        a = self.actions
        self.load = ActionTile(icons.load, "Load", "Load to toolhead", True, a)
        self.unload = ActionTile(icons.unload, "Unload", "Unload from toolhead", parent=a)
        self.change = ActionTile(icons.swap, "Change To", "Swap to this lane", parent=a)
        self.advance = ActionTile(icons.advance, "Advance", f"Move +{LANE_MOVE_MM} mm", parent=a)
        self.retract = ActionTile(icons.retract, "Retract", f"Move −{LANE_MOVE_MM} mm", parent=a)
        place_buttons([self.load, self.unload, self.change, self.advance, self.retract], QRectF(sx(4), sy(22), sx(776), sy(62)), 5, 0)
        self.utils = Panel("Utilities", self)
        self.utils.setGeometry(sx(8), sy(352), sx(784), sy(84))
        u = self.utils
        self.park = ActionTile(icons.house, "Park", "Park the toolhead", parent=u)
        self.refresh = ActionTile(icons.refresh, "Refresh Status", "Re-read AFC state", parent=u)
        self.reset = ActionTile(icons.warning, "Clear Error", "Reset AFC failure", parent=u)
        self.eject = ActionTile(icons.eject, "Eject Lane", "Unload lane to the box", parent=u)
        place_buttons([self.park, self.refresh, self.reset, self.eject], QRectF(sx(4), sy(22), sx(776), sy(58)), 4, 0)
        for btn, key in ((self.load, "lane_load"), (self.unload, "lane_unload"), (self.change, "lane_select"),
                         (self.eject, "lane_eject")):
            btn.clicked.connect(lambda _=False, k=key: self._lane_op(k))
        self.advance.clicked.connect(lambda: self._lane_op("lane_move", distance=LANE_MOVE_MM))
        self.retract.clicked.connect(lambda: self._lane_op("lane_move", distance=-LANE_MOVE_MM))
        self.park.clicked.connect(lambda: self.ctl.run("afc_park"))
        self.reset.clicked.connect(lambda: self.ctl.run("afc_reset"))
        self.refresh.clicked.connect(self.ctl.request_refresh)
        self._data = {}
        self._heat_for = None

    def _lane_op(self, key, **params):
        lane = _selected(self._data)
        if lane:
            self.ctl.run(key, lane=lane["id"], **params)

    def _choose(self, lane_id):
        _LaneSelection.lane_id = lane_id
        self.set_data(self._data)

    def set_data(self, data):
        self._data = data
        _, lanes = _lanes(data)
        sel = _selected(data)
        while len(self.lane_buttons) < len(lanes):
            b = SmallButton(str(len(self.lane_buttons) + 1), parent=self.select, font_px=smin(17))
            self.lane_group.addButton(b)
            self.lane_buttons.append(b)
        for b, lane in zip(self.lane_buttons, lanes):
            try:
                b.clicked.disconnect()
            except TypeError:
                pass
            b.clicked.connect(lambda _=False, i=lane["id"]: self._choose(i))
            b.setChecked(lane is sel)
            b.show()
        for b in self.lane_buttons[len(lanes):]:
            b.hide()
        place_buttons(self.lane_buttons[:len(lanes)], QRectF(sx(8), sy(28), sx(134), sy(154)), 2, smin(6))
        self.detail.set_lane(sel, data)
        if sel and (sel["id"], sel["material"]) != self._heat_for:  # re-derive on lane or material change
            self._heat_for = (sel["id"], sel["material"])
            self.heat.set_heater("extruder", default_temp(sel["material"], sel.get("temp")))
        self.heat.set_data(data)
        enable(self.ctl, data, [(self.load, "lane_load"), (self.unload, "lane_unload"),
                                (self.change, "lane_select"), (self.advance, "lane_move"),
                                (self.retract, "lane_move"), (self.park, "afc_park"),
                                (self.reset, "afc_reset"), (self.eject, "lane_eject")])
        self.refresh.setEnabled(bool(data.get("connected")))
        if sel:
            self.load.setEnabled(self.load.isEnabled() and sel["loaded"] and not sel["tool_loaded"])
            self.unload.setEnabled(self.unload.isEnabled() and sel["tool_loaded"])
        else:
            for b in (self.load, self.unload, self.change, self.advance, self.retract, self.eject):
                b.setEnabled(False)
