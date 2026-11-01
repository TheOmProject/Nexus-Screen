#!/usr/bin/env python3
"""Touch accuracy + latency check for the physical panel (a test tool, not part of the app).

Phase 1: tap the centre of each red crosshair (4 corners, then the centre).
Phase 2: tap anywhere 10 times; each tap flashes the screen.
Results: on screen and in logs/touch-check-<time>.json. Stops itself after 5 minutes.

Run from SSH:  scripts/touch_check.py      (needs the screen free: run launch-test.sh --check first)
"""
import json
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("QT_QPA_PLATFORM", "linuxfb:fb=/dev/fb0")
os.environ.setdefault("QT_QPA_FB_HIDECURSOR", "1")

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from nexus import theme
from nexus.console import ConsoleCursor
from nexus.signals import quit_on_signals

TARGETS = [("top-left", 40, 40), ("top-right", 760, 40), ("bottom-right", 760, 440),
           ("bottom-left", 40, 440), ("centre", 400, 240)]
LATENCY_TAPS = 10


class TouchCheck(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.setFixedSize(800, 480)
        self.hits, self.latency, self.flash = [], [], False
        self.started = datetime.now().strftime("%Y%m%d-%H%M%S")

    def phase(self):
        return "targets" if len(self.hits) < len(TARGETS) else ("latency" if len(self.latency) < LATENCY_TAPS else "done")

    def event(self, e):
        if e.type() == QEvent.Type.TouchBegin:
            pts = e.points()
            if pts:
                self.press(pts[0].position(), e.timestamp(), "touch")
            e.accept()
            return True
        if e.type() == QEvent.Type.MouseButtonPress:  # accepted TouchBegin => no duplicate synthesized press
            self.press(e.position(), e.timestamp(), e.pointingDevice().type().name)
            return True
        return super().event(e)

    def press(self, pos, stamp_ms, kind):
        phase = self.phase()
        if phase == "targets":
            name, tx, ty = TARGETS[len(self.hits)]
            self.hits.append({"target": name, "expected": [tx, ty], "touched": [round(pos.x(), 1), round(pos.y(), 1)],
                              "error_px": round(((pos.x() - tx) ** 2 + (pos.y() - ty) ** 2) ** 0.5, 1), "via": kind})
            self.repaint()
        elif phase == "latency":
            self.flash = not self.flash
            self.repaint()  # synchronous paint + flush to the framebuffer
            done_ms = time.clock_gettime(time.CLOCK_MONOTONIC) * 1000
            # Qt input timestamps are milliseconds on the monotonic clock (libinput / evdev)
            self.latency.append(round(done_ms - stamp_ms, 1))
        if self.phase() == "done":
            self.save()
            self.repaint()

    def save(self):
        lat = sorted(self.latency)
        out = {"time": self.started, "targets": self.hits,
               "max_error_px": max(h["error_px"] for h in self.hits),
               "latency_ms": {"samples": self.latency, "median": lat[len(lat) // 2], "max": lat[-1]} if lat else None}
        os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
        self.result_path = os.path.join(HERE, "logs", f"touch-check-{self.started}.json")
        with open(self.result_path, "w") as fh:
            json.dump(out, fh, indent=1)
        self.summary = out

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(40, 6, 6) if self.flash else theme.BG)
        p.setPen(theme.FG)
        p.setFont(theme.font(26, QFont.Weight.Bold))
        phase = self.phase()
        title = {"targets": "Touch check — tap the centre of the red crosshair",
                 "latency": f"Tap anywhere ({len(self.latency)}/{LATENCY_TAPS})",
                 "done": "Touch check complete"}[phase]
        p.drawText(QRectF(0, 150, 800, 40), Qt.AlignmentFlag.AlignCenter, title)
        p.setFont(theme.font(16))
        p.setPen(theme.DIM)
        for h in self.hits:  # where each tap landed
            x, y = h["touched"]
            p.setPen(QPen(theme.GREEN, 2))
            p.drawEllipse(QPointF(x, y), 6, 6)
        if phase == "targets":
            name, tx, ty = TARGETS[len(self.hits)]
            p.setPen(QPen(theme.RED, 2))
            p.drawEllipse(QPointF(tx, ty), 18, 18)
            p.drawLine(QPointF(tx - 26, ty), QPointF(tx + 26, ty))
            p.drawLine(QPointF(tx, ty - 26), QPointF(tx, ty + 26))
            p.setPen(theme.DIM)
            p.drawText(QRectF(0, 196, 800, 30), Qt.AlignmentFlag.AlignCenter, f"Target {len(self.hits) + 1} of {len(TARGETS)}: {name}")
        elif phase == "done":
            s = self.summary
            lines = [f"Largest target error: {s['max_error_px']} px"] + \
                    [f"{h['target']}: {h['error_px']} px" for h in s["targets"]]
            if s["latency_ms"]:
                lines.append(f"Touch to display: median {s['latency_ms']['median']} ms, max {s['latency_ms']['max']} ms")
            lines.append("Saved to " + os.path.relpath(self.result_path, HERE) + "  —  press Ctrl+C in the terminal")
            p.setPen(theme.FG_SOFT)
            for i, line in enumerate(lines):
                p.drawText(QRectF(0, 200 + i * 26, 800, 26), Qt.AlignmentFlag.AlignCenter, line)
        p.end()


def main():
    app = QApplication(sys.argv)
    theme.load_fonts()
    quit_on_signals(app)
    QTimer.singleShot(5 * 60_000, app.quit)
    cursor = ConsoleCursor() if app.platformName() in ("linuxfb", "eglfs") else None
    if cursor:
        cursor.hide()
    w = TouchCheck()
    w.showFullScreen()
    try:
        return app.exec()
    finally:
        if cursor:
            cursor.restore()
        if getattr(w, "summary", None):
            print(json.dumps(w.summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
