"""Filament — load / unload (heating first when needed), manual extrude / retract,
material from the filament profiles. Plus the Filament main page (PROVISIONAL)."""
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter
from PyQt6.QtWidgets import QWidget

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.moonraker import profiles
from nexus.screens.addon_common import Stepper, place_buttons
from nexus.screens.extrusion import ExtruderStatus, NozzlePanel
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.panels import ActionTile, Panel, SubScreen

MANUAL_MM = 10        # Filament screen's quick extrude / retract
LENGTH_STEP = 10
SPEED_STEP = 1
DEFAULTS = {"load": 100, "unload": 100, "speed": 5}   # from the reference


def active_profile(data):
    store = data.get("filament_profiles") or profiles.defaults()
    return profiles.find(store, store["active"]) or store["profiles"][0]


class OptionsPanel(Panel):
    ROWS = (("Material", 30), ("Load Length", 80), ("Unload Length", 130), ("Speed", 180))

    def __init__(self, screen, parent=None):
        super().__init__("Filament Options", parent)
        self.material = SmallButton("", parent=self, font_px=theme.BUTTON, checkable=False)
        self.material.clicked.connect(screen.pick_material)
        self.load = Stepper(self, lambda d: screen.adjust("load", d * LENGTH_STEP))
        self.unload = Stepper(self, lambda d: screen.adjust("unload", d * LENGTH_STEP))
        self.speed = Stepper(self, lambda d: screen.adjust("speed", d * SPEED_STEP))

    def resizeEvent(self, e):
        w = self.width()
        self.material.setGeometry(sx(124), sy(32), w - sx(132), sy(40))
        for st, (_, y) in zip((self.load, self.unload, self.speed), self.ROWS[1:]):
            st.place(sx(124), sy(y + 2), w - sx(132), sy(40), key_w=sx(46))
        super().resizeEvent(e)

    def paint_body(self, p):
        p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        for label, y in self.ROWS:
            p.drawText(QRectF(sx(10), sy(y + 2), sx(112), sy(40)), Qt.AlignmentFlag.AlignVCenter, label)


class FilamentScreen(SubScreen):
    TITLE = "Filament"
    SUBTITLE = "Manage filament load, unload and extrusion"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.values = dict(DEFAULTS)
        self.material = None  # chosen profile name; None = the active profile
        self.temp = NozzlePanel(ctl, self)
        self.temp.setGeometry(sx(8), sy(58), sx(190), sy(250))
        self.options = OptionsPanel(self, self)
        self.options.setGeometry(sx(206), sy(58), sx(380), sy(250))
        self.status = ExtruderStatus(self)
        self.status.setGeometry(sx(594), sy(58), sx(198), sy(250))
        self.actions = Panel("Actions", self)
        self.actions.setGeometry(sx(8), sy(316), sx(784), sy(120))
        a = self.actions
        self.load_btn = ActionTile(icons.load, "Load", "Heat and load", True, a)
        self.unload_btn = ActionTile(icons.unload, "Unload", "Heat and unload", parent=a)
        self.extrude_btn = ActionTile(icons.advance, "Extrude", f"Manual {MANUAL_MM} mm", parent=a)
        self.retract_btn = ActionTile(icons.retract, "Retract", f"Manual {MANUAL_MM} mm", parent=a)
        self.stop_btn = ActionTile(icons.stop_square, "Stop", "Stop heating", parent=a)
        place_buttons([self.load_btn, self.unload_btn, self.extrude_btn, self.retract_btn, self.stop_btn],
                      QRectF(sx(4), sy(26), sx(776), sy(88)), 5, 0)
        job = ctl.filament_job
        self.load_btn.clicked.connect(lambda: job.start("Loading", self.values["load"], self.values["speed"],
                                                        self._profile()["nozzle"]))
        self.unload_btn.clicked.connect(lambda: job.start("Unloading", -self.values["unload"], self.values["speed"],
                                                          self._profile()["nozzle"]))
        self.extrude_btn.clicked.connect(lambda: job.start("Extruding", MANUAL_MM, self.values["speed"]))
        self.retract_btn.clicked.connect(lambda: job.start("Retracting", -MANUAL_MM, self.values["speed"]))
        self.stop_btn.clicked.connect(job.stop)
        job.changed.connect(lambda: self.set_data(self.ctl._data))
        self._data = {}

    def _profile(self):
        store = self._data.get("filament_profiles") or profiles.defaults()
        return profiles.find(store, self.material or store["active"]) or active_profile(self._data)

    def pick_material(self):
        store = self._data.get("filament_profiles") or profiles.defaults()

        def chosen(name):
            self.material = name
            self.set_data(self._data)
        self.ctl.pick_profile(self._profile()["name"], [p["name"] for p in store["profiles"]], chosen)

    def adjust(self, key, delta):
        max_speed = (self._data.get("extruder_cfg") or {}).get("max_speed", 10.0)
        lo, hi = (1, min(15, int(max_speed))) if key == "speed" else (10, 500)
        self.values[key] = max(lo, min(hi, self.values[key] + delta))
        self.set_data(self._data)

    def set_data(self, data):
        self._data = data
        job = self.ctl.filament_job
        self.temp.set_data(data)
        self.status.set_data(data, job)
        prof = self._profile()
        self.options.material._text = f"{prof['name']}  ({prof['nozzle']}°C)  ▾"
        self.options.material.update()
        self.options.material.setEnabled(not job.busy())
        max_speed = min(15, int((data.get("extruder_cfg") or {}).get("max_speed", 10.0)))
        for st, key, unit, lo, hi in ((self.options.load, "load", "mm", 10, 500),
                                      (self.options.unload, "unload", "mm", 10, 500),
                                      (self.options.speed, "speed", "mm/s", 1, max_speed)):
            v = self.values[key]
            st.set(f"{v} {unit}", not job.busy(), v > lo, v < hi)
        can = self.ctl.can("extrude", data) and not job.busy()
        hot = (data.get("extruder") or {}).get("can_extrude", False)
        self.load_btn.setEnabled(can)
        self.unload_btn.setEnabled(can)
        self.extrude_btn.setEnabled(can and hot)
        self.retract_btn.setEnabled(can and hot)
        self.stop_btn.setEnabled(job.can_stop())


class FilamentPage(QWidget):
    """Filament main page (sidebar + top bar). PROVISIONAL — no approved reference;
    same pattern as the approved Control page."""
    section = "filament"
    open_screen = pyqtSignal(str)

    ENTRIES = [("filament", "Filament", "Load, unload and extrude", icons.filament),
               ("profiles", "Filament Profiles", "Material settings", icons.palette),
               ("boxturtle", "BoxTurtle", "Lanes and filament", icons.spool),
               ("stealthchanger", "StealthChanger", "Toolheads and filament", icons.wrench)]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tiles = {}
        for key, title, sub, icon in self.ENTRIES:
            t = ActionTile(icon, title, sub, parent=self)
            t.clicked.connect(lambda _=False, k=key: self.open_screen.emit(k))
            self.tiles[key] = t
        place_buttons(list(self.tiles.values()), QRectF(sx(8), sy(82), sx(704), sy(180)), 2, 0)

    def set_data(self, data):
        for key in ("boxturtle", "stealthchanger"):  # add-ons only when detected
            self.tiles[key].setVisible(bool(data.get(key)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(theme.font(theme.TITLE, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(sx(14), sy(6), sx(500), sy(34)), Qt.AlignmentFlag.AlignVCenter, "Filament")
        p.setFont(theme.font(theme.SUBTITLE, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(sx(15), sy(37), sx(500), sy(18)), Qt.AlignmentFlag.AlignVCenter, "Load filament and manage materials")
        p.setFont(theme.font(theme.CAPS, QFont.Weight.DemiBold, 0.6))
        p.drawText(QRectF(sx(15), sy(64), sx(300), sy(18)), Qt.AlignmentFlag.AlignVCenter, "FILAMENT")
        p.end()
