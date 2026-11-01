"""Handover from the boot splash (splash/player.py) to the main window.

Only when a splash player is actually running: the window stays hidden while the splash plays, the
first connected snapshot (or `timeout_ms`) marks Nexus Screen as ready, the player is told to stop
and the window is shown once it has released the screen. Without a splash nothing changes."""
import os

from PyQt6.QtCore import QObject, QTimer

RUN_DIR = os.environ.get("NEXUS_SPLASH_DIR", "/run/nexus-splash")


def splash_pid(run_dir=RUN_DIR):
    """PID of a live splash player, else None."""
    try:
        pid = int(open(os.path.join(run_dir, "player.pid")).read().strip())
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ")
    except (OSError, ValueError):
        return None
    return pid if b"splash/player.py" in cmd and not os.path.exists(os.path.join(run_dir, "released")) else None


class Handover(QObject):
    POLL_MS = 40
    RELEASE_MS = 2000  # the player stops within one frame; never wait longer than this

    def __init__(self, show, run_dir=RUN_DIR, timeout_ms=30000, parent=None):
        super().__init__(parent)
        self._show, self.run_dir = show, run_dir
        self.state = "waiting"  # waiting -> releasing -> shown
        self._waited = 0
        QTimer.singleShot(timeout_ms, self.ready)  # disconnected printer: show anyway

    def on_data(self, data):
        if data.get("connected"):
            QTimer.singleShot(0, self.ready)  # after this snapshot has reached the screens

    def ready(self):
        if self.state != "waiting":
            return
        self.state = "releasing"
        try:
            open(os.path.join(self.run_dir, "ready"), "w").close()
        except OSError:
            pass  # run dir gone: the splash has already ended
        self._poll()

    def _poll(self):
        released = os.path.exists(os.path.join(self.run_dir, "released")) or splash_pid(self.run_dir) is None
        if released or self._waited >= self.RELEASE_MS:
            self.state = "shown"
            self._show()
            return
        self._waited += self.POLL_MS
        QTimer.singleShot(self.POLL_MS, self._poll)
