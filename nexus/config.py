import os

MOONRAKER_HOST = "localhost"
MOONRAKER_PORT = 7125
POLL_MS = 1000

# ── Design reference ──────────────────────────────────────────────────────────
# All layout coordinates in the codebase are expressed in this space.
# Do not change these values; they define the approved 800×480 design.
DESIGN_W = 800
DESIGN_H = 480

# ── Actual display dimensions ─────────────────────────────────────────────────
# Read from the framebuffer sysfs at import time, with env-var override for
# testing (NEXUS_SCREEN_W / NEXUS_SCREEN_H).  Falls back to the design
# reference when the sysfs node is absent (desktop / Xvfb builds).

def _read_fb_size():
    """Return (width, height) of /dev/fb0, or the design reference on failure."""
    env_w = os.environ.get("NEXUS_SCREEN_W")
    env_h = os.environ.get("NEXUS_SCREEN_H")
    if env_w and env_h:
        try:
            return int(env_w), int(env_h)
        except ValueError:
            pass
    try:
        raw = open("/sys/class/graphics/fb0/virtual_size").read().strip()
        w, h = (int(v) for v in raw.split(","))
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return DESIGN_W, DESIGN_H


SCREEN_W, SCREEN_H = _read_fb_size()

# Chrome dimensions — proportional to the design reference, with minimums that
# keep the sidebar and topbar usable on very small displays.
SIDEBAR_W = max(60, round(80 * SCREEN_W / DESIGN_W))
TOPBAR_H  = max(30, round(38 * SCREEN_H / DESIGN_H))

# ── Scale helpers ─────────────────────────────────────────────────────────────
# sx / sy map a design-space coordinate or size to the actual screen.
# smin maps a design value using the smaller of the two scale factors — use it
# for elements that must preserve aspect ratio (circles, icons, font sizes).
#
# When SCREEN_W == 800 and SCREEN_H == 480, sx(v) == v and sy(v) == v
# identically, so the 800×480 path is numerically unchanged.

_SX: float = SCREEN_W / DESIGN_W
_SY: float = SCREEN_H / DESIGN_H
_SM: float = min(_SX, _SY)

# Content-area scale: hub pages (non-SubScreen, fullscreen=False) are placed inside the
# stack with width = SCREEN_W - SIDEBAR_W.  SIDEBAR_W has a floor (max(60, ...)) that
# makes it wider than sx(80) on small displays, so sx() alone would overflow those pages.
# cx() corrects for the actual content area rather than the raw screen width.
_DESIGN_SIDEBAR_W: int = 80          # sidebar width in design space
_DESIGN_CONTENT_W: int = DESIGN_W - _DESIGN_SIDEBAR_W   # 720
_CX: float = (SCREEN_W - SIDEBAR_W) / _DESIGN_CONTENT_W

# Minimum font pixel size: Rajdhani is legible down to ~10 px on a touchscreen.
_FONT_MIN = 10


def sx(v: float) -> int:
    """Scale a design-space x-coordinate or width to actual screen pixels."""
    return round(v * _SX)


def sy(v: float) -> int:
    """Scale a design-space y-coordinate or height to actual screen pixels."""
    return round(v * _SY)


def smin(v: float) -> int:
    """Scale preserving aspect ratio (use for circles, icons, font sizes)."""
    return max(_FONT_MIN, round(v * _SM))


def cx(v: float) -> int:
    """Scale a design-space x-coord or width within the content area (hub pages only).

    Use this instead of sx() when laying out children of a non-SubScreen hub page
    (SettingsPage, ControlPage, FilamentPage, PrintPage) where the stack width is
    SCREEN_W - SIDEBAR_W, not SCREEN_W.
    """
    return round(v * _CX)
