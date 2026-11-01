"""Macros — the printer's visible gcode_macro sections; search via the on-screen
keyboard; details show description and G-code; Run asks for confirmation."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QFont, QFontMetricsF

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.overlays import MONO
from nexus.widgets.panels import ActionTile, ListPanel, Panel, SubScreen, paint_rows


def macro_row(p, r, item, selected):
    name, info = item
    icons.play(p, QRectF(r.x() + 12, r.center().y() - 7, 12, 14), theme.RED if selected else theme.FG_SOFT)
    tw = r.width() - 40
    nf = theme.font(theme.BUTTON, QFont.Weight.DemiBold)
    p.setFont(nf)
    p.setPen(theme.FG)
    p.drawText(QRectF(r.x() + 34, r.center().y() - 18, tw, 20), Qt.AlignmentFlag.AlignVCenter,
               QFontMetricsF(nf).elidedText(name, Qt.TextElideMode.ElideRight, tw))
    df = theme.font(theme.SMALL, QFont.Weight.Medium)
    p.setFont(df)
    p.setPen(theme.DIM)
    p.drawText(QRectF(r.x() + 34, r.center().y() + 1, tw, 16), Qt.AlignmentFlag.AlignVCenter,
               QFontMetricsF(df).elidedText(info["description"] or "G-code macro", Qt.TextElideMode.ElideRight, tw))


class DetailsPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Macro Details", parent)
        self.item = None

    def paint_body(self, p):
        if not self.item:
            return
        name, info = self.item
        paint_rows(p, QRectF(8, 30, self.width() - 16, 56), [("Name", name, None),
                                                            ("Description", info["description"] or "-", None)], 90)
        p.setFont(theme.font(theme.BODY, QFont.Weight.DemiBold))
        p.setPen(theme.DIM)
        p.drawText(QRectF(10, 92, 200, 18), Qt.AlignmentFlag.AlignVCenter, "Commands")
        f = QFont(MONO)
        f.setPixelSize(smin(11))
        p.setFont(f)
        p.setPen(theme.FG_SOFT)
        lines = info["gcode"].splitlines()[:12]
        p.drawText(QRectF(12, 114, self.width() - 24, self.height() - 196),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "\n".join(lines) or "(empty)")


class MacrosScreen(SubScreen):
    TITLE = "Macros"
    SUBTITLE = "Run custom macros from printer configuration"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.filter = ""
        self.list = ListPanel("Macro List", macro_row, rows=7, parent=self, top=34, empty_text="No macros found")
        self.list.setGeometry(sx(8), sy(58), sx(486), sy(378))
        self.list.key = lambda item: item[0]
        self.list.chosen.connect(lambda item: self._select(item))
        self.search = SmallButton("Search macros…", parent=self.list, font_px=theme.BUTTON, checkable=False)
        self.search.setGeometry(sx(240), sy(4), sx(238), sy(26))
        self.search.clicked.connect(lambda: self.ctl.keyboard("Search macros", self.filter, self._set_filter))
        self.details = DetailsPanel(self)
        self.details.setGeometry(sx(502), sy(58), sx(290), sy(378))
        self.run = ActionTile(icons.play, "Run Macro", primary=True, parent=self.details)
        self.run.setGeometry(sx(4), sy(304), sx(282), sy(70))
        self.run.clicked.connect(self._run)
        self._data = {}

    def _set_filter(self, text):
        self.filter = text.strip().upper()
        self.search._text = f"Search: {self.filter}" if self.filter else "Search macros…"
        self.search.update()
        self.list.page = 0
        self.set_data(self._data)

    def _select(self, item):
        self.details.item = item
        self.details.update()
        self.set_data(self._data)

    def _run(self):
        if self.details.item:
            name = self.details.item[0]
            self.ctl.confirm(f"Run {name}?", "The macro runs on the printer exactly as configured.",
                             "Run Macro", lambda: self.ctl.run("macro", name=name))

    def set_data(self, data):
        self._data = data
        items = [(n, i) for n, i in (data.get("macros") or {}).items() if self.filter in n]
        self.list.empty_text = f"No macros match \"{self.filter}\"" if self.filter else "No macros found"
        if self.details.item is None and items:
            self.details.item = items[0]
            self.list.selected = items[0][0]
        self.list.set_items(items)
        self.details.update()
        self.run.setEnabled(self.details.item is not None and self.ctl.can("macro", data))
