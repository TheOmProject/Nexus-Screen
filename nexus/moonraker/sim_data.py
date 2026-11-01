"""Canned Moonraker responses for simulation mode (shapes match the real API).
Thumbnails of the two 'real' files are read from this printer's own .thumbs folder."""
import os
import time

from nexus.moonraker import simulator

NOW = 1793232000.0  # fixed clock so captures are reproducible

FILES = {
    "": {"dirs": ["Calibration", "Models"],
         "files": [("benchy.gcode", 3_210_000, NOW - 3600, None),
                   ("Lid_PLA_4h34m.gcode", 7_402_113, NOW - 86400, "Lid_PLA_4h34m"),
                   ("[TPU] NH36Sock_PLA_1h2m.gcode", 5_824_689, NOW - 2 * 86400, "[TPU] NH36Sock_PLA_1h2m"),
                   ("mount_bracket.gcode", 2_118_400, NOW - 3 * 86400, None),
                   ("temperature_tower.gcode", 1_902_330, NOW - 6 * 86400, None),
                   ("retraction_test.gcode", 1_210_552, NOW - 9 * 86400, None)]},
    "Calibration": {"dirs": [], "files": [("calibration_cube.gcode", 900_112, NOW - 12 * 86400, None),
                                          ("flow_test.gcode", 640_220, NOW - 14 * 86400, None)]},
    "Models": {"dirs": [], "files": [("cable_clip.gcode", 410_884, NOW - 20 * 86400, None)]},
}

META = {"estimated_time": 16440, "filament_total": 24060.0, "filament_weight_total": 72.4,
        "layer_height": 0.2, "object_height": 38.6, "slicer": "OrcaSlicer", "slicer_version": "2.1.1",
        "first_layer_extr_temp": 220, "first_layer_bed_temp": 60}


def directory(path):
    d = FILES.get(path.strip("/"))
    if d is None:
        return None
    return {"dirs": [{"dirname": n, "modified": NOW - 86400, "size": 4096} for n in d["dirs"]],
            "files": [{"filename": n, "size": sz, "modified": m} for n, sz, m, _ in d["files"]],
            "disk_usage": {"total": 29_000_000_000, "used": 6_420_000_000, "free": 22_580_000_000}}


def thumb_stem(filename):
    for d in FILES.values():
        for n, _, _, stem in d["files"]:
            if n == os.path.basename(filename):
                return stem
    return None


def metadata(filename):
    stem = thumb_stem(filename)
    m = dict(META, filename=filename, size=3_210_000, modified=NOW - 3600)
    if stem:
        m["thumbnails"] = [{"width": 300, "height": 300, "relative_path": f".thumbs/{stem}-300x300.png"}]
    return m


LOG_LINES = {
    "klippy.log": ["Starting Klippy...", "Loaded MCU 'mcu' 112 commands (v0.13.0)", "Configured MCU 'mcu'",
                   "Starting heater checks for extruder", "Starting heater checks for heater_bed",
                   "beacon: model 'default' loaded", "Stats: print_time=0.000 buffer_time=0.000",
                   "Exiting SD card print (position 0)", "Klipper state: Ready"],
    "moonraker.log": ["Moonraker version: v0.9.3", "Loading Component: file_manager",
                      "Websocket opened: 127.0.0.1", "Klippy Connection Established",
                      "[WARNING] Unparsed config option 'example'", "Update Manager: Refreshed"],
    "crowsnest.log": ["crowsnest: Starting", "[ERROR] No usable camera found", "crowsnest: Stopped"],
}


def log_text(name):
    lines = LOG_LINES.get(name, ["(empty)"]) * 6
    return "\n".join(f"[19:{(i // 60) % 60:02d}:{i % 60:02d}] {l}" for i, l in enumerate(lines)).encode()


SYSTEM_INFO = {"system_info": {
    "distribution": {"name": "Debian GNU/Linux 12 (bookworm)"},
    "cpu_info": {"model": "Raspberry Pi 4 Model B Rev 1.5", "total_memory": 1710184, "cpu_count": 4},
    "network": {"wlan0": {"mac_address": "dc:a6:32:00:00:01",
                          "ip_addresses": [{"family": "ipv4", "address": "192.168.1.100"}]}},
    "available_services": ["klipper", "moonraker", "crowsnest", "KlipperScreen", "sonar"],
    "service_state": {"klipper": {"active_state": "active"}, "moonraker": {"active_state": "active"},
                      "crowsnest": {"active_state": "inactive"}, "KlipperScreen": {"active_state": "inactive"},
                      "sonar": {"active_state": "inactive"}}}}

PROC_STATS = {"system_uptime": 288000.0, "cpu_temp": 58.2,
              "system_memory": {"total": 1710184, "available": 742000, "used": 968184},
              "system_cpu_usage": {"cpu": 6.4}}

UPDATE_STATUS = {"version_info": {
    "klipper": {"version": "v0.13.0-320", "remote_version": "v0.13.0-816", "is_dirty": True},
    "moonraker": {"version": "v0.9.3-120", "remote_version": "v0.11.0-4"},
    "mainsail": {"version": "v2.14.0", "remote_version": "v2.19.0"},
    "crowsnest": {"version": "v4.1.16-1", "remote_version": "v4.2.0-1"},
    "beacon": {"version": "v2.0.0-23", "remote_version": "v2.0.0-35"}}}

WEBCAMS = {"webcams": [{"name": "Simulated camera", "service": "mjpegstreamer", "enabled": True,
                        "stream_url": "/webcam/?action=stream", "snapshot_url": "/webcam/?action=snapshot",
                        "target_fps": 15, "resolution": "1280x720"}]}

TIMELAPSE = {"enabled": True, "mode": "layermacro", "hyperlapse_cycle": 30, "output_framerate": 30,
             "camera": "Simulated camera", "autorender": True}

ENDSTOPS = {"stepper_x": "open", "stepper_y": "TRIGGERED", "stepper_z": "open"}

GCODE_STORE = [{"message": m, "time": NOW + i, "type": t} for i, (m, t) in enumerate([
    ("STATUS", "command"), ("// Klipper state: Ready", "response"), ("M105", "command"),
    ("ok T:25.0 /0.0 B:24.0 /0.0", "response"), ("M114", "command"),
    ("X:125.000 Y:125.000 Z:10.000 E:0.000", "response")])]


def thumbnail_bytes(path):
    """Serve '<dir>/.thumbs/<stem>-300x300.png' from this printer's real thumbnails."""
    name = os.path.basename(path)
    local = os.path.join(simulator.THUMBS_DIR, name)
    if os.path.exists(local):
        with open(local, "rb") as fh:
            return fh.read()
    return None
