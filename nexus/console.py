"""Linux console (VT) handling for the physical display.

Qt's linuxfb plugin tries to open /dev/tty0 read-write to switch the console into graphics
mode; VTs are root:tty mode 620, so a normal user (group tty) can write but not read them and
Qt logs "Failed to open tty" and leaves the console as is — its text cursor then blinks
through the UI. Writing the standard escape sequences only needs write access, so the cursor
of the active VT is hidden while the app runs and shown again on exit.

A permanent service should instead own its VT (see docs/DEPLOYMENT-TTY.md)."""
import os

HIDE, SHOW = "\033[?25l", "\033[?25h"


def active_vt():
    try:
        with open("/sys/class/tty/tty0/active") as fh:
            name = fh.read().strip()
        return f"/dev/{name}" if name.startswith("tty") else None
    except OSError:
        return None


class ConsoleCursor:
    def __init__(self, vt=None):
        self.vt = vt or active_vt()
        self.hidden = False

    def _write(self, seq):
        if not self.vt:
            return False
        try:
            fd = os.open(self.vt, os.O_WRONLY | os.O_NOCTTY | os.O_APPEND)
        except OSError:
            return False
        try:
            os.write(fd, seq.encode())
            return True
        finally:
            os.close(fd)

    def hide(self):
        self.hidden = self._write(HIDE)
        return self.hidden

    def restore(self):
        """The Linux console's default is a visible cursor; restore that state on exit."""
        if self.hidden:
            self._write(SHOW)
            self.hidden = False
