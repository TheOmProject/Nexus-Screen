"""Filament Profiles — list, settings, edit (numeric fields via the keypad), add,
duplicate, delete, set active. Saved in Moonraker's database, not printer config."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.moonraker import profiles
from nexus.screens.addon_common import grid, place_buttons
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.panels import ActionTile, Panel, SubScreen, Tile, paint_rows

ROWS_PER_PAGE = 8


def fmt(field, value):
    key, _, unit, *_ = field
    return f"{value:g}{'°C' if unit == '°C' else ' ' + unit}"


class SettingsPanel(Panel):
    def __init__(self, screen, parent=None):
        super().__init__("Profile Settings", parent)
        self.screen = screen
        self.profile = None
        self.edit_btn = SmallButton("Edit", parent=self, font_px=theme.BUTTON, checkable=True)
        self.edit_btn.toggled.connect(lambda _: screen.refresh())
        self.value_btns = []
        for field in profiles.FIELDS:
            b = SmallButton("", parent=self, font_px=theme.BUTTON, checkable=False)
            b.clicked.connect(lambda _=False, f=field: screen.edit_field(f))
            self.value_btns.append(b)

    def resizeEvent(self, e):
        w = self.width()
        self.edit_btn.setGeometry(w - sx(86), sy(3), sx(78), sy(22))
        for b, r in zip(self.value_btns, grid(self._rows_rect(), 6, 1, 2)[1:]):
            b.setGeometry(int(r.x() + 180), int(r.y() + 1), int(r.width() - 182), int(r.height() - 2))
        super().resizeEvent(e)

    def _rows_rect(self):
        return QRectF(8, 30, self.width() - 16, self.height() - 38)

    def set_profile(self, profile, editable):
        self.profile = profile
        editing = editable and self.edit_btn.isChecked()
        self.edit_btn.setEnabled(editable)
        for b, field in zip(self.value_btns, profiles.FIELDS):
            b._text = fmt(field, profile[field[0]]) if profile else ""
            b.setVisible(editing)
            b.update()
        self.update()

    def paint_body(self, p):
        if not self.profile:
            return
        editing = self.value_btns[0].isVisible()  # values are shown on the edit buttons instead
        rows = [("Name", self.profile["name"], None)]
        rows += [(f[1], "" if editing else fmt(f, self.profile[f[0]]), None) for f in profiles.FIELDS]
        paint_rows(p, self._rows_rect(), rows, label_w=180)


class FilamentProfilesScreen(SubScreen):
    TITLE = "Filament Profiles"
    SUBTITLE = "Manage material profiles for optimal print settings"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.selected = None
        self.page = 0
        self.list_panel = Panel("Profiles", self)
        self.list_panel.setGeometry(sx(8), sy(58), sx(300), sy(378))
        self.add_btn = SmallButton("+  Add Profile", parent=self.list_panel, font_px=theme.BUTTON, checkable=False)
        self.add_btn.setGeometry(sx(150), sy(3), sx(142), sy(22))
        self.add_btn.clicked.connect(self._add)
        self.rows = []
        for i in range(ROWS_PER_PAGE):
            t = Tile(lambda p, r, s: None, self.list_panel)
            t.setCheckable(False)
            t.clicked.connect(lambda _=False, i=i: self._select_row(i))
            self.rows.append(t)
        place_buttons(self.rows, QRectF(sx(2), sy(26), sx(296), sy(316)), 1, 0)
        self.prev = SmallButton(icon=icons.back_arrow, parent=self.list_panel, checkable=False)
        self.next = SmallButton(icon=icons.chevron, parent=self.list_panel, checkable=False)
        self.prev.setGeometry(sx(8), sy(344), sx(136), sy(28))
        self.next.setGeometry(sx(156), sy(344), sx(136), sy(28))
        self.prev.clicked.connect(lambda: self._page(-1))
        self.next.clicked.connect(lambda: self._page(1))
        self.settings = SettingsPanel(self, self)
        self.settings.setGeometry(sx(316), sy(58), sx(476), sy(300))
        self.actions = Panel("", self)
        self.actions.setGeometry(sx(316), sy(366), sx(476), sy(70))
        self.activate = ActionTile(icons.check, "Set as Active", parent=self.actions, primary=True)
        self.duplicate = ActionTile(icons.save, "Duplicate", parent=self.actions)
        self.delete = ActionTile(icons.eject, "Delete", parent=self.actions)
        place_buttons([self.activate, self.duplicate, self.delete], QRectF(sx(2), sy(2), sx(472), sy(66)), 3, 0)
        self.activate.clicked.connect(lambda: self._save(dict(self._store(), active=self.selected)))
        self.duplicate.clicked.connect(self._duplicate)
        self.delete.clicked.connect(lambda: self.ctl.confirm(
            f"Delete '{self.selected}'?", "The profile is removed from Nexus Screen's saved profiles.",
            "Delete", lambda: self._save(profiles.delete(self._store(), self.selected))))
        self._data = {}

    # ── store helpers ────────────────────────────────────────────────────────
    def _store(self):
        return self._data.get("filament_profiles") or profiles.defaults()

    def _save(self, store):
        self.ctl.save_profiles(store)

    def _add(self):
        store, name = profiles.add(self._store())
        self.selected = name
        self._save(store)

    def _duplicate(self):
        store, name = profiles.add(self._store(), profiles.find(self._store(), self.selected))
        self.selected = name
        self._save(store)

    def edit_field(self, field):
        key, label, unit, lo, hi, ints, decs = field
        prof = profiles.find(self._store(), self.selected)
        self.ctl.edit_value(f"{self.selected}: {label}", unit, prof[key], lo, hi, ints, decs,
                            lambda v: self._save(profiles.update(self._store(), self.selected, **{key: int(v)})))

    # ── view ─────────────────────────────────────────────────────────────────
    def _page(self, d):
        self.page += d
        self.refresh()

    def _select_row(self, i):
        names = [p["name"] for p in self._store()["profiles"]]
        idx = self.page * ROWS_PER_PAGE + i
        if idx < len(names):
            self.selected = names[idx]
        self.refresh()

    def refresh(self):
        self.set_data(self._data)

    def set_data(self, data):
        self._data = data
        store = self._store()
        names = [p["name"] for p in store["profiles"]]
        if self.selected not in names:
            self.selected = store["active"] if store["active"] in names else names[0]
        pages = max(1, (len(names) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
        self.page = max(0, min(self.page, pages - 1))
        for b in (self.prev, self.next):
            b.setVisible(pages > 1)
        self.prev.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < pages - 1)
        shown = names[self.page * ROWS_PER_PAGE:(self.page + 1) * ROWS_PER_PAGE]
        for row, name in zip(self.rows, shown + [None] * ROWS_PER_PAGE):
            row.setVisible(name is not None)
            if name is not None:
                row.set_painter(self._row_painter(name, name == store["active"]))
                row.set_highlight(name == self.selected)
        editable = self.ctl.can_edit_metadata(data)
        self.settings.set_profile(profiles.find(store, self.selected), editable)
        self.add_btn.setEnabled(editable)
        self.activate.setEnabled(editable and self.selected != store["active"])
        self.duplicate.setEnabled(editable)
        self.delete.setEnabled(editable and len(names) > 1)

    @staticmethod
    def _row_painter(name, active):
        def paint(p, r, selected):
            p.setFont(theme.font(theme.CARD, QFont.Weight.DemiBold))
            p.setPen(theme.FG)
            p.drawText(r.adjusted(14, 0, -60, 0), Qt.AlignmentFlag.AlignVCenter, name)
            if active:
                p.setFont(theme.font(theme.SMALL, QFont.Weight.Bold, 0.6))
                p.setPen(QColor(theme.GREEN))
                p.drawText(r.adjusted(0, 0, -34, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "ACTIVE")
            icons.chevron(p, QRectF(r.right() - 22, r.center().y() - 6, 8, 12), QColor(theme.FG_SOFT), 1.8)
        return paint
