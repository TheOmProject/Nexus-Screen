"""Behaviour checks for the Print Status controls. Offscreen; never touches the network
except one connection attempt to a closed localhost port (disconnection test).

    QT_QPA_PLATFORM=offscreen python3 tests/test_print_controls.py
"""
import gc
import json
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication, QEvent, QEventLoop, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from nexus import theme
from nexus.app import MainWindow
from nexus.moonraker.client import MoonrakerClient
from nexus.moonraker.simulator import SimulatedSource

app = QApplication(sys.argv)
callback_errors = []
_hook = sys.excepthook
sys.excepthook = lambda *exc: (callback_errors.append(exc[1]), _hook(*exc))  # paint/slot exceptions
theme.load_fonts()
failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def dispose(win):
    """Close AND free a test window: close() alone keeps ~12 MiB per window alive (measured)."""
    win.close()
    wait(30)  # let queued callbacks (simulated replies) reach live widgets first
    win.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    gc.collect()


def tap(w):
    QTest.mouseClick(w, Qt.MouseButton.LeftButton)
    wait(30)


# ── simulated print: navigation, pause/resume, two-step stop, baby step ─────
src = SimulatedSource("printing", "both", 60000)
win = MainWindow(src)
win.show()
src.start()
wait(50)
ps = win.print_status
check(win.stack.currentWidget() is ps, "printing opens Print Status automatically")
check(not win.sidebar.isVisible(), "sidebar hidden while printing")
check(all(b.isEnabled() for b in (ps.pause, ps.stop, ps.home, ps.baby)), "all controls enabled")

tap(ps.baby)
bs = win.baby_step
check(win.stack.currentWidget() is bs and win.back_btn.isVisible(), "Baby Step opens its submenu")
tap(bs.keys[0.01])
tap(bs.keys[0.01])
tap(bs.keys[-0.01])
check(abs(src._data["z_offset"] - 0.01) < 1e-9, "baby step +0.01 +0.01 -0.01 = 0.01")
tap(win.back_btn)
check(win.stack.currentWidget() is ps, "Back returns to Print Status")

tap(ps.pause)
check(src._data["state"] == "paused", "Pause -> paused")
check(ps.pause._label == "Resume", "button reads Resume when paused")
check(not win.sidebar.isVisible(), "sidebar hidden while paused")
tap(ps.pause)
check(src._data["state"] == "printing", "Resume -> printing")

tap(ps.stop)
check(win.stop_dialog.isVisible(), "Stop opens confirmation")
check(src._data["state"] == "printing", "first Stop tap does not cancel")
check(win.stop_dialog.geometry() == win._root.rect(), "dialog covers the whole window")
tap(win.stop_dialog.cancel_btn)
check(not win.stop_dialog.isVisible() and src._data["state"] == "printing", "Cancel keeps printing")

tap(ps.home)
check(win.stack.currentWidget() is win.home and win.sidebar.isVisible(), "Home button -> Home page with sidebar")
check(win.home.resume.isVisible(), "Home shows Return to Print during a print")
tap(win.home.resume)
check(win.stack.currentWidget() is ps, "Return to Print -> Print Status")

tap(ps.stop)
tap(win.stop_dialog.confirm_btn)
check(src._data["state"] == "cancelled", "Confirm Stop cancels")
check(win.stack.currentWidget() is win.home and win.sidebar.isVisible(), "after cancel -> Home with sidebar")
dispose(win)

# ── live client: commands are recorded, never sent ──────────────────────────
sent = []


def fake_client(allow):
    c = MoonrakerClient("127.0.0.1", 1, 60000, allow_commands=allow)
    c._post = lambda path, payload=None, *a, **kw: sent.append((path, payload))
    c._send = lambda method, path, payload=None, query=None, **kw: sent.append((path, payload))
    return c


c = fake_client(False)
c._last = {"connected": True, "state": "printing"}
c.pause(); c.cancel(); c.z_adjust(0.01)
check(sent == [], "live without --allow-commands sends nothing")

c = fake_client(True)
c._last = {"connected": True, "state": "printing"}
c.resume()
check(sent == [], "Resume refused while printing")
c.pause(); c.z_adjust(0.05); c.z_adjust(0.5)
c._last = {"connected": True, "state": "paused"}
c.resume(); c.z_adjust(-0.01); c.cancel()
c._last = {"connected": False, "state": "offline"}
c.cancel()
check(sent == [("/printer/print/pause", None),
               ("/printer/gcode/script", {"script": "SET_GCODE_OFFSET Z_ADJUST=+0.050 MOVE=1"}),
               ("/printer/print/resume", None),
               ("/printer/gcode/script", {"script": "SET_GCODE_OFFSET Z_ADJUST=-0.010 MOVE=0"}),
               ("/printer/print/cancel", None)], f"guarded command sequence {sent}")

# ── disconnection: closed port, UI stays responsive, controls disabled ─────
src = MoonrakerClient("127.0.0.1", 1, 200, allow_commands=True)
win = MainWindow(src)
win.show()
win._show(win.print_status)
src.start()
wait(600)
check(win._root.topbar._state == "offline", "top bar shows Disconnected")
check(not win.print_status.pause.isEnabled() and not win.print_status.stop.isEnabled(),
      "controls disabled while disconnected")
check(win.stack.currentWidget() is win.print_status, "screen kept while disconnected")

# ── group 1: temperature keypad ──────────────────────────────────────────────
from PyQt6.QtCore import QPoint
from nexus.widgets.overlays import validate_target
from nexus.moonraker import commands

check(validate_target("215", (0, 300)) == (215.0, ""), "keypad: 215 valid for 0-300")
check(validate_target("0", (170, 300))[0] == 0.0, "keypad: 0 (off) always valid")
check(validate_target("130", (0, 120))[0] is None, "keypad: 130 rejected for bed 0-120")
check(validate_target("100", (170, 300))[0] is None, "keypad: below min_temp rejected")

src = SimulatedSource("standby", "both", 60000)
win = MainWindow(src)
win.show()
src.start()
wait(50)
kp = win.keypad
nozzle_tile = win.home.temps._tile_rect(0).center().toPoint()
QTest.mouseClick(win.home.temps, Qt.MouseButton.LeftButton, pos=nozzle_tile)
wait(30)
check(kp.isVisible() and kp._heater == "extruder", "tap Nozzle tile opens keypad")
for k in ("0", "2", "1", "5", "5", "back", ".", "5", "7"):
    kp.press(k)
check(kp._text == "21.5", f"keypad: max 3 digits, 1 decimal, no leading 0 (got {kp._text!r})")
tap(kp.cancel_btn)
check(not kp.isVisible() and src.log == [], "Cancel closes keypad, nothing applied")
QTest.mouseClick(win.home.temps, Qt.MouseButton.LeftButton, pos=nozzle_tile)
for k in "215":
    kp.press(k)
tap(kp.confirm_btn)
check(src.log[-1] == "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=215", f"Confirm sets nozzle target ({src.log[-1:]})")
check(src._data["nozzle"][1] == 215, "simulated target updated (no real heater)")
bed_tile = win.home.temps._tile_rect(1).center().toPoint()
QTest.mouseClick(win.home.temps, Qt.MouseButton.LeftButton, pos=bed_tile)
for k in "130":
    kp.press(k)
check(kp._heater == "heater_bed" and not kp.confirm_btn.isEnabled(), "bed 130 > max 120: Confirm disabled")
tap(kp.cancel_btn)
chamber_tile = win.home.temps._tile_rect(2).center().toPoint()
QTest.mouseClick(win.home.temps, Qt.MouseButton.LeftButton, pos=chamber_tile)
check(not kp.isVisible(), "chamber tile does not open the keypad")

# ── group 1: add-on navigation and operations (simulation) ──────────────────
addons = win.home.addons
QTest.mouseClick(addons, Qt.MouseButton.LeftButton, pos=QPoint(60, addons.height() - 30))
wait(30)
check(win.stack.currentWidget() is win.sc_dashboard, "Add-Ons left section opens StealthChanger")
check(not win.sidebar.isVisible() and win.back_btn.isVisible(), "submenu: no sidebar, Back shown")
tap(win.back_btn)
check(win.stack.currentWidget() is win.home and win.sidebar.isVisible(), "Back returns to Home")
QTest.mouseClick(addons, Qt.MouseButton.LeftButton, pos=QPoint(addons.width() - 40, addons.height() - 30))
wait(30)
check(win.stack.currentWidget() is win.bt_dashboard, "Add-Ons right section opens BoxTurtle")
check(not win.bt_dashboard.load.isEnabled() and win.bt_dashboard.unload.isEnabled(),
      "dashboard: lane already in toolhead -> Load off, Unload on")
tap(win.bt_dashboard.manage_btn)
btc = win.bt_controls
check(win.stack.currentWidget() is btc, "Manage opens BoxTurtle Controls")
check(sum(b.isVisible() for b in btc.lane_buttons) == 4, "4 lane buttons for 4 lanes")
tap(btc.unload)
check(src.log[-1] == "TOOL_UNLOAD LANE=lane1", f"Unload lane 1 ({src.log[-1]})")
tap(btc.lane_buttons[2])
tap(btc.change)
check(src.log[-1] == "CHANGE_TOOL LANE=lane3", f"Change To lane 3 ({src.log[-1]})")
tap(btc.advance)
check(src.log[-1] == "LANE_MOVE LANE=lane3 DISTANCE=25", f"Advance lane 3 ({src.log[-1]})")
tap(btc.detail.colour_btn)
check(win.colour_picker.isVisible(), "Colour opens picker")
tap(win.colour_picker.tiles["#2F9BFF"])
tap(win.colour_picker.apply_btn)
check(src.log[-1] == "SET_COLOR LANE=lane3 COLOR=2F9BFF", f"Apply colour ({src.log[-1]})")
tap(btc.detail.material_btn)
tap(win.material_picker.tiles["ASA"])
tap(win.material_picker.apply_btn)
check(src.log[-1] == "SET_MATERIAL LANE=lane3 MATERIAL=ASA", f"Apply material ({src.log[-1]})")
tap(btc.heat.plus)
tap(btc.heat.heat)
check(src.log[-1] == "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=260", f"Set & Heat ASA+5 ({src.log[-1]})")
tap(win.back_btn)
check(win.stack.currentWidget() is win.bt_dashboard, "Back: Controls -> Dashboard")
tap(win.back_btn)
QTest.mouseClick(addons, Qt.MouseButton.LeftButton, pos=QPoint(60, addons.height() - 30))
tap(win.sc_dashboard.manage_btn)
scc = win.sc_controls
check(sum(b.isVisible() for b in scc.tool_buttons) == 5, "5 tool buttons for 5 tools")
check(not scc.select_btn.isEnabled(), "Select Tool disabled for the already active tool")
check(scc.tool_buttons[0].isChecked() and not any(b.isChecked() for b in scc.tool_buttons[1:]),
      "StealthChanger: selected tool (T0) highlighted")
tap(scc.tool_buttons[2])
check(scc.tool_buttons[2].isChecked() and not scc.tool_buttons[0].isChecked(), "StealthChanger: highlight follows selection")
tap(scc.select_btn)
check(src.log[-1] == "SELECT_TOOL T=2", f"Select T2 ({src.log[-1]})")
check(scc.heat.heater == "extruder2", "Temperature panel follows the tool's extruder")
tap(scc.detail.material_btn)
tap(win.material_picker.tiles["PETG"])
tap(win.material_picker.apply_btn)
check(src._data["stealthchanger"]["details"][2]["material"] == "PETG", "tool material stored (simulation)")
tap(scc.park)
check(src.log[-1] == "UNSELECT_TOOL", f"Park Tool ({src.log[-1]})")
dispose(win)

# printing: motion operations locked, heater allowed
src = SimulatedSource("printing", "both", 60000)
win = MainWindow(src)
win.show()
src.start()
wait(50)
win.open_addon("boxturtle")
win.push(win.bt_controls)
btc = win.bt_controls
check(not any(b.isEnabled() for b in (btc.load, btc.unload, btc.change, btc.advance, btc.retract, btc.eject,
                                        btc.park)), "printing: lane motion operations disabled")
check(btc.heat.heat.isEnabled(), "printing: Set & Heat still available")
dispose(win)

# lane count is not fixed
for n, pages in ((8, False), (13, True)):
    src = SimulatedSource("standby", "boxturtle", 60000, lanes=n)
    win = MainWindow(src)
    win.show()
    src.start()
    wait(30)
    win.open_addon("boxturtle")
    shown = sum(t.isVisible() for t in win.bt_dashboard.tiles)
    check(shown == min(n, 12) and win.bt_dashboard.next.isVisible() == pages, f"{n} lanes: {shown} tiles, paging={pages}")
    dispose(win)

# ── group 1: live client gating (network replaced by a recorder) ────────────
sent.clear()
c = fake_client(True)
c._last = {"connected": True, "state": "standby"}
c._registered = frozenset({"SET_HEATER_TEMPERATURE"})
c._limits = {"extruder": (0.0, 300.0), "heater_bed": (0.0, 120.0)}
check(not c.run("lane_load", lane="lane1"), "live: AFC command refused when not registered on printer")
check(not c.run("set_heater", heater="heater_bed", target=130.0), "live: bed 130 refused (max 120)")
check(c.run("set_heater", heater="extruder", target=215.0), "live: nozzle 215 accepted")
c._registered = frozenset({"TOOL_LOAD", "SELECT_TOOL"})
c._last = {"connected": True, "state": "printing"}
check(not c.run("lane_load", lane="lane1"), "live: lane load refused while printing")
c._last = {"connected": True, "state": "standby"}
check(c.run("tool_select", number=3), "live: SELECT_TOOL allowed when registered and idle")
check(sent == [("/printer/gcode/script", {"script": "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=215"}),
               ("/printer/gcode/script", {"script": "SELECT_TOOL T=3"})], f"live: exact scripts {sent}")
c2 = fake_client(False)
c2._last = {"connected": True, "state": "standby"}
c2._registered = frozenset({"SET_HEATER_TEMPERATURE"})
check(not c2.run("set_heater", heater="extruder", target=200.0) and not c2.set_tool_meta("T0", color="#FFFFFF"),
      "live without --allow-commands: nothing sent")
sent.clear()
c.set_tool_meta("T1", material="PETG")
check(sent == [("/server/database/item", {"namespace": "nexus_screen", "key": "toolheads",
                                          "value": {"T1": {"material": "PETG"}}})], "tool metadata -> Moonraker database")

# ── print thumbnail: loading, missing, file change, cache ───────────────────
import tempfile
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QColor as _QColor, QImage
from nexus.moonraker import simulator


def png_bytes(w, h, colour):
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(_QColor(colour))
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


tmp = tempfile.mkdtemp(prefix="nexus-thumbs-")
for size in (32, 300):
    with open(os.path.join(tmp, f"[TPU] Part A_PLA_1h-{size}x{size}.png"), "wb") as fh:
        fh.write(png_bytes(size, size, "#20b0a0"))
simulator.THUMBS_DIR = tmp
raw = simulator.file_thumbnail("[TPU] Part A_PLA_1h.gcode")
check(raw is not None and QImage.fromData(raw).width() == 300, "simulator: largest real thumbnail picked (brackets ok)")
check(simulator.file_thumbnail("missing.gcode") is None, "simulator: no thumbnail -> None")

src = SimulatedSource("printing", "both", 60000, sim_file="[TPU] Part A_PLA_1h.gcode")
win = MainWindow(src)
win.show()
src.start()
wait(50)
hero = win.print_status.hero
check(hero.state == "ready" and hero._source.width() == 300, "Print Status shows the file's thumbnail")
tap(win.print_status.pause)
check(hero.state == "ready", "thumbnail stays visible when paused")
src._set(filename="other.gcode", thumbnail=None, thumbnail_state="none")
wait(30)
check(hero.state == "none", "print-file change without thumbnail -> 'No Preview Available'")
src._set(filename="[TPU] Part A_PLA_1h.gcode", thumbnail=raw, thumbnail_state="ready")
wait(30)
check(hero.state == "ready", "print-file change -> new thumbnail shown")
src._set(thumbnail=b"not a png", thumbnail_state="ready", filename="broken.gcode")
wait(30)
check(hero.state == "none", "undecodable thumbnail -> placeholder, no crash")
dispose(win)

# live client: metadata -> thumbnail pipeline with a fake network
c = MoonrakerClient("127.0.0.1", 1, 60000)
gets = []
c._aux_get = lambda url, ok, err=None: gets.append((url.toEncoded().data().decode(), ok, err))
meta_a = json.dumps({"result": {"layer_height": 0.2, "modified": 100.0, "size": 5,
                                "thumbnails": [{"width": 32, "relative_path": ".thumbs/[TPU] Part A-32x32.png"},
                                               {"width": 300, "relative_path": ".thumbs/[TPU] Part A-300x300.png"}]}}).encode()
c._meta_for = "sub/[TPU] Part A.gcode"; c._meta = {}
c._fetch_metadata("sub/[TPU] Part A.gcode")
check(c._meta["thumbnail_state"] == "loading" and len(gets) == 1, "metadata requested, state loading")
gets.pop()[1](meta_a)
url, ok, err = gets.pop()
check(url.endswith("/server/files/gcodes/sub/.thumbs/%5BTPU%5D%20Part%20A-300x300.png"), f"largest thumbnail, encoded URL ({url})")
ok(raw)
check(c._meta["thumbnail"] == raw and c._meta["thumbnail_state"] == "ready", "thumbnail loaded -> ready")
c._meta_for = "b.gcode"; c._meta = {}
c._fetch_metadata("b.gcode")
gets.pop()[1](json.dumps({"result": {"thumbnails": []}}).encode())
check(c._meta["thumbnail_state"] == "none" and not gets, "file without thumbnails -> none, no image request")
c._meta_for = "sub/[TPU] Part A.gcode"; c._meta = {}
c._fetch_metadata("sub/[TPU] Part A.gcode")
gets.pop()[1](meta_a)
check(not gets and c._meta["thumbnail"] == raw, "same file again -> served from cache, no image request")
c._meta_for = "sub/[TPU] Part A.gcode"; c._meta = {}
c._fetch_metadata("sub/[TPU] Part A.gcode")
gets.pop()[1](meta_a.replace(b'"modified": 100.0', b'"modified": 200.0'))
check(len(gets) == 1, "re-sliced file (new modified time) -> image fetched again")
gets.clear()
c._meta_for = "c.gcode"; c._meta = {}
c._fetch_metadata("c.gcode")
gets.pop()[2]()
check(c._meta["thumbnail_state"] == "none", "metadata request failure -> none (placeholder), not stuck loading")
c._meta_for = "d.gcode"; c._meta = {}
c._fetch_metadata("d.gcode")
c._meta_for = "e.gcode"
gets.pop()[1](meta_a)
check(not gets and "thumbnail" not in c._meta, "late reply for a previous file is ignored")

# ── group 2: Temperature, Fans, Lighting, Move ──────────────────────────────
from nexus.moonraker import devices


def fresh(state="standby", **kw):
    src = SimulatedSource(state, "both", 60000, **kw)
    win = MainWindow(src)
    win.show()
    src.start()
    wait(40)
    return src, win


src, win = fresh()
QTest.mouseClick(win.home.temps, Qt.MouseButton.LeftButton, pos=QPoint(win.home.temps.width() // 2, 12))
wait(30)
ts = win.temperature_screen
check(win.stack.currentWidget() is ts and win.back_btn.isVisible(), "Temperatures header opens Temperature (Back, no sidebar)")
card = ts.cards["extruder"]
for _ in range(3):
    tap(card.stepper.plus)
check(src.log == [], "heater +: debounced, nothing sent yet")
wait(750)
check(src.log == ["SET_HEATER_TEMPERATURE HEATER=extruder TARGET=225"], f"three + taps -> one command 225 ({src.log})")
tap(card.stepper.value)
check(win.keypad.isVisible() and win.keypad._heater == "extruder", "heater value opens the keypad")
tap(win.keypad.cancel_btn)
tap(ts.preset_tiles[2])
check(src.log[-1] == "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=240\nSET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=100",
      "ABS preset sets nozzle 240 / bed 100 in one script")
check(ts.preset_tiles[2].highlight and not ts.preset_tiles[0].highlight, "active preset highlighted from printer targets")
tap(ts.cool)
check(src.log[-1] == "TURN_OFF_HEATERS", "Cooldown")
tap(ts.pid)
check(win.heater_picker.isVisible(), "PID tune asks which heater")
tap(win.heater_picker.tiles["heater_bed"])
tap(win.heater_picker.apply_btn)
check(win.confirm_dialog.isVisible() and src.log[-1] == "TURN_OFF_HEATERS", "PID tune needs a second confirmation")
tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "PID_CALIBRATE HEATER=heater_bed TARGET=60", f"PID tune bed at 60 (no target -> PLA preset) ({src.log[-1]})")
tap(ts.save)
tap(win.confirm_dialog.cancel_btn)
check(src.log[-1].startswith("PID_CALIBRATE"), "Save to Config cancelled -> nothing sent")
tap(ts.save)
tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "SAVE_CONFIG", "Save to Config after confirmation")
dispose(win)

src, win = fresh("printing")
win.push(win.temperature_screen)
ts = win.temperature_screen
check(not ts.pid.isEnabled() and not ts.save.isEnabled() and ts.cool.isEnabled() and ts.cards["extruder"].stepper.plus.isEnabled(),
      "printing: PID/Save locked, heaters and Cooldown available")
dispose(win)

src, win = fresh()
src._data["chamber_heater"] = None
src._emit()
win.push(win.temperature_screen)
check(not win.temperature_screen.cards["chamber"].isVisible(), "chamber without a heater -> no chamber controls")
dispose(win)

# Fans
src, win = fresh()
win.push(win.fans_screen)
fs = win.fans_screen
cards = {c.fan["id"]: c for c in fs.cards if c.isVisible()}
check(sorted(cards) == ["fan", "fan_generic aux_fan", "fan_generic chamber_fan", "heater_fan hotend_fan"], f"fan cards from objects {sorted(cards)}")
check(not cards["heater_fan hotend_fan"].stepper.plus.isVisible(), "heater_fan is read-only (Klipper-controlled)")
tap(cards["fan"].stepper.plus)
wait(700)
check(src.log[-1] == "M106 S140", f"part fan 45%+10% -> M106 S140 ({src.log[-1]})")
tap(cards["fan_generic chamber_fan"].stepper.minus)
wait(700)
check(src.log[-1] == "SET_FAN_SPEED FAN=chamber_fan SPEED=0.20", f"generic fan 30%-10% ({src.log[-1]})")
n = len(src.log)
tap(fs.all_off)
check(src.log[n:] == ["M106 S0", "SET_FAN_SPEED FAN=aux_fan SPEED=0.00", "SET_FAN_SPEED FAN=chamber_fan SPEED=0.00"],
      f"All Fans Off covers every adjustable fan ({src.log[n:]})")
dispose(win)

# Lighting
src, win = fresh()
win.push(win.lighting_screen)
ls = win.lighting_screen
lc = {c.light["led"]: c for c in ls.cards if c.isVisible()}
check(len(lc) == 4, "4 light cards from LED objects")
tap(lc["chamber_light"].toggle)
wait(700)
check(src.log[-1] == "SET_LED LED=chamber_light RED=0.000 GREEN=0.000 BLUE=0.000", f"toggle off ({src.log[-1]})")
tap(lc["chamber_light"].toggle)
wait(700)
check(src.log[-1] == "SET_LED LED=chamber_light RED=0.500 GREEN=0.000 BLUE=0.000", f"toggle on restores colour/level ({src.log[-1]})")
tap(lc["toolhead_light"].dots[6])
wait(700)
check(src.log[-1].startswith("SET_LED LED=toolhead_light RED=0.138 GREEN=0.456 BLUE=0.750"), f"blue dot at 75% ({src.log[-1]})")
n = len(src.log)
tap(ls.preset_btns[1])
check(len(src.log) - n == 4 and all("LED=" in x for x in src.log[n:]), "Low preset applies to every light")
dispose(win)

# Move
src, win = fresh()
win.push(win.move_screen)
ms = win.move_screen
tap(ms.step_buttons[10])
c = ms.wheel.rect().center()
QTest.mouseClick(ms.wheel, Qt.MouseButton.LeftButton, pos=QPoint(c.x() + 110, c.y()))
check(src.log[-1] == "G91\nG1 X10 F6000\nG90", f"X+ jog 10 mm ({src.log[-1]!r})")
QTest.mouseClick(ms.wheel, Qt.MouseButton.LeftButton, pos=QPoint(c.x(), c.y() + 110))
check(src.log[-1] == "G91\nG1 Y-10 F6000\nG90", "Y- jog")
tap(ms.z.up)
check(src.log[-1] == "G91\nG1 Z10 F600\nG90", "Z+ jog at Z feed")
QTest.mouseClick(ms.wheel, Qt.MouseButton.LeftButton, pos=c)
check(src.log[-1] == "G28", "wheel centre homes all")
tap(ms.home_btns["Home Z"])
check(src.log[-1] == "G28 Z", "Home Z")
tap(ms.preset_btns["Front Right"])
check(src.log[-1] == "G90\nG1 X235 Y15 F6000", f"Front Right preset from axis limits ({src.log[-1]!r})")
src._data["toolhead"]["homed"] = "z"
src._emit()
n = len(src.log)
QTest.mouseClick(ms.wheel, Qt.MouseButton.LeftButton, pos=QPoint(c.x() + 110, c.y()))
check(len(src.log) == n and not ms.preset_btns["Center"].isEnabled() and ms.z.up.isEnabled(),
      "unhomed X/Y: XY jog and presets locked, Z still available")
dispose(win)
src, win = fresh("printing")
win.push(win.move_screen)
ms = win.move_screen
check(not ms.z.up.isEnabled() and not ms.home_btns["Home All"].isEnabled() and not ms.preset_btns["Center"].isEnabled(),
      "printing: all motion locked")
dispose(win)

# live parsing + gating for group 2
st = {"fan": {"speed": 0.5}, "heater_fan hotend_fan": {"speed": 1.0}, "controller_fan controller_fan": {"speed": 0.3},
      "fan_generic filter": {"speed": 0.0}, "neopixel rgb_light": {"color_data": [[0.2, 0.4, 0.0, 0.0]]}}
fans = devices.parse_fans(st)
check([(f["kind"], f["name"]) for f in fans] == [("part", "Part Cooling Fan"), ("auto", "Controller Fan"),
                                                 ("auto", "Hotend Fan"), ("generic", "Filter")], "parse fans (real objects)")
check(devices.parse_lights(st) == [{"id": "neopixel rgb_light", "name": "Rgb Light", "led": "rgb_light",
                                    "color": (0.2, 0.4, 0.0)}], "parse neopixel")
check(devices.heater_name("heater_generic chamber") == "chamber", "heater_generic -> heater name")
sent.clear()
c = fake_client(True)
c._registered = frozenset({"SET_LED", "SET_FAN_SPEED"})  # core G-codes are not in gcode/help
c._last = {"connected": True, "state": "standby"}
check(c.run("jog", axis="X", distance=1, feed=6000), "live: core G-code (G1) accepted without help entry")
check({"home", "jog", "move_to", "fan_part"} <= commands.supported(frozenset()), "core ops (incl. G28 home) always supported")
check(c.run_batch([("fan_part", {"value": 0}), ("fan_generic", {"fan": "filter", "speed": 0.0})]),
      "live: fan batch accepted")
check(sent[-1] == ("/printer/gcode/script", {"script": "M106 S0\nSET_FAN_SPEED FAN=filter SPEED=0.00"}), "live: batch is one script")
check(not c.run_batch([("fan_part", {"value": 0}), ("lane_load", {"lane": "l1"})]), "live: batch refused if any item unsupported")
c._last = {"connected": True, "state": "printing"}
check(not c.run("home", axes="") and c.run("fan_part", value=255), "live: no homing while printing; fans allowed")
# ── Control navigation + calibration group (NS-40/41/42) ────────────────────
src, win = fresh()
tap(win.sidebar.buttons["control"])
check(win.stack.currentWidget() is win.control and win.sidebar.isVisible() and not win.back_btn.isVisible(),
      "sidebar Control opens the Control main page (sidebar, no Back)")
check(win.sidebar.buttons["control"].glow > 0 or win.sidebar.buttons["control"]._anim.endValue() == 1.0,
      "Control highlighted in the sidebar")
for key in ("move", "temperature", "fans", "lighting", "z_offset", "bed_screws", "bed_mesh"):
    tap(win.control.tiles[key])
    ok = win.stack.currentWidget() is win.control_targets[key] and win.back_btn.isVisible() and not win.sidebar.isVisible()
    tap(win.back_btn)
    check(ok and win.stack.currentWidget() is win.control, f"Control -> {key} -> Back")
check(all(t.isEnabled() for t in win.control.tiles.values()), "every Control tile is enabled (all screens built)")
tap(win.control.tiles["extruder"])
check(win.stack.currentWidget() is win.extruder_screen, "Control -> Extruder")
tap(win.back_btn)
tap(win.sidebar.buttons["home"])
check(win.stack.currentWidget() is win.home, "sidebar Home returns Home")

# Z offset
win._on_section("control"); win.push(win.z_offset_screen)
zs = win.z_offset_screen
tap(zs.adjust_btns[5])
check(src.log[-1] == "SET_GCODE_OFFSET Z_ADJUST=+0.050 MOVE=0", f"+0.05 while idle, no move ({src.log[-1]})")
tap(zs.stepper.minus)
check(src.log[-1] == "SET_GCODE_OFFSET Z_ADJUST=-0.010 MOVE=0" and abs(src._data["z_offset"] - 0.04) < 1e-9, "stepper -0.01")
n = len(src.log)
tap(zs.preset_tiles[1])
check(win.confirm_dialog.isVisible() and len(src.log) == n, "absolute preset asks for confirmation first")
tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "SET_GCODE_OFFSET Z=-1.250 MOVE=0" and zs.preset_tiles[1].highlight, "preset -1.250 applied + highlighted")
tap(zs.save)
tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "Z_OFFSET_APPLY_PROBE\nSAVE_CONFIG", "Save Z Offset after confirmation")
tap(zs.reset)
check(win.confirm_dialog.isVisible() and src.log[-1] != "SET_GCODE_OFFSET Z=0.000 MOVE=0", "Reset offset asks first")
tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "SET_GCODE_OFFSET Z=0.000 MOVE=0", "Reset offset after confirmation")
dispose(win)
src, win = fresh("printing")
win.push(win.z_offset_screen)
tap(win.z_offset_screen.adjust_btns[1])
check(src.log[-1] == "SET_GCODE_OFFSET Z_ADJUST=-0.010 MOVE=1" and not win.z_offset_screen.save.isEnabled(),
      "printing: adjust moves live (MOVE=1); Save locked")
dispose(win)

# Bed screws
src, win = fresh()
win.push(win.bed_screws_screen)
bs = win.bed_screws_screen
tap(bs.start)
check(src.log[-1] == "SCREWS_TILT_CALCULATE", "Start Assist measures")
for _ in range(2):
    tap(bs.stepper.minus)
check(bs.tolerance == 0.08 and bs.screws.tolerance == 0.08, "target gap is a display tolerance (no command)")
src._data["toolhead"]["homed"] = "xy"
src._emit()
check(not bs.start.isEnabled(), "not homed -> measuring locked")
src._data["screws"] = None
src._emit()
check(bs.screws.view is None and not bs.start.isEnabled() and not bs.stepper.plus.isEnabled(),
      "no [screws_tilt_adjust] -> 'not configured', no controls")
dispose(win)

# Bed mesh
src, win = fresh()
win.push(win.bed_mesh_screen)
bm = win.bed_mesh_screen
check(bm.chart.chart._matrix == src._data["bed_mesh"]["matrix"] and bm.profile_btns[0].isChecked(),
      "loaded mesh shown, active profile highlighted")
check(not bm.load.isEnabled(), "Load needs a different saved profile selected")
tap(bm.profile_btns[1])
check(bm.view_profile == "textured_pei" and bm.load.isEnabled(), "selecting a saved profile previews it")
tap(bm.load)
check(src.log[-1] == "BED_MESH_PROFILE LOAD=textured_pei" and src._data["bed_mesh"]["active"] == "textured_pei", "Load profile")
tap(bm.clear)
check(src.log[-1] == "BED_MESH_CLEAR" and bm.chart.chart._matrix is None, "Clear -> no mesh loaded")
tap(bm.calibrate)
tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "BED_MESH_CALIBRATE", "Calibrate after confirmation")
dispose(win)

# live parsing for this group
from nexus.widgets.bed_mesh_chart import mesh_colour, mesh_stats
check(devices.screw_names({"screws_tilt_adjust": {"screw1": [1, 2], "screw1_name": "front left", "screw2": [3, 4]}})
      == ["front left", "Screw 2"], "screw names from config")
check(devices.screw_names({}) is None, "no screws_tilt_adjust -> None")
m = devices.parse_mesh({"profile_name": "", "probed_matrix": [[]], "profiles": {"default": {"points": [[0.1, -0.1]]}}})
check(m["matrix"] is None and m["profiles"] == {"default": [[0.1, -0.1]]}, "unloaded mesh: profiles kept, no matrix")
check(mesh_stats([[0.1, -0.2], [0.0, 0.05]]) == (-0.2, 0.1, 0.30000000000000004), "mesh stats")
check(mesh_colour(0.0, 0.1).name() == "#262a30" and mesh_colour(0.1, 0.1).name() == "#ff2a22", "mesh colour scale")
# ── Group 3: Filament, Filament Profiles, Extruder ──────────────────────────
from nexus.moonraker.commands import extrude_moves
check(extrude_moves(100, 5) == "G1 E50 F300\nG1 E50 F300", "100 mm load split into 50 mm moves (max_extrude_only_distance)")
check(extrude_moves(-75, 10, 50) == "G1 E-50 F600\nG1 E-25 F600", "retract chunks keep the sign")


def heat_up(src, temp=220.0):
    h = src._data["heaters"]["extruder"]
    src._data["heaters"]["extruder"] = (temp, h[1])
    src._data["nozzle"] = src._data["heaters"]["extruder"]
    src._data["extruder"]["can_extrude"] = temp >= 170
    src._emit()
    wait(20)


src, win = fresh()
tap(win.sidebar.buttons["filament"])
check(win.stack.currentWidget() is win.filament_page and win.sidebar.isVisible(), "sidebar Filament opens the Filament page")
check(win.filament_page.tiles["boxturtle"].isVisible() and win.filament_page.tiles["stealthchanger"].isVisible(),
      "Filament page lists detected add-ons")
tap(win.filament_page.tiles["filament"])
fl = win.filament_screen
check(win.stack.currentWidget() is fl and win.back_btn.isVisible(), "Filament page -> Filament (Back)")
check(not fl.extrude_btn.isEnabled() and fl.load_btn.isEnabled(), "cold nozzle: Extrude locked, Load (heats first) available")
tap(fl.load_btn)
check(src.log[-1] == "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=220" and win.filament_job.state == "Heating",
      "Load when cold: heats to the profile temperature, waits")
check(fl.stop_btn.isEnabled() and not fl.unload_btn.isEnabled(), "while heating: Stop on, other actions locked")
tap(fl.stop_btn)
check(win.filament_job.state == "Idle" and src.log[-1].startswith("SET_HEATER"), "Stop cancels the pending load, nothing moved")
tap(fl.load_btn)
heat_up(src)
check(src.log[-1].endswith("G1 E50 F300\nG1 E50 F300\nM400\nRESTORE_GCODE_STATE NAME=nexus_extrude")
      and src.log[-1].startswith("SAVE_GCODE_STATE NAME=nexus_extrude\nM83"), f"at temperature: chunked load sent ({src.log[-1]!r})")
check(win.filament_job.state == "Loading" and fl.status._rows[-1][1] == "Loading", "status shows Loading")
win.filament_job._finish()  # the move's estimated duration has elapsed
tap(fl.extrude_btn)
check("G1 E10 F300" in src.log[-1], "hot: manual extrude 10 mm")
win.filament_job._finish()
tap(fl.options.material)
tap(win.profile_picker.tiles["ABS"])
tap(win.profile_picker.apply_btn)
check(fl.material == "ABS" and "ABS" in fl.options.material._text, "material chosen from profiles")
tap(fl.options.unload.plus)
tap(fl.unload_btn)
check(src.log[-1] == "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=240", "ABS unload heats to 240 first")
heat_up(src, 240.0)
check("G1 E-50 F300\nG1 E-50 F300\nG1 E-10 F300" in src.log[-1], f"unload 110 mm retract chunks ({src.log[-1]!r})")
dispose(win)

src, win = fresh("printing")
win.push(win.filament_screen)
check(not win.filament_screen.load_btn.isEnabled() and not win.filament_screen.unload_btn.isEnabled(),
      "printing: filament moves locked")
win.push(win.extruder_screen)
ex = win.extruder_screen
check(not ex.moves.extrude.go.isEnabled() and ex.flow.isEnabled() and ex.pa.isEnabled(),
      "printing: extrude locked, flow / pressure advance tunable")
tap(ex.flow)
for k in "110":
    win.keypad.press(k)
tap(win.keypad.confirm_btn)
check(src.log[-1] == "M221 S110" and ex.flow._subtitle == "110 %", "flow rate via keypad")
tap(ex.flow)
for k in "200":
    win.keypad.press(k)
check(not win.keypad.confirm_btn.isEnabled(), "flow 200 % outside 50–150: Confirm disabled")
tap(win.keypad.cancel_btn)
tap(ex.pa)
for k in "0.0455":
    win.keypad.press(k)
check(win.keypad._text == "0.045", "PA entry: 1 integer digit, 3 decimals")
tap(win.keypad.confirm_btn)
check(src.log[-1] == "SET_PRESSURE_ADVANCE ADVANCE=0.045", "pressure advance via keypad")
dispose(win)

src, win = fresh()
heat_up(src)
win.push(win.extruder_screen)
ex = win.extruder_screen
tap(ex.moves.extrude.dist_plus)
tap(ex.moves.extrude.speed_plus)
check(ex.moves.extrude.distance == 25 and ex.moves.extrude.speed == 10, "+ cycles distance 10→25, speed 5→10")
tap(ex.moves.extrude.go)
check("G1 E25 F600" in src.log[-1], "Extrude 25 mm at 10 mm/s")
win.filament_job._finish()
tap(ex.moves.retract.go)
check("G1 E-10 F300" in src.log[-1], "Retract 10 mm at 5 mm/s")
dispose(win)

# profiles
src, win = fresh()
win.push(win.profiles_screen)
ps = win.profiles_screen
tap(ps.rows[1])
check(ps.selected == "PETG" and ps.settings.profile["nozzle"] == 230 and ps.activate.isEnabled(), "select PETG shows its settings")
tap(ps.activate)
check(src._data["filament_profiles"]["active"] == "PETG", "Set as Active")
tap(ps.add_btn)
check(ps.selected == "Custom 1" and any(p["name"] == "Custom 1" for p in src._data["filament_profiles"]["profiles"]),
      "Add Profile creates 'Custom 1' (copy of the active profile)")
ps.settings.edit_btn.setChecked(True)
tap(ps.settings.value_btns[0])
check(win.keypad.isVisible() and win.keypad._spec["title"] == "Custom 1: Nozzle Temperature", "edit opens keypad")
for k in "245":
    win.keypad.press(k)
tap(win.keypad.confirm_btn)
custom = next(p for p in src._data["filament_profiles"]["profiles"] if p["name"] == "Custom 1")
check(custom["nozzle"] == 245, "edited nozzle temperature saved")
tap(ps.duplicate)
dup = ps.selected
names = [p["name"] for p in src._data["filament_profiles"]["profiles"]]
check(dup != "Custom 1" and dup in names and len(names) == 8, f"Duplicate creates a new profile ({dup})")
tap(ps.delete)
check(win.confirm_dialog.isVisible() and len(src._data["filament_profiles"]["profiles"]) == 8, "Delete asks first")
tap(win.confirm_dialog.confirm_btn)
names = [p["name"] for p in src._data["filament_profiles"]["profiles"]]
check(dup not in names and len(names) == 7, "Delete after confirmation")
dispose(win)

from nexus.moonraker import profiles as prof
one = {"active": "PLA", "profiles": [prof.defaults()["profiles"][0]]}
check(prof.delete(one, "PLA") == one, "the last profile cannot be deleted")
st = prof.delete(prof.defaults(), "PLA")
check(st["active"] == "PETG", "deleting the active profile activates the first remaining")

sent.clear()
c = fake_client(False)
c._last = {"connected": True, "state": "standby"}
check(not c.save_profiles(prof.defaults()) and not sent, "live without --allow-commands: profiles not saved")
c = fake_client(True)
c._last = {"connected": True, "state": "standby"}
c.save_profiles(prof.defaults())
check(sent[-1][0] == "/server/database/item" and sent[-1][1]["key"] == "filament_profiles", "profiles -> Moonraker database")
c._registered = frozenset({"SAVE_GCODE_STATE"})
check(c.run_batch([("extrude", {"moves": "G1 E5 F300", "seconds": 1.0})], timeout_ms=31000), "live: extrude accepted when idle")
c._last = {"connected": True, "state": "printing"}
check(not c.run_batch([("extrude", {"moves": "G1 E5 F300", "seconds": 1.0})]), "live: extrude refused while printing")

# ── Final phase: full navigation inventory + remaining screens ──────────────
simulator.THUMBS_DIR = os.path.expanduser("~/printer_data/gcodes/.thumbs")  # undo the thumbnail test's temp dir
from PyQt6.QtWidgets import QAbstractButton


def clickable(screen):
    return [b for b in screen.findChildren(QAbstractButton) if b.isVisible() and b.isEnabled()]


src, win = fresh()
reached, paths = set(), {}
# breadth-first: from every sidebar section, tap every enabled tile/row that changes the screen
frontier = [(key, [f"sidebar:{key}"]) for key in win.sidebar.buttons]
seen_targets = set()
while frontier:
    key, path = frontier.pop(0)
    win._reset_to(win.home)
    win.sidebar.buttons[path[0].split(":")[1]].click()
    wait(10)
    ok = True
    for step in path[1:]:
        btn = next((b for b in clickable(win.stack.currentWidget()) if f"{type(b).__name__}:{getattr(b, '_title', '') or getattr(b, '_text', '')}" == step), None)
        if btn is None:
            ok = False
            break
        btn.click()
        wait(10)
        for ov in (win.confirm_dialog, win.keypad, win.keyboard_overlay):
            ov.hide()
    if not ok:
        continue
    here = win.stack.currentWidget()
    reached.add(here)
    paths.setdefault(here, path)
    if len(path) > 4:
        continue
    for b in clickable(here):
        if b is win.back_btn or type(b).__name__ not in ("ActionTile",):
            continue
        label = f"{type(b).__name__}:{getattr(b, '_title', '')}"
        b.click()
        wait(10)
        dest = win.stack.currentWidget()
        for ov in (win.confirm_dialog, win.keypad, win.keyboard_overlay, win.colour_picker, win.material_picker,
                   win.heater_picker, win.profile_picker):
            ov.hide()
        if dest is not here and dest not in seen_targets:
            seen_targets.add(dest)
            frontier.append((None, path + [label]))
        win._reset_to(win.home)
        win.sidebar.buttons[path[0].split(":")[1]].click()
        wait(5)
        for step in path[1:]:
            btn = next((x for x in clickable(win.stack.currentWidget()) if f"{type(x).__name__}:{getattr(x, '_title', '') or getattr(x, '_text', '')}" == step), None)
            if btn:
                btn.click()
                wait(5)
for sec, page in win.screens.items():
    check(page in reached, f"main section reachable: {sec}")
# screens reached through rows/cards rather than tiles
win._reset_to(win.home); win.open("print_files"); wait(30)
pf = win.print_files
row = next(i for i in pf.files.items if i[1] == "Lid_PLA_4h34m.gcode")
pf.files._pick(pf.files.items.index(row)); tap(pf.preview_btn)
reached.add(win.stack.currentWidget())
win._reset_to(win.home); win.home.addons.addon_requested.emit("boxturtle"); tap(win.bt_dashboard.manage_btn)
reached.add(win.stack.currentWidget())
win._reset_to(win.home); win.home.addons.addon_requested.emit("stealthchanger"); tap(win.sc_dashboard.manage_btn)
reached.add(win.stack.currentWidget())
missing = [k for k, w in win.registry.items() if w not in reached]
check(not missing, f"every registered screen reachable through the UI (missing: {missing})")
INVENTORY_REACHED = len(set(win.registry.values()) & reached)
dispose(win)

src, win = fresh()
src._data["stealthchanger"] = None
src._data["boxturtle"] = None
src._emit(); wait(10)
for key in ("stealthchanger", "sc_controls", "boxturtle", "bt_controls"):
    win.open(key)
    check(win.stack.currentWidget() is win.home, f"no add-on hardware: open('{key}') is refused")
check(not win.filament_page.tiles["boxturtle"].isVisible(), "no add-ons: Filament page hides them")
dispose(win)

# Print files / preview / start
src, win = fresh()
win._on_section("print")
tap(win.print_page.files_tile)
pf = win.print_files
wait(30)
names = [i[1] for i in pf.files.items]
check(names[:2] == ["Calibration", "Models"] and "benchy.gcode" in names, f"file list: folders first ({names[:4]})")
check(not pf.print_btn.isEnabled(), "Print disabled until a file is selected")
pf.files._pick(0)
wait(30)
check(pf.path == "Calibration" and pf.files.items[0][0] == "up", "open folder; '..' entry to go up")
pf.files._pick(0)
wait(30)
check(pf.path == "", "'..' returns to the root")
pf.files._pick(names.index("Lid_PLA_4h34m.gcode"))
tap(pf.preview_btn)
pv = win.preview
wait(40)
check(win.stack.currentWidget() is pv and pv.thumb.state == "ready", "Preview shows the file's real thumbnail")
check(any(r[0] == "Estimated Time" and r[1] == "4h 34m" for r in pv.details._rows), "metadata: estimated time")
tap(pv.print_btn)
check(win.confirm_dialog.isVisible() and src._data["state"] == "standby", "Start Print asks first")
tap(win.confirm_dialog.confirm_btn)
wait(30)
check(src.log[-1].startswith("API print_start") and win.stack.currentWidget() is win.print_status,
      "confirmed print -> Print Status (fullscreen)")
check(win.print_status.hero.state == "ready", "Print Status shows the started file's thumbnail")
src._set(state="complete", progress=1.0, print_stats={"print_duration": 600.0, "total_duration": 660.0,
                                                       "filament_used": 1500.0})
wait(40)
check(win.stack.currentWidget() is win.complete and not win.sidebar.isVisible(), "print finished -> Print Complete")
check(any(r[1] == "Completed Successfully" for r in win.complete.details._rows), "complete summary")
tap(win.complete.home_btn)
check(win.stack.currentWidget() is win.home, "Return to Home")
pf_n = len(src.log)
win.open("print_files"); wait(30)
pf.files._pick([i[1] for i in pf.files.items].index("benchy.gcode"))
tap(pf.delete_btn); tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "API file_delete {'path': 'benchy.gcode'}", f"Delete after confirmation ({src.log[-1]})")
tap(pf.rename_btn)
check(win.keyboard_overlay.isVisible() and win.keyboard_overlay._text == "benchy.gcode", "Rename opens the keyboard")
for _ in range(6):
    win.keyboard_overlay.press("back")
for k in "2":
    win.keyboard_overlay.press(k)
tap(win.keyboard_overlay.done_btn)
check(src.log[-1].startswith("API file_move") and "gcodes/benchy2.gcode" in src.log[-1], f"rename -> move ({src.log[-1]})")
dispose(win)

# Error detected / recovery
src, win = fresh("error")
check(win.error_dialog.isVisible() and "Extruder temperature too low" in win.error_dialog.message, "Error Detected opens")
check(win.error_dialog.restart_btn.isEnabled(), "Restart Klipper available in the error state")
tap(win.error_dialog.close_btn)
src._emit(); wait(20)
check(not win.error_dialog.isVisible(), "closed error stays closed for the same message")
win.open("system")
check(win.registry["system"].fw_btn.isEnabled() and win.registry["system"].off_btn.isEnabled(),
      "recovery actions allowed in the error state")
win._reset_to(win.home)
src._set(message="MCU 'mcu' shutdown: Timer too close")
wait(20)
check(win.error_dialog.isVisible(), "a new error message opens the dialog again")
tap(win.error_dialog.restart_btn)
check(src.log[-1] == "FIRMWARE_RESTART" and src._data["state"] == "standby" and not win.error_dialog.isVisible(),
      "Restart Klipper recovers (simulation)")
dispose(win)
src, win = fresh("error")
tap(win.error_dialog.logs_btn)
wait(40)
check(win.stack.currentWidget() is win.registry["logs"] and win.registry["logs"].current == "klippy.log",
      "View Logs opens klippy.log")
dispose(win)

# Disconnect / reconnect
src, win = fresh("printing")
check(win.print_status.pause.isEnabled(), "connected: controls enabled")
src.set_connected(False); wait(20)
check(win._root.topbar._state == "offline" and not win.print_status.pause.isEnabled()
      and win.stack.currentWidget() is win.print_status, "disconnected: shown, controls off, screen kept")
src.set_connected(True); wait(20)
check(win._root.topbar._state == "printing" and win.print_status.pause.isEnabled(), "reconnected: state and controls back")
dispose(win)

# Macros / console / webcam / timelapse / limits / system / settings
src, win = fresh()
win.open("macros")
ms = win.registry["macros"]
check(len(ms.list.items) == 12 and ms.list.pages() == 2, "12 macros, paged")
tap(ms.search)
for k in "PRINT":
    win.keyboard_overlay.press(k)
tap(win.keyboard_overlay.done_btn)
check([n for n, _ in ms.list.items] == ["PRINT_START", "PRINT_END", "CANCEL_PRINT"], "search filters macros")
ms.list._pick(1)
tap(ms.run)
tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "PRINT_END", "Run Macro after confirmation")
win.open("console"); wait(30)
co = win.registry["console"]
tap(co.quick_btns[0])
wait(450)
check(src.log[-1] == "M105" and any("simulation" in l for l in co.view.lines), "quick command sent, shown in console")
win.open("webcam"); wait(40)
wc = win.registry["webcam"]
check(wc.view.frame is not None and wc.timer.isActive(), "webcam frames while visible")
tap(wc.snap)
check(wc.frozen, "Snapshot freezes the image")
win._reset_to(win.home)
check(not wc.timer.isActive(), "webcam polling stops when hidden")
win.open("timelapse"); wait(30)
tl = win.registry["timelapse"]
tap(tl.mode_btns["hyperlapse"])
check("API timelapse_settings" in src.log[-1] and tl.cycle.plus.isEnabled(), "timelapse mode change; interval editable")
win.open("limits"); wait(30)
check(any("Triggered" in r[1] for r in win.registry["limits"].endstops._rows), "endstop states shown")
win.open("screen")
sc = win.registry["screen"]
tap(sc.tab_list.tiles[1])
tap(sc.timeout_btns[5])
check(win.display.prefs["timeout_min"] == 5 and win.blank_timer.interval() == 300_000, "screen timeout 5 min")
sc.select("brightness"); tap(sc.bright_step.minus)
check(sc.bright_val == 90, "brightness -10% (simulated, nothing written)")
win.set_screen_timeout(0)
check(not win.blank_timer.isActive(), "Never = no blanking")
win._blank()
check(win.blank.isVisible(), "blanked")
QTest.mouseClick(win._root, Qt.MouseButton.LeftButton, pos=QPoint(400, 240))
check(not win.blank.isVisible() and win.stack.currentWidget() is win.registry["screen"], "first touch only wakes")
win.open("printer")
pr = win.registry["printer"]
tap(pr.steppers["ACCEL"].plus)
check(src.log[-1] == "SET_VELOCITY_LIMIT ACCEL=3500", f"runtime accel limit ({src.log[-1]})")
pr.tab_list._pick(1)
check(win.stack.currentWidget() is win.move_screen, "Printer Settings › Movement opens Move")
win.open("network"); wait(30)
nw = win.registry["network"]
check(nw.networks.items[0][1] == "Home_Network" and any(r[1] == "192.168.1.100/24" for r in nw.conn._rows), "network info")
win.open("firmware"); wait(30)
check(any(r[1] == "Update available" for r in win.registry["firmware"].details._rows), "firmware versions")
win.open("system"); wait(30)
check(any(r[0] == "Klipper" and r[1].startswith("v0.13") for r in win.registry["system"].info._rows), "system info")
win.open("maintenance")
mt = win.registry["maintenance"]
tap(mt.tiles["Clean Nozzle"]); tap(win.confirm_dialog.confirm_btn)
check(src.log[-1] == "CLEAN_NOZZLE", "Maintenance › Clean Nozzle runs the macro after confirmation")
check(not mt.tiles["Self Test"].isEnabled() and not mt.tiles["Maintenance Wizard"].isEnabled(),
      "undefined entries disabled")
dispose(win)

# printing locks for new screens; read-only live gating of API calls
src, win = fresh("printing")
win.open("print_files"); wait(30)
pf = win.print_files
pf.files._pick([i[1] for i in pf.files.items].index("mount_bracket.gcode"))
check(not pf.print_btn.isEnabled() and not pf.delete_btn.isEnabled(), "printing: no new print, no delete")
win.open("system")
check(not win.registry["system"].reboot_btn.isEnabled() and not win.registry["system"].fw_btn.isEnabled(),
      "printing: no reboot / firmware restart")
dispose(win)
sent.clear()
c = fake_client(False)
c._last = {"connected": True, "state": "standby"}
check(not c.call("print_start", query={"filename": "x.gcode"}), "live without --allow-commands: no API calls")
c = fake_client(True)
c._last = {"connected": True, "state": "printing"}
check(not c.call("host_reboot") and not c.call("file_delete", path_params={"path": "a.gcode"}), "live: reboot/delete refused while printing")
c._last = {"connected": True, "state": "error"}
c._registered = frozenset({"FIRMWARE_RESTART"})
check(c.run("firmware_restart") and not c.run("jog", axis="X", distance=1, feed=6000), "live: error state allows recovery only")
c._registered = frozenset({"CLEAN_NOZZLE"})
c._last = {"connected": True, "state": "standby"}
check(c.run("macro", name="CLEAN_NOZZLE") and not c.run("macro", name="NOT_A_MACRO"), "live: only registered macros run")
check(not c.run("console", script="   "), "live: empty console line refused")

# ── Physical-test defect regressions ────────────────────────────────────────
import signal as _signal, subprocess as _sp, tempfile as _tf
from nexus.console import HIDE, SHOW, ConsoleCursor
from nexus.screens.settings import group_networks
from nexus.widgets.panels import ListPanel, Panel, text_row

# 1. console cursor hidden while running, restored on SIGTERM (dead-man) and Ctrl+C
for sig in (_signal.SIGTERM, _signal.SIGINT):
    vt = _tf.NamedTemporaryFile(delete=False).name
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", NEXUS_CONSOLE_VT=vt)
    proc = _sp.Popen([sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"),
                      "--windowed"], env=env, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
    time.sleep(3)
    hidden_while_running = open(vt).read() == HIDE
    proc.send_signal(sig)
    code = proc.wait(10)
    check(hidden_while_running and open(vt).read() == HIDE + SHOW and code == 0,
          f"{_signal.Signals(sig).name}: cursor hidden while running, restored on exit (exit {code})")
check(not ConsoleCursor("/nonexistent/tty").hide(), "unwritable console: no error, nothing to restore")
race = _sp.run([sys.executable, "-c", (
    "import os, signal, sys; sys.path.insert(0, %r)\n"
    "from PyQt6.QtWidgets import QApplication\n"
    "from nexus.signals import quit_on_signals\n"
    "app = QApplication([]); quit_on_signals(app)\n"
    "os.kill(os.getpid(), signal.SIGTERM)\n"
    "sys.exit(app.exec())") % os.path.dirname(os.path.dirname(os.path.abspath(__file__)))],
    env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=20, capture_output=True)
check(race.returncode == 0, "SIGTERM arriving before the event loop starts still stops the app (startup race)")

# 2. lists: loading state, rows only with data, pager only when needed, empty / failure text
lp = ListPanel("Test", text_row(lambda i: i), rows=3, empty_text="Nothing here")
lp.resize(300, 200); lp.show(); wait(10)
check(lp.message == "Loading…" and not any(t.isVisible() for t in lp.tiles) and not lp.prev.isVisible(),
      "list before data: 'Loading…', no row frames, no pager")
lp.set_items([])
check(lp.message == "Nothing here" and not any(t.isVisible() for t in lp.tiles), "empty result: empty-state text")
lp.set_items(["a", "b"])
check(lp.message == "" and sum(t.isVisible() for t in lp.tiles) == 2 and not lp.next.isVisible(), "2 items: 2 rows, no pager")
lp.set_items(list("abcdefg"))
check(lp.next.isVisible() and lp.pages() == 3, "7 items / 3 rows: pager shown")
lp.set_loading("Unavailable")
check(lp.message == "Unavailable" and not lp.next.isVisible() and not any(t.isVisible() for t in lp.tiles),
      "failure text replaces rows and pager")
lp.close(); lp.deleteLater()
src, win = fresh()
pf = win.print_files
win.open("print_files"); wait(30)
calls = []
orig_get = src.get_json
src.get_json = lambda path, q, cb, err=None: calls.append((path, q, cb, err))  # hold the reply
pf.files._pick(0)  # open 'Calibration'
check(pf.files.message == "Loading…" and not any(t.isVisible() for t in pf.files.tiles), "opening a folder shows Loading…")
path, q, cb, err = calls[-1]
cb({"dirs": [], "files": []})
check(pf.files.message == "" and pf.files.items == [("up", "", None, None)], "empty folder: only '..'")
pf.files._pick(0); err()
check(pf.files.message == "File list unavailable", "listing failure: message, no stale rows")
src.get_json = orig_get
dispose(win)

# 3. Wi-Fi: same SSID through several access points
nm = (" :AA\\:01:mugon:100:WPA2\n :AA\\:02:mugon:92:WPA2\n*:AA\\:03:mugon:63:WPA2\n :AA\\:04::65:WPA2\n"
      " :AA\\:05:Z2_2020:50:WPA2")
check(group_networks(nm) == [(True, "mugon", "100", "WPA2", 3), (False, "Z2_2020", "50", "WPA2", 1)],
      f"in-use AP later in the list keeps SSID connected ({group_networks(nm)})")
src, win = fresh()
win.open("network"); wait(40)
nw = win.registry["network"]
check(nw.networks.items[0][:2] == (True, "Home_Network") and nw.networks.selected == "Home_Network"
      and any(r == ("Network", "Home_Network", None) for r in nw.conn._rows), "Network screen: Connected SSID (2 APs)")
tap(nw.scan); wait(40)
check(nw.networks.items[0][0] and nw.networks.message == "", "Connected label kept after Refresh")
dispose(win)

# 4. no widget hides a panel title (all screens and main states)
GLOW_MARGIN = {"ActionTile": 5, "Tile": 5, "ActionButton": 7}


def title_overlaps(win):
    found = []
    screen = win.stack.currentWidget()
    widgets = [w for w in screen.findChildren(QWidget) if w.isVisible()]
    for panel in [w for w in widgets if isinstance(w, Panel) and w.title]:
        fm = QFontMetricsF(theme.font(14, QFont.Weight.DemiBold))
        text = QRectF(10, 4, fm.horizontalAdvance(panel.title), 20)
        r = QRectF(QPointF(panel.mapTo(screen, text.topLeft().toPoint())), text.size())
        for w in widgets:
            if w is panel or w.isAncestorOf(panel):  # the panel itself and what contains it
                continue
            wr = QRectF(QPointF(w.mapTo(screen, QPoint(0, 0))), QSizeF(w.width(), w.height()))
            m = GLOW_MARGIN.get(type(w).__name__, 0)  # transparent glow margin around the painted body
            wr = wr.adjusted(m, m, -m, -m)
            if wr.intersects(r):
                found.append(f"{type(screen).__name__}: '{panel.title}' covered by {type(w).__name__}")
    return found


from PyQt6.QtCore import QPointF, QRectF, QSizeF
from PyQt6.QtGui import QFont, QFontMetricsF
from PyQt6.QtWidgets import QWidget
overlaps = []
for state in ("standby", "printing"):
    src, win = fresh(state)
    for key in [k for k in win.registry] + list(win.screens):
        win._reset_to(win.home)
        (win._on_section if key in win.screens else win.open)(key)
        wait(30)
        overlaps += title_overlaps(win)
    win._reset_to(win.print_status if state == "printing" else win.home); wait(10)
    overlaps += title_overlaps(win)
    dispose(win)
check(not overlaps, f"no panel title covered by a widget ({sorted(set(overlaps))[:6]})")

# ── Touchscreen usability: Back button size, NEXUS SCREEN branding ─────────
import re as _re
from nexus.app import BACK_W, FULL_TOPBAR_H
src, win = fresh()
bb = win.back_btn
check(bb.width() >= 80 and bb.height() >= 44, f"Back touch target >= 80x44 ({bb.width()}x{bb.height()})")
check(bb.y() + bb.VISIBLE_H <= FULL_TOPBAR_H, "visible Back key stays within the top bar")
back_area, problems, checked = bb.geometry(), [], 0
for key, screen in win.registry.items():
    win._reset_to(win.home); win.open(key); wait(20)
    if win.stack.currentWidget() is not screen or not getattr(screen, "submenu", False):
        continue
    checked += 1
    if not bb.isVisible():
        problems.append(f"{key}: Back hidden")
    top = win._root.topbar.rect
    if top.left() < bb.x() + bb.VISIBLE_W:  # the painted (non-interactive) bar may sit under the touch margin
        problems.append(f"{key}: top bar overlaps the visible Back key")
    for w in screen.findChildren(QAbstractButton):
        if w.isVisible() and QRectF(QPointF(w.mapTo(win._root, QPoint(0, 0))), QSizeF(w.width(), w.height())).intersects(QRectF(back_area)):
            problems.append(f"{key}: {type(w).__name__} under the Back touch area")
check(checked >= 30 and not problems, f"{checked} submenus: Back visible, nothing interactive under it, top bar clear ({problems[:4]})")
win._reset_to(win.home); win.open("timelapse"); wait(20)
QTest.mouseClick(bb, Qt.MouseButton.LeftButton, pos=QPoint(bb.width() // 2, bb.height() - 4))  # tap in the extension
check(win.stack.currentWidget() is win.home, "tap in the lower (extended) part of Back goes back")
win._on_section("control"); win.push(win.z_offset_screen); wait(10)
tap(win.z_offset_screen.preset_tiles[1])
target = win._root.childAt(bb.geometry().center())
check(win.confirm_dialog.isVisible() and target is not bb and not bb.isAncestorOf(target or win), "open dialog covers the Back button (modal)")
tap(win.confirm_dialog.cancel_btn)
dispose(win)
legacy = []
for root, _, files in os.walk(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nexus")):
    for fn in files:
        if fn.endswith(".py"):
            text = open(os.path.join(root, fn)).read()
            if _re.search(r"OM EDITION|OM Edition|\"OM\"|\"EDITION\"", text):
                legacy.append(fn)
check(not legacy, f"no legacy OM Edition branding in the interface code ({legacy})")

# ── Kinematics-aware Home image, larger Back target ─────────────────────────
from nexus.screens.home import HOTEND_PNG, PRINTER_PNG, hero_image, load_pixmap
from nexus.app import BACK_TOUCH_W, BACK_TOUCH_H
expect = {"corexy": "corexy", "corexz": "cartesian", "coreyz": "corexy", "cartesian": "cartesian", "delta": "delta"}
check(all(hero_image(k) == PRINTER_PNG[v] for k, v in expect.items()), "kinematics mapping (corexy/corexz/coreyz/cartesian/delta)")
check(hero_image("CoreXY") == PRINTER_PNG["corexy"], "kinematics value is case-insensitive")
check(all(hero_image(k) == HOTEND_PNG for k in (None, "", "polar", "winch", "hybrid_corexy", "none")),
      "unknown / missing kinematics -> hotend fallback")
sizes = {k: (load_pixmap(p).width(), load_pixmap(p).height()) for k, p in PRINTER_PNG.items()}
check(sizes == {"corexy": (508, 772), "cartesian": (516, 749), "delta": (508, 975)}, f"printer assets load ({sizes})")
check(load_pixmap(PRINTER_PNG["delta"]) is load_pixmap(PRINTER_PNG["delta"]), "decoded images are cached")

for state in ("standby", "printing"):
    for kin, key in (("corexy", "corexy"), ("corexz", "cartesian"), ("delta", "delta"), ("scara", None)):
        src = SimulatedSource(state, "both", 60000)
        src._data["config"]["kinematics"] = kin
        win = MainWindow(src); win.show(); src.start(); wait(30)
        if state == "printing":
            win._reset_to(win.home); wait(20)
        hero = win.home.hero
        hero.repaint()
        ok = hero.image_path == (PRINTER_PNG[key] if key else HOTEND_PNG)
        check(ok and win.stack.currentWidget() is win.home, f"Home {state}: '{kin}' -> {key or 'hotend'}")
        dispose(win)

src, win = fresh()
check(win.home.hero.image_path == PRINTER_PNG["corexy"], "connected corexy printer shows the CoreXY image")
src.set_connected(False); wait(20)
check(win.home.hero.image_path == HOTEND_PNG, "Moonraker disconnected -> hotend fallback")
src.set_connected(True); wait(20)
check(win.home.hero.image_path == PRINTER_PNG["corexy"], "reconnected -> printer image again")
src._data["config"]["kinematics"] = "delta"; src._emit(); wait(20)
check(win.home.hero.image_path == PRINTER_PNG["delta"], "configuration change (kinematics) -> image updates")
dispose(win)

c = MoonrakerClient("127.0.0.1", 1, 60000)
c._query = "q"
c._klippy_state = "ready"
c._on_status({"status": {"webhooks": {"state": "startup"}}})
check(c._query == "q", "Klipper restarting: keep polling")
c._on_status({"status": {"webhooks": {"state": "ready"}}})
check(c._query is None, "Klipper ready again: objects + configuration (kinematics) re-read")
check(devices.config_summary({"printer": {"kinematics": "corexz"}})["kinematics"] == "corexz",
      "kinematics read from configfile.settings.printer.kinematics")

simulator.THUMBS_DIR = os.path.expanduser("~/printer_data/gcodes/.thumbs")
src = SimulatedSource("printing", "both", 60000, sim_file="Lid_PLA_4h34m.gcode")
src._data["config"]["kinematics"] = "delta"
win = MainWindow(src); win.show(); src.start(); wait(30)
check(win.stack.currentWidget() is win.print_status and win.print_status.hero.state == "ready"
      and type(win.print_status.hero).__name__ == "ThumbnailView", "Print Status still shows the G-code thumbnail")
dispose(win)

src, win = fresh()
bb = win.back_btn
check((bb.width(), bb.height()) == (BACK_TOUCH_W, BACK_TOUCH_H) == (130, 60) and bb.VISIBLE_W == 120 and bb.VISIBLE_H == 34,
      f"Back: visible {bb.VISIBLE_W}x{bb.VISIBLE_H}, touch {bb.width()}x{bb.height()}")
hits = []
for x, y in ((1, 1), (BACK_TOUCH_W - 2, 1), (1, BACK_TOUCH_H - 2), (BACK_TOUCH_W - 2, BACK_TOUCH_H - 2),
             (BACK_TOUCH_W // 2, BACK_TOUCH_H - 2), (BACK_TOUCH_W - 2, BACK_TOUCH_H // 2)):
    win._reset_to(win.home); win.open("timelapse"); wait(10)
    gp = bb.mapTo(win._root, QPoint(x, y))
    target = win._root.childAt(gp)
    QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=target.mapFrom(win._root, gp))
    hits.append(win.stack.currentWidget() is win.home)
check(all(hits), f"Back hit at all corners and edges of the 130x60 target ({hits})")
outside = []
for dx, dy in ((BACK_TOUCH_W + 3, 20), (40, BACK_TOUCH_H + 3)):
    win._reset_to(win.home); win.open("timelapse"); wait(10)
    gp = bb.mapTo(win._root, QPoint(dx, dy))
    target = win._root.childAt(gp)
    if target is not None:
        QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=target.mapFrom(win._root, gp))
    outside.append(win.stack.currentWidget() is win.registry["timelapse"])
check(all(outside), "taps just outside the target do not go back")
dispose(win)

# ── Command mode readiness: real network path against a local fake Moonraker ──
import http.server, threading, socketserver
from nexus.moonraker import client as client_mod


class FakeMoonraker(http.server.BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        FakeMoonraker.requests.append((self.path, body))
        script = json.loads(body or "{}").get("script", "")
        if "G1 X999" in script:
            self._reply(400, {"error": {"code": 400, "message": "Move out of range: 999.000 0.000 0.000 [0.000]"}})
        elif script == "SLOW":
            time.sleep(2); self._reply(200, {"result": "ok"})
        elif script == "SAVE_CONFIG":
            self.close_connection = True; self.wfile.flush(); self.connection.shutdown(2)
        else:
            self._reply(200, {"result": "ok"})

    def _reply(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


def wait_for(cond, ms=5000):
    end = time.monotonic() + ms / 1000
    while not cond() and time.monotonic() < end:
        wait(20)
    return cond()


srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeMoonraker)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
client_mod.LOG_PATH = os.path.join(tempfile.mkdtemp(), "commands.jsonl")
c = MoonrakerClient("127.0.0.1", port, 60000, allow_commands=True)
c._last = {"connected": True, "state": "standby"}
c._registered = frozenset({"SAVE_CONFIG"})
c.context = lambda: "MoveScreen"
failures_seen = []
c.command_failed.connect(lambda what, msg: failures_seen.append((what, msg)))

c.run("jog", axis="X", distance=999, feed=6000); wait_for(lambda: failures_seen)
check(failures_seen and failures_seen[-1][1].startswith("Move out of range"),
      f"Klipper rejection reaches the UI ({failures_seen[-1:]}; server got {FakeMoonraker.requests[-1:]}, "
      f"pending {len(c._pending)}, busy {c.busy}, server thread alive {any(t.name != 'MainThread' for t in threading.enumerate())})")
check(not c.busy, "busy cleared after the reply")
logged = [json.loads(l) for l in open(client_mod.LOG_PATH)]
check(logged[-1]["ok"] is False and logged[-1]["screen"] == "MoveScreen" and "G1 X999" in logged[-1]["command"]
      and logged[-1]["printer_state"] == "standby" and logged[-1]["error"].startswith("Move out of range"),
      "failure logged: screen, command, Moonraker message, printer state")
c._send("POST", "/printer/gcode/script", {"script": "SLOW"}, label="SLOW")
wait(1000)
check(c.busy and not failures_seen[1:], "long command (2 s): still running, controls locked, no false timeout")
wait_for(lambda: not c.busy)
check(not c.busy and len(failures_seen) == 1 and logged != [json.loads(l) for l in open(client_mod.LOG_PATH)],
      "long command completes normally and is logged")
c.busy = True
check(c.emergency_stop(), "Emergency stop is accepted while another command is running")
wait_for(lambda: FakeMoonraker.requests[-1][0] == "/printer/emergency_stop")
check(FakeMoonraker.requests[-1][0] == "/printer/emergency_stop", "Emergency stop -> POST /printer/emergency_stop")
c.busy = False
c._last = {"connected": True, "state": "printing"}
check(c.emergency_stop(), "Emergency stop allowed while printing")
c._last = {"connected": False, "state": "offline"}
check(not c.emergency_stop(), "Emergency stop refused while disconnected (nothing to send to)")
c2 = MoonrakerClient("127.0.0.1", port, 60000, allow_commands=False); c2._last = {"connected": True, "state": "printing"}
check(not c2.emergency_stop(), "read-only mode: no emergency stop either")
c._last = {"connected": True, "state": "standby"}
n = len(failures_seen)
c.run("save_config"); wait_for(lambda: not c.busy)
check(len(failures_seen) == n, "SAVE_CONFIG: Klipper restarting (dropped connection) is not reported as a failure")
srv.shutdown()

# the UI shows the message (info dialog: only OK); approved confirmations keep Cancel
src, win = fresh()
src.fail_next = "Must home axis first: 125.000 125.000 10.000 [0.000]"
win.push(win.move_screen); tap(win.move_screen.z.up); wait(20)
cd = win.confirm_dialog
check(cd.isVisible() and cd._title == "Command failed" and cd._message.startswith("Must home axis first")
      and not cd.cancel_btn.isVisible() and cd.confirm_btn._label == "OK", "failed command: message dialog with OK only")
tap(cd.confirm_btn)
check(not cd.isVisible() and win.stack.currentWidget() is win.move_screen, "OK closes it, screen unchanged")
win.push(win.z_offset_screen); tap(win.z_offset_screen.preset_tiles[1])
check(cd.isVisible() and cd.cancel_btn.isVisible(), "approved confirmations still show Cancel")
tap(cd.cancel_btn)
check(win.emergency_stop() and src._data["state"] == "error" and src.log[-1] == "EMERGENCY_STOP",
      "controller emergency stop (simulation: state -> error)")
dispose(win)

# every dangerous action asks first: nothing is logged before Confirm
src, win = fresh()
dangerous = {
    "input shaper": lambda: (win.open("input_shaper"), win.registry["input_shaper"].run_btn.click()),
    "probe accuracy": lambda: (win.open("calibrate"), win.registry["calibrate"].tiles["Probe Accuracy"].click()),
    "firmware restart": lambda: (win.open("system"), win.registry["system"].fw_btn.click()),
    "host reboot": lambda: (win.open("system"), win.registry["system"].reboot_btn.click()),
    "host shutdown": lambda: (win.open("system"), win.registry["system"].off_btn.click()),
    "klipper restart": lambda: (win.open("tools"), win.registry["tools"].tiles["Restart"].click()),
    "service restart": lambda: (win.open("system"), wait(30), win.registry["system"].services.btns[0].click()),
    "save config": lambda: (win.open("temperature"), win.temperature_screen.save.click()),
    "bed mesh calibrate": lambda: (win.open("bed_mesh"), win.bed_mesh_screen.calibrate.click()),
    "z offset save": lambda: (win.open("z_offset"), win.z_offset_screen.save.click()),
}
unconfirmed = []
for name, act in dangerous.items():
    win._reset_to(win.home); wait(10)
    n = len(src.log)
    act(); wait(20)
    if len(src.log) != n or not win.confirm_dialog.isVisible():
        unconfirmed.append(name)
    win.confirm_dialog.hide()
check(not unconfirmed, f"dangerous actions all ask for confirmation first ({unconfirmed})")
dispose(win)

# ── Emergency Stop key (simulator only: nothing reaches a printer) ─────────
def hold(w, ms):
    QTest.mousePress(w, Qt.MouseButton.LeftButton, pos=w.rect().center())
    wait(ms)
    QTest.mouseRelease(w, Qt.MouseButton.LeftButton, pos=w.rect().center())
    wait(20)


def idle(src, **extra):
    d = src._data
    d["heaters"] = {h: (v[0], 0.0) for h, v in d["heaters"].items()}
    d.update({"nozzle": (d["nozzle"][0], 0.0), "bed": (d["bed"][0], 0.0), "klipper_busy": False, **extra})
    src._emit(); wait(20)


src, win = fresh("printing")
es = win.estop
bar = win._root.topbar
check(es.isVisible() and win.stack.currentWidget() is win.print_status, "E-stop shown on Print Status while printing")
check(bar.rect.toRect().contains(es.geometry()), f"E-stop inside the top bar ({es.geometry().getRect()})")
check(es.geometry().bottom() < win.stack.geometry().top(), "E-stop does not cover the screen (thumbnail, controls)")
check(es.x() > bar.free_span()[0] + 8, "E-stop clear of the printer state text")
check(es.width() >= 140 and es.height() >= 36, f"E-stop target at least 140x36 ({es.width()}x{es.height()})")
check(not es.geometry().intersects(win.back_btn.geometry()) or not win.back_btn.isVisible(), "E-stop clear of Back")
hold(es, 150)
check("EMERGENCY_STOP" not in src.log and es.progress == 0, "short touch (150 ms) does nothing")
QTest.mousePress(es, Qt.MouseButton.LeftButton, pos=es.rect().center()); wait(200)
QTest.mouseMove(es, QPoint(es.width() + 40, es.height() // 2)); wait(400)
QTest.mouseRelease(es, Qt.MouseButton.LeftButton, pos=QPoint(es.width() + 40, es.height() // 2)); wait(20)
check("EMERGENCY_STOP" not in src.log, "sliding off the key cancels it")
win.open_stop_dialog(); wait(20)
check(win._root.childAt(es.geometry().center()) is not es, "dialogs cover the E-stop")
win.stop_dialog.hide(); wait(20)
src.busy = True  # another command still running must not block it
hold(es, 650)
src.busy = False
check(src.log.count("EMERGENCY_STOP") == 1, f"hold 0.5 s: emergency stop sent once, no dialog first ({src.log[-2:]})")
wait(30)
check(not es.isVisible() and win.error_dialog.isVisible(), "after the stop: key hidden, error dialog shows the shutdown")
dispose(win)

src, win = fresh("standby")
check(win.estop.isVisible(), "standby with heaters on: E-stop shown")
idle(src)
check(not win.estop.isVisible(), "idle, heaters off: E-stop hidden (nothing to stop)")
idle(src, klipper_busy=True)
check(win.estop.isVisible(), "Klipper executing commands (moves, homing, macros): E-stop shown")
for scr in (win.move_screen, win.z_offset_screen):
    win.push(scr); wait(20)
    check(win.estop.isVisible() and not win.estop.geometry().intersects(win.back_btn.geometry())
          and win.estop.geometry().bottom() < win.stack.geometry().top(),
          f"{type(scr).__name__}: E-stop in the bar, clear of Back and the screen")
src.commands_enabled = False; src._emit(); wait(20)
check(not win.estop.isVisible(), "read-only mode: no E-stop")
src.commands_enabled = True; src.set_connected(False); wait(20)
check(not win.estop.isVisible(), "disconnected: no E-stop")
check(not win.emergency_stop() and "EMERGENCY_STOP" not in src.log, "controller refuses while disconnected")
dispose(win)

check(not callback_errors, f"no exceptions in Qt callbacks/paint ({callback_errors[:3]})")

print(f"\nscreens reachable through the UI: {INVENTORY_REACHED}")
print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
