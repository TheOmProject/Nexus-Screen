"""Timelapse — moonraker-timelapse settings and status. When the component is not
loaded in Moonraker the screen says so instead of offering controls."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QFont

from nexus import theme
from nexus.screens.addon_common import Stepper, place_buttons
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton, ToggleSwitch
from nexus.widgets.panels import ActionTile, Panel, RowsPanel, SubScreen

MODES = (("layermacro", "Layer"), ("hyperlapse", "Hyperlapse"))


class TimelapseScreen(SubScreen):
    TITLE = "Timelapse"
    SUBTITLE = "Create and manage timelapse recordings"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.settings = None
        self.frames = None
        self.panel = Panel("Timelapse Settings", self)
        self.panel.setGeometry(8, 58, 450, 300)
        self.panel.paint_body = self._paint_labels
        self.enabled = ToggleSwitch(self.panel)
        self.enabled.setGeometry(330, 40, 56, 26)
        self.enabled.clicked.connect(lambda: self._set(enabled=self.enabled.isChecked()))
        self.mode_btns = {}
        for i, (key, label) in enumerate(MODES):
            b = SmallButton(label, parent=self.panel, font_px=theme.BUTTON, checkable=True)
            b.setGeometry(170 + i * 136, 84, 130, 38)
            b.clicked.connect(lambda _=False, k=key: self._set(mode=k))
            self.mode_btns[key] = b
        self.cycle = Stepper(self.panel, lambda d: self._set(hyperlapse_cycle=max(1, self.settings["hyperlapse_cycle"] + d * 5)))
        self.cycle.place(170, 136, 266, 38, key_w=46)
        self.fps = Stepper(self.panel, lambda d: self._set(output_framerate=max(1, min(60, self.settings["output_framerate"] + d * 5))))
        self.fps.place(170, 188, 266, 38, key_w=46)
        self.autorender = ToggleSwitch(self.panel)
        self.autorender.setGeometry(330, 248, 56, 26)
        self.autorender.clicked.connect(lambda: self._set(autorender=self.autorender.isChecked()))
        self.status = RowsPanel("Current Print Timelapse", self, label_w=130)
        self.status.setGeometry(466, 58, 326, 300)
        self.actions = Panel("", self)
        self.actions.setGeometry(8, 366, 784, 70)
        self.render = ActionTile(icons.play, "Render Now", "Build the video from frames", True, self.actions)
        self.refresh = ActionTile(icons.refresh, "Refresh", "Re-read timelapse status", parent=self.actions)
        place_buttons([self.render, self.refresh], QRectF(2, 2, 780, 66), 2, 0)
        self.render.clicked.connect(lambda: self.ctl.call("timelapse_render"))
        self.refresh.clicked.connect(self.reload)
        self._data = {}

    def showEvent(self, e):
        self.reload()
        super().showEvent(e)

    def reload(self):
        self.ctl.get_json("/machine/timelapse/settings", None, self._loaded, lambda: self._loaded(None))
        self.ctl.get_json("/machine/timelapse/lastframeinfo", None, self._frames_loaded, lambda: None)

    def _frames_loaded(self, info):
        self.frames = info
        self._sync()

    def _loaded(self, settings):
        self.settings = settings
        self._sync()

    def _set(self, **change):
        if self.settings is None:
            return
        self.ctl.call("timelapse_settings", body=change)
        self.settings.update(change)  # optimistic; reload confirms
        self._sync()

    def _paint_labels(self, p):
        p.setFont(theme.font(theme.LABEL, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        if self.settings is None:
            p.setFont(theme.font(theme.CARD, QFont.Weight.DemiBold))
            p.setPen(theme.FG_SOFT)
            p.drawText(QRectF(20, 90, self.panel.width() - 40, 90), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       "Timelapse is not enabled in Moonraker\n(the moonraker-timelapse component is not loaded).")
            return
        for y, label in ((40, "Enabled"), (84, "Mode"), (136, "Hyperlapse Interval"), (188, "Output Framerate"),
                         (248, "Auto Render")):
            p.drawText(QRectF(12, y, 156, 34), Qt.AlignmentFlag.AlignVCenter, label)

    def _sync(self):
        s = self.settings
        on = s is not None
        controls = [self.enabled, self.autorender, *self.mode_btns.values(),
                    self.cycle.minus, self.cycle.value, self.cycle.plus, self.fps.minus, self.fps.value, self.fps.plus]
        for w in controls:
            w.setVisible(on)
        editable = on and self.ctl.can_call("timelapse_settings")
        if on:
            self.enabled.setChecked(bool(s.get("enabled")))
            self.autorender.setChecked(bool(s.get("autorender")))
            for k, b in self.mode_btns.items():
                b.setChecked(s.get("mode") == k)
                b.setEnabled(editable)
            self.cycle.set(f"{s.get('hyperlapse_cycle', 0)} s", editable and s.get("mode") == "hyperlapse")
            self.fps.set(f"{s.get('output_framerate', 0)} fps", editable)
            self.enabled.setEnabled(editable)
            self.autorender.setEnabled(editable)
        f = self.frames or {}
        self.status.set_rows([("Status", "Enabled" if on and s.get("enabled") else ("Not available" if not on else "Disabled"),
                               theme.GREEN if on and s.get("enabled") else theme.DIM),
                              ("Camera", (s or {}).get("camera") or "-", None),
                              ("Frames Captured", str(f.get("count", "-")), None),
                              ("Last Frame", f.get("lastframefile") or "-", None),
                              ("Storage", "timelapse/", None)])
        self.render.setEnabled(on and self.ctl.can_call("timelapse_render"))
        self.refresh.setEnabled(True)
        self.panel.update()

    def set_data(self, data):
        self._data = data
        self._sync()
