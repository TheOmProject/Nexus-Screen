"""Hub submenu (Maintenance, Calibrate, Tools, Help references): 3 × 3 tiles plus a wide
tile. Entries without a defined function are shown disabled ("Not available")."""
from PyQt6.QtCore import QRectF

from nexus.screens.addon_common import place_buttons
from nexus.widgets.panels import ActionTile, SubScreen


class HubScreen(SubScreen):
    def __init__(self, title, subtitle, entries, wide, parent=None):
        """entries / wide: (title, subtitle, icon, action|None); action() runs on tap."""
        super().__init__(parent)
        self.TITLE, self.SUBTITLE = title, subtitle
        self.tiles = {}
        for name, sub, icon, action in entries + [wide]:
            t = ActionTile(icon, name, sub if action else "Not available", parent=self)
            if action:
                t.clicked.connect(action)
            t.setEnabled(action is not None)
            self.tiles[name] = t
        place_buttons([self.tiles[e[0]] for e in entries], QRectF(4, 52, 792, 300), 3, 0)
        self.tiles[wide[0]].setGeometry(4, 354, 792, 82)
        self.requires = {}  # tile title -> predicate(data): enabled only when it holds

    def set_data(self, data):
        for name, ok in self.requires.items():
            self.tiles[name].setEnabled(bool(ok(data)))


