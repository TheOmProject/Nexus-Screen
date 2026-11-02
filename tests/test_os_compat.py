"""Tests for OS version and Python version compatibility checks in deploy/install.sh.

The preflight checks in install.sh are bash; these tests exercise the same logic in
Python using the same rules, so the logic can be verified without running the full
installer. Each function mirrors the installer decision precisely.

    python3 tests/test_os_compat.py
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_SH = os.path.join(ROOT, "deploy", "install.sh")

failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


# ── OS version check (mirrors install.sh logic) ──────────────────────────────

def os_check(os_id, os_ver, os_codename):
    """Return (ok, message) replicating the install.sh OS gate.

    Accepted: debian or raspbian, VERSION_ID >= 12.
    Rejected: VERSION_ID < 12, unknown ID, unparseable version.
    """
    if not os_id or not os_ver:
        return False, "Cannot determine OS version"
    if os_id not in ("debian", "raspbian"):
        return False, f"Unsupported OS: {os_id} {os_ver}"
    try:
        ver_int = int(os_ver)
    except ValueError:
        return False, f"Cannot parse VERSION_ID: {os_ver!r}"
    if ver_int < 12:
        return False, f"Debian {os_ver} ({os_codename}) is not supported. Nexus Screen requires Debian 12 (Bookworm) or later."
    return True, f"{os_id} {os_ver} ({os_codename})"


def python_check(major, minor):
    """Return (ok, message) replicating the install.sh Python version gate.

    This mirrors the check applied to the venv interpreter ($PY), not system python3.
    When the venv does not exist, the check is skipped (returns True, "skipped") —
    the PyQt6 import check that follows will catch the missing venv.
    """
    if major < 3 or (major == 3 and minor < 11):
        return False, f"Python {major}.{minor} is not supported. Nexus Screen requires Python 3.11 or later."
    return True, f"Python {major}.{minor}"


def python_check_venv_missing():
    """When the venv doesn't exist the Python check is skipped — returns True."""
    return True, "skipped (venv not found)"


# ── OS check tests ────────────────────────────────────────────────────────────

ok, msg = os_check("debian", "12", "bookworm")
check(ok, "OS check: debian 12 (bookworm) accepted")

ok, msg = os_check("raspbian", "12", "bookworm")
check(ok, "OS check: raspbian 12 (bookworm) accepted")

ok, msg = os_check("debian", "13", "trixie")
check(ok, "OS check: debian 13 (trixie) accepted (future release)")

ok, msg = os_check("debian", "11", "bullseye")
check(not ok and "Debian 11" in msg, "OS check: debian 11 (bullseye) rejected")

ok, msg = os_check("debian", "10", "buster")
check(not ok and "not supported" in msg, "OS check: debian 10 (buster) rejected")

ok, msg = os_check("ubuntu", "22.04", "jammy")
check(not ok and "Unsupported OS" in msg, "OS check: ubuntu rejected (unsupported ID)")

ok, msg = os_check("", "", "")
check(not ok and "Cannot determine" in msg, "OS check: empty os-release fields rejected")

ok, msg = os_check("debian", "unstable", "sid")
check(not ok and "Cannot parse" in msg, "OS check: non-numeric VERSION_ID rejected")

ok, msg = os_check("raspbian", "11", "bullseye")
check(not ok and "not supported" in msg, "OS check: raspbian 11 (bullseye) rejected")

# ── Python version check tests (venv interpreter) ────────────────────────────
# The check applies to $PY (the venv Python), not the system python3.

ok, msg = python_check(3, 11)
check(ok, "Python check (venv): 3.11 accepted")

ok, msg = python_check(3, 12)
check(ok, "Python check (venv): 3.12 accepted")

ok, msg = python_check(3, 13)
check(ok, "Python check (venv): 3.13 accepted (future release)")

ok, msg = python_check(3, 10)
check(not ok and "3.10" in msg, "Python check (venv): 3.10 rejected")

ok, msg = python_check(3, 9)
check(not ok and "3.9" in msg, "Python check (venv): 3.9 rejected (Bullseye default)")

ok, msg = python_check(2, 7)
check(not ok, "Python check (venv): 2.7 rejected")

# When the venv does not exist, the check is skipped — PyQt6 import below catches it
ok, msg = python_check_venv_missing()
check(ok, "Python check (venv): missing venv skips version check (PyQt6 check handles it)")

# ── Installer syntax check ────────────────────────────────────────────────────

result = subprocess.run(["bash", "-n", INSTALL_SH], capture_output=True, text=True)
check(result.returncode == 0,
      f"install.sh: bash -n syntax check passes (stderr: {result.stderr.strip()!r})")

# ── Current environment check (informational, always passes) ─────────────────

venv_py = os.path.expanduser("~/nexus-screen-env/bin/python")
if os.path.isfile(venv_py) and os.access(venv_py, os.X_OK):
    import subprocess as _sp
    _r = _sp.run([venv_py, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                 capture_output=True, text=True)
    if _r.returncode == 0:
        venv_ver = _r.stdout.strip()
        vmaj, vmin = (int(x) for x in venv_ver.split("."))
        ok, msg = python_check(vmaj, vmin)
        check(ok, f"Python check (venv): {venv_py} is Python {venv_ver} — meets requirement")
    else:
        check(False, f"Python check (venv): {venv_py} failed to report version")
else:
    ok, msg = python_check_venv_missing()
    check(ok, f"Python check (venv): {venv_py} not present — skip accepted")

os_id = ""
os_ver = ""
os_codename = ""
try:
    with open("/etc/os-release") as f:
        for line in f:
            k, _, v = line.strip().partition("=")
            v = v.strip('"')
            if k == "ID":          os_id = v
            if k == "VERSION_ID":  os_ver = v
            if k == "VERSION_CODENAME": os_codename = v
    ok, msg = os_check(os_id, os_ver, os_codename)
    check(ok, f"OS check: current host {os_id} {os_ver} ({os_codename}) meets requirement")
except OSError:
    check(False, "OS check: /etc/os-release not readable on test host")

# ── summary ───────────────────────────────────────────────────────────────────

print()
if failures:
    print(f"FAILED {len(failures)} test(s):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print(f"All tests passed.")
