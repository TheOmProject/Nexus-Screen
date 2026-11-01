"""Simulated printer data for visual review. Emits at the same cadence as the live client.

Commands are applied to the simulated state only — nothing is ever sent anywhere,
so no real heater, motor or add-on is touched in simulation mode.
"""
import copy
import glob
import math
import os

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from nexus.moonraker import commands, devices, profiles

_TOOL_SPECS = [("T0", "#FFFFFF", "PLA"), ("T1", "#FF2A22", "PETG"), ("T2", "#2F9BFF", "ABS"),
               ("T3", "#FFD21A", "TPU"), ("T4", "#33D14F", "PLA")]
_LANE_SPECS = [("#FF2A22", "PLA", 220), ("#2F9BFF", "PETG", 240), ("#FFD21A", "PLA", 220),
               ("#33D14F", "ABS", 250), ("#FFFFFF", "PLA", 220), ("#1A1A1A", "PC", 270),
               ("#A04BFF", "ASA", 255), ("#FF7A1A", "PETG", 240)]


def _tools():
    details = [{"name": n, "number": i, "extruder": "extruder" if i == 0 else f"extruder{i}",
                "state": "Active" if i == 0 else "Docked", "color": c, "material": m}
               for i, (n, c, m) in enumerate(_TOOL_SPECS)]
    return {"tools": [d["name"] for d in details], "active": 0, "status": "ready", "details": details}


def _lanes(count):
    lanes = []
    for i in range(count):
        colour, material, temp = _LANE_SPECS[i % len(_LANE_SPECS)]
        lanes.append({"name": str(i + 1), "id": f"lane{i + 1}", "color": colour, "loaded": True,
                      "sensor": True, "tool_loaded": i == 0, "material": material, "temp": temp,
                      "runout": "lane2" if i == 0 else None, "buffer": "Advancing"})
    return {"lanes": lanes, "current": "lane1", "error": False, "state": "Ready"}


# fake Klipper objects, parsed by the same code as live data
_DEVICE_STATUS = {
    "fan": {"speed": 0.45},
    "heater_fan hotend_fan": {"speed": 0.80},
    "fan_generic chamber_fan": {"speed": 0.30},
    "fan_generic aux_fan": {"speed": 0.0},
    "neopixel toolhead_light": {"color_data": [[0.75, 0.75, 0.75, 0.0]]},
    "neopixel chamber_light": {"color_data": [[0.50, 0.0, 0.0, 0.0]]},
    "neopixel frame_light": {"color_data": [[0.055, 0.17, 0.30, 0.0]]},
    "neopixel logo_light": {"color_data": [[0.63, 0.29, 1.0, 0.0]]},
    "toolhead": {"homed_axes": "xyz", "axis_minimum": [0, 0, -2], "axis_maximum": [250, 250, 230]},
    "gcode_move": {"gcode_position": [125.0, 125.0, 10.0, 0.0]},
}

def _mesh_points(n, amp, phase):
    return [[round(amp * math.sin((x / (n - 1)) * math.pi + phase) * math.cos((y / (n - 1)) * math.pi * 0.8), 3)
             for x in range(n)] for y in range(n)]


_MESH_STATUS = {"profile_name": "default", "mesh_min": [15.0, 15.0], "mesh_max": [235.0, 235.0],
                "profiles": {"default": {"points": _mesh_points(7, 0.14, 0.3)},
                             "textured_pei": {"points": _mesh_points(7, 0.09, 1.1)}}}
_MESH_STATUS["probed_matrix"] = _MESH_STATUS["profiles"]["default"]["points"]
_SCREW_NAMES = ["Front Left", "Front Right", "Rear Right", "Rear Left"]
_SCREW_RESULTS = {"results": {"screw1": {"z": 2.38, "sign": "CW", "adjust": "00:17", "is_base": False},
                              "screw2": {"z": 2.53, "sign": "CW", "adjust": "00:00", "is_base": True},
                              "screw3": {"z": 2.71, "sign": "CCW", "adjust": "00:14", "is_base": False},
                              "screw4": {"z": 2.44, "sign": "CW", "adjust": "00:07", "is_base": False}}}

_MACROS = [("PRINT_START", "Start print sequence", "G28\nQUAD_GANTRY_LEVEL\nBED_MESH_PROFILE LOAD=default\nPRIME"),
           ("PRINT_END", "End print sequence", "G91\nG1 Z10 F600\nG90\nTURN_OFF_HEATERS\nM107"),
           ("PAUSE", "Pause the print", "PAUSE_BASE\n_TOOLHEAD_PARK_PAUSE_CANCEL"),
           ("RESUME", "Resume the print", "RESUME_BASE"),
           ("CANCEL_PRINT", "Cancel the print", "TURN_OFF_HEATERS\nCANCEL_PRINT_BASE"),
           ("CLEAN_NOZZLE", "Clean the nozzle on the brush", "G90\nG1 X50 Y250 F6000\nG1 X80 F9000\nG1 X50 F9000"),
           ("NOZZLE_POOP", "Purge into the bucket", "G1 E20 F300"),
           ("QUAD_GANTRY_LEVEL", "Level the gantry", "_QUAD_GANTRY_LEVEL\nG28 Z"),
           ("PARK", "Park the toolhead", "G90\nG1 X125 Y240 Z50 F6000"),
           ("HEATSOAK_CHAMBER", "Heat soak the chamber", "M140 S100\nG4 P600000"),
           ("TOGGLE_FILTER", "Toggle the chamber filter", "SET_FAN_SPEED FAN=filter SPEED=1"),
           ("PRIME", "Prime line", "G1 X5 Y20 Z0.3 F6000\nG1 Y200 E15 F1500")]

_JOB = {"filename": "benchy.gcode", "progress": 0.62, "eta": "1h 28m left",
        "layer": (124, 200), "layer_height": 0.20}

SCENARIOS = {
    "standby": {
        "state": "standby", "nozzle": (25.0, 210.0), "bed": (24.0, 60.0), "chamber": (21.0, 35.0),
    },
    "printing": dict(_JOB, state="printing", nozzle=(210.0, 210.0), bed=(60.0, 60.0), chamber=(34.0, 35.0)),
    "paused": dict(_JOB, state="paused", nozzle=(208.0, 210.0), bed=(60.0, 60.0), chamber=(33.0, 35.0)),
    "complete": dict(_JOB, state="complete", progress=1.0, eta="", layer=(200, 200), nozzle=(182.0, 0.0),
                     bed=(55.0, 0.0), chamber=(33.0, 0.0)),
    "cancelled": dict(_JOB, state="cancelled", nozzle=(150.0, 0.0), bed=(50.0, 0.0), chamber=(30.0, 0.0)),
    "error": {"state": "error", "nozzle": (25.0, 0.0), "bed": (24.0, 0.0), "chamber": (21.0, 0.0),
              "message": "Extruder temperature too low\nSee the 'verify_heater' section in docs/Config_Reference.md\n"
                         "Once the underlying issue is corrected, use the \"FIRMWARE_RESTART\" command to reset "
                         "the firmware, reload the config, and restart the host software."},
}


THUMBS_DIR = os.path.expanduser("~/printer_data/gcodes/.thumbs")


def file_thumbnail(gcode_name, thumbs_dir=None):
    """Largest thumbnail Moonraker extracted for a real G-code file (read locally), or None."""
    thumbs_dir = thumbs_dir or THUMBS_DIR
    stem = os.path.splitext(os.path.basename(gcode_name))[0]
    best, best_w = None, 0
    for path in glob.glob(os.path.join(glob.escape(thumbs_dir), glob.escape(stem) + "-*x*.png")):
        try:
            w = int(path.rsplit("-", 1)[1].split("x")[0])
        except ValueError:
            continue
        if w > best_w:
            best, best_w = path, w
    if not best:
        return None
    with open(best, "rb") as fh:
        return fh.read()


def scenario(name="standby", addons="both", lanes=4, sim_file=None):
    d = {"connected": True, "message": "", "filename": "", "progress": 0.0, "eta": "",
         "layer": None, "layer_height": None, "z_offset": 0.0, "thumbnail": None,
         "thumbnail_state": "none"}
    d.update(SCENARIOS[name])
    if sim_file and name != "standby":
        d["filename"] = sim_file
        d["thumbnail"] = file_thumbnail(sim_file)
        d["thumbnail_state"] = "ready" if d["thumbnail"] else "none"
    d["stealthchanger"] = _tools() if addons in ("both", "stealthchanger") else None
    d["boxturtle"] = _lanes(lanes) if addons in ("both", "boxturtle") else None
    d["heaters"] = {"extruder": d["nozzle"], "heater_bed": d["bed"], "chamber": d["chamber"]}
    d["chamber_heater"] = "chamber"
    if d["stealthchanger"]:
        for i in range(1, len(_TOOL_SPECS)):
            d["heaters"][f"extruder{i}"] = (24.0, 0.0)
    d["limits"] = {h: (0.0, {"heater_bed": 120.0, "chamber": 75.0}.get(h, 300.0)) for h in d["heaters"]}
    status = copy.deepcopy(_DEVICE_STATUS)
    d["fans"] = devices.parse_fans(status)
    d["lights"] = devices.parse_lights(status)
    d["toolhead"] = devices.parse_toolhead(status)
    d["bed_mesh"] = devices.parse_mesh(copy.deepcopy(_MESH_STATUS))
    d["extruder"] = {"pa": 0.040, "can_extrude": d["nozzle"][0] >= 170, "velocity": 0.0, "flow": 1.0}
    d["extruder_cfg"] = {"min_extrude_temp": 170.0, "max_chunk": 50.0, "max_speed": 50.0}
    d["filament_profiles"] = profiles.defaults()
    d["macros"] = {n: {"description": desc, "gcode": code} for n, desc, code in _MACROS}
    d["config"] = {"shaper": {"type_x": "mzv", "type_y": "mzv", "freq_x": 74.8, "freq_y": 71.6},
                   "kinematics": "corexy", "homing": {"x": 250.0, "y": 250.0, "z": None}}
    d["toolhead"]["limits"] = {"max_velocity": 300.0, "max_accel": 3000.0, "square_corner_velocity": 5.0}
    d["print_stats"] = {"print_duration": 16380.0 if name in ("complete", "printing", "paused") else 0.0,
                        "total_duration": 16710.0 if name == "complete" else 0.0,
                        "filament_used": 24060.0 if name == "complete" else 0.0}
    d["screws"] = devices.parse_screws(_SCREW_NAMES, {"screws_tilt_adjust": copy.deepcopy(_SCREW_RESULTS)})
    d["operations"] = frozenset(commands.COMMANDS)
    return d


class SimulatedSource(QObject):
    data_updated = pyqtSignal(dict)
    command_failed = pyqtSignal(str, str)
    commands_enabled = True  # simulated: applied locally, never sent
    busy = False
    fail_next = None  # tests: the next operation is rejected with this message

    def __init__(self, name="standby", addons="both", poll_ms=1000, lanes=4, sim_file=None, parent=None):
        super().__init__(parent)
        self._data = scenario(name, addons, lanes, sim_file)
        self.log = []  # operations "executed" in simulation, for tests
        self._connected = True
        self._timelapse = {}
        self._console = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._snapshot = None
        self._poll_ms = poll_ms

    def start(self):
        self._emit()
        self._timer.start(self._poll_ms)

    def _emit(self):
        """Publish a fresh copy of the simulated state (call after every change)."""
        if not self._connected:
            self._snapshot = {"connected": False, "state": "offline", "message": "Simulated disconnect"}
        else:
            self._snapshot = copy.deepcopy(self._data)
        self.data_updated.emit(self._snapshot)

    def _tick(self):
        """1 Hz heartbeat like the live poll; nothing changed, so resend the last snapshot."""
        self.data_updated.emit(self._snapshot)

    def _set(self, **changes):
        self._data.update(changes)
        self._emit()

    def pause(self):
        if self._data["state"] == "printing":
            self._set(state="paused")

    def resume(self):
        if self._data["state"] == "paused":
            self._set(state="printing")

    def cancel(self):
        if self._data["state"] in ("printing", "paused"):
            self._set(state="cancelled")

    def z_adjust(self, delta):
        if self._data["state"] in ("printing", "paused"):
            self._set(z_offset=round(self._data["z_offset"] + delta, 3))

    def run(self, key, **params):
        return self.run_batch([(key, params)])

    def run_batch(self, items, timeout_ms=None):
        d = self._data
        if self.fail_next:
            msg, self.fail_next = self.fail_next, None
            what = "\n".join(commands.render(k, **p) for k, p in items)
            self.log.append("FAILED " + what)
            QTimer.singleShot(0, lambda: self.command_failed.emit(what, msg))
            return True
        if not items or not all(commands.state_allows(k, d["state"]) for k, _ in items):
            return False
        for key, params in items:
            if self._apply(key, params) is False:
                return False
        self._emit()
        return True

    def _set_target(self, heater, target):
        d = self._data
        lo, hi = d["limits"].get(heater, (0, 0))
        if not (target == 0 or lo <= target <= hi):
            return False
        cur = d["heaters"].get(heater, (25.0, 0.0))
        d["heaters"][heater] = (cur[0], target)
        if heater == "extruder" and "extruder" in d:
            d["extruder"]["can_extrude"] = cur[0] >= d["extruder_cfg"]["min_extrude_temp"]
        alias = {"extruder": "nozzle", "heater_bed": "bed", "chamber": "chamber"}.get(heater)
        if alias:
            d[alias] = d["heaters"][heater]
        return True

    def _apply(self, key, params):
        d = self._data
        self.log.append(commands.render(key, **params))
        bt, sc = d.get("boxturtle"), d.get("stealthchanger")
        th = d["toolhead"]
        fan = next((f for f in d["fans"] if f["param"] == params.get("fan")), None)
        light = next((l for l in d["lights"] if l["led"] == params.get("led")), None)
        lane = next((l for l in (bt or {}).get("lanes", []) if l["id"] == params.get("lane")), None)
        if key in ("console", "macro"):
            text = params.get("script") or params.get("name")
            self._console += [{"message": text, "time": 0, "type": "command"},
                              {"message": "// (simulation: not sent to the printer)", "time": 0, "type": "response"}]
        if key == "firmware_restart" and d["state"] == "error":
            d.update(state="standby", message="")
        if key == "preheat":
            return self._set_target("extruder", params["nozzle"]) and self._set_target("heater_bed", params["bed"])
        if key == "heaters_off":
            for h in list(d["heaters"]):
                self._set_target(h, 0)
        elif key == "fan_part":
            next(f for f in d["fans"] if f["kind"] == "part")["speed"] = params["value"] / 255
        elif key == "fan_generic" and fan:
            fan["speed"] = params["speed"]
        elif key == "set_led" and light:
            light["color"] = (params["r"], params["g"], params["b"])
        elif key == "jog":
            i = "XYZ".index(params["axis"])
            th["pos"][i] = min(th["max"][i], max(th["min"][i], th["pos"][i] + params["distance"]))
        elif key == "home":
            axes = params["axes"].strip().lower() or "xyz"
            for a in axes:
                th["pos"]["xyz".index(a)] = 0.0
            th["homed"] = "".join(a for a in "xyz" if a in th["homed"] + axes)
        elif key == "move_to":
            th["pos"][0], th["pos"][1] = params["x"], params["y"]
        elif key == "flow_rate":
            d["extruder"]["flow"] = params["percent"] / 100
        elif key == "pressure_advance":
            d["extruder"]["pa"] = params["value"]
        elif key == "z_offset_set":
            d["z_offset"] = round(params["z"], 3)
        elif key == "z_offset_adjust":
            d["z_offset"] = round(d["z_offset"] + params["delta"], 3)
        elif key == "screws_measure":
            d["screws"] = devices.parse_screws(_SCREW_NAMES, {"screws_tilt_adjust": copy.deepcopy(_SCREW_RESULTS)})
        elif key in ("mesh_calibrate", "mesh_load"):
            mesh = d["bed_mesh"]
            mesh["active"] = params.get("profile", "default")
            mesh["matrix"] = copy.deepcopy(mesh["profiles"][mesh["active"]])
        elif key == "mesh_clear":
            d["bed_mesh"].update(active="", matrix=None)
        elif key == "set_heater":
            return self._set_target(params["heater"], params["target"])
        elif key in ("lane_load", "lane_select") and lane:
            for l in bt["lanes"]:
                l["tool_loaded"] = l is lane
            bt["current"] = lane["id"]
        elif key == "lane_unload" and lane:
            lane["tool_loaded"] = False
            bt["current"] = None
        elif key == "lane_eject" and lane:
            lane.update(loaded=False, sensor=False, tool_loaded=False)
            if bt["current"] == lane["id"]:
                bt["current"] = None
        elif key == "lane_color" and lane:
            lane["color"] = params["color"]
        elif key == "lane_material" and lane:
            lane.update(material=params["material"], temp=None)  # temp now follows the material
        elif key == "tool_select" and sc:
            sc["active"] = params["number"]
            for t in sc["details"]:
                t["state"] = "Active" if t["number"] == params["number"] else "Docked"
        elif key == "tool_park" and sc:
            sc["active"] = None
            for t in sc["details"]:
                t["state"] = "Docked"
        return True

    def set_tool_meta(self, tool, color=None, material=None):
        for t in (self._data.get("stealthchanger") or {}).get("details", []):
            if t["name"] == tool:
                if color:
                    t["color"] = color
                if material:
                    t["material"] = material
        self._emit()
        return True

    def refresh(self):
        self._emit()

    # ── read-only API (canned) ───────────────────────────────────────────────
    def get_json(self, path, query, callback, on_error=None):
        from nexus.moonraker import sim_data as sd
        q = query or {}
        handlers = {
            "/server/files/directory": lambda: sd.directory(str(q.get("path", "gcodes"))[len("gcodes"):]),
            "/server/files/metadata": lambda: sd.metadata(q.get("filename", "")),
            "/server/files/list": lambda: [{"path": n, "size": 4096, "modified": sd.NOW} for n in sd.LOG_LINES],
            "/machine/system_info": lambda: sd.SYSTEM_INFO,
            "/machine/proc_stats": lambda: sd.PROC_STATS,
            "/printer/info": lambda: {"software_version": "v0.13.0-320-gc80324946", "hostname": "micron",
                                      "state": "ready"},
            "/server/info": lambda: {"moonraker_version": "v0.9.3-120-g5836eab"},
            "/machine/update/status": lambda: sd.UPDATE_STATUS,
            "/server/webcams/list": lambda: sd.WEBCAMS,
            "/machine/timelapse/settings": lambda: dict(sd.TIMELAPSE, **self._timelapse),
            "/machine/timelapse/lastframeinfo": lambda: {"count": 148, "lastframefile": "frame000148.jpg"},
            "/printer/query_endstops/status": lambda: sd.ENDSTOPS,
            "/server/gcode_store": lambda: {"gcode_store": sd.GCODE_STORE + self._console},
        }
        h = handlers.get(path)
        result = h() if h else None
        QTimer.singleShot(0, lambda: callback(result) if result is not None else (on_error and on_error()))

    def get_bytes(self, path, callback, on_error=None, tail=None):
        from nexus.moonraker import sim_data as sd
        data = None
        if path.startswith("/server/files/logs/"):
            data = sd.log_text(path.rsplit("/", 1)[1])
            data = data[-tail:] if tail else data
        elif "/.thumbs/" in path:
            data = sd.thumbnail_bytes(path)
        QTimer.singleShot(0, lambda: callback(data) if data is not None else (on_error and on_error()))

    def get_url(self, url, callback, on_error=None):
        QTimer.singleShot(0, lambda: callback(_camera_frame()))

    def call(self, key, path_params=None, query=None, body=None):
        d = self._data
        if not commands.api_allows(key, d["state"]):
            return False
        self.log.append(f"API {key} {path_params or ''}{query or ''}{body or ''}".strip())
        if key == "print_start":
            name = (query or {}).get("filename", "")
            self._data.update(state="printing", filename=name, progress=0.0, eta="",
                              thumbnail=file_thumbnail(name), layer=(1, 200))
            self._data["thumbnail_state"] = "ready" if self._data["thumbnail"] else "none"
        elif key in ("klipper_restart", "service_restart") and d["state"] == "error":
            self._data.update(state="standby", message="")
        elif key == "timelapse_settings":
            self._timelapse.update(body or {})
        self._emit()
        return True

    def local(self, kind, arg, callback):
        canned = {
            "wifi": (" :AA\\:BB\\:CC\\:00\\:00\\:01:Home_Network:81:WPA2\n"   # same SSID via 2 APs;
                     "*:AA\\:BB\\:CC\\:00\\:00\\:02:Home_Network:64:WPA2\n"   # the in-use one is not first
                     " :AA\\:BB\\:CC\\:00\\:00\\:03:Office_WiFi:64:WPA2\n"
                     " :AA\\:BB\\:CC\\:00\\:00\\:04:Guest_Network:52:WPA2\n"
                     " :AA\\:BB\\:CC\\:00\\:00\\:05::40:WPA2\n"                 # hidden SSID
                     " :AA\\:BB\\:CC\\:00\\:00\\:06:IoT_Devices:40:WPA2"),
            "devices": "wlan0:wifi:connected:Home_Network\neth0:ethernet:unavailable:\nlo:loopback:connected (externally):lo",
            "show": "GENERAL.STATE:100 (connected)\nGENERAL.HWADDR:DC\\:A6\\:32\\:00\\:00\\:01\n"
                    "IP4.ADDRESS[1]:192.168.1.100/24\nIP4.GATEWAY:192.168.1.1\nIP4.DNS[1]:192.168.1.1"}
        QTimer.singleShot(0, lambda: callback(canned[kind]))

    def emergency_stop(self):
        if not self._connected:
            return False
        self.log.append("EMERGENCY_STOP")
        self._data.update(state="error", message="Shutdown due to webhooks request")
        self._emit()
        return True

    def set_connected(self, connected):
        """Simulate Moonraker going away / coming back (tests)."""
        self._connected = connected
        self._emit()

    def request_mesh(self):
        self._emit()

    def save_profiles(self, store):
        self._data["filament_profiles"] = copy.deepcopy(store)
        self._emit()
        return True


def _camera_frame():
    """PNG test pattern standing in for a webcam snapshot in simulation (clearly labelled)."""
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter
    img = QImage(640, 360, QImage.Format.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, 360)
    g.setColorAt(0, QColor(40, 44, 50))
    g.setColorAt(1, QColor(12, 13, 15))
    p.fillRect(img.rect(), g)
    p.setPen(QColor(70, 75, 82))
    for x in range(0, 640, 40):
        p.drawLine(x, 0, x, 360)
    for y in range(0, 360, 40):
        p.drawLine(0, y, 640, y)
    p.setPen(QColor(230, 232, 235))
    f = QFont("Rajdhani")
    f.setPixelSize(34)
    f.setBold(True)
    p.setFont(f)
    p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, "SIMULATED CAMERA")
    p.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)
