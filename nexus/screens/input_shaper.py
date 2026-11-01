"""Input Shaper — configured shaper per axis, run SHAPER_CALIBRATE (confirmed, homed,
idle), save to config (confirmed), and the runtime acceleration limit."""
from PyQt6.QtCore import QRectF, Qt

from nexus import theme
from nexus.screens.addon_common import Stepper, enable, place_buttons
from nexus.widgets import icons
from nexus.widgets.panels import ActionTile, Panel, RowsPanel, SubScreen

ACCEL_STEP = 500


class InputShaperScreen(SubScreen):
    TITLE = "Input Shaper"
    SUBTITLE = "Reduce vibrations for better print quality"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.status = RowsPanel("Status", self, label_w=110)
        self.status.setGeometry(8, 58, 300, 378)
        self.actions = Panel("Actions", self)
        self.actions.setGeometry(316, 58, 476, 160)
        self.run_btn = ActionTile(icons.mesh_grid, "Run Calibration", "Measure resonances", True, self.actions)
        self.save_btn = ActionTile(icons.save, "Save to Config", "Apply results (restarts)", parent=self.actions)
        place_buttons([self.run_btn, self.save_btn], QRectF(4, 26, 468, 130), 2, 0)
        self.run_btn.clicked.connect(lambda: self.ctl.confirm(
            "Run Input Shaper Calibration?", "Runs SHAPER_CALIBRATE: the toolhead vibrates on both axes for "
            "a few minutes. Results appear in the console.", "Start", lambda: self.ctl.run("shaper_calibrate")))
        self.save_btn.clicked.connect(self.ctl.confirm_save_config)
        self.accel = Panel("Current Acceleration", self)
        self.accel.setGeometry(316, 226, 476, 110)
        self.accel_stepper = Stepper(self.accel, self._accel, font_px=theme.FIELD)
        self.accel_stepper.place(10, 40, 456, 44, key_w=60)
        self.note = Panel("", self)
        self.note.setGeometry(316, 344, 476, 92)
        self.note.paint_body = self._paint_note
        self._data = {}

    def _paint_note(self, p):
        p.setFont(theme.font(theme.BODY))
        p.setPen(theme.DIM)
        p.drawText(QRectF(14, 8, 448, 76), Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                   "Values shown are from printer.cfg. Calibration needs an accelerometer (here: the "
                   "Beacon) and homed axes. The acceleration limit applies until Klipper restarts.")

    def _accel(self, d):
        cur = ((self._data.get("toolhead") or {}).get("limits") or {}).get("max_accel") or 0
        self.ctl.run("velocity_limit", param="ACCEL", value=max(ACCEL_STEP, cur + d * ACCEL_STEP))

    def set_data(self, data):
        self._data = data
        sh = (data.get("config") or {}).get("shaper")
        f = lambda v: "-" if v is None else f"{v:.1f} Hz"
        self.status.set_rows([("Shaper X", (sh or {}).get("type_x") or "-", None), ("Frequency X", f((sh or {}).get("freq_x")), None),
                              ("Shaper Y", (sh or {}).get("type_y") or "-", None), ("Frequency Y", f((sh or {}).get("freq_y")), None),
                              ("Configured", "Yes" if sh else "No", None)])
        homed = set("xyz") <= set((data.get("toolhead") or {}).get("homed", ""))
        enable(self.ctl, data, [(self.run_btn, "shaper_calibrate"), (self.save_btn, "save_config")])
        self.run_btn.setEnabled(self.run_btn.isEnabled() and homed)
        accel = ((data.get("toolhead") or {}).get("limits") or {}).get("max_accel")
        self.accel_stepper.set("--" if accel is None else f"{accel:.0f} mm/s²", self.ctl.can("velocity_limit", data),
                               (accel or 0) > ACCEL_STEP)
