"""Nexus Screen entry point.

Simulated data by default. `--live` reads status from Moonraker; print commands
(pause/resume/cancel/baby-step) are sent only with `--live --allow-commands`.
`--capture PATH` grabs the running application's screen after `--delay` ms and exits.
"""
import argparse
import os
import subprocess
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from nexus import theme
from nexus.app import MainWindow
from nexus.config import MOONRAKER_HOST, MOONRAKER_PORT, POLL_MS


def _build_id():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        out = subprocess.run(["git", "-C", here, "describe", "--always", "--dirty"],
                             capture_output=True, text=True, timeout=3)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


REVIEWS = {
    "stop-dialog":     lambda w: w.open_stop_dialog(),
    "home":            lambda w: w.print_status.go_home.emit(),
    "keypad-nozzle":   lambda w: (w.open_keypad("extruder"), [w.keypad.press(k) for k in "215"]),
    "keypad-bed":      lambda w: (w.open_keypad("heater_bed"), [w.keypad.press(k) for k in "130"]),
    "bt-dashboard":    lambda w: w.open_addon("boxturtle"),
    "bt-controls":     lambda w: (w.open_addon("boxturtle"), w.push(w.bt_controls)),
    "sc-dashboard":    lambda w: w.open_addon("stealthchanger"),
    "sc-controls":     lambda w: (w.open_addon("stealthchanger"), w.push(w.sc_controls)),
    "temperature":     lambda w: w.push(w.temperature_screen),
    "fans":            lambda w: w.push(w.fans_screen),
    "lighting":        lambda w: w.push(w.lighting_screen),
    "move":            lambda w: w.push(w.move_screen),
    "control":         lambda w: w._on_section("control"),
    "z-offset":        lambda w: (w._on_section("control"), w.push(w.z_offset_screen)),
    "z-offset-preset": lambda w: (w._on_section("control"), w.push(w.z_offset_screen),
                                  w.z_offset_screen.preset_tiles[1].click()),
    "bed-screws":      lambda w: (w._on_section("control"), w.push(w.bed_screws_screen)),
    "bed-mesh":        lambda w: (w._on_section("control"), w.push(w.bed_mesh_screen)),
    "bed-mesh-profile": lambda w: (w._on_section("control"), w.push(w.bed_mesh_screen),
                                   w.bed_mesh_screen._preview("textured_pei")),
    "bed-mesh-default": lambda w: (w._on_section("control"), w.push(w.bed_mesh_screen),
                                   QTimer.singleShot(2500, lambda: w.bed_mesh_screen._preview("default"))),
    "filament-page":   lambda w: w._on_section("filament"),
    "filament":        lambda w: (w._on_section("filament"), w.push(w.filament_screen)),
    "filament-heating": lambda w: (w._on_section("filament"), w.push(w.filament_screen),
                                   w.filament_screen.load_btn.click()),
    "filament-material": lambda w: (w._on_section("filament"), w.push(w.filament_screen),
                                    w.filament_screen.options.material.click()),
    "profiles":        lambda w: (w._on_section("filament"), w.push(w.profiles_screen)),
    "profiles-edit":   lambda w: (w._on_section("filament"), w.push(w.profiles_screen),
                                  w.profiles_screen.settings.edit_btn.setChecked(True)),
    "profiles-keypad": lambda w: (w._on_section("filament"), w.push(w.profiles_screen),
                                  w.profiles_screen.settings.edit_btn.setChecked(True),
                                  w.profiles_screen.settings.value_btns[0].click()),
    "extruder":        lambda w: (w._on_section("control"), w.push(w.extruder_screen)),
    "extruder-pa":     lambda w: (w._on_section("control"), w.push(w.extruder_screen), w.extruder_screen.pa.click()),
    "print-page":      lambda w: w._on_section("print"),
    "settings-page":   lambda w: w._on_section("settings"),
    "complete":        lambda w: (w.complete.show_for(w._data), w._reset_to(w.complete)),
    "preview-file":    lambda w: w.open_preview("Lid_PLA_4h34m.gcode"),
    "baby-step":       lambda w: w.print_status.baby.click(),
    "print-confirm":   lambda w: (w.open_preview("Lid_PLA_4h34m.gcode"), w.preview.print_btn.click()),
    "keyboard":        lambda w: (w.open("console"), w.keyboard("Send G-code", "G28 X", lambda t: None)),
    "macro-confirm":   lambda w: (w.open("macros"), w.registry["macros"].run.click()),
    "disconnected":    lambda w: w._source.set_connected(False),
    "screen-timeout":  lambda w: (w.open("screen"), w.registry["screen"].select("timeout")),
    "zoffset-confirm": lambda w: (w.open("z_offset"), w.z_offset_screen.preset_tiles[1].click()),
    "pid-confirm":     lambda w: (w.push(w.temperature_screen), w._confirm_pid("extruder")),
    "colour-picker":   lambda w: (w.open_addon("boxturtle"), w.push(w.bt_controls),
                                  w.bt_controls.detail.colour_btn.click()),
    "material-picker": lambda w: (w.open_addon("stealthchanger"), w.push(w.sc_controls),
                                  w.sc_controls.detail.material_btn.click()),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="read status from Moonraker")
    ap.add_argument("--allow-commands", action="store_true",
                    help="with --live: enable Pause/Resume/Stop/Baby Step (off by default)")
    ap.add_argument("--host", default=MOONRAKER_HOST)
    ap.add_argument("--port", type=int, default=MOONRAKER_PORT)
    ap.add_argument("--state", default="standby", choices=["standby", "printing", "paused", "complete", "error"])
    ap.add_argument("--addons", default="both", choices=["both", "stealthchanger", "boxturtle", "none"])
    ap.add_argument("--windowed", action="store_true", help="do not go fullscreen")
    ap.add_argument("--hardware-display", action="store_true",
                    help="read the real backlight / preferences (physical screen)")
    ap.add_argument("--display-writes", action="store_true",
                    help="with --hardware-display: allow brightness changes and saving preferences")
    ap.add_argument("--capture", metavar="PNG")
    ap.add_argument("--delay", type=int, default=1500)
    ap.add_argument("--lanes", type=int, default=4, help="simulated BoxTurtle lane count")
    ap.add_argument("--sim-file", help="simulate printing this real G-code file (uses its own thumbnail)")
    ap.add_argument("--sim-kinematics", help="simulated printer kinematics (default corexy)")
    ap.add_argument("--review", type=lambda v: v if v in REVIEWS or v.startswith("open:") else ap.error(f"bad review {v}"),
                    help="review captures: open a screen or overlay directly")
    args, qt_args = ap.parse_known_args()

    if args.display_writes and not args.hardware_display:
        ap.error("--display-writes requires --hardware-display")
    app = QApplication([sys.argv[0]] + qt_args)
    # Ctrl+C / SIGTERM (dead-man timer) quit the event loop cleanly so the console is restored
    from nexus.signals import quit_on_signals
    quit_on_signals(app)
    cursor = None
    test_vt = os.environ.get("NEXUS_CONSOLE_VT")  # regression tests point this at a file
    if app.platformName() in ("linuxfb", "eglfs") or test_vt:  # physical display: keep the console cursor out
        from nexus.console import ConsoleCursor
        cursor = ConsoleCursor(test_vt)
        cursor.hide()
    app.setApplicationName("Nexus Screen")
    theme.load_fonts()

    if args.live:
        from nexus.moonraker.client import MoonrakerClient
        source = MoonrakerClient(args.host, args.port, POLL_MS, allow_commands=args.allow_commands)
    else:
        from nexus.moonraker.simulator import SimulatedSource
        source = SimulatedSource(args.state, args.addons, POLL_MS, lanes=args.lanes, sim_file=args.sim_file)
        if args.sim_kinematics:
            source._data["config"]["kinematics"] = args.sim_kinematics

    from nexus.display import Display
    win = MainWindow(source, Display(live=args.hardware_display, allow_writes=args.display_writes))
    win.move(0, 0)
    handover = None
    if args.windowed or args.capture:
        win.show()
    else:
        from nexus.splash import Handover, splash_pid
        if splash_pid():  # boot splash on screen: show the window when it has handed over
            handover = Handover(win.showFullScreen)
            source.data_updated.connect(handover.on_data)
        else:
            win.showFullScreen()
    source.start()
    if args.review:
        if args.review.startswith("open:"):
            key = args.review[5:]
            action = (lambda w: w._on_section(key)) if key in win.screens else (lambda w: w.open(key))
        else:
            action = REVIEWS[args.review]
        QTimer.singleShot(300, lambda: action(win))

    if args.capture:
        def grab():
            img = app.primaryScreen().grabWindow(0).toImage()
            img.setText("nexus-build", _build_id())
            img.setText("nexus-args", " ".join(sys.argv[1:]))
            img.setText("nexus-platform", app.platformName())
            ok = img.save(args.capture, "PNG")
            print(f"capture {'saved' if ok else 'FAILED'}: {args.capture} "
                  f"{img.width()}x{img.height()} platform={app.platformName()}", flush=True)
            app.exit(0 if ok else 1)
        QTimer.singleShot(args.delay, grab)

    try:
        return app.exec()
    finally:
        if cursor:
            cursor.restore()


if __name__ == "__main__":
    sys.exit(main())
