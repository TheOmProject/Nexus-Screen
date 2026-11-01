"""Shared extruder pieces: the heat-then-move job, the nozzle temperature panel and the
status panel used by Filament and Extruder."""
from PyQt6.QtCore import QObject, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from nexus import theme
from nexus.moonraker.commands import extrude_moves, move_seconds
from nexus.screens.addon_common import Debounce, Stepper
from nexus.widgets.glow_widget import paint_panel
from nexus.widgets.panels import Panel, RowsPanel

TEMP_STEP = 5
READY_MARGIN = 5.0  # °C below target that counts as "at temperature" for loading


def nozzle(data):
    return ((data.get("heaters") or {}).get("extruder")) or data.get("nozzle") or (None, None)


class FilamentJob(QObject):
    """One extruder operation at a time. Load/unload heat first if needed (target raised,
    moves sent once the nozzle is at temperature); Stop cancels while heating. Moves
    already sent cannot be cancelled (Klipper has no abort short of an emergency stop)."""
    changed = pyqtSignal()

    def __init__(self, ctl):
        super().__init__(ctl)
        self.ctl = ctl
        self.state = "Idle"
        self.distance = 0.0
        self._pending = None  # (label, distance, speed, temp)
        self._done = QTimer(self)
        self._done.setSingleShot(True)
        self._done.timeout.connect(self._finish)

    def busy(self):
        return self.state != "Idle"

    def can_stop(self):
        return self._pending is not None

    def start(self, label, distance, speed, temp=None):
        if self.busy() or not self.ctl.can("extrude"):
            return False
        d = self.ctl._data
        cur, target = nozzle(d)
        if temp:
            if (target or 0) < temp:
                self.ctl.run("set_heater", heater="extruder", target=float(temp))
            if cur is None or cur < temp - READY_MARGIN:
                self._pending = (label, distance, speed, temp)
                self._set("Heating", distance)
                return True
        elif not (d.get("extruder") or {}).get("can_extrude"):
            return False
        return self._send(label, distance, speed)

    def _send(self, label, distance, speed):
        cfg = self.ctl._data.get("extruder_cfg") or {"max_chunk": 50.0}
        seconds = move_seconds(distance, speed)
        ok = self.ctl.run_batch([("extrude", {"moves": extrude_moves(distance, speed, cfg["max_chunk"]),
                                              "seconds": seconds})], timeout_ms=int((seconds + 30) * 1000))
        if ok:
            self._set(label, distance)
            self._done.start(int(seconds * 1000) + 500)
        return ok

    def on_data(self, data):
        if self._pending and self.state == "Heating":
            label, distance, speed, temp = self._pending
            cur, _ = nozzle(data)
            if cur is not None and cur >= temp - READY_MARGIN:
                self._pending = None
                if not self._send(label, distance, speed):
                    self._set("Idle", 0.0)

    def stop(self):
        if self._pending:
            self._pending = None
            self._set("Idle", 0.0)

    def _finish(self):
        self._set("Idle", self.distance)

    def _set(self, state, distance):
        self.state, self.distance = state, distance
        self.changed.emit()


class NozzlePanel(Panel):
    """Temperature panel (Filament / Extruder references): current, target, − value +."""

    def __init__(self, ctl, parent=None):
        super().__init__("Temperature", parent)
        self.ctl = ctl
        self.current = self.target = None
        self.pending = None
        self.limits = (0.0, 300.0)
        self.debounce = Debounce(self)
        self.stepper = Stepper(self, self._step, lambda: self.ctl.open_keypad("extruder"), font_px=theme.FIELD)

    def resizeEvent(self, e):
        self.stepper.place(8, self.height() - 48, self.width() - 16, 38, key_w=44)
        super().resizeEvent(e)

    def set_data(self, data):
        self.current, self.target = nozzle(data)
        self.limits = (data.get("limits") or {}).get("extruder", (0.0, 300.0))
        if not self.debounce.pending():
            self.pending = None
        shown = self.pending if self.pending is not None else (self.target or 0)
        self.stepper.set(f"{shown:.0f}", self.ctl.can("set_heater", data), shown > 0, shown + TEMP_STEP <= self.limits[1])
        self.update()

    def _step(self, d):
        base = self.pending if self.pending is not None else (self.target or 0)
        self.pending = max(0, min(self.limits[1], base + d * TEMP_STEP))
        self.stepper.set(f"{self.pending:.0f}", True, self.pending > 0, self.pending + TEMP_STEP <= self.limits[1])
        self.debounce(lambda t: self.ctl.run("set_heater", heater="extruder", target=float(t)), self.pending)

    def paint_body(self, p):
        w = self.width()
        box = QRectF(8, 30, w - 16, self.height() - 88)
        paint_panel(p, box, 6, top=QColor(8, 9, 11), bottom=QColor(16, 18, 21), border=QColor(52, 56, 62))
        p.setFont(theme.font(32, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(box.adjusted(0, -12, 0, -12), Qt.AlignmentFlag.AlignCenter,
                   "--" if self.current is None else f"{self.current:.0f}°C")
        p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(box.x(), box.center().y() + 14, box.width(), 18), Qt.AlignmentFlag.AlignCenter,
                   "Target: Off" if not self.target else f"Target: {self.target:.0f}°C")


class ExtruderStatus(RowsPanel):
    def __init__(self, parent=None):
        super().__init__("Status", parent, label_w=70)

    def set_data(self, data, job):
        cur, target = nozzle(data)
        ext = data.get("extruder") or {}
        fmt = lambda v: "--" if v is None else f"{v:.0f}°C"
        state_colour = theme.GREEN if job.state == "Idle" else (theme.AMBER if job.state == "Heating" else theme.RED)
        self.set_rows([("Nozzle", fmt(cur), None), ("Target", fmt(target) if target else "Off", None),
                       ("Speed", f"{ext.get('velocity', 0.0):.1f} mm/s", None),
                       ("Distance", f"{job.distance:g} mm", None), ("State", job.state, state_colour)])
