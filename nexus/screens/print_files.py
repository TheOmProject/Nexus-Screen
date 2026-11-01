"""Print section: Print main page (PROVISIONAL), Print Files, File Preview (PROVISIONAL),
Print Complete. File data comes from Moonraker's file manager; starting, renaming and
deleting go through the gated controller."""
import os
import posixpath
from datetime import datetime

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QWidget

from nexus import theme
from nexus.screens.addon_common import place_buttons
from nexus.screens.print_status import ThumbnailView
from nexus.widgets import icons
from nexus.widgets.panels import ActionTile, ListPanel, Panel, RowsPanel, SubScreen

ROOT = "gcodes"


def fmt_size(n):
    return "-" if n is None else (f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{n / 1e3:.0f} KB")


def fmt_date(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "-"


def fmt_time(s):
    if not s:
        return "-"
    m = int(s // 60)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m {int(s % 60):02d}s"


def thumbnail_path(meta, filename):
    thumbs = [t for t in meta.get("thumbnails") or [] if t.get("relative_path")]
    if not thumbs:
        return None
    best = max(thumbs, key=lambda t: t.get("width", 0))
    return "/server/files/gcodes/" + posixpath.join(posixpath.dirname(filename), best["relative_path"])


class FileRow:
    """Row painter for folders / files / the parent entry."""

    @staticmethod
    def paint(p, r, item, selected):
        kind, name, size, modified = item
        icon = {"dir": icons.load, "up": icons.back_arrow}.get(kind, icons.print_)
        col = QColor(theme.AMBER) if kind == "dir" else QColor(theme.FG_SOFT)
        icon(p, QRectF(r.x() + 12, r.center().y() - 8, 14, 16), col)
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
        p.setPen(theme.FG)
        p.drawText(QRectF(r.x() + 36, r.y(), r.width() - 300, r.height()), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(".." if kind == "up" else name, Qt.TextElideMode.ElideMiddle,
                                              int(r.width() - 300)))
        p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        if kind == "file":
            p.drawText(QRectF(r.right() - 258, r.y(), 80, r.height()), Qt.AlignmentFlag.AlignVCenter, fmt_size(size))
        if kind != "up":
            p.drawText(QRectF(r.right() - 160, r.y(), 150, r.height()), Qt.AlignmentFlag.AlignVCenter, fmt_date(modified))


class PrintFilesScreen(SubScreen):
    TITLE = "Print Files"
    SUBTITLE = "Browse, select and manage print files"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.path = ""          # folder inside gcodes
        self.sort = "date"
        self.listing = None
        self.storage = RowsPanel("Storage", self, label_w=4)  # value-only rows
        self.storage.setGeometry(8, 58, 150, 300)
        self.files = ListPanel("Files", FileRow.paint, rows=7, parent=self, top=50, empty_text="This folder is empty")
        self.files.setGeometry(166, 58, 626, 300)
        self.files.key = lambda item: item[1]
        self.files.chosen.connect(self._chosen)
        self.files.paint_body = self._paint_header
        self.actions = Panel("", self)
        self.actions.setGeometry(8, 366, 784, 70)
        self.print_btn = ActionTile(icons.play, "Print", primary=True, parent=self.actions)
        self.preview_btn = ActionTile(icons.print_, "Preview", parent=self.actions)
        self.rename_btn = ActionTile(icons.terminal, "Rename", parent=self.actions)
        self.delete_btn = ActionTile(icons.eject, "Delete", parent=self.actions)
        self.sort_btn = ActionTile(icons.refresh, "Sort: Date", parent=self.actions)
        place_buttons([self.print_btn, self.preview_btn, self.rename_btn, self.delete_btn, self.sort_btn],
                      QRectF(2, 2, 780, 66), 5, 0)
        self.print_btn.clicked.connect(lambda: self.ctl.confirm_print(self.selected_path()))
        self.preview_btn.clicked.connect(lambda: self.ctl.open_preview(self.selected_path()))
        self.rename_btn.clicked.connect(self._rename)
        self.delete_btn.clicked.connect(self._delete)
        self.sort_btn.clicked.connect(self._toggle_sort)
        self._data = {}

    def showEvent(self, e):
        self.reload()
        super().showEvent(e)

    def reload(self):
        if self.listing is None or self.listing.get("_path") != self.path:
            self.files.set_loading()  # new folder: no stale rows while it loads
        self.ctl.get_json("/server/files/directory", {"path": posixpath.join(ROOT, self.path).rstrip("/")},
                          self._loaded, lambda: self._loaded(None))

    def _loaded(self, result):
        self.listing = None if result is None else dict(result, _path=self.path)
        self._fill()

    def _fill(self):
        if self.listing is None:
            self.files.set_loading("File list unavailable")
            self.storage.set_rows([("", "Not available", None)])
            self._sync_buttons()
            return
        r = self.listing
        files = [("file", f["filename"], f.get("size"), f.get("modified")) for f in r.get("files", [])
                 if f["filename"].lower().endswith((".gcode", ".g", ".gco"))]
        files.sort(key=(lambda i: -(i[3] or 0)) if self.sort == "date" else (lambda i: i[1].lower()))
        dirs = sorted((("dir", d["dirname"], None, d.get("modified")) for d in r.get("dirs", [])
                       if not d["dirname"].startswith(".")), key=lambda i: i[1].lower())
        up = [("up", "", None, None)] if self.path else []
        self.files.set_items(up + dirs + files)
        du = r.get("disk_usage") or {}
        self.storage.set_rows([("", "Local", theme.RED), ("", "gcodes/" + self.path, None),
                               ("", f"{du['free'] / 1e9:.1f} GB free" if du else "", None)])
        self._sync_buttons()

    def _paint_header(self, p):
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.DemiBold))
        p.setPen(theme.DIM)
        w = self.files.width()
        for x, label in ((40, "Name"), (w - 258, "Size"), (w - 160, "Modified")):
            p.drawText(QRectF(x, 28, 120, 20), Qt.AlignmentFlag.AlignVCenter, label)

    def selected_item(self):
        return next((i for i in self.files.items if i[1] == self.files.selected and i[0] == "file"), None)

    def selected_path(self):
        item = self.selected_item()
        return posixpath.join(self.path, item[1]) if item else None

    def _chosen(self, item):
        kind, name = item[0], item[1]
        if kind in ("dir", "up"):
            self.path = posixpath.dirname(self.path.rstrip("/")) if kind == "up" else posixpath.join(self.path, name)
            self.files.selected, self.files.page = None, 0
            self.reload()
        self._sync_buttons()

    def _toggle_sort(self):
        self.sort = "name" if self.sort == "date" else "date"
        self.sort_btn._title = "Sort: Name" if self.sort == "name" else "Sort: Date"
        self.sort_btn.update()
        self._fill()

    def _rename(self):
        path = self.selected_path()
        if not path:
            return
        base = os.path.basename(path)

        def done(text):
            new = text.strip()
            if new and new != base:
                if not new.lower().endswith(".gcode"):
                    new += ".gcode"
                self.ctl.call("file_move", body={"source": f"{ROOT}/{path}",
                                                 "dest": f"{ROOT}/{posixpath.join(self.path, new)}"})
                QTimer.singleShot(800, self.reload)
        self.ctl.keyboard(f"Rename {base}", base, done)

    def _delete(self):
        path = self.selected_path()
        if path:
            self.ctl.confirm(f"Delete {os.path.basename(path)}?", "The file is removed from the printer.",
                             "Delete", lambda: (self.ctl.call("file_delete", path_params={"path": path}),
                                                QTimer.singleShot(800, self.reload)))

    def set_data(self, data):
        self._data = data
        self._sync_buttons()

    def _sync_buttons(self):
        has = self.selected_item() is not None
        self.print_btn.setEnabled(has and self.ctl.can_call("print_start"))
        self.preview_btn.setEnabled(has)
        self.rename_btn.setEnabled(has and self.ctl.can_call("file_move"))
        self.delete_btn.setEnabled(has and self.ctl.can_call("file_delete")
                                   and self.selected_path() != self._data.get("filename"))


class FileDetails(SubScreen):
    """Thumbnail + metadata for one file (File Preview and Print Complete share this)."""

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.filename = None
        self.meta = {}
        self.thumb = ThumbnailView(self)
        self.thumb.setGeometry(8, 58, 330, 296)
        self.details = RowsPanel("Details", self, label_w=140)
        self.details.setGeometry(346, 58, 446, 296)

    def load(self, filename):
        self.filename, self.meta = filename, {}
        self.thumb.set_data({"filename": filename, "thumbnail": None, "thumbnail_state": "loading"})
        self.ctl.get_json("/server/files/metadata", {"filename": filename}, self._meta_loaded,
                          lambda: self._meta_loaded({}))

    def _meta_loaded(self, meta):
        self.meta = meta or {}
        path = thumbnail_path(self.meta, self.filename or "")
        if path:
            self.ctl.get_bytes(path, lambda raw: self.thumb.set_data(
                {"filename": self.filename, "thumbnail": raw, "thumbnail_state": "ready"}),
                lambda: self.thumb.set_data({"filename": self.filename, "thumbnail_state": "none"}))
        else:
            self.thumb.set_data({"filename": self.filename, "thumbnail_state": "none"})
        self.refresh_details()

    def refresh_details(self):
        pass


class FilePreviewScreen(FileDetails):
    TITLE = "File Preview"
    SUBTITLE = "Check the file before printing"

    def __init__(self, ctl, parent=None):
        super().__init__(ctl, parent)
        self.actions = Panel("", self)
        self.actions.setGeometry(8, 362, 784, 74)
        self.print_btn = ActionTile(icons.play, "Start Print", "Begin printing this file", True, self.actions)
        self.delete_btn = ActionTile(icons.eject, "Delete", "Remove from the printer", parent=self.actions)
        place_buttons([self.print_btn, self.delete_btn], QRectF(2, 2, 780, 70), 2, 0)
        self.print_btn.clicked.connect(lambda: self.ctl.confirm_print(self.filename))
        self.delete_btn.clicked.connect(lambda: self.ctl.confirm(
            f"Delete {os.path.basename(self.filename)}?", "The file is removed from the printer.", "Delete",
            lambda: (self.ctl.call("file_delete", path_params={"path": self.filename}), self.ctl.back())))

    def refresh_details(self):
        m = self.meta
        fil = m.get("filament_total")
        self.details.set_rows([
            ("File", os.path.basename(self.filename or ""), None), ("Size", fmt_size(m.get("size")), None),
            ("Modified", fmt_date(m.get("modified")), None),
            ("Slicer", f"{m.get('slicer', '-')} {m.get('slicer_version', '')}".strip(), None),
            ("Estimated Time", fmt_time(m.get("estimated_time")), None),
            ("Filament", "-" if not fil else f"{fil / 1000:.2f} m" + (f" / {m['filament_weight_total']:.1f} g"
                                                                    if m.get("filament_weight_total") else ""), None),
            ("Layer Height", f"{m['layer_height']:.2f} mm" if m.get("layer_height") else "-", None),
            ("First Layer", f"{m.get('first_layer_extr_temp', '-')}°C / {m.get('first_layer_bed_temp', '-')}°C", None),
        ])

    def set_data(self, data):
        self.print_btn.setEnabled(bool(self.filename) and self.ctl.can_call("print_start", data))
        self.delete_btn.setEnabled(bool(self.filename) and self.ctl.can_call("file_delete", data)
                                   and self.filename != data.get("filename"))


class PrintCompleteScreen(FileDetails):
    """Shown when a print finishes. Fullscreen like Print Status (no sidebar, no Back)."""
    submenu = False
    TITLE = "Print Complete"
    SUBTITLE = "The print has finished successfully"

    def __init__(self, ctl, parent=None):
        super().__init__(ctl, parent)
        self.stats = {}
        self.actions = Panel("", self)
        self.actions.setGeometry(8, 362, 784, 74)
        self.home_btn = ActionTile(icons.house, "Return to Home", "Ready for next print", True, self.actions)
        self.view_btn = ActionTile(icons.print_, "View File", "Open the file details", parent=self.actions)
        self.again_btn = ActionTile(icons.refresh, "Print Again", "Start this file again", parent=self.actions)
        place_buttons([self.home_btn, self.view_btn, self.again_btn], QRectF(2, 2, 780, 70), 3, 0)
        self.home_btn.clicked.connect(self.ctl.go_home)
        self.view_btn.clicked.connect(lambda: self.ctl.open_preview(self.filename))
        self.again_btn.clicked.connect(lambda: self.ctl.confirm_print(self.filename))

    def show_for(self, data):
        self.stats = dict(data.get("print_stats") or {}, layer=data.get("layer"))
        self.load(data.get("filename") or "")

    def refresh_details(self):
        s = self.stats
        layer = s.get("layer")
        self.details.set_rows([
            ("File Name", os.path.basename(self.filename or ""), None),
            ("Total Time", fmt_time(s.get("total_duration")), None),
            ("Print Time", fmt_time(s.get("print_duration")), None),
            ("Filament Used", f"{(s.get('filament_used') or 0) / 1000:.2f} m", None),
            ("Layer Count", str(layer[1]) if layer and layer[1] else "-", None),
            ("Status", "Completed Successfully", theme.GREEN),
        ])

    def set_data(self, data):
        self.again_btn.setEnabled(bool(self.filename) and self.ctl.can_call("print_start", data))


class PrintPage(QWidget):
    """Print main page (sidebar + top bar). PROVISIONAL — no approved reference."""
    section = "print"
    open_files = pyqtSignal()
    open_print = pyqtSignal()
    open_file = pyqtSignal(str)

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.files_tile = ActionTile(icons.print_, "Print Files", "Browse and start a print", True, self)
        self.status_tile = ActionTile(icons.play, "Return to Print", "No print running", parent=self)
        place_buttons([self.files_tile, self.status_tile], QRectF(8, 82, 704, 90), 2, 0)
        self.files_tile.clicked.connect(self.open_files)
        self.status_tile.clicked.connect(self.open_print)
        self.recent = ListPanel("Recent Files", FileRow.paint, rows=4, parent=self, empty_text="No print files")
        self.recent.setGeometry(8, 182, 704, 252)
        self.recent.key = lambda item: item[1]
        self.recent.chosen.connect(lambda item: self.open_file.emit(item[1]))

    def showEvent(self, e):
        self.ctl.get_json("/server/files/directory", {"path": ROOT}, self._loaded, lambda: self._loaded(None))
        super().showEvent(e)

    def _loaded(self, result):
        files = [("file", f["filename"], f.get("size"), f.get("modified")) for f in (result or {}).get("files", [])
                 if f["filename"].lower().endswith(".gcode")]
        self.recent.set_items(sorted(files, key=lambda i: -(i[3] or 0))[:4])

    def set_data(self, data):
        active = data.get("state") in ("printing", "paused")
        self.status_tile.setEnabled(bool(active))
        self.status_tile._subtitle = (os.path.basename(data.get("filename") or "") if active else "No print running")
        self.status_tile.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(theme.font(theme.TITLE, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(14, 6, 500, 34), Qt.AlignmentFlag.AlignVCenter, "Print")
        p.setFont(theme.font(theme.SUBTITLE, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(15, 37, 500, 18), Qt.AlignmentFlag.AlignVCenter, "Start prints and manage files")
        p.setFont(theme.font(theme.CAPS, QFont.Weight.DemiBold, 0.6))
        p.drawText(QRectF(15, 64, 300, 18), Qt.AlignmentFlag.AlignVCenter, "PRINT")
        p.end()
