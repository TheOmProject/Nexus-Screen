#!/usr/bin/env python3
"""Nexus Screen boot splash: the intro once, then the wait loop until Nexus Screen takes the screen.

Started by nexus-splash.service before nexus-screen.service. ffmpeg decodes each video to raw RGB565
frames that are written straight into the framebuffer (no Qt, ~20 MB plus ffmpeg).

Handover with Nexus Screen, through files in RUN_DIR (/run/nexus-splash):
  player.pid   written at start: Nexus Screen knows a splash is on screen and keeps its window hidden
  ready        created by Nexus Screen when its first screen is ready to draw
  released     created here after the last frame; Nexus Screen then shows its window
The player also stops on SIGTERM and after --max-seconds (hard limit), and does nothing at all when
the disable file exists. If a video cannot be played, the still frame is held instead."""
import argparse
import ctypes
import fcntl
import os
import select
import signal
import subprocess
import sys
import time

W, H = 800, 480
FRAME = W * H * 2  # RGB565
KDSETMODE, KD_GRAPHICS = 0x4B3A, 1
PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL = 47, 4
T0 = time.monotonic()


def drop_capabilities():
    """ffmpeg (which parses the media files) runs without the player's console capability."""
    try:
        ctypes.CDLL(None, use_errno=True).prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0)
    except (OSError, AttributeError):
        pass


def log(msg):
    print(f"nexus-splash: {time.monotonic() - T0:6.2f}s {msg}", flush=True)


def wait_for_device(path, seconds):
    """At boot the splash may start a few ms before the display driver creates /dev/fb0."""
    end = time.monotonic() + seconds
    while not os.path.exists(path):
        if time.monotonic() >= end:
            return False
        time.sleep(0.05)
    return True


def other_holders(path):
    """PIDs (of this user) other than us that have the framebuffer open, e.g. a running Nexus Screen."""
    target, me, found = os.path.realpath(path), os.getpid(), []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        if int(pid) == me:
            continue
        try:
            fds = os.listdir(f"/proc/{pid}/fd")
        except OSError:
            continue
        for fd in fds:
            try:
                if os.readlink(f"/proc/{pid}/fd/{fd}") == target:
                    found.append(int(pid))
                    break
            except OSError:
                pass
    return found


class Framebuffer:
    """Whole-frame writes at offset 0; refuses anything but a 800x480 16-bit framebuffer."""

    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR)
        self.stride = W * 2
        if path.startswith("/dev/fb"):
            sysfs = "/sys/class/graphics/" + os.path.basename(path)
            size = open(sysfs + "/virtual_size").read().strip()
            bpp = int(open(sysfs + "/bits_per_pixel").read())
            if not size.startswith(f"{W},") or bpp != 16:
                raise SystemExit(f"nexus-splash: {path} is {size} at {bpp} bpp, expected {W}x{H} at 16 — not drawing")
            self.stride = int(open(sysfs + "/stride").read())

    def show(self, frame):
        if self.stride == W * 2:
            os.pwrite(self.fd, frame, 0)
        else:
            for y in range(H):
                os.pwrite(self.fd, frame[y * W * 2:(y + 1) * W * 2], y * self.stride)


class Splash:
    def __init__(self, args):
        self.args = args
        self.fb = Framebuffer(args.fb)
        self.run = args.run_dir
        self.deadline = T0 + args.max_seconds
        self.stop_reason = None
        self.frames = 0
        self._graphics_at = 0.0
        self._graphics_failed = False
        signal.signal(signal.SIGTERM, lambda *_: self._stop("SIGTERM"))
        signal.signal(signal.SIGINT, lambda *_: self._stop("SIGINT"))

    def _stop(self, why):
        self.stop_reason = self.stop_reason or why

    def graphics_mode(self):
        """Keep the console in graphics mode (no text or cursor over the video). Re-applied while
        playing because nexus-screen.service resets tty7 to text mode when it starts."""
        if not self.args.tty or time.monotonic() - self._graphics_at < 0.5:
            return
        self._graphics_at = time.monotonic()
        # write-only is enough for the ioctl (group tty may write); the kernel additionally requires
        # CAP_SYS_TTY_CONFIG, the one capability nexus-splash.service grants
        try:
            fd = os.open(self.args.tty, os.O_WRONLY | os.O_NOCTTY)
            try:
                fcntl.ioctl(fd, KDSETMODE, KD_GRAPHICS)
            finally:
                os.close(fd)
        except OSError as e:
            if not self._graphics_failed:
                self._graphics_failed = True
                log(f"console graphics mode not set ({e}); continuing")

    def should_stop(self):
        if self.stop_reason is None:
            if os.path.exists(os.path.join(self.run, "ready")):
                self.stop_reason = "Nexus Screen ready"
            elif time.monotonic() >= self.deadline:
                self.stop_reason = f"time limit {self.args.max_seconds}s"
        return self.stop_reason is not None

    def _read_frame(self, fd):
        """Next frame from ffmpeg; None at the end of the video, b"" if a stop condition came first.
        Waits in 50 ms steps so a stall in ffmpeg never delays the handover."""
        buf = bytearray()
        while len(buf) < FRAME:
            if self.should_stop():
                return b""
            if not select.select([fd], [], [], 0.05)[0]:
                continue
            chunk = os.read(fd, FRAME - len(buf))
            if not chunk:
                return None
            buf += chunk
        return bytes(buf)

    def _wait_until(self, t):
        while not self.should_stop() and time.monotonic() < t:
            time.sleep(min(0.05, max(0.0, t - time.monotonic())))

    def play(self, path, loop=False):
        """Play until the video ends or a stop condition; False if nothing could be shown.
        ffmpeg decodes ahead only as far as the pipe allows; frames are paced here at --fps."""
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-threads", "2"] + (["-stream_loop", "-1"] if loop else []) + \
              ["-i", path, "-an", "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb565le", "-"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                                    preexec_fn=drop_capabilities)
        except OSError as e:
            log(f"cannot start ffmpeg: {e}")
            return False
        shown, period, base = 0, 1.0 / self.args.fps, None
        try:
            while True:
                frame = self._read_frame(proc.stdout.fileno())
                if not frame:
                    break
                if base is None or time.monotonic() - (base + shown * period) > 0.5:
                    base = time.monotonic() - shown * period  # first frame, or far behind: no catch-up burst
                self._wait_until(base + shown * period)
                if self.should_stop():
                    break
                self.fb.show(frame)
                shown += 1
                self.graphics_mode()
        finally:
            proc.stdout.close()  # ffmpeg may be blocked writing the next frame: end it at once
            proc.kill()
            proc.wait()
            err = proc.stderr.read().decode(errors="replace").strip()
        self.frames += shown
        log(f"{os.path.basename(path)}: {shown} frames" + (f" ({err.splitlines()[-1]})" if err and not shown else ""))
        return shown > 0

    def hold_still(self):
        try:
            frame = open(self.args.still, "rb").read()
        except OSError as e:
            log(f"still frame unavailable: {e}")
            frame = b""
        if len(frame) == FRAME:
            self.fb.show(frame)
            log("holding the still frame")
        while not self.should_stop():
            self.graphics_mode()
            if len(frame) == FRAME:
                self.fb.show(frame)  # repaint: the console may have drawn over it
            time.sleep(0.1)

    def main(self):
        os.makedirs(self.run, exist_ok=True)
        for name in ("ready", "released"):
            try:
                os.remove(os.path.join(self.run, name))
            except FileNotFoundError:
                pass
        with open(os.path.join(self.run, "player.pid"), "w") as fh:
            fh.write(str(os.getpid()))
        self.graphics_mode()
        played = self.play(self.args.intro)
        if not self.should_stop():
            if not self.play(self.args.loop, loop=True) and not self.should_stop():
                self.hold_still()
        elif not played:
            self.hold_still()
        open(os.path.join(self.run, "released"), "w").close()
        log(f"stopped: {self.stop_reason or 'end'} — {self.frames} frames shown, screen released")
        return 0


def parse(argv=None):
    home = os.path.join(os.path.expanduser("~"), "nexus-splash")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fb", default="/dev/fb0")
    ap.add_argument("--tty", default="/dev/tty7", help="console to switch to graphics mode ('' = leave it)")
    ap.add_argument("--run-dir", default="/run/nexus-splash")
    ap.add_argument("--intro", default=f"{home}/build/intro.mp4")
    ap.add_argument("--loop", default=f"{home}/build/loop.mp4")
    ap.add_argument("--still", default=f"{home}/build/still.rgb565")
    ap.add_argument("--disable-file", default=f"{home}/DISABLED")
    ap.add_argument("--max-seconds", type=float, default=90)
    ap.add_argument("--fps", type=float, default=24, help="frame rate of the built media")
    ap.add_argument("--wait-fb", type=float, default=10, help="seconds to wait for the framebuffer at boot")
    return ap.parse_args(argv)


if __name__ == "__main__":
    a = parse()
    if os.path.exists(a.disable_file):
        log(f"disabled ({a.disable_file} exists) — not drawing")
        sys.exit(0)
    if not wait_for_device(a.fb, a.wait_fb):
        log(f"{a.fb} did not appear within {a.wait_fb:g}s — not drawing")
        sys.exit(0)
    busy = other_holders(a.fb)
    if busy:  # never draw over a display client that is already running
        log(f"{a.fb} already in use by pid(s) {busy} — not drawing")
        sys.exit(0)
    sys.exit(Splash(a).main())
