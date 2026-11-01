"""Moonraker client: status polling plus guarded print commands.

Non-blocking: every request goes through QNetworkAccessManager on the Qt event
loop, so the UI thread never waits on the network.

Status is read with GET /printer/objects/list, /printer/objects/query and
/server/files/metadata. Commands (pause, resume, cancel, Z baby-step) are only
sent when the client was created with allow_commands=True, and each one is
re-checked against the last known printer state before sending.
"""
from PyQt6.QtCore import QByteArray, QObject, QProcess, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
import json
import os
import posixpath
import re
import time
from collections import OrderedDict
import sys

from nexus.moonraker import boxturtle, commands, devices, profiles, stealthchanger

BASE_OBJECTS = ["webhooks", "print_stats", "virtual_sdcard", "extruder", "heater_bed", "gcode_move", "toolhead",
                "motion_report", "idle_timeout"]
PROFILES_KEY = "filament_profiles"
MAX_BABY_STEP = 0.10
GCODE_TIMEOUT_MS = 30 * 60_000  # G-code requests return when Klipper has finished (homing, PID, mesh, macros…)
API_TIMEOUT_MS = 15_000
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "logs", "commands.jsonl")
LOG_MAX_BYTES = 1_000_000
# commands that restart Klipper/the host: a dropped connection is their expected outcome, not a failure
RESTARTING = ("SAVE_CONFIG", "FIRMWARE_RESTART", "klipper_restart", "service_restart", "host_reboot", "host_shutdown")
DISCONNECT_HINTS = re.compile(r"disconnect|closed|shutdown|restart|refused|Operation canceled|remote host", re.I)


def pct(text, safe=b""):
    return bytes(QUrl.toPercentEncoding(str(text), safe)).decode()


def api_url(base, path, query=None):
    """Moonraker URL with every query value fully percent-encoded. QUrlQuery leaves '+' as is and
    Moonraker (Tornado) reads a literal '+' as a space, so 'A+B.gcode' was requested as 'A B.gcode'."""
    url = QUrl(base + path)
    if query:
        url.setQuery("&".join(f"{pct(k)}={pct(v)}" for k, v in query.items()))
    return url


def file_url(base, path):
    """/server/files/... URL, each path segment percent-encoded ('+', spaces, '#', '?')."""
    return QUrl(base + "/".join(pct(seg) for seg in path.split("/")))


def expected_disconnect(what):
    return any(k in what for k in RESTARTING)


def moonraker_error(raw, fallback):
    """Moonraker error body {"error": {"message": ...}} -> Klipper's own text when available."""
    try:
        err = json.loads(raw).get("error")
        msg = err.get("message") if isinstance(err, dict) else err
        if msg:
            return str(msg).strip()
    except (ValueError, AttributeError):
        pass
    return fallback or "No response from Moonraker"


def log_command(what, ok, message, state, screen):
    """Append one JSON line per command to logs/commands.jsonl (no credentials are ever involved)."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX_BYTES:
            os.replace(LOG_PATH, LOG_PATH + ".1")
        with open(LOG_PATH, "a") as fh:
            fh.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "screen": screen, "command": what,
                                 "ok": ok, "error": message, "printer_state": state}) + "\n")
    except OSError as exc:
        print(f"nexus: command log: {exc}", file=sys.stderr)
THUMB_CACHE_MAX = 8
CHAMBER_CANDIDATES = ["heater_generic chamber", "temperature_fan chamber", "temperature_sensor chamber"]
DB_NAMESPACE = "nexus_screen"
TOOL_META_KEY = "toolheads"


def is_extruder(name):
    return name == "extruder" or (name.startswith("extruder") and name[8:].isdigit())


def _fmt_eta(seconds):
    if not seconds or seconds <= 0:
        return ""
    m = int(seconds // 60)
    return f"{m // 60}h {m % 60:02d}m left" if m >= 60 else f"{m}m left"


def normalise(status, chamber_obj, tool_meta=None):
    """Moonraker status dict -> the flat dict the screens consume."""
    hooks = status.get("webhooks", {})
    ps = status.get("print_stats", {})
    vsd = status.get("virtual_sdcard", {})
    ext = status.get("extruder", {})
    bed = status.get("heater_bed", {})
    state = ps.get("state", "standby")
    message = ps.get("message", "")
    if hooks.get("state") not in (None, "ready"):
        state, message = "error", hooks.get("state_message", "")
    progress = vsd.get("progress", 0.0) or 0.0
    duration = ps.get("print_duration", 0.0) or 0.0
    eta = _fmt_eta(duration / progress - duration) if progress > 0.01 else ""
    chamber = None
    heaters = {k: (v.get("temperature", 0.0), v.get("target", 0.0))
               for k, v in status.items() if is_extruder(k) or k == "heater_bed"}
    chamber_heater = None
    if chamber_obj:
        ch = status.get(chamber_obj, {})
        chamber = (ch.get("temperature", 0.0), ch.get("target"))
        if chamber_obj.startswith("heater_generic "):
            chamber_heater = devices.heater_name(chamber_obj)
            heaters[chamber_heater] = chamber
    info = ps.get("info") or {}
    layer = None
    if info.get("total_layer"):
        layer = (info.get("current_layer") or 0, info["total_layer"])
    origin = status.get("gcode_move", {}).get("homing_origin") or [0, 0, 0, 0]
    return {
        "connected": True,
        "state": state,
        "message": message,
        "filename": ps.get("filename", ""),
        "progress": progress,
        "eta": eta,
        "nozzle": (ext.get("temperature", 0.0), ext.get("target", 0.0)),
        "bed": (bed.get("temperature", 0.0), bed.get("target", 0.0)),
        "chamber": chamber,
        "layer": layer,
        "klipper_busy": (status.get("idle_timeout") or {}).get("state") == "Printing",  # commands executing
        "print_stats": {"print_duration": ps.get("print_duration", 0.0), "total_duration": ps.get("total_duration", 0.0),
                        "filament_used": ps.get("filament_used", 0.0)},
        "z_offset": origin[2],
        "heaters": heaters,
        "chamber_heater": chamber_heater,
        "fans": devices.parse_fans(status),
        "lights": devices.parse_lights(status),
        "toolhead": devices.parse_toolhead(status),
        "extruder": {"pa": ext.get("pressure_advance"), "can_extrude": bool(ext.get("can_extrude")),
                     "velocity": abs((status.get("motion_report") or {}).get("live_extruder_velocity") or 0.0),
                     "flow": status.get("gcode_move", {}).get("extrude_factor")},
        "stealthchanger": stealthchanger.parse(status, tool_meta or {}),
        "boxturtle": boxturtle.parse(status),
    }


class MoonrakerClient(QObject):
    data_updated = pyqtSignal(dict)
    command_failed = pyqtSignal(str, str)  # (command, Moonraker / Klipper message)

    def __init__(self, host="localhost", port=7125, poll_ms=1000, allow_commands=False, parent=None):
        super().__init__(parent)
        self.commands_enabled = allow_commands
        self.context = lambda: ""  # current screen name, set by the main window (for the command log)
        self.busy = False
        self._last = {}
        self._meta_for = None
        self._meta = {}
        self._registered = frozenset()
        self._limits = {}
        self._tool_meta = {}
        self._thumb_cache = OrderedDict()
        self._screw_names = None
        self._klippy_state = None
        self._config = {}
        self._extruder_cfg = {"min_extrude_temp": 170.0, "max_chunk": 50.0, "max_speed": 10.0}
        self._profiles = profiles.defaults()
        self._mesh = None
        self._mesh_profile = None
        self._base = f"http://{host}:{port}"
        self._poll_ms = poll_ms
        self._net = QNetworkAccessManager(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)
        self._query = None
        self._chamber = None
        self._status = {}
        self._backoff = 1000
        self._inflight = False
        # In-flight replies must stay referenced from Python: their finished-slot
        # closures capture the reply, and an unreachable reply<->closure cycle can
        # be freed by the cyclic GC while Qt still holds the connection (segfault).
        self._pending = set()

    def start(self):
        self._step()

    def _get(self, path, query, handler):
        req = QNetworkRequest(api_url(self._base, path, query))
        req.setTransferTimeout(2500)
        self._inflight = True
        self._track(self._net.get(req), lambda reply: self._finished(reply, handler))

    def _track(self, reply, callback):
        self._pending.add(reply)

        def done():
            self._pending.discard(reply)
            try:
                callback(reply)
            finally:
                reply.deleteLater()
        reply.finished.connect(done)

    def _finished(self, reply, handler):
        self._inflight = False
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise ConnectionError(reply.errorString())
            handler(json.loads(bytes(reply.readAll()))["result"])
            self._backoff = 1000
            self._timer.start(self._poll_ms)
        except Exception as exc:  # network down, Klippy restarting, bad payload
            self._query = None
            self.data_updated.emit({"connected": False, "state": "offline", "message": str(exc)[:80]})
            self._timer.start(self._backoff)
            self._backoff = min(self._backoff * 2, 8000)

    def _step(self):
        if self._inflight:
            return
        if self._query is None:
            self._get("/printer/objects/list", None, self._on_objects)
        else:
            self._get("/printer/objects/query", self._query, self._on_status)

    def _on_objects(self, result):
        objects = set(result.get("objects", []))
        self._chamber = next((c for c in CHAMBER_CANDIDATES if c in objects), None)
        names = [o for o in BASE_OBJECTS if o in objects or o == "webhooks"]
        names += [self._chamber] if self._chamber else []
        names += sorted(o for o in objects if is_extruder(o) and o != "extruder")
        names += devices.fan_objects(objects) + devices.light_objects(objects)
        names += ["screws_tilt_adjust"] if "screws_tilt_adjust" in objects else []
        names += ["bed_mesh=profile_name"] if "bed_mesh" in objects else []  # matrices fetched on demand
        names += stealthchanger.query_objects(objects) + boxturtle.query_objects(objects)
        self._fetch_capabilities(stealthchanger.detect(objects))
        self._query = dict(n.partition("=")[::2] for n in names)
        self._status = {}

    def _on_status(self, result):
        for name, values in result.get("status", {}).items():
            self._status.setdefault(name, {}).update(values)
        klippy = self._status.get("webhooks", {}).get("state")
        if klippy == "ready" and self._klippy_state not in (None, "ready"):
            self._query = None  # Klipper (re)started: re-read objects and configuration (kinematics, limits…)
        self._klippy_state = klippy
        data = normalise(self._status, self._chamber, self._tool_meta)
        started = data["state"] == "printing" and self._last.get("state") not in ("printing", "paused")
        if data["filename"] != self._meta_for or started:  # new file, or a new print of the same name
            self._meta_for = data["filename"]
            self._meta = {}
            if data["filename"]:
                self._fetch_metadata(data["filename"])
        if "bed_mesh" in self._status:
            profile = self._status["bed_mesh"].get("profile_name")
            if profile != self._mesh_profile:
                self._mesh_profile = profile
                self.request_mesh()
        data["bed_mesh"] = self._mesh
        data["screws"] = devices.parse_screws(self._screw_names, self._status)
        data["limits"] = self._limits
        data["extruder_cfg"] = self._extruder_cfg
        data["macros"] = self._config.get("macros", {})
        data["config"] = self._config.get("settings_summary", {})
        data["filament_profiles"] = self._profiles
        data["operations"] = commands.supported(self._registered)
        data["layer_height"] = self._meta.get("layer_height")
        data["thumbnail"] = self._meta.get("thumbnail")
        data["thumbnail_state"] = self._meta.get("thumbnail_state", "none")
        self._last = data
        self.data_updated.emit(data)

    # ── generic read-only access used by the screens ────────────────────────
    def get_json(self, path, query, callback, on_error=None):
        """GET a Moonraker endpoint; callback(result) on success, on_error() otherwise."""
        self._aux_get(api_url(self._base, path, query), lambda raw: callback(json.loads(raw)["result"]), on_error)

    def get_bytes(self, path, callback, on_error=None, tail=None):
        """GET a file; `tail` asks only for its last N bytes (large logs)."""
        self._aux_get(file_url(self._base, path), callback, on_error, tail)

    def get_url(self, url, callback, on_error=None):
        """GET an absolute URL or a host-relative one (webcam snapshots served by the web server)."""
        if not url.startswith("http"):
            url = f"http://{QUrl(self._base).host()}{url}"
        self._aux_get(QUrl(url), callback, on_error)

    # ── file metadata (read-only, best effort) ──────────────────────────────
    def _aux_get(self, url, on_bytes, on_error=None, tail=None):
        req = QNetworkRequest(url)
        req.setTransferTimeout(4000)
        if tail:
            req.setRawHeader(b"Range", f"bytes=-{int(tail)}".encode())

        def done(reply):
            if reply.error() == QNetworkReply.NetworkError.NoError:
                try:
                    on_bytes(bytes(reply.readAll()))
                except Exception as exc:
                    print(f"nexus: metadata: {exc}", file=sys.stderr)
                    if on_error:
                        on_error()
            elif on_error:
                on_error()
        self._track(self._net.get(req), done)

    def _fetch_metadata(self, filename):
        """Layer height + largest thumbnail for `filename`; thumbnails are cached by
        (path, modified, size) so revisiting a file costs one small metadata request."""
        url = api_url(self._base, "/server/files/metadata", {"filename": filename})
        self._meta["thumbnail_state"] = "loading"

        def none():
            if filename == self._meta_for:
                self._meta.update(thumbnail=None, thumbnail_state="none")

        def on_meta(raw):
            if filename != self._meta_for:
                return
            meta = json.loads(raw)["result"]
            self._meta["layer_height"] = meta.get("layer_height")
            thumbs = [t for t in meta.get("thumbnails") or [] if t.get("relative_path")]
            if not thumbs:
                return none()
            best = max(thumbs, key=lambda t: t.get("width", 0))
            path = posixpath.join(posixpath.dirname(filename), best["relative_path"])
            key = (path, meta.get("modified"), meta.get("size"))
            cached = self._thumb_cache.get(key)
            if cached is not None:
                self._thumb_cache.move_to_end(key)
                self._meta.update(thumbnail=cached, thumbnail_state="ready")
                return
            self._aux_get(file_url(self._base, "/server/files/gcodes/" + path),
                          lambda data: on_thumb(key, data), none)

        def on_thumb(key, raw):
            self._thumb_cache[key] = raw
            while len(self._thumb_cache) > THUMB_CACHE_MAX:
                self._thumb_cache.popitem(last=False)
            if filename == self._meta_for:
                self._meta.update(thumbnail=raw, thumbnail_state="ready")
        self._aux_get(url, on_meta, none)

    # ── capabilities: registered G-code, heater limits, tool metadata ───────
    def _json_get(self, path, query, on_result):
        self._aux_get(api_url(self._base, path, query), lambda raw: on_result(json.loads(raw)["result"]))

    def _fetch_capabilities(self, has_toolchanger):
        def on_help(result):
            self._registered = frozenset(k.upper() for k in result)

        def on_config(result):
            settings = result["status"]["configfile"]["settings"]
            self._screw_names = devices.screw_names(settings)
            self._config = {"macros": devices.parse_macros(settings), "settings_summary": devices.config_summary(settings)}
            ext = settings.get("extruder", {})
            self._extruder_cfg = {"min_extrude_temp": float(ext.get("min_extrude_temp", 170)),
                                  "max_chunk": float(ext.get("max_extrude_only_distance", 50)),
                                  "max_speed": float(ext.get("max_extrude_only_velocity") or 10)}
            self._limits = {devices.heater_name(name): (float(cfg.get("min_temp", 0)), float(cfg.get("max_temp", 0)))
                            for name, cfg in settings.items()
                            if is_extruder(name) or name == "heater_bed" or name.startswith("heater_generic ")}

        def on_meta(result):
            self._tool_meta = result.get("value") or {}

        def on_profiles(result):
            value = result.get("value")
            if isinstance(value, dict) and value.get("profiles"):
                self._profiles = value
        self._json_get("/printer/gcode/help", None, on_help)
        # a missing key is a 404: the built-in default profiles stay in use until a permitted save
        self._json_get("/server/database/item", {"namespace": DB_NAMESPACE, "key": PROFILES_KEY}, on_profiles)
        self._json_get("/printer/objects/query", {"configfile": "settings"}, on_config)
        if has_toolchanger:  # a missing key is a 404 and simply leaves the metadata empty
            self._json_get("/server/database/item", {"namespace": DB_NAMESPACE, "key": TOOL_META_KEY}, on_meta)

    # ── commands (only with allow_commands, re-checked against state) ───────
    def _post(self, path, payload=None, timeout_ms=None, label=None):
        self._send("POST", path, payload=payload, timeout_ms=timeout_ms, label=label)

    def _send(self, method, path, payload=None, query=None, timeout_ms=None, label=None, block=True):
        """Every write goes through here: waits for Klipper/Moonraker to finish (Moonraker answers a G-code
        request only when the command has completed), reports failures to the UI and logs each command."""
        req = QNetworkRequest(api_url(self._base, path, query))
        req.setTransferTimeout(timeout_ms or (GCODE_TIMEOUT_MS if path == "/printer/gcode/script" else API_TIMEOUT_MS))
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        what = label or (payload or {}).get("script") or f"{method} {path}"
        state = self._last.get("state")
        if block:
            self.busy = True
        body = QByteArray(json.dumps(payload or {}).encode())
        reply = self._net.deleteResource(req) if method == "DELETE" else self._net.post(req, body)

        def done(r):
            if block:
                self.busy = False
            raw = bytes(r.readAll())
            ok = r.error() == QNetworkReply.NetworkError.NoError
            message = "" if ok else moonraker_error(raw, r.errorString())
            log_command(what, ok, message, state, self.context())
            if not ok and not (expected_disconnect(what) and DISCONNECT_HINTS.search(message)):
                self.command_failed.emit(what, message)
            if not self._inflight:
                self._timer.start(0)  # refresh state right away
        self._track(reply, done)

    def _allowed(self, *states):
        return (self.commands_enabled and not self.busy and self._last.get("connected")
                and self._last.get("state") in states)

    def pause(self):
        if self._allowed("printing"):
            self._post("/printer/print/pause", label="PAUSE")

    def resume(self):
        if self._allowed("paused"):
            self._post("/printer/print/resume", label="RESUME")

    def cancel(self):
        if self._allowed("printing", "paused"):
            self._post("/printer/print/cancel", label="CANCEL")

    def z_adjust(self, delta):
        if not self._allowed("printing", "paused") or not 0 < abs(delta) <= MAX_BABY_STEP:
            return
        # while printing the nozzle follows immediately; while paused (parked)
        # the offset is applied on the next move, i.e. after resume
        move = 1 if self._last["state"] == "printing" else 0
        self._post("/printer/gcode/script", {"script": f"SET_GCODE_OFFSET Z_ADJUST={delta:+.3f} MOVE={move}"})

    def _target_ok(self, heater, target):
        lo, hi = self._limits.get(heater, (0.0, 0.0))
        return target == 0 or lo <= target <= hi

    def _valid(self, key, params):
        if key not in commands.supported(self._registered):
            return False
        if not commands.state_allows(key, self._last["state"]):
            return False
        if key in ("set_heater", "pid_tune"):
            return self._target_ok(params["heater"], params["target"]) and (key != "pid_tune" or params["target"] > 0)
        if key == "extrude":
            return 0 < params.get("seconds", 0) and "moves" in params
        if key == "console":
            return bool(str(params.get("script", "")).strip())
        if key == "macro":
            return str(params.get("name", "")).upper() in self._registered
        if key == "preheat":
            return self._target_ok("extruder", params["nozzle"]) and self._target_ok("heater_bed", params["bed"])
        return True

    def run(self, key, **params):
        """Send an operation from commands.COMMANDS if registered and allowed now."""
        return self.run_batch([(key, params)])

    def run_batch(self, items, timeout_ms=None):
        """Several operations as one script (e.g. 'All Fans Off'); all must be valid.
        Long scripts (filament load) pass a timeout covering their M400 wait.
        Per-operation state rules (incl. recovery in 'error') live in commands.state_allows."""
        if not self._allowed(*("standby", "complete", "cancelled", "printing", "paused", "error")):
            return False
        if not items or not all(self._valid(k, p) for k, p in items):
            return False
        script = "\n".join(commands.render(k, **p) for k, p in items)
        self._post("/printer/gcode/script", {"script": script}, timeout_ms)
        return True

    def save_profiles(self, store):
        """Filament profiles -> Moonraker database (only with --allow-commands)."""
        if not (self.commands_enabled and self._last.get("connected")):
            return False
        self._profiles = store
        self._post("/server/database/item", {"namespace": DB_NAMESPACE, "key": PROFILES_KEY, "value": store})
        return True

    def set_tool_meta(self, tool, color=None, material=None):
        """Toolhead colour/material live in Moonraker's database, not in printer config."""
        if not (self.commands_enabled and self._last.get("connected")):
            return False
        entry = dict(self._tool_meta.get(tool, {}))
        if color:
            entry["color"] = color
        if material:
            entry["material"] = material
        self._tool_meta = {**self._tool_meta, tool: entry}
        self._post("/server/database/item", {"namespace": DB_NAMESPACE, "key": TOOL_META_KEY,
                                             "value": self._tool_meta})
        return True

    def refresh(self):
        """Poll again right away (Refresh Status buttons)."""
        if not self._inflight:
            self._timer.start(0)

    def request_mesh(self):
        """Full bed_mesh (matrices + profiles); only on profile change or when the Bed Mesh screen asks."""
        def on_mesh(result):
            self._mesh = devices.parse_mesh(result["status"].get("bed_mesh"))
        self._json_get("/printer/objects/query", {"bed_mesh": ""}, on_mesh)

    def call(self, key, path_params=None, query=None, body=None):
        """Non-G-code Moonraker operation from commands.API (print start, file ops, restarts…)."""
        if not (self.commands_enabled and self._last.get("connected") and not self.busy):
            return False
        if not commands.api_allows(key, self._last.get("state")):
            return False
        method, path = commands.API[key]
        path = path.format(**{k: pct(v, b"/") for k, v in (path_params or {}).items()})
        self._send(method, path, payload=body, query=query, label=key)
        return True

    def emergency_stop(self):
        """Never blocked by 'busy' or printer state: only needs a connection and command mode."""
        if not (self.commands_enabled and self._last.get("connected")):
            return False
        self._send("POST", "/printer/emergency_stop", label="EMERGENCY_STOP", block=False)
        return True

    # ── local read-only queries (Network screen); only these nmcli invocations ──
    LOCAL = {"wifi": ["-t", "-f", "IN-USE,BSSID,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
             "devices": ["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev"],
             "show": ["-t", "-f", "GENERAL.STATE,GENERAL.HWADDR,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS", "dev", "show"]}

    def local(self, kind, arg, callback):
        args = list(self.LOCAL[kind]) + ([arg] if arg else [])
        proc = QProcess(self)
        self._pending.add(proc)  # keep the process (and its slot) alive until it finishes

        def done(*_):
            self._pending.discard(proc)
            callback(bytes(proc.readAllStandardOutput()).decode("utf-8", "replace"))
            proc.deleteLater()
        proc.finished.connect(done)
        proc.errorOccurred.connect(lambda *_: (self._pending.discard(proc), callback("")))
        proc.start("nmcli", args)
