"""Main window: brushed graphite backdrop, sidebar, minimal top bar, screen stack.

Also the controller the screens talk to: navigation (push/back), overlays, and
the single gate (`can` / `run`) every printer operation goes through.
"""
import os

from PyQt6.QtCore import QEvent, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget

from nexus import theme
from nexus.config import SCREEN_H, SCREEN_W, SIDEBAR_W, TOPBAR_H
from nexus.moonraker import commands
from nexus.screens.baby_step import BabyStepScreen
from nexus.screens.bed_mesh import BedMeshScreen
from nexus.screens.bed_screws import BedScrewsScreen
from nexus.screens.boxturtle import BoxTurtleControls, BoxTurtleDashboard
from nexus.screens.control import ControlPage
from nexus.screens.extruder import ExtruderScreen
from nexus.screens.extrusion import FilamentJob
from nexus.screens.filament import FilamentPage, FilamentScreen
from nexus.screens.filament_profiles import FilamentProfilesScreen
from nexus.display import Display
from nexus.screens.hub import HubScreen
from nexus.screens.input_shaper import InputShaperScreen
from nexus.screens.limits import LimitsScreen
from nexus.screens.macros import MacrosScreen
from nexus.screens.print_files import FilePreviewScreen, PrintCompleteScreen, PrintFilesScreen, PrintPage
from nexus.screens.settings import (AboutScreen, CameraSettings, FirmwareScreen, NetworkScreen, PrinterSettings,
                                    ScreenSettings, SettingsPage)
from nexus.screens.timelapse import TimelapseScreen
from nexus.screens.tools import ConsoleScreen, LogsScreen, SystemScreen
from nexus.screens.webcam import WebcamScreen
from nexus.screens.fans import FansScreen
from nexus.screens.home import HomeScreen
from nexus.screens.lighting import LightingScreen
from nexus.screens.move import MoveScreen
from nexus.screens.print_status import PrintStatusScreen
from nexus.screens.stealthchanger import StealthChangerControls, StealthChangerDashboard
from nexus.screens.temperature import PRESETS as TEMP_PRESETS, TemperatureScreen
from nexus.screens.zoffset import ZOffsetScreen
from nexus.widgets import icons
from nexus.widgets.brushed import brushed_pixmap
from nexus.widgets.buttons import BackButton, EmergencyStopButton
from nexus.widgets.dialog import ConfirmDialog
from nexus.widgets.overlays import (ColourPicker, ErrorDialog, HeaterPicker, Keyboard, MaterialPicker, ProfilePicker,
                                    TemperatureKeypad)
from nexus.widgets.sidebar import Sidebar
from nexus.widgets.topbar import TopBar

FULL_TOPBAR_H = 36
BACK_W = 120        # visible Back key width (78 approved originally, then 112)
BACK_TOUCH_W = 130  # touch target: 10 px past the key over the (non-interactive) status box edge
BACK_TOUCH_H = 60   # visible 34 px within the top bar + 26 px over the non-interactive screen title
ACTIVE_STATES = ("printing", "paused")
ESTOP_MAX_W = 160
HEATER_LABELS = {"extruder": "Nozzle", "heater_bed": "Bed", "chamber": "Chamber"}


class Root(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.topbar = TopBar(self, QRectF(SIDEBAR_W, 0, SCREEN_W - SIDEBAR_W, TOPBAR_H))

    def paintEvent(self, e):
        p = QPainter(self)
        p.drawPixmap(e.rect(), brushed_pixmap(SCREEN_W, SCREEN_H, base=12, spread=8), e.rect())
        if e.rect().intersects(self.topbar.rect.toAlignedRect()):
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.topbar.paint(p)
        p.end()


class BlankOverlay(QWidget):
    """Screen timeout: black cover; the first touch only wakes the screen."""

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        p.end()


class MainWindow(QMainWindow):
    def __init__(self, source, display=None):
        super().__init__()
        self.display = display or Display()
        self.hostname = None
        self.setWindowTitle("Nexus Screen")
        self.setFixedSize(SCREEN_W, SCREEN_H)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(theme.qss())
        self._root = Root()
        self.setCentralWidget(self._root)

        self.sidebar = Sidebar(SIDEBAR_W, SCREEN_H, self._root)
        self.sidebar.move(0, 0)
        self.sidebar.section_requested.connect(self._on_section)
        self.back_btn = BackButton(self._root)
        self.back_btn.setGeometry(4, 1, BACK_TOUCH_W, BACK_TOUCH_H)
        self.back_btn.clicked.connect(self.back)
        self.estop = EmergencyStopButton(self._root)  # above the stack with Back, below every dialog
        self.estop.hide()
        self.estop.triggered.connect(self.emergency_stop)

        self._data = {}
        self._last_data = {}
        self._source = source
        self.filament_job = FilamentJob(self)  # shared by Filament and Extruder
        self.stack = QStackedWidget(self._root)
        self.stack.stackUnder(self.back_btn)  # Back's touch extension lies over the screen; dialogs stay above
        self.home = HomeScreen()
        self.print_status = PrintStatusScreen()
        self.baby_step = BabyStepScreen(self)
        self.bt_dashboard = BoxTurtleDashboard(self)
        self.bt_controls = BoxTurtleControls(self)
        self.sc_dashboard = StealthChangerDashboard(self)
        self.sc_controls = StealthChangerControls(self)
        self.temperature_screen = TemperatureScreen(self)
        self.fans_screen = FansScreen(self)
        self.lighting_screen = LightingScreen(self)
        self.move_screen = MoveScreen(self)
        self.z_offset_screen = ZOffsetScreen(self)
        self.bed_screws_screen = BedScrewsScreen(self)
        self.bed_mesh_screen = BedMeshScreen(self)
        self.extruder_screen = ExtruderScreen(self)
        self.filament_screen = FilamentScreen(self)
        self.profiles_screen = FilamentProfilesScreen(self)
        self.filament_page = FilamentPage()
        self.filament_targets = {"filament": self.filament_screen, "profiles": self.profiles_screen,
                                 "boxturtle": self.bt_dashboard, "stealthchanger": self.sc_dashboard}
        self.filament_page.open_screen.connect(lambda key: self.push(self.filament_targets[key]))
        self.control_targets = {"move": self.move_screen, "temperature": self.temperature_screen,
                                "fans": self.fans_screen, "lighting": self.lighting_screen,
                                "z_offset": self.z_offset_screen, "bed_screws": self.bed_screws_screen,
                                "bed_mesh": self.bed_mesh_screen, "extruder": self.extruder_screen}
        # remaining sections
        self.print_page = PrintPage(self)
        self.print_files = PrintFilesScreen(self)
        self.preview = FilePreviewScreen(self)
        self.complete = PrintCompleteScreen(self)
        self.settings_page = SettingsPage()
        self.registry = {
            "print_files": self.print_files, "preview": self.preview,
            "macros": MacrosScreen(self), "webcam": WebcamScreen(self), "timelapse": TimelapseScreen(self),
            "input_shaper": InputShaperScreen(self), "limits": LimitsScreen(self),
            "console": ConsoleScreen(self), "logs": LogsScreen(self), "system": SystemScreen(self),
            "screen": ScreenSettings(self), "printer": PrinterSettings(self), "network": NetworkScreen(self),
            "camera": CameraSettings(self), "firmware": FirmwareScreen(self), "about": AboutScreen(self),
            "filament": self.filament_screen, "profiles": self.profiles_screen,
            "boxturtle": self.bt_dashboard, "stealthchanger": self.sc_dashboard,
            "bt_controls": self.bt_controls, "sc_controls": self.sc_controls,
        }
        self.registry.update(self.control_targets)
        self.registry.update(self._build_hubs())
        self.control_targets.update({k: self.registry[k] for k in ("macros", "webcam", "timelapse", "calibrate")})
        self.control = ControlPage(set(self.control_targets))
        self.control.open_screen.connect(lambda key: self.push(self.control_targets[key]))
        self.settings_page.open_screen.connect(self.open)
        self.print_page.open_files.connect(lambda: self.push(self.print_files))
        self.print_page.open_print.connect(lambda: self._reset_to(self.print_status))
        self.print_page.open_file.connect(self.open_preview)
        for s in (self.home, self.control, self.filament_page, self.print_page, self.settings_page,
                  self.print_status, self.baby_step, self.complete, *dict.fromkeys(self.registry.values())):
            self.stack.addWidget(s)
        self.screens = {"home": self.home, "print": self.print_page, "filament": self.filament_page,
                        "control": self.control, "settings": self.settings_page}
        self._history = []

        self.stop_dialog = ConfirmDialog(
            "Stop Print?", "Are you sure you want to stop the current print? This cannot be undone.",
            "Cancel", "Confirm Stop", self._root)
        self.confirm_dialog = ConfirmDialog("", "", "Cancel", "Confirm", self._root)
        self._confirm_cb = None
        self.confirm_dialog.confirmed.connect(lambda: self._confirm_cb and self._confirm_cb())
        self.heater_picker = HeaterPicker(self._root)
        self.heater_picker.applied.connect(self._confirm_pid)
        self.keypad = TemperatureKeypad(self._root)
        self.keyboard_overlay = Keyboard(self._root)
        self.error_dialog = ErrorDialog(self._root)
        self._dismissed_error = None
        self.error_dialog.close_btn.clicked.connect(lambda: setattr(self, "_dismissed_error", self.error_dialog.message))
        self.error_dialog.restart_btn.clicked.connect(lambda: self.run("firmware_restart"))
        self.error_dialog.logs_btn.clicked.connect(self._error_logs)
        self.blank = BlankOverlay(self._root)
        self.blank.hide()
        self.blank_timer = QTimer(self)
        self.blank_timer.setSingleShot(True)
        self.blank_timer.timeout.connect(self._blank)
        QApplication.instance().installEventFilter(self)
        self.set_screen_timeout(self.display.prefs["timeout_min"])
        self.profile_picker = ProfilePicker(self._root)
        self.profile_picker.applied.connect(lambda v: self._pick_cb and self._pick_cb(v))
        self.colour_picker = ColourPicker(self._root)
        self.material_picker = MaterialPicker(self._root)
        self._pick_cb = None
        self.colour_picker.applied.connect(lambda v: self._pick_cb and self._pick_cb(v))
        self.material_picker.applied.connect(lambda v: self._pick_cb and self._pick_cb(v))
        self.keypad.confirmed.connect(lambda heater, value: self.run("set_heater", heater=heater, target=value))

        self._was_active = False
        source.data_updated.connect(self._on_data)
        source.command_failed.connect(self.show_command_error)
        source.context = lambda: type(self.stack.currentWidget()).__name__
        self.home.return_to_print.connect(lambda: self._reset_to(self.print_status))
        self.print_status.go_home.connect(lambda: self._reset_to(self.home))
        self.print_status.pause_requested.connect(source.pause)
        self.print_status.resume_requested.connect(source.resume)
        self.print_status.stop_requested.connect(self.open_stop_dialog)
        self.print_status.baby_step_requested.connect(lambda: self.push(self.baby_step))
        self.baby_step.adjust.connect(source.z_adjust)  # the same baby-step command as before
        self.stop_dialog.confirmed.connect(source.cancel)
        for card in (self.home.temps, self.print_status.temps):
            card.heater_requested.connect(self.open_keypad)
            card.open_requested.connect(lambda: self.push(self.temperature_screen))
        for card in (self.home.addons, self.print_status.addons):
            card.addon_requested.connect(self.open_addon)
        self.bt_dashboard.manage.connect(lambda: self.push(self.bt_controls))
        self.sc_dashboard.manage.connect(lambda: self.push(self.sc_controls))
        self._show(self.home, animate=False)
        self.get_json("/printer/info", None, lambda r: setattr(self, "hostname", r.get("hostname")), lambda: None)

    def _build_hubs(self):
        o = self.open
        homed = lambda d: set("xyz") <= set((d.get("toolhead") or {}).get("homed", ""))
        probe = ("Probe Accuracy", "Test probe repeatability", icons.z_arrows, lambda: self.confirm(
            "Run probe accuracy test?", "PROBE_ACCURACY probes the bed several times at the current position.",
            "Start", lambda: self.run("probe_accuracy")))
        mesh = ("Bed Mesh", "Level print bed", icons.mesh_grid, lambda: o("bed_mesh"))
        zoff = ("Z Offset", "Set nozzle height", icons.crosshair, lambda: o("z_offset"))
        pid = ("PID Tuning", "Tune temperatures", icons.thermometer, lambda: o("temperature"))
        maintenance = HubScreen("Maintenance", "Tools and utilities for printer maintenance", [
            ("Clean Nozzle", "Run CLEAN_NOZZLE", icons.refresh, lambda: self.confirm(
                "Clean the nozzle?", "Runs the printer's CLEAN_NOZZLE macro.", "Run",
                lambda: self.run("macro", name="CLEAN_NOZZLE"))),
            mesh, zoff, ("Extruder Test", "Check extrusion", icons.filament, lambda: o("extruder")), pid, probe,
            ("Fans Test", "Test all fans", icons.fan, lambda: o("fans")),
            ("Lights Test", "Test all lights", icons.bulb, lambda: o("lighting")),
            ("Self Test", "", icons.check, None)],
            ("Maintenance Wizard", "", icons.wrench, None))
        maintenance.requires = {"Clean Nozzle": lambda d: "CLEAN_NOZZLE" in (d.get("macros") or {}) and self.can("macro", d),
                                "Probe Accuracy": lambda d: self.can("probe_accuracy", d) and homed(d)}
        calibrate = HubScreen("Calibrate", "Calibration tools for optimal print quality", [
            mesh, zoff, ("Input Shaper", "Reduce vibrations", icons.mesh_grid, lambda: o("input_shaper")), pid, probe,
            ("Axis Limits", "View movement limits", icons.corner, lambda: o("limits")),
            ("Extruder Calibrate", "", icons.filament, None), ("Fans Calibrate", "", icons.fan, None),
            ("Lights Calibrate", "", icons.bulb, None)],
            ("Calibration Wizard", "", icons.crosshair, None))
        calibrate.requires = {"Probe Accuracy": maintenance.requires["Probe Accuracy"]}
        tools = HubScreen("Tools", "Additional tools and utilities", [
            ("Console", "Send G-code commands", icons.terminal, lambda: o("console")),
            ("G-code Files", "Browse and manage", icons.print_, lambda: o("print_files")),
            ("File Manager", "", icons.load, None),
            ("Webcam", "View live feed", icons.camera, lambda: o("webcam")),
            ("Timelapse", "Create and manage", icons.clock, lambda: o("timelapse")),
            ("Logs", "View system logs", icons.terminal, lambda: o("logs")),
            ("System", "Info and services", icons.gear, lambda: o("system")),
            ("Firmware", "Versions and restarts", icons.load, lambda: o("firmware")),
            ("Restart", "Restart Klipper", icons.refresh, lambda: self.confirm(
                "Restart Klipper?", "Klipper reloads printer.cfg.", "Restart", lambda: self.call("klipper_restart")))],
            ("Advanced Tools", "", icons.wrench, None))
        tools.requires = {"Restart": lambda d: self.can_call("klipper_restart", d)}
        docs = lambda: self.info("Klipper Docs", "Klipper documentation: https://www.klipper3d.org — "
                                 "Moonraker: https://moonraker.readthedocs.io")
        help_hub = HubScreen("Help", "Documentation and support", [
            ("User Guide", "", icons.print_, None), ("FAQ", "", icons.warning, None), ("Tips & Tricks", "", icons.bulb, None),
            ("Video Guides", "", icons.play, None), ("Useful Links", "", icons.refresh, None),
            ("About", "Version info and credits", icons.check, lambda: o("about")),
            ("Troubleshooting", "", icons.warning, None),
            ("Klipper Docs", "Official documentation", icons.terminal, docs), ("Contact", "", icons.terminal, None)],
            ("Online Resources", "Documentation links", icons.crosshair, docs))
        return {"maintenance": maintenance, "calibrate": calibrate, "tools": tools, "help": help_hub}

    # ── navigation ───────────────────────────────────────────────────────────
    def _show(self, screen, animate=True):
        full = getattr(screen, "fullscreen", False)
        sub = getattr(screen, "submenu", False)
        self.sidebar.setVisible(not full)
        self.back_btn.setVisible(sub)
        top = self._root.topbar
        if full:
            left = 4 + BACK_W + 4 if sub else 0
            top.set_mode(QRectF(left, 0, SCREEN_W - left, FULL_TOPBAR_H), boxed=True)
            self.stack.setGeometry(0, FULL_TOPBAR_H, SCREEN_W, SCREEN_H - FULL_TOPBAR_H)
        else:
            top.set_mode(QRectF(SIDEBAR_W, 0, SCREEN_W - SIDEBAR_W, TOPBAR_H), boxed=False)
            self.stack.setGeometry(SIDEBAR_W, TOPBAR_H, SCREEN_W - SIDEBAR_W, SCREEN_H - TOPBAR_H)
            self.sidebar.set_active(getattr(screen, "section", "home"), animate)
        if screen not in (self.home, self.print_status) and self._data and hasattr(screen, "set_data"):
            screen.set_data(self._data)
        self.stack.setCurrentWidget(screen)
        self._root.update()
        self._update_estop(self._last_data)

    def push(self, screen):
        self._history.append(self.stack.currentWidget())
        self._show(screen)

    def back(self):
        self._show(self._history.pop() if self._history else self.home)

    def _reset_to(self, screen):
        self._history.clear()
        self._show(screen)

    def open(self, key):
        screen = self.registry[key]
        needs = getattr(screen, "requires", None)
        if isinstance(needs, str) and not self._data.get(needs):
            return  # add-on screens only exist when the printer reports the add-on
        self.push(screen)

    def go_home(self):
        self._reset_to(self.home)

    def open_preview(self, filename):
        if filename:
            self.preview.load(filename)
            self.push(self.preview)

    def _on_section(self, key):
        screen = self.screens.get(key)
        if screen is not None:
            self._reset_to(screen)

    def open_addon(self, name):
        screen = {"boxturtle": self.bt_dashboard, "stealthchanger": self.sc_dashboard}[name]
        if self._data.get(name):
            self.push(screen)

    # ── controller API used by the screens ───────────────────────────────────
    def commands_ready(self):
        """Printer commands enabled and no command of ours still running."""
        return getattr(self._source, "commands_enabled", False) and not getattr(self._source, "busy", False)

    def can(self, key, data=None):
        d = data or self._data
        return bool(d.get("connected") and getattr(self._source, "commands_enabled", False)
                    and not getattr(self._source, "busy", False)
                    and key in d.get("operations", ()) and commands.state_allows(key, d.get("state")))

    def can_edit_metadata(self, data=None):
        d = data or self._data
        return bool(d.get("connected") and getattr(self._source, "commands_enabled", False))

    def run(self, key, **params):
        if self.can(key):
            return self._source.run(key, **params)
        return False

    def run_batch(self, items, timeout_ms=None):
        if items and all(self.can(k) for k, _ in items):
            return self._source.run_batch(items, timeout_ms)
        return False

    def save_profiles(self, store):
        if self.can_edit_metadata():
            return self._source.save_profiles(store)
        return False

    def pick_profile(self, current, names, callback):
        self._pick_cb = callback
        self.profile_picker.open_for("", current, names)

    def edit_value(self, title, unit, current, lo, hi, int_digits, decimals, callback):
        allowed = self.can_edit_metadata()
        self.keypad.open_value(title, unit, current, lo, hi, int_digits, decimals, callback, allowed)

    def confirm(self, title, message, confirm_label, callback, detail="", info=False):
        self._confirm_cb = callback
        self.confirm_dialog.ask(title, message, confirm_label, detail, info)

    def show_command_error(self, command, message):
        """Klipper / Moonraker rejected a command: show its own message (also in logs/commands.jsonl)."""
        first = command.strip().splitlines()[-1] if command.strip() else command
        self.confirm("Command failed", message or "The printer did not accept the command.", "OK", None,
                     detail=first, info=True)

    def emergency_stop(self):
        """Immediate halt (Moonraker /printer/emergency_stop), no confirmation. Klipper then reports
        'shutdown' and the error dialog explains it; a failed request shows 'Command failed'."""
        if self._last_data.get("connected") and getattr(self._source, "commands_enabled", False):
            return self._source.emergency_stop()
        return False

    def operating(self, data):
        """Printer doing something an emergency stop could halt: printing/paused, Klipper executing
        commands (moves, homing, macros), a heater on, or a command of ours still running."""
        if not (data.get("connected") and getattr(self._source, "commands_enabled", False)):
            return False
        if data.get("state") == "error":
            return False  # already halted
        return (data.get("state") in ACTIVE_STATES or bool(data.get("klipper_busy"))
                or any(t and t[1] for t in (data.get("heaters") or {}).values())
                or getattr(self._source, "busy", False))

    def _update_estop(self, data):
        show = self.operating(data)
        if show:
            left, right = self._root.topbar.free_span()
            w = min(ESTOP_MAX_W, int(right - left) - 24)
            bar = self._root.topbar.rect
            geo = QRect(int(right) - 8 - w, int(bar.top()), w, int(bar.height()))
            if self.estop.geometry() != geo:
                self.estop.setGeometry(geo)
        self.estop.setVisible(show)

    def start_pid_tune(self):
        self.heater_picker.open_for("", "extruder")

    def _confirm_pid(self, heater):
        target = ((self._data.get("heaters") or {}).get(heater) or (0, 0))[1]
        if not target:  # no target set: use the PLA preset values from the Temperature reference
            target = TEMP_PRESETS[0][1] if heater == "extruder" else TEMP_PRESETS[0][2]
        self.confirm(f"PID Tune {HEATER_LABELS[heater]}?",
                     f"The {HEATER_LABELS[heater].lower()} will heat to {target:.0f}°C and cycle for several "
                     "minutes. Do not leave the printer unattended.", "Start Tune",
                     lambda: self.run("pid_tune", heater=heater, target=float(target)))

    def confirm_save_config(self):
        self.confirm("Save to Config?", "Writes pending settings (such as PID results) to printer.cfg "
                     "and restarts Klipper.", "Save & Restart", lambda: self.run("save_config"))

    def set_tool_meta(self, tool, **meta):
        if self.can_edit_metadata():
            return self._source.set_tool_meta(tool, **meta)
        return False

    def pick_colour(self, subject, current, callback):
        self._pick_cb = callback
        self.colour_picker.open_for(subject, (current or "").upper())

    def pick_material(self, subject, current, callback):
        self._pick_cb = callback
        self.material_picker.open_for(subject, current)

    # ── generic access + gated API calls (non-G-code Moonraker operations) ─────
    def get_json(self, path, query, callback, on_error=None):
        self._source.get_json(path, query, callback, on_error)

    def get_bytes(self, path, callback, on_error=None, tail=None):
        self._source.get_bytes(path, callback, on_error, tail)

    def get_url(self, url, callback, on_error=None):
        self._source.get_url(url, callback, on_error)

    def local(self, kind, arg, callback):
        self._source.local(kind, arg, callback)

    def can_call(self, key, data=None):
        d = data or self._data
        return bool(d.get("connected") and getattr(self._source, "commands_enabled", False)
                    and not getattr(self._source, "busy", False) and commands.api_allows(key, d.get("state")))

    def call(self, key, **kw):
        if self.can_call(key):
            return self._source.call(key, **kw)
        return False

    def confirm_print(self, filename):
        if filename and self.can_call("print_start"):
            self.confirm("Start print?", f"{os.path.basename(filename)} will start printing now.", "Start Print",
                         lambda: self.call("print_start", query={"filename": filename}))

    def keyboard(self, title, text, callback):
        self.keyboard_overlay.open_for(title, text, callback)

    def info(self, title, message):
        self.confirm(title, message, "OK", None, info=True)

    def platform_name(self):
        return QApplication.platformName()

    def set_screen_timeout(self, minutes):
        self.display.set_pref("timeout_min", minutes)
        self.blank_timer.stop()
        if minutes:
            self.blank_timer.start(minutes * 60_000)

    def _blank(self):
        self.blank.setGeometry(self._root.rect())
        self.blank.raise_()
        self.blank.show()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin):
            minutes = self.display.prefs["timeout_min"]
            if minutes:
                self.blank_timer.start(minutes * 60_000)
            if self.blank.isVisible():
                self.blank.hide()
                return True  # this touch only wakes the screen
        return False

    def _error_logs(self):
        self.error_dialog.hide()
        self._dismissed_error = self.error_dialog.message
        self.open("logs")

    def request_refresh(self):
        self._source.refresh()

    def request_mesh(self):
        self._source.request_mesh()

    def refresh_controls(self):
        screen = self.stack.currentWidget()
        if getattr(screen, "submenu", False) and self._data:
            screen.set_data(self._data)

    def open_keypad(self, heater):
        d = self._data
        if not d.get("connected"):
            return
        cur = (d.get("heaters") or {}).get(heater) or d.get({"extruder": "nozzle", "heater_bed": "bed"}.get(heater, ""))
        limits = (d.get("limits") or {}).get(heater, (0.0, 0.0))
        self.keypad.open_for(heater, HEATER_LABELS[heater], cur[0] if cur else None, cur[1] if cur else None,
                             limits, self.can("set_heater"))

    def open_stop_dialog(self):
        d = self._data
        pct = round((d.get("progress") or 0) * 100)
        self.stop_dialog.open(f"{os.path.basename(d.get('filename') or '')} · {pct}% complete")

    # ── data ─────────────────────────────────────────────────────────────────
    def _on_data(self, data):
        self._last_data = data
        self._root.topbar.set_data(data)
        self._update_estop(data)
        self.home.set_data(data)
        cmds = getattr(self._source, "commands_enabled", False)
        self.print_status.set_data(data, cmds, getattr(self._source, "busy", False))
        if not data.get("connected"):
            if self.stack.currentWidget() is self.baby_step:
                self.baby_step.set_data(data)  # keys off while disconnected
            return  # keep the current screen; controls are disabled until Moonraker returns
        self._data = data
        self.filament_job.on_data(data)
        self.filament_page.set_data(data)
        if self.keypad.isVisible():
            h = self.keypad._heater
            cur = (data.get("heaters") or {}).get(h)
            if cur:
                self.keypad.set_readings(cur[0], cur[1])
        current = self.stack.currentWidget()
        if current not in (self.home, self.print_status) and hasattr(current, "set_data"):
            needs = getattr(current, "requires", None)
            if isinstance(needs, str) and not data.get(needs):
                self._reset_to(self.home)  # add-on no longer reported by the printer
            else:
                current.set_data(data)
        if data["state"] == "error" and data.get("message"):
            if not self.error_dialog.isVisible() and data["message"] != self._dismissed_error:
                self.error_dialog.open_for(data["message"])
        else:
            self.error_dialog.hide()
            self._dismissed_error = None
        active = data["state"] in ACTIVE_STATES
        if active and not self._was_active:
            self._reset_to(self.print_status)
        elif not active:
            self.stop_dialog.hide()
            if self._was_active and data["state"] == "complete":
                self.complete.show_for(data)
                self._reset_to(self.complete)
            elif self.stack.currentWidget() in (self.print_status, self.baby_step):
                self._reset_to(self.home)
        self._was_active = active
