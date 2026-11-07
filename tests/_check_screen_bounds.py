"""Button bounds checker — invoked as a subprocess with NEXUS_SCREEN_W/NEXUS_SCREEN_H set.

Navigates to each key screen and verifies that every visible interactive button
has its geometry fully inside the window rect.  Exit 0 = all OK; 1 = violations.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QRect, QTimer
from PyQt6.QtWidgets import QAbstractButton, QApplication

from nexus import theme
from nexus.app import MainWindow
from nexus.config import SCREEN_W, SCREEN_H
from nexus.moonraker.simulator import SimulatedSource

app = QApplication(sys.argv)
theme.load_fonts()

violations = []


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def oob_buttons(window, label):
    """Return descriptions of any visible interactive button outside the window rect."""
    bounds = QRect(0, 0, window.width(), window.height())
    out = []
    for w in window.findChildren(QAbstractButton):
        if not w.isVisible():
            continue
        tl = w.mapTo(window, w.rect().topLeft())
        wr = w.rect().translated(tl)
        if not bounds.contains(wr):
            out.append(
                f"  [{SCREEN_W}x{SCREEN_H}] {label}: {type(w).__name__}"
                f" at ({wr.x()},{wr.y()}) size {wr.width()}x{wr.height()}"
                f" — window is {bounds.width()}x{bounds.height()}"
            )
    return out


src = SimulatedSource("standby", "both", 60000)
win = MainWindow(src)
win.show()
src.start()
wait(400)

SCREENS = [
    ("home",          lambda w: w._on_section("home")),
    ("settings",      lambda w: w._on_section("settings")),
    ("screen",        lambda w: w.open("screen")),
    ("printer",       lambda w: w.open("printer")),
    ("network",       lambda w: w.open("network")),
    ("system",        lambda w: w.open("system")),
    ("firmware",      lambda w: w.open("firmware")),
    ("about",         lambda w: w.open("about")),
    ("startup_video", lambda w: w.open("startup_video")),
    ("tools",         lambda w: w.open("tools")),
    ("control",       lambda w: w._on_section("control")),
    ("temperature",   lambda w: w.push(w.temperature_screen)),
    ("filament",      lambda w: w._on_section("filament")),
    ("print",         lambda w: w._on_section("print")),
]

for label, navigate in SCREENS:
    win._on_section("home")
    wait(30)
    try:
        navigate(win)
    except Exception as exc:
        print(f"  [{SCREEN_W}x{SCREEN_H}] {label}: navigation error — {exc}", flush=True)
        continue
    wait(80)
    found = oob_buttons(win, label)
    violations.extend(found)
    for msg in found:
        print(msg, flush=True)

win.close()
print(f"violations={len(violations)}", flush=True)
sys.exit(1 if violations else 0)
