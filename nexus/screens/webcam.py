"""Webcam — live view from Moonraker's configured webcams (snapshot polling while the
screen is visible). Shows a clear notice when no webcam is configured."""
from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QWidget

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import place_buttons
from nexus.widgets import icons
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.panels import ActionTile, Panel, RowsPanel, SubScreen

FRAME_MS = 500


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = None
        self.message = "Loading…"
        self.footer = ""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        paint_panel(p, r, 8, top=QColor(6, 7, 9), bottom=QColor(6, 7, 9), border=QColor(48, 52, 59), alpha=255)
        if self.frame is not None:
            img = self.frame.scaled(int(r.width()) - 8, int(r.height()) - 38, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int((r.width() - img.width()) / 2), 4 + int((r.height() - 34 - img.height()) / 2), img)
        else:
            icons.camera(p, QRectF(r.center().x() - 26, r.center().y() - 50, 52, 44), QColor(theme.MUTED))
            p.setFont(theme.font(smin(17), QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(QRectF(10, r.center().y(), r.width() - 20, 50), Qt.AlignmentFlag.AlignHCenter
                       | Qt.TextFlag.TextWordWrap, self.message)
        p.setFont(theme.font(theme.BODY, QFont.Weight.DemiBold))
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(12, r.height() - 30, r.width() - 24, 24), Qt.AlignmentFlag.AlignVCenter, self.footer)
        p.end()


class WebcamScreen(SubScreen):
    TITLE = "Webcam"
    SUBTITLE = "View live camera feed"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.cams, self.cam, self.frozen, self.full, self._busy = [], None, False, False, False
        self.view = VideoView(self)
        self.side = Panel("Camera Controls", self)
        self.snap = ActionTile(icons.camera, "Snapshot", "Freeze the image", True, self.side)
        self.fullscreen = ActionTile(icons.crosshair, "Full View", "Enlarge the image", parent=self.side)
        self.timelapse = ActionTile(icons.clock, "Timelapse", "Open timelapse", parent=self.side)
        place_buttons([self.snap, self.fullscreen, self.timelapse], QRectF(4, 26, 282, 222), 1, 0)
        self.info = RowsPanel("Camera", self, label_w=80)
        self.snap.clicked.connect(self._toggle_freeze)
        self.fullscreen.clicked.connect(self._toggle_full)
        self.timelapse.clicked.connect(lambda: self.ctl.open("timelapse"))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._grab)
        self._layout()

    def _layout(self):
        if self.full:
            self.view.setGeometry(sx(8), sy(58), sx(640), sy(378))
            self.side.setGeometry(sx(656), sy(58), sx(136), sy(378))
            self.info.hide()
        else:
            self.view.setGeometry(sx(8), sy(58), sx(486), sy(378))
            self.side.setGeometry(sx(502), sy(58), sx(290), sy(256))
            self.info.setGeometry(sx(502), sy(322), sx(290), sy(114))
            self.info.show()
        place_buttons([self.snap, self.fullscreen, self.timelapse],
                      QRectF(sx(4), sy(26), self.side.width() - sx(8), sy(346 if self.full else 224)), 1, 0)

    def showEvent(self, e):
        self.ctl.get_json("/server/webcams/list", None, self._cams, lambda: self._cams(None))
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()  # no polling while hidden
        super().hideEvent(e)

    def _cams(self, result):
        self.cams = [c for c in (result or {}).get("webcams", []) if c.get("enabled", True)]
        self.cam = self.cams[0] if self.cams else None
        if self.cam is None:
            self.view.frame, self.view.footer = None, ""
            self.view.message = ("No webcam is configured in Moonraker." if result is not None
                                 else "Webcam list unavailable.")
            self.timer.stop()
        else:
            self.view.message = "Waiting for image…"
            self.timer.start(FRAME_MS)
            self._grab()
        self.info.set_rows([("Name", self.cam["name"], None), ("Service", self.cam.get("service", "-"), None),
                            ("Status", "Online" if self.cam else "-", theme.GREEN)] if self.cam
                           else [("Status", "No camera", theme.DIM)])
        for b in (self.snap, self.fullscreen):
            b.setEnabled(self.cam is not None)
        self.view.update()

    def _grab(self):
        if self.frozen or self._busy or not self.cam:
            return
        self._busy = True
        self.ctl.get_url(self.cam.get("snapshot_url") or "", self._frame, self._failed)

    def _frame(self, raw):
        self._busy = False
        px = QPixmap()
        if px.loadFromData(raw):
            self.view.frame = px
            self.view.footer = f"{px.width()} × {px.height()}  •  {'Frozen' if self.frozen else 'Live'}"
            self.view.update()

    def _failed(self):
        self._busy = False
        self.view.frame, self.view.message = None, "Camera not responding."
        self.view.update()

    def _toggle_freeze(self):
        self.frozen = not self.frozen
        self.snap._title, self.snap._subtitle = ("Resume", "Back to live view") if self.frozen else ("Snapshot", "Freeze the image")
        self.snap.update()
        if self.view.frame is not None:
            self.view.footer = self.view.footer.replace("Live", "Frozen") if self.frozen else self.view.footer.replace("Frozen", "Live")
            self.view.update()

    def _toggle_full(self):
        self.full = not self.full
        self.fullscreen._title = "Normal View" if self.full else "Full View"
        self._layout()

    def set_data(self, data):
        pass
