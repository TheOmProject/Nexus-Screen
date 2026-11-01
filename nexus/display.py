"""Display backend: backlight brightness (sysfs), screen timeout and app-local preferences.

Preferences are Nexus Screen's own settings (~/.config/nexus-screen/preferences.json), not
printer configuration. In simulation nothing is written anywhere — values live in memory."""
import glob
import json
import os

PREFS_PATH = os.path.expanduser("~/.config/nexus-screen/preferences.json")
TIMEOUTS = (1, 5, 10, 30, 0)          # minutes; 0 = never (reference: 1 min … 30 min, Never)
DEFAULTS = {"timeout_min": 30, "brightness": 100}


class Display:
    def __init__(self, live=False, allow_writes=False):
        self.live, self.allow = live, allow_writes
        self.prefs = dict(DEFAULTS)
        paths = sorted(glob.glob("/sys/class/backlight/*/brightness")) if live else []
        self.backlight = paths[0] if paths else None
        self.max = self._read_int(os.path.join(os.path.dirname(self.backlight), "max_brightness")) if self.backlight else None
        if live and os.path.exists(PREFS_PATH):
            try:
                with open(PREFS_PATH) as fh:
                    self.prefs.update(json.load(fh))
            except (OSError, ValueError):
                pass

    @staticmethod
    def _read_int(path):
        try:
            with open(path) as fh:
                return int(fh.read().strip())
        except (OSError, ValueError):
            return None

    def can_set_brightness(self):
        return bool(not self.live or (self.allow and self.backlight and os.access(self.backlight, os.W_OK)))

    def brightness(self):
        if self.backlight and self.max:
            v = self._read_int(self.backlight)
            if v is not None:
                return round(v * 100 / self.max)
        return self.prefs["brightness"]

    def set_brightness(self, pct):
        pct = max(10, min(100, int(pct)))  # never fully dark from the UI
        if not self.can_set_brightness():
            return False
        if self.live:
            with open(self.backlight, "w") as fh:
                fh.write(str(round(self.max * pct / 100)))
        self.set_pref("brightness", pct)
        return True

    def set_pref(self, key, value):
        self.prefs[key] = value
        if self.live and self.allow:
            os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
            with open(PREFS_PATH, "w") as fh:
                json.dump(self.prefs, fh)

    def describe(self):
        return {"backlight": self.backlight or "none", "max": self.max}
