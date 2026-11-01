"""Regression test: interactive buttons must stay within screen bounds at all supported resolutions.

Any QAbstractButton whose window-coordinate rect extends outside the window dimensions is a
functional bug on that display — the user cannot reach that control.

    QT_QPA_PLATFORM=offscreen python3 tests/test_button_bounds.py

The test runs a clean subprocess at each resolution so that nexus.config is initialised
with the correct SCREEN_W / SCREEN_H values (they are read once at module import time).
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKER = os.path.join(ROOT, "tests", "_check_screen_bounds.py")
PY = os.environ.get("NEXUS_PY", sys.executable)

RESOLUTIONS = [
    (480,  320,  "CB1 / 480×320 — minimum supported"),
    (800,  480,  "reference / design size"),
    (1024, 600,  "tablet display"),
    (1920, 1080, "HD monitor"),
]

failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


for w, h, label in RESOLUTIONS:
    env = dict(
        os.environ,
        QT_QPA_PLATFORM="offscreen",
        NEXUS_SCREEN_W=str(w),
        NEXUS_SCREEN_H=str(h),
    )
    result = subprocess.run(
        [PY, "-I", CHECKER], env=env, capture_output=True, text=True, timeout=90
    )
    output = result.stdout.strip()
    if output:
        for line in output.splitlines():
            if not line.startswith("violations="):
                print(line)
    if result.returncode != 0 and result.stderr.strip():
        for line in result.stderr.strip().splitlines():
            if "error" in line.lower() or "traceback" in line.lower() or "Exception" in line:
                print(f"  stderr: {line}")
    check(result.returncode == 0, f"no buttons out of bounds at {w}x{h} ({label})")

print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
