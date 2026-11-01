"""Boot splash: player sequence, stop conditions, fallback, kill switch, precheck and the handover to
Nexus Screen. Never touches the real screen: the "framebuffer" is a plain 768000-byte file.

    QT_QPA_PLATFORM=offscreen python3 tests/test_splash.py
"""
import os
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PLAYER = os.path.join(ROOT, "splash", "player.py")
FRAME = 800 * 480 * 2
failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def until(cond, s=10):
    end = time.monotonic() + s
    while not cond() and time.monotonic() < end:
        time.sleep(0.02)
    return cond()


tmp = tempfile.mkdtemp(prefix="nexus-splash-test-")
# short test clips (1 s intro, 1 s loop) so the sequence runs quickly
for name, src in (("intro.mp4", "testsrc=size=1280x720:rate=24:duration=1"),
                  ("loop.mp4", "smptebars=size=1280x720:rate=24:duration=1")):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", os.path.join(tmp, name)], check=True)
still = bytes([0x1F, 0xF8]) * (800 * 480)  # a solid colour, easy to recognise
open(os.path.join(tmp, "still.rgb565"), "wb").write(still)


def run(case, extra=(), intro="intro.mp4", loop="loop.mp4"):
    d = os.path.join(tmp, case)
    os.makedirs(d)
    fb = os.path.join(d, "fb")
    open(fb, "wb").write(bytes(FRAME))
    p = subprocess.Popen([sys.executable, PLAYER, "--fb", fb, "--tty", "", "--run-dir", os.path.join(d, "run"),
                          "--intro", os.path.join(tmp, intro), "--loop", os.path.join(tmp, loop),
                          "--still", os.path.join(tmp, "still.rgb565"),
                          "--disable-file", os.path.join(d, "DISABLED"), *extra],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p, fb, os.path.join(d, "run")


def finish(p):
    out, _ = p.communicate(timeout=10)
    return p.returncode, out


# 1. intro once, then the loop until Nexus Screen is ready
p, fb, rd = run("sequence")
check(until(lambda: os.path.exists(os.path.join(rd, "player.pid"))), "pid file written for Nexus Screen")
time.sleep(2.5)  # past the 1 s intro, into the loop
check(any(open(fb, "rb").read()), "frames reach the framebuffer")
t = time.monotonic()
open(os.path.join(rd, "ready"), "w").close()
check(until(lambda: os.path.exists(os.path.join(rd, "released")), 2), "released after 'ready'")
release_ms = (time.monotonic() - t) * 1000
check(release_ms < 250, f"released within one frame or two ({release_ms:.0f} ms)")
rc, out = finish(p)
check(rc == 0 and "intro.mp4: 24 frames" in out and "loop.mp4:" in out and "Nexus Screen ready" in out,
      f"intro played once (24 frames), then the loop, stop reason logged ({out.strip().splitlines()[-1]})")
check(not subprocess.run(["pgrep", "-f", os.path.join(tmp, "loop.mp4")], capture_output=True).stdout,
      "no ffmpeg left behind")

# 2. videos missing: the still frame is held instead
p, fb, rd = run("fallback", intro="missing.mp4", loop="missing2.mp4")
check(until(lambda: open(fb, "rb").read() == still, 5), "videos unplayable: still frame shown")
open(os.path.join(rd, "ready"), "w").close()
rc, out = finish(p)
check(rc == 0 and "holding the still frame" in out, "still frame held until ready, clean exit")

# 3. kill switch: nothing drawn, nothing written
d = os.path.join(tmp, "disabled")
os.makedirs(d)
fb = os.path.join(d, "fb")
open(fb, "wb").write(bytes(FRAME))
open(os.path.join(d, "DISABLED"), "w").close()
p = subprocess.Popen([sys.executable, PLAYER, "--fb", fb, "--tty", "", "--run-dir", os.path.join(d, "run"),
                      "--disable-file", os.path.join(d, "DISABLED")],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
rc, out = finish(p)
check(rc == 0 and "disabled" in out and not any(open(fb, "rb").read()) and not os.path.exists(os.path.join(d, "run")),
      "DISABLED file: exits at once, screen untouched")

# 4. hard time limit
p, fb, rd = run("limit", ["--max-seconds", "2"])
t = time.monotonic()
rc, out = finish(p)
check(rc == 0 and "time limit" in out and os.path.exists(os.path.join(rd, "released"))
      and time.monotonic() - t < 4, "stops by itself at --max-seconds")

# 5. SIGTERM (systemd stop)
p, fb, rd = run("sigterm")
until(lambda: os.path.exists(os.path.join(rd, "player.pid")))
time.sleep(0.5)
p.send_signal(signal.SIGTERM)
rc, out = finish(p)
check(rc == 0 and "SIGTERM" in out and os.path.exists(os.path.join(rd, "released")), "SIGTERM: clean stop")

# 5b. console mode refused: reported once, playback unaffected
d = os.path.join(tmp, "ttyfail")
os.makedirs(d)
fb = os.path.join(d, "fb")
open(fb, "wb").write(bytes(FRAME))
notatty = os.path.join(d, "not-a-tty")
open(notatty, "w").close()
p = subprocess.Popen([sys.executable, PLAYER, "--fb", fb, "--tty", notatty, "--run-dir", os.path.join(d, "run"),
                      "--intro", os.path.join(tmp, "intro.mp4"), "--loop", os.path.join(tmp, "loop.mp4"),
                      "--still", os.path.join(tmp, "still.rgb565"), "--disable-file", os.path.join(d, "X"),
                      "--max-seconds", "3"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
rc, out = finish(p)
check(rc == 0 and out.count("console graphics mode not set") == 1 and "intro.mp4: 24 frames" in out,
      f"console mode failure logged once, playback unaffected ({out.count('console graphics mode not set')}x)")

# 5c. boot: the framebuffer appears a moment after the splash starts
d = os.path.join(tmp, "latefb")
os.makedirs(d)
fb = os.path.join(d, "fb")
p = subprocess.Popen([sys.executable, PLAYER, "--fb", fb, "--tty", "", "--run-dir", os.path.join(d, "run"),
                      "--intro", os.path.join(tmp, "intro.mp4"), "--loop", os.path.join(tmp, "loop.mp4"),
                      "--still", os.path.join(tmp, "still.rgb565"), "--disable-file", os.path.join(d, "X"),
                      "--max-seconds", "3"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(0.6)
open(fb, "wb").write(bytes(FRAME))
rc, out = finish(p)
check(rc == 0 and "intro.mp4: 24 frames" in out, "framebuffer appearing late: the splash waits and plays")
d = os.path.join(tmp, "nofb")
os.makedirs(d)
t = time.monotonic()
p = subprocess.Popen([sys.executable, PLAYER, "--fb", os.path.join(d, "fb"), "--tty", "", "--run-dir",
                      os.path.join(d, "run"), "--disable-file", os.path.join(d, "X"), "--wait-fb", "1"],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
rc, out = finish(p)
check(rc == 0 and "did not appear" in out and time.monotonic() - t < 3, "no framebuffer at all: gives up quietly")

# 5d. a display client already on the screen (Nexus Screen running): never draw over it
d = os.path.join(tmp, "inuse")
os.makedirs(d)
fb = os.path.join(d, "fb")
open(fb, "wb").write(bytes(FRAME))
holder = subprocess.Popen([sys.executable, "-c", f"f=open({fb!r},'rb'); import time; time.sleep(30)"])
time.sleep(0.5)
p = subprocess.Popen([sys.executable, PLAYER, "--fb", fb, "--tty", "", "--run-dir", os.path.join(d, "run"),
                      "--disable-file", os.path.join(d, "X")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True)
rc, out = finish(p)
holder.kill(); holder.wait()
check(rc == 0 and "already in use" in out and not any(open(fb, "rb").read()) and not os.path.exists(os.path.join(d, "run")),
      "screen already in use: the splash draws nothing")

# 6. precheck: the splash player may hold the framebuffer, nothing else may
p, fb, rd = run("precheck")
until(lambda: os.path.exists(os.path.join(rd, "player.pid")))
pre = os.path.join(ROOT, "deploy", "precheck.sh")
r = subprocess.run([pre], env=dict(os.environ, NEXUS_FB=fb), capture_output=True, text=True)
check(r.returncode == 0, f"precheck allows the splash player ({r.stderr.strip()})")
other = subprocess.Popen([sys.executable, "-c", f"f=open({fb!r},'rb'); import time; time.sleep(30)"])
time.sleep(0.5)
r = subprocess.run([pre], env=dict(os.environ, NEXUS_FB=fb), capture_output=True, text=True)
check(r.returncode == 1 and str(other.pid) in r.stderr, "precheck still refuses any other display client")
other.kill(); other.wait()
p.send_signal(signal.SIGTERM); finish(p)

# 7. Nexus Screen side: hidden while the splash plays, shown once it has released the screen
from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from nexus.splash import Handover, splash_pid  # noqa: E402

app = QApplication(sys.argv)


def spin(cond, s=5):
    end = time.monotonic() + s
    while not cond() and time.monotonic() < end:
        loop = QEventLoop(); QTimer.singleShot(20, loop.quit); loop.exec()
    return cond()


p, fb, rd = run("handover")
until(lambda: os.path.exists(os.path.join(rd, "player.pid")))
check(splash_pid(rd) == p.pid, "Nexus Screen detects the running splash")
check(splash_pid(os.path.join(tmp, "nowhere")) is None, "no splash: normal start (window shown at once)")
shown = []
h = Handover(lambda: shown.append(os.path.exists(os.path.join(rd, "released"))), run_dir=rd, timeout_ms=30000)
h.on_data({"connected": False, "state": "offline"})
spin(lambda: False, 0.5)
check(not shown and h.state == "waiting", "window stays hidden while not yet connected")
h.on_data({"connected": True, "state": "standby"})
check(spin(lambda: shown), "connected: window shown")
check(shown == [True], "window shown only after the splash released the screen")
rc, out = finish(p)
check(rc == 0 and "Nexus Screen ready" in out, "splash stopped because Nexus Screen was ready")

p, fb, rd = run("timeout")
until(lambda: os.path.exists(os.path.join(rd, "player.pid")))
shown = []
h = Handover(lambda: shown.append(True), run_dir=rd, timeout_ms=600)
check(spin(lambda: shown, 4), "printer never connects: window shown after the timeout anyway")
finish(p)

p, fb, rd = run("hung")
until(lambda: os.path.exists(os.path.join(rd, "player.pid")))
time.sleep(0.3)
p.send_signal(signal.SIGSTOP)  # frozen splash: alive, never answers
shown = []
h = Handover(lambda: shown.append(time.monotonic()), run_dir=rd, timeout_ms=30000)
t = time.monotonic()
h.on_data({"connected": True})
check(spin(lambda: shown, 5) and shown[0] - t < 2.6, "frozen splash: Nexus Screen shows its window after <= 2 s anyway")
p.send_signal(signal.SIGCONT); p.send_signal(signal.SIGTERM); finish(p)

# 8. the real main.py hands over (simulator, offscreen)
p, fb, rd = run("main", ["--max-seconds", "40"])
until(lambda: os.path.exists(os.path.join(rd, "player.pid")))
app_proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "main.py")], cwd=ROOT,
                            env=dict(os.environ, NEXUS_SPLASH_DIR=rd, QT_QPA_PLATFORM="offscreen"),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t = time.monotonic()
rc, out = finish(p) if until(lambda: p.poll() is not None, 25) else (None, "")
check(rc == 0 and "Nexus Screen ready" in out,
      f"main.py signals ready and the splash stops ({time.monotonic() - t:.1f} s after app start)")
app_proc.send_signal(signal.SIGTERM)
check(app_proc.wait(timeout=10) == 0, "app keeps running normally and quits cleanly")

subprocess.run(["rm", "-rf", tmp])
print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
