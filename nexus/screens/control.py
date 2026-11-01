"""Control main page (sidebar + top bar). Approved. Links the control and calibration
screens; screens not built yet are shown disabled."""
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter
from PyQt6.QtWidgets import QWidget

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import place_buttons
from nexus.widgets import icons
from nexus.widgets.panels import ActionTile

CONTROL = [("move", "Move", "Jog axes and home", icons.control),
           ("temperature", "Temperature", "Heaters and presets", icons.thermometer),
           ("fans", "Fans", "Part and auxiliary fans", icons.fan),
           ("lighting", "Lighting", "LEDs, brightness, colour", icons.bulb),
           ("extruder", "Extruder", "Motor, flow, pressure advance", icons.filament),
           ("macros", "Macros", "Run printer macros", icons.terminal),
           ("webcam", "Webcam", "Live camera view", icons.camera),
           ("timelapse", "Timelapse", "Recording settings", icons.clock)]
CALIBRATION = [("z_offset", "Z Offset", "Nozzle-to-bed distance", icons.z_arrows),
               ("bed_screws", "Bed Screws", "Manual bed levelling", icons.corner),
               ("bed_mesh", "Bed Mesh", "Probe and view the mesh", icons.mesh_grid),
               ("calibrate", "Calibrate", "All calibration tools", icons.crosshair)]


class ControlPage(QWidget):
    """Main page: keeps the sidebar (Control active) and the flat top bar."""
    section = "control"
    open_screen = pyqtSignal(str)

    def __init__(self, available, parent=None):
        super().__init__(parent)
        self.tiles = {}
        for key, title, sub, icon in CONTROL + CALIBRATION:
            t = ActionTile(icon, title, sub, parent=self)
            t.clicked.connect(lambda _=False, k=key: self.open_screen.emit(k))
            t.setEnabled(key in available)
            self.tiles[key] = t
        place_buttons([self.tiles[k] for k, *_ in CONTROL], QRectF(sx(8), sy(82), sx(704), sy(180)), 4, 0)
        place_buttons([self.tiles[k] for k, *_ in CALIBRATION], QRectF(sx(8), sy(300), sx(704), sy(90)), 4, 0)  # same tile size as before

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(theme.font(theme.TITLE, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(sx(14), sy(6), sx(500), sy(34)), Qt.AlignmentFlag.AlignVCenter, "Control")
        p.setFont(theme.font(theme.SUBTITLE, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(sx(15), sy(37), sx(500), sy(18)), Qt.AlignmentFlag.AlignVCenter,
                   "Motion, temperature, fans, lighting and calibration")
        p.setFont(theme.font(theme.CAPS, QFont.Weight.DemiBold, 0.6))
        for y, label in ((sy(64), "CONTROLS"), (sy(282), "CALIBRATION")):
            p.drawText(QRectF(sx(15), y, sx(300), sy(18)), Qt.AlignmentFlag.AlignVCenter, label)
        p.end()
