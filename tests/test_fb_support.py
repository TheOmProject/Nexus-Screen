"""Tests for framebuffer format detection and pixel reading (deploy/healthcheck.py).

All tests run without hardware — they operate on pure logic and synthetic temp files.

    python3 tests/test_fb_support.py
"""
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from deploy.healthcheck import _parse_fb_format, _read_pixels

failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def raises(fn, match=None):
    try:
        fn()
        return False
    except RuntimeError as e:
        return match is None or match in str(e)


# ── helpers ───────────────────────────────────────────────────────────────────

RGB565_FMT = {"bpp": 16, "name": "RGB565", "bytes_pp": 2,
              "r_off": 11, "r_len": 5, "g_off": 5, "g_len": 6, "b_off": 0, "b_len": 5}

BGRA8888_FMT = {"bpp": 32, "name": "BGRA8888", "bytes_pp": 4,
                "r_off": 16, "r_len": 8, "g_off": 8, "g_len": 8, "b_off": 0, "b_len": 8}

RGBA8888_FMT = {"bpp": 32, "name": "RGBA8888", "bytes_pp": 4,
                "r_off": 0, "r_len": 8, "g_off": 8, "g_len": 8, "b_off": 16, "b_len": 8}


def write_fb16(pixels_hw, stride_px=None):
    h, w = pixels_hw.shape
    if stride_px is None:
        stride_px = w
    padded = np.zeros((h, stride_px), dtype=np.uint16)
    padded[:, :w] = pixels_hw
    fd, path = tempfile.mkstemp(suffix=".fb")
    os.write(fd, padded.tobytes())
    os.close(fd)
    return path


def write_fb32(r_ch, g_ch, b_ch, fmt, stride_px=None):
    h, w = r_ch.shape
    if stride_px is None:
        stride_px = w
    packed = (((r_ch.astype(np.uint32)) << fmt["r_off"]) |
              ((g_ch.astype(np.uint32)) << fmt["g_off"]) |
              ((b_ch.astype(np.uint32)) << fmt["b_off"]))
    padded = np.zeros((h, stride_px), dtype=np.uint32)
    padded[:, :w] = packed
    fd, path = tempfile.mkstemp(suffix=".fb")
    os.write(fd, padded.tobytes())
    os.close(fd)
    return path


# ── _parse_fb_format: accepted formats ───────────────────────────────────────

fmt = _parse_fb_format(16, 11, 5, 5, 6, 0, 5)
check(fmt["name"] == "RGB565",   "_parse_fb_format: 16-bit RGB565 accepted")
check(fmt["bpp"] == 16,          "_parse_fb_format: 16-bit bpp field correct")
check(fmt["bytes_pp"] == 2,      "_parse_fb_format: 16-bit bytes_pp correct")

fmt32 = _parse_fb_format(32, 16, 8, 8, 8, 0, 8)
check(fmt32["name"] == "BGRA8888",  "_parse_fb_format: 32-bit BGRA8888 accepted (Voron 2.4)")
check(fmt32["bpp"] == 32,           "_parse_fb_format: 32-bit BGRA bpp correct")
check(fmt32["bytes_pp"] == 4,       "_parse_fb_format: 32-bit bytes_pp correct")

fmt32r = _parse_fb_format(32, 0, 8, 8, 8, 16, 8)
check(fmt32r["name"] == "RGBA8888",  "_parse_fb_format: 32-bit RGBA8888 accepted")

fmt32a = _parse_fb_format(32, 8, 8, 16, 8, 24, 8)
check(fmt32a["bpp"] == 32 and "32bpp" in fmt32a["name"],
      "_parse_fb_format: 32-bit arbitrary 8-bit channels accepted")

# ── _parse_fb_format: rejected formats ───────────────────────────────────────

check(raises(lambda: _parse_fb_format(16, 10, 5, 5, 6, 0, 5), "Unsupported 16-bit"),
      "_parse_fb_format: non-RGB565 16-bit rejected")

check(raises(lambda: _parse_fb_format(16, 0, 5, 5, 6, 11, 5), "Unsupported 16-bit"),
      "_parse_fb_format: BGR565 rejected")

check(raises(lambda: _parse_fb_format(32, 16, 6, 8, 8, 0, 8), "channel is"),
      "_parse_fb_format: 32-bit non-8-bit channel rejected")

check(raises(lambda: _parse_fb_format(32, 28, 8, 8, 8, 0, 8), "overflows"),
      "_parse_fb_format: 32-bit channel overflow rejected")

check(raises(lambda: _parse_fb_format(32, 0, 8, 4, 8, 8, 8), "overlap"),
      "_parse_fb_format: 32-bit overlapping channels rejected")

check(raises(lambda: _parse_fb_format(24, 16, 8, 8, 8, 0, 8), "bits per pixel"),
      "_parse_fb_format: 24-bit bpp rejected")

check(raises(lambda: _parse_fb_format(8, 0, 3, 3, 3, 6, 2), "bits per pixel"),
      "_parse_fb_format: 8-bit bpp rejected")

# ── _read_pixels: 16-bit RGB565 ───────────────────────────────────────────────

px = np.full((4, 8), 0xF800, dtype=np.uint16)   # pure red
path = write_fb16(px)
r, g, b = _read_pixels(path, 8, 4, 8 * 2, RGB565_FMT)
os.unlink(path)
check(r.mean() > 240 and g.mean() < 5 and b.mean() < 5,
      "_read_pixels 16-bit: pure red decoded correctly")

px = np.full((4, 8), 0x07E0, dtype=np.uint16)   # pure green
path = write_fb16(px)
r, g, b = _read_pixels(path, 8, 4, 8 * 2, RGB565_FMT)
os.unlink(path)
check(g.mean() > 240 and r.mean() < 5 and b.mean() < 5,
      "_read_pixels 16-bit: pure green decoded correctly")

px = np.full((4, 8), 0x001F, dtype=np.uint16)   # pure blue
path = write_fb16(px)
r, g, b = _read_pixels(path, 8, 4, 8 * 2, RGB565_FMT)
os.unlink(path)
check(b.mean() > 240 and r.mean() < 5 and g.mean() < 5,
      "_read_pixels 16-bit: pure blue decoded correctly")

px = np.full((4, 8), 0xF800, dtype=np.uint16)
path = write_fb16(px, stride_px=16)
r, g, b = _read_pixels(path, 8, 4, 16 * 2, RGB565_FMT)
os.unlink(path)
check(r.shape == (4, 8) and r.mean() > 240,
      "_read_pixels 16-bit: padded stride trimmed correctly")

px = np.full((4, 8), 0xFFFF, dtype=np.uint16)   # white
path = write_fb16(px)
r, g, b = _read_pixels(path, 8, 4, 8 * 2, RGB565_FMT)
os.unlink(path)
lum = r * 0.3 + g * 0.59 + b * 0.11
check(lum.mean() > 200, "_read_pixels 16-bit: white luminance > 200")

# ── _read_pixels: 32-bit BGRA8888 ────────────────────────────────────────────

rc = np.full((4, 8), 255, dtype=np.uint8)
zc = np.zeros((4, 8), dtype=np.uint8)

path = write_fb32(rc, zc, zc, BGRA8888_FMT)
r, g, b = _read_pixels(path, 8, 4, 8 * 4, BGRA8888_FMT)
os.unlink(path)
check(r.mean() > 250 and g.mean() < 5 and b.mean() < 5,
      "_read_pixels 32-bit BGRA8888: pure red decoded correctly")

path = write_fb32(zc, zc, rc, BGRA8888_FMT)
r, g, b = _read_pixels(path, 8, 4, 8 * 4, BGRA8888_FMT)
os.unlink(path)
check(b.mean() > 250 and r.mean() < 5,
      "_read_pixels 32-bit BGRA8888: pure blue decoded correctly")

# ── _read_pixels: 32-bit RGBA8888 ────────────────────────────────────────────

path = write_fb32(zc, rc, zc, RGBA8888_FMT)
r, g, b = _read_pixels(path, 8, 4, 8 * 4, RGBA8888_FMT)
os.unlink(path)
check(g.mean() > 250 and r.mean() < 5 and b.mean() < 5,
      "_read_pixels 32-bit RGBA8888: pure green decoded correctly")

# ── _read_pixels: 32-bit padded stride ───────────────────────────────────────

r50 = np.full((4, 8), 200, dtype=np.uint8)
g50 = np.full((4, 8), 100, dtype=np.uint8)
b50 = np.full((4, 8),  50, dtype=np.uint8)
path = write_fb32(r50, g50, b50, BGRA8888_FMT, stride_px=16)
r, g, b = _read_pixels(path, 8, 4, 16 * 4, BGRA8888_FMT)
os.unlink(path)
check(r.shape == (4, 8) and abs(r.mean() - 200) < 2 and abs(g.mean() - 100) < 2,
      "_read_pixels 32-bit: padded stride trimmed correctly")

# ── summary ───────────────────────────────────────────────────────────────────

print()
if failures:
    print(f"FAILED {len(failures)} test(s):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print(f"All {25 - len(failures)} tests passed.")
