#!/usr/bin/env python3
"""Health check for the installed Nexus Screen service (run as root by install.sh, or as user).

  deploy/healthcheck.py [--wait SECONDS] [--png PATH] [--max-restarts N] [--commands]

Exit 0 when the essential checks pass: service running without restart loop, live mode
without printer commands, owns the framebuffer, connected to Moonraker, screen not black.
Console graphics mode (tty7) is reported but is not essential (the app also hides the cursor).

Supported framebuffer formats:
  16-bit RGB565  (Voron Micron, CB1)
  32-bit BGRA8888 and compatible 32-bit layouts  (Voron 2.4 / BCM2708)"""
import argparse
import fcntl
import json
import os
import struct
import subprocess
import sys
import time

UNIT = "nexus-screen.service"
KDGETMODE = 0x4B3B
FBIOGET_VSCREENINFO = 0x4600


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


def _parse_fb_format(bpp, r_off, r_len, g_off, g_len, b_off, b_len):
    """Validate a framebuffer pixel format; return a format dict or raise RuntimeError.

    The dict contains: bpp, name, bytes_pp, r_off, r_len, g_off, g_len, b_off, b_len.
    This function is pure (no I/O) and is directly testable without hardware.
    """
    if bpp == 16:
        if (r_off, r_len, g_off, g_len, b_off, b_len) == (11, 5, 5, 6, 0, 5):
            return {"bpp": 16, "name": "RGB565", "bytes_pp": 2,
                    "r_off": 11, "r_len": 5, "g_off": 5, "g_len": 6, "b_off": 0, "b_len": 5}
        raise RuntimeError(
            f"Unsupported 16-bit framebuffer layout: "
            f"R={r_len}/{r_off} G={g_len}/{g_off} B={b_len}/{b_off} "
            f"(Nexus Screen requires RGB565: R=5/11 G=6/5 B=5/0)."
        )
    if bpp == 32:
        for ch_name, off, length in (("R", r_off, r_len), ("G", g_off, g_len), ("B", b_off, b_len)):
            if length != 8:
                raise RuntimeError(
                    f"Unsupported 32-bit framebuffer: {ch_name} channel is {length} bits "
                    f"(all channels must be 8 bits). "
                    f"Layout: R={r_len}/{r_off} G={g_len}/{g_off} B={b_len}/{b_off}."
                )
            if off + 8 > 32:
                raise RuntimeError(
                    f"Unsupported 32-bit framebuffer: {ch_name} channel at bit offset {off} "
                    f"overflows 32 bits."
                )
        used = 0
        for off in (r_off, g_off, b_off):
            mask = 0xFF << off
            if used & mask:
                raise RuntimeError(
                    f"Unsupported 32-bit framebuffer: RGB channels overlap. "
                    f"Layout: R={r_len}/{r_off} G={g_len}/{g_off} B={b_len}/{b_off}."
                )
            used |= mask
        if r_off == 16 and g_off == 8 and b_off == 0:
            name = "BGRA8888"   # confirmed Voron 2.4 / BCM2708 format
        elif r_off == 0 and g_off == 8 and b_off == 16:
            name = "RGBA8888"
        else:
            name = f"32bpp-R8/{r_off}-G8/{g_off}-B8/{b_off}"
        return {"bpp": 32, "name": name, "bytes_pp": 4,
                "r_off": r_off, "r_len": 8, "g_off": g_off, "g_len": 8,
                "b_off": b_off, "b_len": 8}
    raise RuntimeError(
        f"Unsupported framebuffer: {bpp} bits per pixel. "
        f"Nexus Screen supports 16-bit RGB565 and compatible 32-bit framebuffers "
        f"with 8-bit R, G, B channels."
    )


def fb_info():
    """Return (width, height, stride, fmt) from /dev/fb0 sysfs + ioctl, or raise RuntimeError.

    fmt is the dict returned by _parse_fb_format().
    """
    try:
        stride = int(open("/sys/class/graphics/fb0/stride").read().strip())
        vsize  = open("/sys/class/graphics/fb0/virtual_size").read().strip()  # "W,H"
        fb_w, fb_h = (int(v) for v in vsize.split(","))
        bpp = int(open("/sys/class/graphics/fb0/bits_per_pixel").read().strip())
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Cannot read framebuffer sysfs: {exc}") from exc

    # Read channel layout via FBIOGET_VSCREENINFO ioctl.
    # struct fb_var_screeninfo layout (first 80 bytes, 20 × uint32):
    #   [0-5]  xres, yres, xres_v, yres_v, xoff, yoff
    #   [6]    bits_per_pixel   [7] grayscale
    #   [8-10] red   (offset, length, msb_right)
    #   [11-13] green  [14-16] blue  [17-19] transp
    try:
        with open("/dev/fb0", "rb") as f:
            raw = fcntl.ioctl(f, FBIOGET_VSCREENINFO, bytes(160))
        fields = struct.unpack_from("20I", raw)
        r_off, r_len = fields[8],  fields[9]
        g_off, g_len = fields[11], fields[12]
        b_off, b_len = fields[14], fields[15]
    except OSError:
        # Fallback when /dev/fb0 is not accessible for ioctl (test environments).
        # For 16-bit we know the format; for 32-bit the layout is ambiguous without ioctl.
        if bpp == 16:
            r_off, r_len, g_off, g_len, b_off, b_len = 11, 5, 5, 6, 0, 5   # RGB565
        else:
            raise RuntimeError(
                f"Cannot determine {bpp}-bit framebuffer pixel format: "
                f"/dev/fb0 not accessible for ioctl (FBIOGET_VSCREENINFO)."
            )

    return fb_w, fb_h, stride, _parse_fb_format(bpp, r_off, r_len, g_off, g_len, b_off, b_len)


def _read_pixels(fb_path, fb_w, fb_h, stride, fmt):
    """Read RGB pixel data from a framebuffer file.

    Returns three float32 arrays (r, g, b) shaped (fb_h, fb_w) with values in 0–255.
    Handles padded strides correctly for both 16-bit and 32-bit formats.
    This function is testable with any file, not only /dev/fb0.
    """
    import numpy as np
    bpp = fmt["bpp"]
    if bpp == 16:
        row_px = stride // 2                    # full row in pixels (may include padding)
        raw = (np.fromfile(fb_path, dtype=np.uint16, count=row_px * fb_h)
               .reshape(fb_h, row_px)[:, :fb_w])
        r = ((raw >> 11) & 0x1F).astype(np.float32) * (255.0 / 31)
        g = ((raw >>  5) & 0x3F).astype(np.float32) * (255.0 / 63)
        b = ( raw        & 0x1F).astype(np.float32) * (255.0 / 31)
    else:                                        # 32-bit: use detected channel offsets
        row_px = stride // 4
        raw32 = (np.fromfile(fb_path, dtype=np.uint32, count=row_px * fb_h)
                 .reshape(fb_h, row_px)[:, :fb_w])
        r = ((raw32 >> fmt["r_off"]) & 0xFF).astype(np.float32)
        g = ((raw32 >> fmt["g_off"]) & 0xFF).astype(np.float32)
        b = ((raw32 >> fmt["b_off"]) & 0xFF).astype(np.float32)
    return r, g, b


def screen(png=None):
    import numpy as np
    fb_w, fb_h, stride, fmt = fb_info()
    r, g, b = _read_pixels("/dev/fb0", fb_w, fb_h, stride, fmt)
    lum = r * 0.3 + g * 0.59 + b * 0.11
    if png:
        from PIL import Image
        Image.fromarray(np.dstack([r.astype(np.uint8),
                                   g.astype(np.uint8),
                                   b.astype(np.uint8)])).save(png)
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
        try:
            mean, std = screen(args.png)
            r["screen_mean"], r["screen_contrast"] = round(mean, 1), round(std, 1)
            r["screen_not_black"] = mean > 8 and std > 10
        except ImportError:
            r["screen_not_black"] = None   # numpy absent — skip luminance check
            r["screen_warning"] = "numpy not installed; screen luminance check skipped"
        except RuntimeError as exc:
            r["screen_not_black"] = None
            r["screen_warning"] = str(exc)
    else:
        r["screen_not_black"] = False
    r["healthy"] = bool(essential and r["screen_not_black"] is not False)
    print(json.dumps(r, indent=1))
    return 0 if r["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
