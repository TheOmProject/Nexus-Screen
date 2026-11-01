#!/usr/bin/env python3
"""Health check for the installed Nexus Screen service (run as root by install.sh, or as omar).

  deploy/healthcheck.py [--wait SECONDS] [--png PATH] [--max-restarts N] [--commands]

Exit 0 when the essential checks pass: service running without restart loop, live mode
without printer commands, owns the framebuffer, connected to Moonraker, screen not black.
Console graphics mode (tty7) is reported but is not essential (the app also hides the cursor)."""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import time

UNIT = "nexus-screen.service"
KDGETMODE = 0x4B3B


def show(*props):
    out = subprocess.run(["systemctl", "show", UNIT, "-p", ",".join(props)], capture_output=True, text=True).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def holds_fb(pid):
    try:
        return any(os.readlink(f"/proc/{pid}/fd/{fd}") == "/dev/fb0" for fd in os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        return False


def moonraker_connected(pid, port=7125):
    try:
        inodes = {os.readlink(f"/proc/{pid}/fd/{fd}")[8:-1] for fd in os.listdir(f"/proc/{pid}/fd")
                  if os.readlink(f"/proc/{pid}/fd/{fd}").startswith("socket:[")}
    except OSError:
        return False
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            rows = open(table).read().splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            f = row.split()
            if f[9] in inodes and f[3] == "01" and int(f[2].rsplit(":", 1)[1], 16) == port:
                return True
    return False


def vt_state():
    try:
        active = open("/sys/class/tty/tty0/active").read().strip()
    except OSError:
        return None, None
    try:
        fd = os.open("/dev/tty7", os.O_WRONLY | os.O_NOCTTY)
        try:
            mode = fcntl.ioctl(fd, KDGETMODE, b"\0\0\0\0")
            graphics = int.from_bytes(mode, sys.byteorder) == 1
        finally:
            os.close(fd)
    except OSError:
        graphics = None
    return active, graphics


def screen(png=None):
    import numpy as np
    stride = int(open("/sys/class/graphics/fb0/stride").read())
    raw = np.fromfile("/dev/fb0", dtype=np.uint16, count=stride // 2 * 480).reshape(480, stride // 2)[:, :800]
    lum = ((raw >> 11) & 0x1F) * 8 * 0.3 + ((raw >> 5) & 0x3F) * 4 * 0.59 + (raw & 0x1F) * 8 * 0.11
    if png:
        from PIL import Image
        r = ((raw >> 11) & 0x1F) << 3
        g = ((raw >> 5) & 0x3F) << 2
        b = (raw & 0x1F) << 3
        Image.fromarray(np.dstack([r, g, b]).astype("uint8")).save(png)
    return float(lum.mean()), float(lum.std())


def check():
    s = show("ActiveState", "SubState", "MainPID", "NRestarts", "ActiveEnterTimestamp")
    pid = int(s.get("MainPID", "0") or 0)
    cmd = open(f"/proc/{pid}/cmdline").read().split("\0") if pid else []
    active, graphics = vt_state()
    r = {"active": s.get("ActiveState"), "sub": s.get("SubState"), "pid": pid,
         "restarts": int(s.get("NRestarts", "0") or 0), "since": s.get("ActiveEnterTimestamp"),
         "live_mode": "--live" in cmd, "commands_enabled": "--allow-commands" in cmd,
         "owns_framebuffer": holds_fb(pid) if pid else False,
         "moonraker_connected": moonraker_connected(pid) if pid else False,
         "active_vt": active, "console_graphics_mode": graphics}
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=0, help="keep re-checking up to N seconds")
    ap.add_argument("--png")
    ap.add_argument("--max-restarts", type=int, default=0, help="restarts already expected (planned restarts)")
    ap.add_argument("--commands", action="store_true", help="expect printer commands enabled (drop-in installed)")
    args = ap.parse_args()
    deadline = time.time() + args.wait
    while True:
        r = check()
        essential = (r["active"] == "active" and r["sub"] == "running" and r["restarts"] <= args.max_restarts
                     and r["live_mode"]
                     and r["commands_enabled"] == args.commands and r["owns_framebuffer"] and r["moonraker_connected"])
        if essential or time.time() >= deadline:
            break
        time.sleep(2)
    if r["owns_framebuffer"]:
        time.sleep(1)
        mean, std = screen(args.png)
        r["screen_mean"], r["screen_contrast"] = round(mean, 1), round(std, 1)
        r["screen_not_black"] = mean > 8 and std > 10
    else:
        r["screen_not_black"] = False
    r["healthy"] = bool(essential and r["screen_not_black"])
    print(json.dumps(r, indent=1))
    return 0 if r["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
