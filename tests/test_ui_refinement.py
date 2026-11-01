"""Focused checks for the typography / touchscreen refinement: Baby Step submenu, Print Status
without the duplicate thumbnail, central type scale. Simulator and mocks only; one window.

    QT_QPA_PLATFORM=offscreen python3 tests/test_ui_refinement.py
"""
import gc
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication, QEvent, QEventLoop, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QAbstractButton, QApplication

from nexus import theme
from nexus.app import MainWindow
from nexus.moonraker.client import MoonrakerClient
from nexus.moonraker.simulator import SimulatedSource
from nexus.screens.baby_step import LOWER, RAISE
from nexus.widgets.buttons import GLOW

app = QApplication(sys.argv)
callback_errors = []
_hook = sys.excepthook
sys.excepthook = lambda *exc: (callback_errors.append(exc[1]), _hook(*exc))
theme.load_fonts()
failures = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def tap(w):
    QTest.mouseClick(w, Qt.MouseButton.LeftButton)
    wait(30)


def overlaps(widgets, margin=0):
    """Pairs whose touch areas intersect, in window coordinates; `margin` strips a painted halo."""
    rects = []
    for w in widgets:
        if w.isVisible():
            top_left = w.mapTo(w.window(), w.rect().topLeft())
            rects.append((w, w.rect().translated(top_left).adjusted(margin, margin, -margin, -margin)))
    return [(a, b) for i, (a, ra) in enumerate(rects) for b, rb in rects[i + 1:] if ra.intersects(rb)]


# ── central type scale: no literal sizes <= 16 px left in screens and shared widgets ──
ROLES = ("TITLE", "SUBTITLE", "HEADING", "CAPS", "NAME", "CARD", "FIELD", "BUTTON", "LABEL", "BODY", "CAPTION",
         "SMALL", "JOG", "JOG_Z")
check(all(isinstance(getattr(theme, r, None), int) for r in ROLES), "typography roles defined in nexus.theme")
check(theme.SMALL >= 13 and theme.HEADING > theme.BODY > theme.SMALL, "scale keeps its hierarchy (min 13 px)")
literal = []
for folder in ("nexus/screens", "nexus/widgets"):
    for name in os.listdir(os.path.join(ROOT, folder)):
        if not name.endswith(".py") or name in ("sidebar.py", "topbar.py"):  # approved chrome, unchanged
            continue
        for i, line in enumerate(open(os.path.join(ROOT, folder, name)), 1):
            for m in re.finditer(r"(?:theme\.font\(|font_px=)(\d+)\b", line):
                if int(m.group(1)) <= 16 and not (name == "buttons.py" and "Weight.Bold" in line):
                    literal.append(f"{name}:{i}")  # buttons.py Bold 15: Emergency Stop label, unchanged by request
check(not literal, f"small text uses the shared scale ({literal[:5]})")

# ── Print Status: one thumbnail (the large hero), Baby Step key instead of inline controls ──
src = SimulatedSource("printing", "both", 60000, sim_file="Lid_PLA_4h34m.gcode")
win = MainWindow(src)
win.show()
src.start()
wait(60)
ps = win.print_status
check(win.stack.currentWidget() is ps, "printing opens Print Status")
check(ps.hero.state == "ready", "large thumbnail shown in the hero panel")
check(not hasattr(ps.progress, "_thumb"), "Print Progress card no longer holds a second thumbnail")
check(isinstance(ps.baby, QAbstractButton) and ps.baby._label == "Baby Step", "single Baby Step key in the bar")
bar_keys = [ps.pause, ps.stop, ps.baby, ps.home]
check(not overlaps(bar_keys, margin=GLOW), "bottom-bar keys do not overlap (glow halo excluded)")
check(all(k.height() - 14 >= 58 for k in bar_keys), "bottom-bar keys keep their 58 px height")

# ── Baby Step submenu ──
tap(ps.baby)
bs = win.baby_step
check(win.stack.currentWidget() is bs, "Baby Step key opens the submenu")
check(not win.sidebar.isVisible() and win.back_btn.isVisible(), "submenu: minimal top bar, Back, no sidebar")
check(win.back_btn.width() >= 130 and win.back_btn.height() >= 60, "Back keeps its 130x60 touch target")
check(sorted(bs.keys) == sorted(RAISE + LOWER) and RAISE == (0.005, 0.01, 0.025, 0.05),
      "keys: +/-0.005, 0.01, 0.025, 0.05 mm")
check(all(k.width() >= 100 and k.height() >= 75 for k in bs.keys.values()),
      f"keys at least 100x75 px ({min(k.width() for k in bs.keys.values())}x{min(k.height() for k in bs.keys.values())})")
check(not overlaps(list(bs.keys.values())), "keys do not overlap")
raise_y = {k.parent().y() for d, k in bs.keys.items() if d > 0}
lower_y = {k.parent().y() for d, k in bs.keys.items() if d < 0}
check(len(raise_y) == len(lower_y) == 1 and raise_y != lower_y, "positive and negative keys in separate groups")
check(all(k.isEnabled() for k in bs.keys.values()), "keys enabled while printing")
z0 = src._data["z_offset"]
for d in (0.005, 0.025, -0.01):
    tap(bs.keys[d])
check(abs(src._data["z_offset"] - (z0 + 0.02)) < 1e-9, "+0.005 +0.025 -0.01 reach the existing z_adjust (+0.020)")
wait(20)
check(bs.current.value is not None and abs(bs.current.value - src._data["z_offset"]) < 1e-9,
      "displayed Z offset follows the printer state")
src.pause()
wait(30)
check(all(k.isEnabled() for k in bs.keys.values()), "keys enabled while paused (applied on resume)")
src.resume()
src.commands_enabled = False
src._emit(); wait(20)
check(not any(k.isEnabled() for k in bs.keys.values()), "read-only mode: keys disabled")
src.commands_enabled = True
src.busy = True
src._emit(); wait(20)
check(not any(k.isEnabled() for k in bs.keys.values()), "another command running: keys disabled")
src.busy = False
src.set_connected(False); wait(20)
check(not any(k.isEnabled() for k in bs.keys.values()) and win.stack.currentWidget() is bs,
      "disconnected: keys disabled, screen kept")
src.set_connected(True); wait(20)
check(all(k.isEnabled() for k in bs.keys.values()), "reconnected: keys enabled again")
tap(win.back_btn)
check(win.stack.currentWidget() is ps, "Back returns to Print Status")
tap(ps.baby)
src.cancel(); wait(30)
check(win.stack.currentWidget() is win.home, "print ends while on Baby Step: back to Home")
win.close()
win.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
gc.collect()

# ── live client: same command text as before for the new step sizes (no network: _post recorded) ──
c = MoonrakerClient("127.0.0.1", 1, 60000, allow_commands=True)
sent = []
c._post = lambda path, payload=None, **kw: sent.append(payload["script"])
c._last = {"connected": True, "state": "printing"}
for d in (0.005, -0.025, 0.05):
    c.z_adjust(d)
c._last = {"connected": True, "state": "paused"}
c.z_adjust(0.01)
check(sent == ["SET_GCODE_OFFSET Z_ADJUST=+0.005 MOVE=1", "SET_GCODE_OFFSET Z_ADJUST=-0.025 MOVE=1",
               "SET_GCODE_OFFSET Z_ADJUST=+0.050 MOVE=1", "SET_GCODE_OFFSET Z_ADJUST=+0.010 MOVE=0"],
      f"z_adjust commands unchanged ({sent})")

check(not callback_errors, f"no exceptions in Qt callbacks/paint ({callback_errors[:3]})")
print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
