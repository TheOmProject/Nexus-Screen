"""Tools screens: Console, Logs, System. All reads are Moonraker GETs while visible;
sending G-code, restarts, reboot and shutdown go through the gated controller."""
from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.addon_common import enable, grid, paint_bar, place_buttons
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton, ToggleSwitch
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.overlays import MONO
from nexus.widgets.panels import ActionTile, ListPanel, Panel, RowsPanel, SubScreen, text_row

QUICK = [("M105", "Get Temperatures"), ("M114", "Get Position"), ("STATUS", "Printer Status"),
         ("QUERY_ENDSTOPS", "Endstop States"), ("HELP", "List Commands")]
LOG_TAIL = 24_000  # bytes fetched from the end of a log (rotated logs are tens of MB)


def mono(px):
    f = QFont(MONO)
    f.setPixelSize(px)
    return f


class TextView(Panel):
    """Monospace text area showing the last lines that fit; ▲ ▼ page back/forward."""

    def __init__(self, title, parent=None, colourize=None):
        super().__init__(title, parent)
        self.lines, self.offset, self.colourize = [], 0, colourize
        self.up = SmallButton(icon=icons.chevron_up, parent=self, checkable=False)
        self.down = SmallButton(icon=icons.chevron_down, parent=self, checkable=False)
        self.up.clicked.connect(lambda: self._scroll(1))
        self.down.clicked.connect(lambda: self._scroll(-1))

    def resizeEvent(self, e):
        self.up.setGeometry(self.width() - 44, 30, 36, 40)
        self.down.setGeometry(self.width() - 44, self.height() - 48, 36, 40)
        super().resizeEvent(e)

    def visible_count(self):
        return max(1, int((self.height() - 40) / 15))

    def set_lines(self, lines, follow=True):
        self.lines = lines
        if follow:
            self.offset = 0
        self.update()

    def _scroll(self, d):
        n = self.visible_count()
        self.offset = max(0, min(max(0, len(self.lines) - n), self.offset + d * (n - 2)))
        self.update()

    def paint_body(self, p):
        r = QRectF(8, 28, self.width() - 60, self.height() - 36)
        paint_panel(p, r, 5, top=QColor(6, 7, 9), bottom=QColor(10, 11, 13), border=QColor(40, 44, 50), alpha=255)
        n = self.visible_count()
        end = len(self.lines) - self.offset
        p.setFont(mono(smin(12)))
        for i, line in enumerate(self.lines[max(0, end - n):end]):
            colour = self.colourize(line) if self.colourize else None
            p.setPen(QColor(colour) if colour else theme.FG_SOFT)
            p.drawText(QRectF(r.x() + 8, r.y() + 4 + i * 15, r.width() - 16, 15), Qt.AlignmentFlag.AlignVCenter,
                       p.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, int(r.width() - 16)))


def log_colour(line):
    low = line.lower()
    if "error" in low or line.startswith("!!"):
        return theme.RED
    if "warn" in low:
        return theme.AMBER
    return None


class ConsoleScreen(SubScreen):
    TITLE = "Console"
    SUBTITLE = "Send G-code commands and view printer responses"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.view = TextView("", self, lambda l: theme.RED if l.startswith("!!") else
                             ("#ffffff" if l.startswith(">") else None))
        self.view.setGeometry(sx(8), sy(58), sx(520), sy(306))
        self.quick = Panel("Quick Commands", self)
        self.quick.setGeometry(sx(536), sy(58), sx(256), sy(306))
        self.quick_btns = []
        for cmd, label in QUICK:
            b = ActionTile(icons.terminal, cmd, label, parent=self.quick)
            b.clicked.connect(lambda _=False, c=cmd: self.send(c))
            self.quick_btns.append(b)
        place_buttons(self.quick_btns, QRectF(sx(2), sy(24), sx(252), sy(280)), 1, 0)
        self.bar = Panel("", self)
        self.bar.setGeometry(sx(8), sy(372), sx(784), sy(64))
        self.entry = SmallButton("Enter G-code command…", parent=self.bar, font_px=theme.BUTTON, checkable=False)
        self.entry.setGeometry(sx(8), sy(8), sx(380), sy(48))
        self.entry.clicked.connect(lambda: self.ctl.keyboard("Send G-code", "", self.send))
        self.refresh_btn = ActionTile(icons.refresh, "Refresh", parent=self.bar)
        self.refresh_btn.setGeometry(sx(396), sy(2), sx(190), sy(60))
        self.refresh_btn.clicked.connect(self.reload)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.reload)

    def showEvent(self, e):
        self.reload()
        self.timer.start(2000)
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def reload(self):
        self.ctl.get_json("/server/gcode_store", {"count": 100}, self._loaded, lambda: None)

    def _loaded(self, result):
        lines = []
        for entry in (result or {}).get("gcode_store", []):
            for line in str(entry.get("message", "")).splitlines():
                lines.append(("> " if entry.get("type") == "command" else "") + line)
        self.view.set_lines(lines or ["(no recent G-code activity)"])

    def send(self, script):
        script = script.strip()
        if script and self.ctl.run("console", script=script):
            QTimer.singleShot(400, self.reload)

    def set_data(self, data):
        ok = self.ctl.can("console", data)
        for b in self.quick_btns + [self.entry]:
            b.setEnabled(ok)


class LogsScreen(SubScreen):
    TITLE = "Logs"
    SUBTITLE = "View printer and service logs"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.current = None
        self.files = ListPanel("Log Files", text_row(lambda i: i), rows=8, parent=self, empty_text="No logs available")
        self.files.setGeometry(sx(8), sy(58), sx(200), sy(378))
        self.files.chosen.connect(self.open_log)
        self.view = TextView("Log Viewer", self, log_colour)
        self.view.setGeometry(sx(216), sy(58), sx(576), sy(306))
        self.auto = ToggleSwitch(self.view)
        self.auto.setGeometry(sx(510), sy(3), sx(50), sy(22))
        self.auto.setChecked(True)
        self.bar = Panel("", self)
        self.bar.setGeometry(sx(216), sy(372), sx(576), sy(64))
        self.refresh_btn = ActionTile(icons.refresh, "Refresh", "Read the latest lines", True, self.bar)
        self.refresh_btn.setGeometry(sx(2), sy(2), sx(286), sy(60))
        self.refresh_btn.clicked.connect(lambda: self.open_log(self.current))
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.auto.isChecked() and self.current and self.open_log(self.current))

    def showEvent(self, e):
        self.ctl.get_json("/server/files/list", {"root": "logs"}, self._listed, lambda: self._listed(None))
        self.timer.start(3000)
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def _listed(self, result):
        names = sorted({f["path"] for f in (result or []) if f["path"].endswith(".log")},  # current logs only
                       key=lambda n: (n != "klippy.log", n != "moonraker.log", n.lower()))
        self.files.set_items(names, self.current or (names[0] if names else None))
        if names and self.current is None:
            self.open_log(names[0])
        elif not names:
            self.view.set_lines(["(no logs available)"])

    def open_log(self, name):
        if not name:
            return
        self.current = name
        self.files.selected = name
        self.files._refresh()
        self.view.title = f"Log Viewer — {name}"
        self.ctl.get_bytes(f"/server/files/logs/{name}", self._text, lambda: self.view.set_lines(["(could not read log)"]),
                           tail=LOG_TAIL)

    def _text(self, raw):
        lines = raw.decode("utf-8", "replace").splitlines()[1:]  # first line may be cut by the tail
        self.view.set_lines(lines[-400:], follow=self.view.offset == 0)

    def set_data(self, data):
        pass


class ServicesPanel(Panel):
    def __init__(self, ctl, parent=None):
        super().__init__("Services", parent)
        self.ctl = ctl
        self.services = []
        self.btns = [SmallButton("Restart", parent=self, font_px=theme.BUTTON, checkable=False) for _ in range(5)]
        for b in self.btns:
            b.clicked.connect(lambda _=False, btn=b: self._restart(btn.service))

    def set_services(self, services, can):
        self.services = services[:5]
        rows = grid(QRectF(8, 28, self.width() - 16, self.height() - 34), max(1, len(self.btns)), 1, 2)
        for b, r, svc in zip(self.btns, rows, self.services + [None] * 5):
            b.setVisible(svc is not None)
            if svc:
                b.service = svc[0]
                b.setGeometry(int(r.right() - 88), int(r.y() + 2), 86, int(r.height() - 4))
                b.setEnabled(can)
        self.update()

    def _restart(self, name):
        self.ctl.confirm(f"Restart {name}?", f"Restarts the {name} service on the host.", "Restart",
                         lambda: self.ctl.call("service_restart", query={"service": name}))

    def paint_body(self, p):
        rows = grid(QRectF(8, 28, self.width() - 16, self.height() - 34), len(self.btns), 1, 2)
        for r, (name, state) in zip(rows, self.services):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.GREEN if state == "active" else theme.MUTED)
            p.drawEllipse(QRectF(r.x() + 4, r.center().y() - 4, 8, 8))
            p.setFont(theme.font(theme.LABEL, QFont.Weight.DemiBold))
            p.setPen(theme.FG)
            p.drawText(QRectF(r.x() + 18, r.y(), 140, r.height()), Qt.AlignmentFlag.AlignVCenter, name)
            p.setFont(theme.font(theme.BODY))
            p.setPen(theme.DIM)
            p.drawText(QRectF(r.x() + 150, r.y(), 90, r.height()), Qt.AlignmentFlag.AlignVCenter,
                       "Running" if state == "active" else state.capitalize())


class SystemScreen(SubScreen):
    TITLE = "System"
    SUBTITLE = "View system information and maintenance tools"

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.info = RowsPanel("System Info", self, label_w=120)
        self.info.setGeometry(sx(8), sy(58), sx(380), sy(292))
        self.usage = Panel("Usage", self)
        self.usage.setGeometry(sx(396), sy(58), sx(396), sy(100))
        self.usage.paint_body = self._paint_usage
        self.services = ServicesPanel(ctl, self)
        self.services.setGeometry(sx(396), sy(166), sx(396), sy(184))
        self.actions = Panel("Actions", self)
        self.actions.setGeometry(sx(8), sy(358), sx(784), sy(78))
        self.fw_btn = ActionTile(icons.refresh, "Restart Firmware", "FIRMWARE_RESTART", True, self.actions)
        self.reboot_btn = ActionTile(icons.refresh, "Restart Host", "Reboot the Pi", parent=self.actions)
        self.updates_btn = ActionTile(icons.load, "Check Updates", "Firmware & updates", parent=self.actions)
        self.off_btn = ActionTile(icons.warning, "Shutdown Host", "Power off safely", parent=self.actions)
        place_buttons([self.fw_btn, self.reboot_btn, self.updates_btn, self.off_btn], QRectF(sx(4), sy(22), sx(776), sy(52)), 4, 0)
        self.fw_btn.clicked.connect(lambda: self.ctl.confirm("Restart firmware?", "Runs FIRMWARE_RESTART: the MCUs "
                                    "restart and Klipper reloads its config.", "Restart",
                                    lambda: self.ctl.run("firmware_restart")))
        self.reboot_btn.clicked.connect(lambda: self.ctl.confirm("Restart the host?", "The Raspberry Pi reboots; "
                                        "the screen and printer services restart.", "Reboot",
                                        lambda: self.ctl.call("host_reboot")))
        self.off_btn.clicked.connect(lambda: self.ctl.confirm("Shut down the host?", "The Raspberry Pi powers off. "
                                     "It must be restarted by hand.", "Shut Down",
                                     lambda: self.ctl.call("host_shutdown")))
        self.updates_btn.clicked.connect(lambda: self.ctl.open("firmware"))
        self.sysinfo, self.proc, self.versions, self.disk = {}, {}, {}, {}
        self._data = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.ctl.get_json("/machine/proc_stats", None, self._proc, lambda: None))

    def showEvent(self, e):
        g = self.ctl.get_json
        g("/machine/system_info", None, self._sys, lambda: None)
        g("/machine/proc_stats", None, self._proc, lambda: None)
        g("/printer/info", None, lambda r: (self._ver("hostname", r.get("hostname")),
                                            self._ver("klipper", r.get("software_version"))), lambda: None)
        g("/server/info", None, lambda r: self._ver("moonraker", r.get("moonraker_version")), lambda: None)
        g("/server/files/directory", {"path": "gcodes"}, lambda r: self._disk(r.get("disk_usage")), lambda: None)
        self.timer.start(3000)
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def _sys(self, r):
        self.sysinfo = r.get("system_info", {})
        self._render()

    def _proc(self, r):
        self.proc = r
        self._render()

    def _ver(self, k, v):
        self.versions[k] = v
        self._render()

    def _disk(self, d):
        self.disk = d or {}
        self._render()

    def _render(self):
        s, p = self.sysinfo, self.proc
        up = p.get("system_uptime")
        net = s.get("network") or {}
        ip = next((a["address"] for i in net.values() for a in i.get("ip_addresses", []) if a.get("family") == "ipv4"), "-")
        self.info.set_rows([("Hostname", self.versions.get("hostname") or "-", None),
                            ("OS", (s.get("distribution") or {}).get("name") or "-", None),
                            ("Board", (s.get("cpu_info") or {}).get("model") or "-", None),
                            ("IP Address", ip, None),
                            ("Uptime", "-" if up is None else f"{int(up // 86400)}d {int(up % 86400 // 3600)}h {int(up % 3600 // 60)}m", None),
                            ("Klipper", self.versions.get("klipper") or "-", None),
                            ("Moonraker", self.versions.get("moonraker") or "-", None),
                            ("CPU Temp", "-" if p.get("cpu_temp") is None else f"{p['cpu_temp']:.0f}°C", None)])
        states = s.get("service_state") or {}
        self.services.set_services([(n, (states.get(n) or {}).get("active_state", "unknown"))
                                    for n in s.get("available_services", [])], self.ctl.can_call("service_restart"))
        self.usage.update()

    def _paint_usage(self, p):
        mem = self.proc.get("system_memory") or {}
        cpu = (self.proc.get("system_cpu_usage") or {}).get("cpu")
        rows = [("CPU", (cpu or 0) / 100, f"{cpu:.0f}%" if cpu is not None else "-", theme.GREEN),
                ("Memory", mem.get("used", 0) / mem["total"] if mem.get("total") else 0,
                 f"{mem.get('used', 0) / 1024:.0f} / {mem.get('total', 0) / 1024:.0f} MB" if mem else "-", "#2f8bff"),
                ("Storage", self.disk.get("used", 0) / self.disk["total"] if self.disk.get("total") else 0,
                 f"{self.disk.get('used', 0) / 1e9:.1f} / {self.disk.get('total', 0) / 1e9:.1f} GB" if self.disk else "-", theme.AMBER)]
        for r, (label, frac, text, colour) in zip(grid(QRectF(10, 28, self.usage.width() - 20, 66), 3, 1, 2), rows):
            p.setFont(theme.font(theme.BODY))
            p.setPen(theme.DIM)
            p.drawText(QRectF(r.x(), r.y(), 70, r.height()), Qt.AlignmentFlag.AlignVCenter, label)
            paint_bar(p, QRectF(r.x() + 70, r.center().y() - 3, 160, 6), frac, colour)
            p.setPen(theme.FG_SOFT)
            p.drawText(QRectF(r.x() + 238, r.y(), 140, r.height()), Qt.AlignmentFlag.AlignVCenter, text)

    def set_data(self, data):
        self._data = data
        self.fw_btn.setEnabled(self.ctl.can("firmware_restart", data))
        self.reboot_btn.setEnabled(self.ctl.can_call("host_reboot", data))
        self.off_btn.setEnabled(self.ctl.can_call("host_shutdown", data))
