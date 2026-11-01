"""Settings section: Settings main page (PROVISIONAL), Screen, Printer Settings, Network,
Camera Settings, Firmware and About (PROVISIONAL). Tabs without a defined function in
Klipper/Moonraker are left out rather than shown as dead controls."""
import re
import subprocess
import sys

from PyQt6.QtCore import QRectF, Qt, pyqtSignal, PYQT_VERSION_STR, QT_VERSION_STR
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PyQt6.QtWidgets import QWidget

from nexus import theme
from nexus.display import TIMEOUTS
from nexus.screens.addon_common import Stepper, paint_bar, place_buttons
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.panels import ActionTile, ListPanel, Panel, RowsPanel, SubScreen, text_row

SETTINGS = [("screen", "Screen", "Brightness, screen timeout", icons.camera),
            ("printer", "Printer", "Motion limits, kinematics", icons.printer),
            ("network", "Network", "Wi-Fi, Ethernet", icons.refresh),
            ("camera", "Camera", "Webcam status", icons.camera),
            ("timelapse", "Timelapse", "Mode, interval, output", icons.clock),
            ("system", "System", "Info, services, power", icons.gear),
            ("firmware", "Firmware", "Versions, restarts, updates", icons.load),
            ("about", "About", "Version and credits", icons.check)]
SUPPORT = [("tools", "Tools", "Console, logs, utilities", icons.terminal),
           ("maintenance", "Maintenance", "Upkeep and tests", icons.wrench),
           ("help", "Help", "Documentation links", icons.warning)]


class SettingsPage(QWidget):
    """Settings main page (sidebar). PROVISIONAL — the reference shows these tiles as a submenu."""
    section = "settings"
    open_screen = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tiles = {}
        for key, title, sub, icon in SETTINGS + SUPPORT:
            t = ActionTile(icon, title, sub, parent=self)
            t.clicked.connect(lambda _=False, k=key: self.open_screen.emit(k))
            self.tiles[key] = t
        place_buttons([self.tiles[k] for k, *_ in SETTINGS], QRectF(8, 82, 704, 180), 4, 0)
        place_buttons([self.tiles[k] for k, *_ in SUPPORT], QRectF(8, 300, 528, 90), 3, 0)

    def set_data(self, data):
        pass

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(theme.font(theme.TITLE, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(14, 6, 500, 34), Qt.AlignmentFlag.AlignVCenter, "Settings")
        p.setFont(theme.font(theme.SUBTITLE, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(15, 37, 500, 18), Qt.AlignmentFlag.AlignVCenter, "Configure screen, printer and system settings")
        p.setFont(theme.font(theme.CAPS, QFont.Weight.DemiBold, 0.6))
        for y, label in ((64, "SETTINGS"), (282, "SUPPORT")):
            p.drawText(QRectF(15, y, 300, 18), Qt.AlignmentFlag.AlignVCenter, label)
        p.end()


class TabbedScreen(SubScreen):
    """Left tab list (as in the Screen / Printer / Network / Firmware references) + right page."""

    def __init__(self, ctl, tabs, parent=None, tab_w=190):
        super().__init__(parent)
        self.ctl = ctl
        self.tab_list = ListPanel("", text_row(lambda t: t[1]), rows=max(len(tabs), 5), parent=self, top=6)
        self.tab_list.setGeometry(8, 58, tab_w, 378)
        self.tab_list.key = lambda t: t[0]
        self.tab_list.chosen.connect(lambda t: self.select(t[0]))
        self.tab_list.set_items(tabs, tabs[0][0])
        self.page_rect = QRectF(tab_w + 16, 58, 784 - tab_w - 8, 378)
        self.pages = {}

    def select(self, key):
        self.tab_list.selected = key
        self.tab_list._refresh()
        for k, w in self.pages.items():
            w.setVisible(k == key)

    def add_page(self, key, widget):
        widget.setParent(self)
        widget.setGeometry(self.page_rect.toRect())
        self.pages[key] = widget
        widget.setVisible(key == self.tab_list.selected)


class ScreenSettings(TabbedScreen):
    TITLE = "Screen"
    SUBTITLE = "Configure display settings"

    def __init__(self, ctl, parent=None):
        super().__init__(ctl, [("brightness", "Brightness"), ("timeout", "Screen Timeout"), ("display", "Display Info")],
                         parent)
        d = ctl.display
        bright = Panel("Brightness", None)
        self.add_page("brightness", bright)
        self.bright_val = d.brightness()
        bright.paint_body = self._paint_bright
        self.bright_step = Stepper(bright, self._bright, font_px=theme.FIELD)
        self.bright_step.place(16, 120, self.page_rect.width() - 32, 50, key_w=70)
        timeout = Panel("Screen Timeout", None)
        self.add_page("timeout", timeout)
        self.timeout_btns = {}
        for i, m in enumerate(TIMEOUTS):
            b = SmallButton("Never" if m == 0 else f"{m} min", parent=timeout, font_px=theme.BUTTON, checkable=True)
            b.clicked.connect(lambda _=False, v=m: self._timeout(v))
            self.timeout_btns[m] = b
        place_buttons(list(self.timeout_btns.values()), QRectF(12, 40, self.page_rect.width() - 24, 56), 5, 8)
        self.info = RowsPanel("Display Info", None, label_w=150)
        self.add_page("display", self.info)
        self._sync()

    def _paint_bright(self, p):
        r = QRectF(16, 50, self.page_rect.width() - 32, 50)
        icons.bulb(p, QRectF(r.x(), r.y() + 10, 24, 30), QColor(theme.FG_SOFT))
        paint_bar(p, QRectF(r.x() + 40, r.center().y() - 5, r.width() - 120, 10), self.bright_val / 100, theme.RED)
        p.setFont(theme.font(20, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(r.right() - 70, r.y(), 70, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{self.bright_val}%")
        p.setFont(theme.font(theme.BODY))
        p.setPen(theme.DIM)
        p.drawText(QRectF(16, 190, r.width(), 60), Qt.TextFlag.TextWordWrap,
                   "Backlight of the touchscreen (never below 10%)." if self.ctl.display.can_set_brightness()
                   else "Brightness changes are disabled (read-only mode or no backlight control).")

    def _bright(self, d):
        if self.ctl.display.set_brightness(self.bright_val + d * 10):
            self.bright_val = self.ctl.display.brightness()
        self._sync()

    def _timeout(self, minutes):
        self.ctl.set_screen_timeout(minutes)
        self._sync()

    def _sync(self):
        d = self.ctl.display
        self.bright_step.set(f"{self.bright_val}%", d.can_set_brightness(), self.bright_val > 10, self.bright_val < 100)
        for m, b in self.timeout_btns.items():
            b.setChecked(d.prefs["timeout_min"] == m)
        bl = d.describe()
        self.info.set_rows([("Resolution", "800 × 480", None), ("Qt platform", self.ctl.platform_name(), None),
                            ("Backlight", bl["backlight"], None), ("Max level", str(bl["max"] or "-"), None)])
        for w in self.pages.values():
            w.update()

    def set_data(self, data):
        pass


class PrinterSettings(TabbedScreen):
    TITLE = "Printer Settings"
    SUBTITLE = "Printer motion limits and links to printer controls"
    LINKS = {"movement": "move", "temperature": "temperature", "extrusion": "extruder", "fans": "fans"}

    def __init__(self, ctl, parent=None):
        super().__init__(ctl, [("general", "General"), ("movement", "Movement  ›"), ("temperature", "Temperature  ›"),
                               ("extrusion", "Extrusion  ›"), ("fans", "Fans  ›")], parent)
        self.tab_list.chosen.disconnect()
        self.tab_list.chosen.connect(self._tab)
        page = Panel("General", None)
        self.add_page("general", page)
        page.paint_body = self._paint_general
        w = self.page_rect.width()
        self.steppers = {}
        for i, (key, step) in enumerate((("VELOCITY", 25), ("ACCEL", 500), ("SQUARE_CORNER_VELOCITY", 1))):
            st = Stepper(page, lambda d, k=key, s=step: self._limit(k, s, d), font_px=theme.FIELD)
            st.place(w - 260, 104 + i * 48, 250, 40, key_w=46)
            self.steppers[key] = st
        self.pa = Stepper(page, self._pa, font_px=theme.FIELD)
        self.pa.place(w - 260, 248, 250, 40, key_w=46)
        self.page = page
        self._data = {}

    def _tab(self, tab):
        if tab[0] in self.LINKS:
            self.tab_list.selected = "general"
            self.tab_list._refresh()
            self.ctl.open(self.LINKS[tab[0]])
        else:
            self.select(tab[0])

    def _limit(self, key, step, d):
        lim = (self._data.get("toolhead") or {}).get("limits") or {}
        cur = {"VELOCITY": lim.get("max_velocity"), "ACCEL": lim.get("max_accel"),
               "SQUARE_CORNER_VELOCITY": lim.get("square_corner_velocity")}[key] or 0
        self.ctl.run("velocity_limit", param=key, value=max(step, cur + d * step))

    def _pa(self, d):
        pa = (self._data.get("extruder") or {}).get("pa") or 0.0
        self.ctl.run("pressure_advance", value=round(max(0.0, pa + d * 0.005), 3))

    def _paint_general(self, p):
        cfg = self._data.get("config") or {}
        p.setFont(theme.font(theme.LABEL))
        p.setPen(theme.DIM)
        rows = [(30, "Printer Name"), (62, "Kinematics"), (104, "Max Print Speed"), (152, "Max Acceleration"),
                (200, "Square Corner Velocity"), (248, "Pressure Advance")]
        for y, label in rows:
            p.drawText(QRectF(14, y, 220, 40 if y > 90 else 30), Qt.AlignmentFlag.AlignVCenter, label)
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
        p.setPen(theme.FG)
        p.drawText(QRectF(240, 30, 300, 30), Qt.AlignmentFlag.AlignVCenter, self.ctl.hostname or "-")
        p.drawText(QRectF(240, 62, 300, 30), Qt.AlignmentFlag.AlignVCenter, cfg.get("kinematics") or "-")
        p.setFont(theme.font(theme.CAPTION))
        p.setPen(theme.DIM)
        p.drawText(QRectF(14, 300, self.page.width() - 28, 60), Qt.TextFlag.TextWordWrap,
                   "Runtime values (SET_VELOCITY_LIMIT / SET_PRESSURE_ADVANCE): they apply immediately and "
                   "reset when Klipper restarts. printer.cfg is not changed.")

    def set_data(self, data):
        self._data = data
        lim = (data.get("toolhead") or {}).get("limits") or {}
        ok = self.ctl.can("velocity_limit", data)
        fmt = {"VELOCITY": ("max_velocity", "mm/s"), "ACCEL": ("max_accel", "mm/s²"),
               "SQUARE_CORNER_VELOCITY": ("square_corner_velocity", "mm/s")}
        for key, st in self.steppers.items():
            field, unit = fmt[key]
            v = lim.get(field)
            st.set("--" if v is None else f"{v:g} {unit}", ok)
        pa = (data.get("extruder") or {}).get("pa")
        self.pa.set("--" if pa is None else f"{pa:.3f}", self.ctl.can("pressure_advance", data), (pa or 0) > 0)
        self.page.update()


def nm_fields(line):
    return [f.replace("\\:", ":") for f in re.split(r"(?<!\\):", line)]


def group_networks(text):
    """nmcli 'IN-USE,BSSID,SSID,SIGNAL,SECURITY' lines -> one entry per SSID:
    (connected, ssid, best signal, security, access points). An SSID seen through several
    access points is connected when any of its BSSIDs is the one in use."""
    nets = {}
    for line in text.splitlines():
        f = nm_fields(line)
        if len(f) < 5 or not f[2]:
            continue  # malformed or hidden SSID
        inuse, bssid, ssid, signal, sec = f[0].strip() == "*", f[1], f[2], int(f[3] or 0), f[4]
        n = nets.setdefault(ssid, {"inuse": False, "signal": 0, "sec": sec, "aps": set()})
        n["inuse"] |= inuse
        n["signal"] = max(n["signal"], signal)
        n["aps"].add(bssid)
    items = [(n["inuse"], ssid, str(n["signal"]), n["sec"], len(n["aps"])) for ssid, n in nets.items()]
    return sorted(items, key=lambda n: (not n[0], -int(n[2]), n[1].lower()))


class NetworkScreen(TabbedScreen):
    TITLE = "Network"
    SUBTITLE = "Network status (changes are made with the system tools)"

    def __init__(self, ctl, parent=None):
        super().__init__(ctl, [("wifi", "Wi-Fi"), ("ethernet", "Ethernet")], parent)
        w = self.page_rect.width()
        self.wifi = QWidget()
        self.add_page("wifi", self.wifi)
        self.networks = ListPanel("Wi-Fi Networks", self._net_row, rows=6, parent=self.wifi,
                                  empty_text="No Wi-Fi networks found")
        self.networks.setGeometry(0, 0, int(w * 0.56), 378)
        self.networks.key = lambda n: n[1]
        self.scan = SmallButton("Refresh", parent=self.networks, font_px=theme.BUTTON, checkable=False)
        self.scan.setGeometry(int(w * 0.56) - 92, 3, 84, 22)
        self.scan.clicked.connect(self.reload)
        self.conn = RowsPanel("Connection Info", self.wifi, label_w=90)
        self.conn.setGeometry(int(w * 0.56) + 8, 0, int(w * 0.44) - 8, 378)
        self.eth = RowsPanel("Ethernet", None, label_w=120)
        self.add_page("ethernet", self.eth)
        self.connected_ssid, self._dev_info = None, None

    @staticmethod
    def _net_row(p, r, n, selected):
        inuse, ssid, signal, sec, aps = n
        icons.refresh(p, QRectF(r.x() + 10, r.center().y() - 8, 16, 16), QColor(theme.FG_SOFT))
        status = (("Connected · " if inuse else "") + f"{signal}%" + (" · " + sec if sec else "")
                  + (f" · {aps} APs" if aps > 1 else ""))
        sf = theme.font(theme.CAPTION, QFont.Weight.DemiBold)
        name_w = r.width() - 34 - 12 - QFontMetricsF(sf).horizontalAdvance(status) - 12  # name never runs into it
        nf = theme.font(theme.BUTTON, QFont.Weight.DemiBold)
        p.setFont(nf)
        p.setPen(theme.FG)
        p.drawText(QRectF(r.x() + 34, r.y(), name_w, r.height()), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetricsF(nf).elidedText(ssid or "(hidden)", Qt.TextElideMode.ElideRight, name_w))
        p.setFont(sf)
        p.setPen(theme.GREEN if inuse else theme.DIM)
        p.drawText(r.adjusted(0, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, status)

    def showEvent(self, e):
        self.reload()
        super().showEvent(e)

    def reload(self):
        self.networks.set_loading("Scanning…")
        self.ctl.local("wifi", None, self._wifi)
        self.ctl.local("devices", None, self._devices)

    def _wifi(self, text):
        items = group_networks(text)
        self.connected_ssid = next((n[1] for n in items if n[0]), None)
        self.networks.set_items(items, self.connected_ssid)
        if not items:
            self.conn.set_rows([("Status", "No Wi-Fi information", theme.DIM)])
        elif self._dev_info:
            self._show(*self._dev_info)  # Network row shows the connected SSID

    def _devices(self, text):
        devs = [nm_fields(l) for l in text.splitlines() if l]
        wifi = next((d for d in devs if len(d) > 2 and d[1] == "wifi"), None)
        eth = next((d for d in devs if len(d) > 2 and d[1] == "ethernet"), None)
        self.eth.set_rows([("Device", eth[0], None), ("State", eth[2].capitalize(), theme.GREEN if eth[2] == "connected" else theme.DIM)]
                          if eth else [("Status", "No Ethernet device", theme.DIM)])
        if wifi:
            self.ctl.local("show", wifi[0], lambda t: self._show(wifi, t))

    def _show(self, dev, text):
        kv = {}
        for line in text.splitlines():
            k, _, v = line.partition(":")
            kv.setdefault(k.split("[")[0], v.replace("\\:", ":"))
        self._dev_info = (dev, text)
        connected = dev[2] == "connected"
        network = self.connected_ssid or (dev[3] if len(dev) > 3 else "-")
        self.conn.set_rows([("Status", dev[2].capitalize(), theme.GREEN if connected else theme.DIM),
                            ("Network", network, None),
                            ("IP Address", kv.get("IP4.ADDRESS", "-"), None), ("Gateway", kv.get("IP4.GATEWAY", "-"), None),
                            ("DNS", kv.get("IP4.DNS", "-"), None), ("MAC", kv.get("GENERAL.HWADDR", "-"), None)])

    def set_data(self, data):
        pass


class CameraSettings(SubScreen):
    TITLE = "Camera Settings"
    SUBTITLE = "Webcam configuration reported by Moonraker"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.status = RowsPanel("Camera Status", self, label_w=130)
        self.status.setGeometry(8, 58, 784, 290)
        self.actions = Panel("", self)
        self.actions.setGeometry(8, 356, 784, 80)
        self.open_btn = ActionTile(icons.camera, "Open Webcam", "Live view", True, self.actions)
        self.open_btn.setGeometry(2, 2, 388, 76)
        self.open_btn.clicked.connect(lambda: self.ctl.open("webcam"))

    def showEvent(self, e):
        self.ctl.get_json("/server/webcams/list", None, self._loaded, lambda: self._loaded(None))
        super().showEvent(e)

    def _loaded(self, result):
        cams = (result or {}).get("webcams", [])
        if not cams:
            self.status.set_rows([("Status", "No webcam configured" if result is not None else "Unavailable", theme.DIM)])
            return
        c = cams[0]
        self.status.set_rows([("Status", "Enabled" if c.get("enabled", True) else "Disabled", theme.GREEN),
                              ("Name", c.get("name", "-"), None), ("Service", c.get("service", "-"), None),
                              ("Stream URL", c.get("stream_url", "-"), None), ("Snapshot URL", c.get("snapshot_url", "-"), None),
                              ("Target FPS", str(c.get("target_fps", "-")), None)])

    def set_data(self, data):
        pass


class FirmwareScreen(SubScreen):
    TITLE = "Firmware"
    SUBTITLE = "View versions, restart Klipper and check for updates"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.info = {}
        self.list = ListPanel("", text_row(lambda c: c.capitalize()), rows=7, parent=self, top=6,
                              empty_text="Update information unavailable")
        self.list.setGeometry(8, 58, 190, 378)
        self.list.chosen.connect(lambda c: self._show(c))
        self.details = RowsPanel("Details", self, label_w=150)
        self.details.setGeometry(206, 58, 586, 218)
        self.actions = Panel("Actions", self)
        self.actions.setGeometry(206, 284, 586, 152)
        self.restart_btn = ActionTile(icons.refresh, "Restart Klipper", "Reload config", True, self.actions)
        self.fw_btn = ActionTile(icons.refresh, "Firmware Restart", "Restart MCUs", parent=self.actions)
        self.logs_btn = ActionTile(icons.terminal, "View Logs", "klippy.log", parent=self.actions)
        self.check_btn = ActionTile(icons.load, "Check Updates", "Refresh update status", parent=self.actions)
        place_buttons([self.restart_btn, self.fw_btn, self.logs_btn, self.check_btn], QRectF(4, 24, 578, 124), 2, 0)
        self.restart_btn.clicked.connect(lambda: self.ctl.confirm("Restart Klipper?", "Klipper reloads printer.cfg.",
                                         "Restart", lambda: self.ctl.call("klipper_restart")))
        self.fw_btn.clicked.connect(lambda: self.ctl.confirm("Firmware restart?", "Runs FIRMWARE_RESTART.", "Restart",
                                    lambda: self.ctl.run("firmware_restart")))
        self.logs_btn.clicked.connect(lambda: self.ctl.open("logs"))
        self.check_btn.clicked.connect(lambda: (self.ctl.call("update_refresh"), self.reload()))

    def showEvent(self, e):
        self.reload()
        super().showEvent(e)

    def reload(self):
        self.ctl.get_json("/machine/update/status", None, self._loaded, lambda: self._loaded(None))

    def _loaded(self, result):
        self.info = (result or {}).get("version_info", {})
        names = [n for n in self.info if n != "system"]
        self.list.set_items(names, self.list.selected or (names[0] if names else None))
        self._show(self.list.selected)

    def _show(self, name):
        v = self.info.get(name) or {}
        if not v:
            self.details.set_rows([("Status", "Update information unavailable", theme.DIM)])
            return
        newer = v.get("remote_version") and v.get("remote_version") != v.get("version")
        self.details.title = name.capitalize()
        self.details.set_rows([("Installed", v.get("version") or "-", None), ("Latest", v.get("remote_version") or "-", None),
                               ("Status", "Update available" if newer else "Up to date", theme.AMBER if newer else theme.GREEN),
                               ("Local changes", "Yes" if v.get("is_dirty") else "No", None),
                               ("Updating", "Use Mainsail's update manager", theme.DIM)])

    def set_data(self, data):
        self.restart_btn.setEnabled(self.ctl.can_call("klipper_restart", data))
        self.fw_btn.setEnabled(self.ctl.can("firmware_restart", data))
        self.check_btn.setEnabled(self.ctl.can_call("update_refresh", data))


def build_id():
    try:
        out = subprocess.run(["git", "-C", __file__.rsplit("/nexus/", 1)[0], "describe", "--always", "--dirty"],
                             capture_output=True, text=True, timeout=3)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class AboutScreen(SubScreen):
    """PROVISIONAL — no reference."""
    TITLE = "About"
    SUBTITLE = "Nexus Screen version and credits"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.info = RowsPanel("Nexus Screen", self, label_w=180)
        self.info.setGeometry(8, 58, 784, 378)
        self.info.set_rows([("Application", "Nexus Screen (PyQt6)", None), ("Build", build_id(), None),
                            ("PyQt / Qt", f"{PYQT_VERSION_STR} / {QT_VERSION_STR}", None),
                            ("Python", sys.version.split()[0], None), ("Display", "800 × 480 touchscreen", None),
                            ("Typeface", "Rajdhani (SIL Open Font License)", None),
                            ("Printer API", "Moonraker (REST)", None)])

    def set_data(self, data):
        pass
