#!/usr/bin/env python3
"""Read-only audit of every printer operation Nexus Screen can send, against the real printer.

Uses only GET requests (gcode/help, objects/list, configfile). For each operation: the exact G-code
or Moonraker endpoint, whether this printer supports it, the state rule and whether the UI asks
for confirmation. Nothing is sent to the printer.   Usage: scripts/command_audit.py [--md]"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nexus.moonraker import commands  # noqa: E402

BASE = "http://localhost:7125"
EXAMPLES = {
    "set_heater": dict(heater="extruder", target=210), "preheat": dict(nozzle=220, bed=60),
    "pid_tune": dict(heater="extruder", target=220), "fan_part": dict(value=128),
    "fan_generic": dict(fan="filter", speed=0.5), "set_led": dict(led="rgb_light", r=1, g=0, b=0),
    "jog": dict(axis="X", distance=10, feed=6000), "home": dict(axes=""), "move_to": dict(x=86.5, y=95, feed=6000),
    "extrude": dict(moves="G1 E10 F300"), "flow_rate": dict(percent=100), "pressure_advance": dict(value=0.05),
    "z_offset_set": dict(z=-1.25, move=0), "z_offset_adjust": dict(delta=0.01, move=1), "mesh_load": dict(profile="default"),
    "lane_load": dict(lane="lane1"), "lane_unload": dict(lane="lane1"), "lane_select": dict(lane="lane1"),
    "lane_eject": dict(lane="lane1"), "lane_move": dict(lane="lane1", distance=25), "lane_color": dict(lane="lane1", color="#FF0000"),
    "lane_material": dict(lane="lane1", material="PLA"), "tool_select": dict(number=0),
    "console": dict(script="M105"), "macro": dict(name="CLEAN_NOZZLE"), "velocity_limit": dict(param="ACCEL", value=3000),
}
CONFIRMED = {"pid_tune", "save_config", "z_offset_set", "z_offset_save", "mesh_calibrate", "shaper_calibrate",
             "probe_accuracy", "macro", "firmware_restart", "print_start", "file_delete", "klipper_restart",
             "service_restart", "host_reboot", "host_shutdown"}
NOTE = {"set_heater": "keypad has its own Confirm", "z_offset_set": "presets and Reset ask first",
        "extrude": "heats first when loading; Stop cancels while heating", "console": "free text typed by the user",
        "preheat": "single tap on a preset", "home": "single tap (homing is Klipper-safe)"}


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.load(r)["result"]


def main():
    help_ = get("/printer/gcode/help")
    registered = frozenset(k.upper() for k in help_)
    supported = commands.supported(registered)
    objects = set(get("/printer/objects/list")["objects"])
    macros = sorted(o.split(" ", 1)[1] for o in objects if o.startswith("gcode_macro ") and not o.split(" ", 1)[1].startswith("_"))
    rows = []
    for key, tpl in commands.COMMANDS.items():
        try:
            example = commands.render(key, **EXAMPLES.get(key, {})).replace("\n", " ⏎ ")
        except KeyError:
            example = tpl
        rule = "idle only" if key in commands.IDLE_ONLY else ("not while printing; allowed in error" if key in commands.RECOVERY else "any state")
        rows.append((key, example, "yes" if key in supported else "NO (not registered)", rule,
                     "yes" if key in CONFIRMED else "no", NOTE.get(key, "")))
    for key, (method, path) in commands.API.items():
        rule = "idle only" if key in commands.API_IDLE else ("not while printing" if key in commands.API_NOT_PRINTING else "any state")
        if key in commands.API_RECOVERY:
            rule += "; allowed in error"
        rows.append((key, f"{method} {path}", "yes (Moonraker)", rule, "yes" if key in CONFIRMED else "no", ""))
    rows += [("pause / resume / cancel", "POST /printer/print/pause|resume|cancel", "yes (Moonraker)",
              "printing / paused", "cancel: yes", ""),
             ("baby step", "SET_GCODE_OFFSET Z_ADJUST=±step MOVE=1", "yes", "printing / paused", "no", ""),
             ("emergency stop", "POST /printer/emergency_stop", "yes (Moonraker)", "any state, never blocked",
              "-", "not bound to a control yet (needs placement approval)")]
    md = "--md" in sys.argv
    head = ("Operation", "Exact command", "This printer", "State rule", "Confirms", "Note")
    if md:
        print("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
        for r in rows:
            print("| " + " | ".join(r).replace("{", "\\{") + " |")
    else:
        for r in rows:
            print(f"{r[0]:<20} {r[2]:<22} {r[3]:<36} confirm={r[4]:<4} {r[1][:70]}")
    print(f"\n{len(supported)} of {len(commands.COMMANDS)} G-code operations supported here; "
          f"macros visible: {len(macros)} ({', '.join(macros)})")


if __name__ == "__main__":
    main()
