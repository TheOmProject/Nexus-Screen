"""Printer operations exposed by the UI, as G-code templates.

An operation is offered only when its G-code command is registered on the
printer (checked against GET /printer/gcode/help), so commands from an add-on
that is not installed can never be sent. Klipper's core G-codes (G1, G28, M106…)
are always registered but carry no help text, so they are listed in CORE.
AFC and klipper-toolchanger names follow those projects' command references;
they are not installed on the development printer, so they are verified at
runtime on the target printer.
"""
import functools

COMMANDS = {
    # Klipper core — temperatures
    "set_heater":    "SET_HEATER_TEMPERATURE HEATER={heater} TARGET={target:g}",
    "preheat":       "SET_HEATER_TEMPERATURE HEATER=extruder TARGET={nozzle:g}\n"
                     "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={bed:g}",
    "heaters_off":   "TURN_OFF_HEATERS",
    "pid_tune":      "PID_CALIBRATE HEATER={heater} TARGET={target:g}",
    "save_config":   "SAVE_CONFIG",
    # fans and lights
    "fan_part":      "M106 S{value}",
    "fan_generic":   "SET_FAN_SPEED FAN={fan} SPEED={speed:.2f}",
    "set_led":       "SET_LED LED={led} RED={r:.3f} GREEN={g:.3f} BLUE={b:.3f}",
    # motion
    "jog":           "G91\nG1 {axis}{distance:g} F{feed}\nG90",
    "home":          "G28{axes}",
    "move_to":       "G90\nG1 X{x:g} Y{y:g} F{feed}",
    # extruder (moves built by extrude_moves(): chunks within max_extrude_only_distance)
    "extrude":         "SAVE_GCODE_STATE NAME=nexus_extrude\nM83\n{moves}\nM400\nRESTORE_GCODE_STATE NAME=nexus_extrude",
    "flow_rate":       "M221 S{percent:g}",
    "pressure_advance": "SET_PRESSURE_ADVANCE ADVANCE={value:.3f}",
    # Z offset, bed levelling, mesh
    "z_offset_set":    "SET_GCODE_OFFSET Z={z:.3f} MOVE={move}",
    "z_offset_adjust": "SET_GCODE_OFFSET Z_ADJUST={delta:+.3f} MOVE={move}",
    "z_offset_save":   "Z_OFFSET_APPLY_PROBE\nSAVE_CONFIG",
    "screws_measure":  "SCREWS_TILT_CALCULATE",
    "mesh_calibrate":  "BED_MESH_CALIBRATE",
    "mesh_load":       "BED_MESH_PROFILE LOAD={profile}",
    "mesh_clear":      "BED_MESH_CLEAR",
    # console / macros / calibration / limits / recovery
    "console":         "{script}",
    "macro":           "{name}",
    "probe_accuracy":  "PROBE_ACCURACY",
    "shaper_calibrate": "SHAPER_CALIBRATE",
    "velocity_limit":  "SET_VELOCITY_LIMIT {param}={value:g}",
    "firmware_restart": "FIRMWARE_RESTART",
    # AFC (BoxTurtle)
    "lane_load":     "TOOL_LOAD LANE={lane}",
    "lane_unload":   "TOOL_UNLOAD LANE={lane}",
    "lane_select":   "CHANGE_TOOL LANE={lane}",
    "lane_eject":    "LANE_UNLOAD LANE={lane}",
    "lane_move":     "LANE_MOVE LANE={lane} DISTANCE={distance:g}",
    "lane_color":    "SET_COLOR LANE={lane} COLOR={color}",
    "lane_material": "SET_MATERIAL LANE={lane} MATERIAL={material}",
    "afc_park":      "AFC_PARK",
    "afc_reset":     "RESET_FAILURE",
    # klipper-toolchanger (StealthChanger)
    "tool_select":   "SELECT_TOOL T={number}",
    "tool_park":     "UNSELECT_TOOL",
    "tc_initialize": "INITIALIZE_TOOLCHANGER",
}

CORE = frozenset({"G1", "G28", "G90", "G91", "M83", "M106", "M107", "M221", "M400"})

# operations that move hardware, run long procedures or restart Klipper:
# never while a print is running or paused
IDLE_ONLY = {"lane_load", "lane_unload", "lane_select", "lane_eject", "lane_move", "afc_park",
             "tool_select", "tool_park", "tc_initialize", "jog", "home", "move_to",
             "pid_tune", "save_config", "extrude", "z_offset_save", "screws_measure", "mesh_calibrate", "mesh_load",
             "mesh_clear", "probe_accuracy", "shaper_calibrate"}
RAW = {"console", "macro"}  # free-form scripts: "console" always offered, "macro" checked per name
RECOVERY = {"firmware_restart"}  # also allowed in the error state, never during a print

# Moonraker endpoints that are not G-code: key -> (method, path)
API = {
    "print_start":     ("POST", "/printer/print/start"),
    "file_delete":     ("DELETE", "/server/files/gcodes/{path}"),
    "file_move":       ("POST", "/server/files/move"),
    "klipper_restart": ("POST", "/printer/restart"),
    "service_restart": ("POST", "/machine/services/restart"),
    "host_reboot":     ("POST", "/machine/reboot"),
    "host_shutdown":   ("POST", "/machine/shutdown"),
    "update_refresh":  ("POST", "/machine/update/refresh"),
    "timelapse_render": ("POST", "/machine/timelapse/render"),
    "timelapse_settings": ("POST", "/machine/timelapse/settings"),
}
API_IDLE = {"print_start", "timelapse_render"}
API_NOT_PRINTING = {"klipper_restart", "service_restart", "host_reboot", "host_shutdown", "update_refresh",
                    "file_delete", "file_move"}
API_RECOVERY = {"klipper_restart", "service_restart", "host_reboot", "host_shutdown"}
IDLE_STATES = ("standby", "complete", "cancelled")

LANE_MOVE_MM = 25
XY_FEED = 6000
Z_FEED = 600


def extrude_moves(distance, speed, max_chunk=50.0):
    """Relative E moves for `distance` mm (negative = retract) at `speed` mm/s, each at most
    `max_chunk` mm so Klipper's max_extrude_only_distance check never rejects them."""
    sign = 1 if distance >= 0 else -1
    left, moves = abs(distance), []
    while left > 1e-9:
        step = min(left, max_chunk)
        moves.append(f"G1 E{sign * step:g} F{speed * 60:g}")
        left -= step
    return "\n".join(moves)


def move_seconds(distance, speed):
    return abs(distance) / max(speed, 0.1)


def gcode_name(key):
    return COMMANDS[key].split()[0].split("{")[0]  # "G28{axes}" -> "G28"


@functools.lru_cache(maxsize=8)  # registered is a frozenset that only changes after a Klipper restart
def supported(registered):
    """Operation keys whose G-code command exists in `registered` (upper-case names) or in CORE."""
    return frozenset(k for k in COMMANDS
                     if k in RAW or gcode_name(k) in registered or gcode_name(k) in CORE)


def render(key, **params):
    if "color" in params:
        params["color"] = params["color"].lstrip("#").upper()
    return COMMANDS[key].format(**params)


def state_allows(key, state):
    if key in RECOVERY:
        return state not in ("printing", "paused")
    if state == "error":
        return False
    return state in IDLE_STATES if key in IDLE_ONLY else True


def api_allows(key, state):
    if state == "error":
        return key in API_RECOVERY
    if key in API_IDLE:
        return state in IDLE_STATES
    if key in API_NOT_PRINTING:
        return state not in ("printing", "paused")
    return True
