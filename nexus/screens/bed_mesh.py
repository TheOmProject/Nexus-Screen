"""Bed Mesh (approved). 2D heat map of the loaded mesh
(or a selected saved profile), mesh statistics, profile list, Calibrate / Load / Clear."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QFont, QLinearGradient

from nexus import theme
from nexus.screens.addon_common import enable, place_buttons
from nexus.widgets import icons
from nexus.widgets.bed_mesh_chart import HIGH, LOW, MID, BedMeshChart, mesh_stats
from nexus.widgets.buttons import SmallButton
from nexus.widgets.panels import ActionTile, Panel, RowsPanel, SubScreen

MAX_PROFILES = 4


class ChartPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Mesh", parent)
        self.chart = BedMeshChart(self)
        self.scale = 0.0

    def resizeEvent(self, e):
        self.chart.setGeometry(10, 30, self.width() - 20, self.height() - 76)
        super().resizeEvent(e)

    def set_matrix(self, title, matrix):
        self.title = title
        self.chart.set_matrix(matrix)
        self.scale = self.chart.scale()
        self.update()

    def paint_body(self, p):
        w, h = self.width(), self.height()
        if not self.scale:
            return
        bar = QRectF(60, h - 34, w - 120, 10)
        g = QLinearGradient(bar.topLeft(), bar.topRight())
        g.setColorAt(0, LOW)
        g.setColorAt(0.5, MID)
        g.setColorAt(1, HIGH)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(bar, 5, 5)
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.DemiBold))
        p.setPen(theme.DIM)
        p.drawText(QRectF(4, h - 40, 52, 22), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{-self.scale:+.2f}")
        p.drawText(QRectF(w - 56, h - 40, 52, 22), Qt.AlignmentFlag.AlignVCenter, f"{self.scale:+.2f}")
        p.drawText(QRectF(0, h - 22, w, 16), Qt.AlignmentFlag.AlignCenter, "mm · front of bed at the bottom")


class BedMeshScreen(SubScreen):
    TITLE = "Bed Mesh"
    SUBTITLE = "Probe, view and load bed mesh profiles"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.view_profile = None  # profile previewed in the chart; None = the loaded mesh
        self.chart = ChartPanel(self)
        self.chart.setGeometry(8, 58, 440, 378)
        self.info = RowsPanel("Mesh Info", self, label_w=96)
        self.info.setGeometry(456, 58, 336, 150)
        self.profiles = Panel("Profiles", self)
        self.profiles.setGeometry(456, 216, 336, 112)
        self.profile_btns = [SmallButton("", parent=self.profiles, font_px=theme.BUTTON, checkable=True) for _ in range(MAX_PROFILES)]
        for b in self.profile_btns:
            b.clicked.connect(lambda _=False, btn=b: self._preview(btn._text))
        place_buttons(self.profile_btns, QRectF(8, 28, 320, 76), 2, 6)
        self.actions = Panel("", self)
        self.actions.setGeometry(456, 336, 336, 100)
        self.calibrate = ActionTile(icons.mesh_grid, "Calibrate", parent=self.actions, stacked=True)
        self.load = ActionTile(icons.load, "Load", parent=self.actions, stacked=True)
        self.clear = ActionTile(icons.eject, "Clear", parent=self.actions, stacked=True)
        place_buttons([self.calibrate, self.load, self.clear], QRectF(4, 4, 328, 92), 3, 0)
        self.calibrate.clicked.connect(lambda: self.ctl.confirm(
            "Calibrate Bed Mesh?", "Probes the bed (BED_MESH_CALIBRATE). This takes several minutes and the "
            "toolhead will move.", "Start", lambda: self.ctl.run("mesh_calibrate")))
        self.load.clicked.connect(lambda: self.view_profile and self.ctl.run("mesh_load", profile=self.view_profile))
        self.clear.clicked.connect(lambda: self.ctl.run("mesh_clear"))
        self._data = {}

    def showEvent(self, e):
        self.ctl.request_mesh()  # matrices are fetched on demand, not on every poll
        super().showEvent(e)

    def _preview(self, name):
        mesh = self._data.get("bed_mesh") or {}
        self.view_profile = None if name == mesh.get("active") else name
        self.set_data(self._data)

    def set_data(self, data):
        self._data = data
        mesh = data.get("bed_mesh")
        if not mesh:
            self.chart.set_matrix("Mesh", None)
            self.info.set_rows([("Status", "Bed mesh not configured", None)])
            for b in (self.calibrate, self.load, self.clear, *self.profile_btns):
                b.setEnabled(False)
            return
        names = sorted(mesh["profiles"])[:MAX_PROFILES]
        if self.view_profile not in names or self.view_profile == mesh["active"]:
            self.view_profile = None  # preview ends once that profile is the loaded one
        shown = self.view_profile or mesh["active"] or None
        matrix = mesh["profiles"].get(self.view_profile) if self.view_profile else mesh["matrix"]
        title = (f"Profile '{self.view_profile}' (saved, not loaded)" if self.view_profile
                 else f"Loaded mesh: {mesh['active']}" if mesh["matrix"] else "No mesh loaded")
        self.chart.set_matrix(title, matrix)
        if matrix:
            lo, hi, rng = mesh_stats(matrix)
            rows = [("Profile", shown or "--", None), ("Points", f"{len(matrix[0])} × {len(matrix)}", None),
                    ("Min / Max", f"{lo:+.3f} / {hi:+.3f}", None), ("Range", f"{rng:.3f} mm", None)]
        else:
            rows = [("Profile", "--", None), ("Points", "--", None), ("Min / Max", "--", None), ("Range", "--", None)]
        self.info.set_rows(rows)
        for b, name in zip(self.profile_btns, names + [""] * MAX_PROFILES):
            b._text = name
            b.setVisible(bool(name))
            b.setChecked(name == shown)
            b.update()
        enable(self.ctl, data, [(self.calibrate, "mesh_calibrate"), (self.load, "mesh_load"),
                                (self.clear, "mesh_clear")])
        homed = set("xyz") <= set((data.get("toolhead") or {}).get("homed", ""))
        self.calibrate.setEnabled(self.calibrate.isEnabled() and homed)
        self.load.setEnabled(self.load.isEnabled() and bool(self.view_profile))
        self.clear.setEnabled(self.clear.isEnabled() and bool(mesh["matrix"]))
