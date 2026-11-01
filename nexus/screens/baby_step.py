"""Baby Step — Z offset adjustment during a print (opened from Print Status).

Same command as before: every key emits `adjust(delta)`, which MainWindow routes to the data
source's existing z_adjust (SET_GCODE_OFFSET Z_ADJUST=… MOVE=1 while printing, MOVE=0 while
paused). Keys work only while printing or paused with printer commands available."""
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import place_buttons
from nexus.screens.zoffset import CurrentPanel
from nexus.widgets.panels import Panel, SubScreen, Tile

RAISE = (0.005, 0.01, 0.025, 0.05)  # nozzle away from the bed
LOWER = tuple(-d for d in RAISE)    # nozzle towards the bed
ACTIVE = ("printing", "paused")


def _label(delta):
    return f"{delta:+.3f}".rstrip("0")  # +0.005, +0.01, +0.025, +0.05


class BabyStepScreen(SubScreen):
    TITLE = "Baby Step"
    SUBTITLE = "Fine Z offset adjustment during the print"

    adjust = pyqtSignal(float)

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.current = CurrentPanel(self)
        self.current.setGeometry(sx(8), sy(58), sx(250), sy(378))
        self.keys = {}
        for title, deltas, y in (("Raise Nozzle  (+)", RAISE, 58), ("Lower Nozzle  (-)", LOWER, 251)):
            panel = Panel(title, self)
            panel.setGeometry(sx(266), sy(y), sx(526), sy(185))
            row = []
            for d in deltas:
                t = Tile(self._key_painter(d), panel)
                t.setCheckable(False)
                t.clicked.connect(lambda _=False, v=d: self.adjust.emit(v))
                self.keys[d] = t
                row.append(t)
            place_buttons(row, QRectF(sx(6), sy(34), sx(514), sy(140)), 4, smin(6))

    @staticmethod
    def _key_painter(delta):
        def paint(p, r, selected):
            p.setFont(theme.font(smin(26), QFont.Weight.Bold))
            p.setPen(theme.FG)
            p.drawText(QRectF(r.x(), r.center().y() - sy(26), r.width(), sy(32)), Qt.AlignmentFlag.AlignCenter, _label(delta))
            p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            p.drawText(QRectF(r.x(), r.center().y() + sy(8), r.width(), sy(20)), Qt.AlignmentFlag.AlignCenter, "mm")
        return paint

    def set_data(self, data):
        connected = bool(data.get("connected"))
        if connected:
            self.current.set_value(data.get("z_offset"))
        on = connected and data.get("state") in ACTIVE and self.ctl.commands_ready()
        for t in self.keys.values():
            t.setEnabled(on)
