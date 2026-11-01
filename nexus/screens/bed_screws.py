"""Bed Screws — Klipper [screws_tilt_adjust]: measure with SCREWS_TILT_CALCULATE
and show how far / which way to turn each screw. Printers without that section get a
'not configured' notice instead of controls."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPen

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import Stepper, enable, grid, place_buttons
from nexus.widgets.glow_widget import paint_panel, paint_red_fill
from nexus.widgets import icons
from nexus.widgets.panels import ActionTile, Panel, SubScreen

TOLERANCE_STEP = 0.01
DEFAULT_TOLERANCE = 0.10  # the reference's "Target Gap"
STEPS = ["Home all axes", "Start Assist to measure", "Turn each screw as shown", "Check & Repeat until all OK"]


class ScrewsPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("", parent)
        self.view = None
        self.tolerance = DEFAULT_TOLERANCE

    def set_view(self, view, tolerance):
        if (view, tolerance) != (self.view, self.tolerance):
            self.view, self.tolerance = view, tolerance
            self.update()

    def paint_body(self, p):
        w, h = self.width(), self.height()
        if self.view is None:
            p.setFont(theme.font(smin(18), QFont.Weight.DemiBold))
            p.setPen(theme.FG_SOFT)
            p.drawText(QRectF(sx(20), h / 2 - sy(40), w - sx(40), sy(26)), Qt.AlignmentFlag.AlignCenter, "Bed screws are not configured")
            p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            p.drawText(QRectF(sx(20), h / 2 - sy(8), w - sx(40), sy(44)), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       "This printer has no [screws_tilt_adjust] section, so there is nothing to measure here.")
            return
        screws = self.view["screws"]
        worst = max((s for s in screws if s["dz"] is not None and not s["base"]),
                    key=lambda s: abs(s["dz"]), default=None)
        for r, s in zip(grid(QRectF(sx(4), sy(4), w - sx(8), h - sy(8)), len(screws), 1, smin(6)), screws):
            hot = s is worst and abs(s["dz"]) > self.tolerance
            if hot:
                paint_red_fill(p, r, 7, 0.9)
            else:
                paint_panel(p, r, 7, top=QColor(22, 25, 29), bottom=QColor(13, 15, 18), border=QColor(44, 48, 55))
            i = screws.index(s) + 1
            c = QPointF(r.x() + sx(32), r.center().y())
            p.setPen(QPen(QColor(255, 48, 36), 2.2))
            p.setBrush(QColor(12, 13, 15))
            p.drawEllipse(c, smin(19), smin(19))
            p.setFont(theme.font(smin(20), QFont.Weight.Bold))
            p.setPen(theme.FG)
            p.drawText(QRectF(c.x() - smin(19), c.y() - smin(19), smin(38), smin(38)), Qt.AlignmentFlag.AlignCenter, str(i))
            p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
            p.setPen(theme.FG_SOFT)
            p.drawText(QRectF(r.x() + sx(64), r.y() + sy(6), sx(200), sy(20)), Qt.AlignmentFlag.AlignVCenter, s["name"])
            p.setFont(theme.font(smin(19), QFont.Weight.Bold))
            p.setPen(theme.FG)
            p.drawText(QRectF(r.x() + sx(64), r.y() + sy(24), sx(200), sy(26)), Qt.AlignmentFlag.AlignVCenter,
                       "--" if s["dz"] is None else f"{s['dz']:+.2f} mm")
            if s["dz"] is None:
                status, colour = "Not measured", theme.DIM
            elif s["base"]:
                status, colour = "Reference", theme.FG_SOFT
            elif abs(s["dz"]) <= self.tolerance:
                status, colour = "OK", theme.GREEN
            else:
                status, colour = f"Turn {s['adjust']}", theme.FG
            p.setFont(theme.font(smin(17), QFont.Weight.DemiBold))
            p.setPen(colour)
            p.drawText(r.adjusted(0, 0, -16, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, status)


class InstructionsPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Instructions", parent)

    def paint_body(self, p):
        for i, (r, text) in enumerate(zip(grid(QRectF(sx(10), sy(30), self.width() - sx(20), self.height() - sy(40)), 4, 1, sy(4)), STEPS), 1):
            c = QPointF(r.x() + sx(11), r.center().y())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.FG_SOFT))
            p.drawEllipse(c, smin(10), smin(10))
            p.setFont(theme.font(theme.BODY, QFont.Weight.Bold))
            p.setPen(QColor(12, 13, 15))
            p.drawText(QRectF(c.x() - smin(10), c.y() - smin(10), smin(20), smin(20)), Qt.AlignmentFlag.AlignCenter, str(i))
            p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
            p.setPen(theme.FG_SOFT)
            p.drawText(r.adjusted(30, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, text)


class BedScrewsScreen(SubScreen):
    TITLE = "Bed Screws"
    SUBTITLE = "Help level your bed using the bed screws (manual levelling)"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.tolerance = DEFAULT_TOLERANCE
        self.screws = ScrewsPanel(self)
        self.screws.setGeometry(sx(8), sy(58), sx(500), sy(296))
        self.gap = Panel("Target Gap", self)
        self.gap.setGeometry(sx(516), sy(58), sx(276), sy(86))
        self.stepper = Stepper(self.gap, self._tol, font_px=theme.FIELD)
        self.stepper.place(sx(10), sy(30), sx(256), sy(46), key_w=sx(56))
        self.instructions = InstructionsPanel(self)
        self.instructions.setGeometry(sx(516), sy(152), sx(276), sy(202))
        self.actions = Panel("", self)
        self.actions.setGeometry(sx(8), sy(362), sx(784), sy(74))
        self.start = ActionTile(icons.play, "Start Assist", "Measure all screws", True, self.actions)
        self.repeat = ActionTile(icons.refresh, "Check & Repeat", "Measure again after adjusting", parent=self.actions)
        place_buttons([self.start, self.repeat], QRectF(sx(4), sy(4), sx(776), sy(66)), 2, 0)
        for b in (self.start, self.repeat):
            b.clicked.connect(lambda: self.ctl.run("screws_measure"))
        self._data = {}

    def _tol(self, d):
        self.tolerance = round(max(0.01, min(0.5, self.tolerance + d * TOLERANCE_STEP)), 2)
        self.set_data(self._data)

    def set_data(self, data):
        self._data = data
        view = data.get("screws")
        self.screws.set_view(view, self.tolerance)
        self.stepper.set(f"{self.tolerance:.2f} mm", view is not None, self.tolerance > 0.011, self.tolerance < 0.5)
        homed = set("xyz") <= set((data.get("toolhead") or {}).get("homed", ""))
        enable(self.ctl, data, [(self.start, "screws_measure"), (self.repeat, "screws_measure")])
        ok = view is not None and homed
        self.start.setEnabled(self.start.isEnabled() and ok)
        self.repeat.setEnabled(self.repeat.isEnabled() and ok and view["measured"])
