# Nexus Screen — Installation Guide

This guide covers a fresh installation of Nexus Screen on a compatible Raspberry Pi.

**Tested configurations:** Raspberry Pi 4 (2 GB) with 800×480 DSI touchscreen;
BigTreeTech CB1 with 480×320 DSI touchscreen; Voron 2.4 with 32-bit BCM2708 framebuffer.
OS: 64-bit Debian 12 (Bookworm) or Raspberry Pi OS based on Bookworm (aarch64).
Klipper + Moonraker (MainsailOS or FluiddOS).

**Operating system requirement:** Debian 12 (Bookworm) or later. Debian 11 (Bullseye) is
**not supported** — see [Why Debian 12 or later?](#why-debian-12-or-later) below.

**Python requirement:** Python 3.11 or later. Bookworm ships Python 3.11 by default.

**Display requirement:** the framebuffer at `/dev/fb0` must be 16-bit RGB565 or a 32-bit
framebuffer with 8-bit R, G, B channels (BGRA8888 / RGBA8888). Nexus Screen auto-detects
the resolution and scales to fit; 800×480 is the reference resolution.

---

## Prerequisites

Before you begin:

1. **Debian 12 (Bookworm) or Raspberry Pi OS (Bookworm), 64-bit:**
   ```bash
   cat /etc/os-release   # VERSION_ID must be 12 or higher
   uname -m              # must print aarch64
   ```
   Debian 11 (Bullseye) is not supported. See [Why Debian 12 or later?](#why-debian-12-or-later).

2. **Klipper and Moonraker must be running.** Verify with:
   ```bash
   systemctl is-active klipper moonraker
   ```
   Both should report `active`.

3. **Klipper must be in the `ready` state** (not error/disconnected):
   ```bash
   curl -s http://localhost:7125/printer/info | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["state"])'
   ```
   Should print `ready`.

4. **A framebuffer display at `/dev/fb0`** (16-bit RGB565 or 32-bit with 8-bit R, G, B channels):
   ```bash
   ls /dev/fb0
   cat /sys/class/graphics/fb0/bits_per_pixel   # 16 (RGB565) or 32 (BGRA8888 etc.)
   cat /sys/class/graphics/fb0/virtual_size      # prints W,H — detected automatically
   ```

---

## Step 1 — Install Dependencies

PyQt6 and NumPy are available from the Debian 12 / Raspberry Pi OS (Bookworm) package repository:

```bash
sudo apt update
sudo apt install python3-pyqt6 python3-numpy
```

Verify:
```bash
python3 -c "import PyQt6.QtWidgets; print('PyQt6 OK')"
python3 -c "import numpy; print('NumPy OK')"
```

NumPy is required for `deploy/healthcheck.py` to read and validate the framebuffer
after installation. The app itself runs without NumPy, but the installer will warn
and the health check will skip the screen-content check if it is absent.

> **Debian 11 (Bullseye) note:** `python3-pyqt6` is not in the Bullseye apt repository.
> A pip-based workaround exists (PyQt6 6.7.1 on manylinux_2_28) but the framebuffer
> hardware rendering path has not been validated on Bullseye hardware, and PyQt6 would
> be permanently pinned at an old version. Nexus Screen does not officially support
> Bullseye. Please upgrade to Bookworm.

---

## Step 2 — Clone the Repository

```bash
git clone https://github.com/omarmunoz5371/Nexus-Screen.git ~/nexus-screen
```

---

## Step 3 — Create the Python Virtual Environment

```bash
python3 -m venv ~/nexus-screen-env --system-site-packages
```

The `--system-site-packages` flag makes the venv use the system-installed PyQt6.

Verify PyQt6 is accessible from the venv:
```bash
~/nexus-screen-env/bin/python -c "import PyQt6.QtWidgets; print('PyQt6 OK in venv')"
```

---

## Step 4 — Dry Run

Run the installer in dry-run mode first. It checks all prerequisites and prints what it will do — **no changes are made**:

```bash
sudo ~/nexus-screen/deploy/install.sh
```

Review the output. If any check fails, fix the issue before proceeding.

---

## Step 5 — Install

```bash
sudo ~/nexus-screen/deploy/install.sh --confirm
```

The installer will:
1. Create a backup of your current interface state to `~/nexus-screen-backups/deploy-<timestamp>/`
2. Stop and disable KlipperScreen if it is running (not uninstalled — restorable with `rollback.sh`)
3. Install and start `nexus-screen.service`
4. Run a health check for up to 40 seconds
5. **Automatically roll back** if the health check fails, restoring your previous state

---

## Step 6 — Verify

After a successful install, the touchscreen should show the Nexus Screen interface.
Run the health check manually to confirm everything is working:

```bash
~/nexus-screen-env/bin/python ~/nexus-screen/deploy/healthcheck.py
```

Check the service status:
```bash
systemctl status nexus-screen
journalctl -u nexus-screen -b
```

---

## Optional: Enable Printer Commands

By default, Nexus Screen runs in read-only mode — it displays printer status but does not
send commands (Pause, Resume, Stop, Baby Step). To enable commands:

```bash
# Dry run first
sudo ~/nexus-screen/deploy/commands.sh enable

# Enable (restarts the service; auto-reverts on health check failure)
sudo ~/nexus-screen/deploy/commands.sh enable --confirm
```

---

## Optional: Boot Splash

Nexus Screen includes a cinematic boot splash sequence. It is **optional** and installed
separately. The splash media files must be built locally from source — they are not
distributed in the repository.

See `docs/SPLASH.md` for setup instructions.

---

## Recovery

If Nexus Screen fails to start or the screen goes black, you can recover over SSH:

```bash
sudo ~/nexus-screen/deploy/rollback.sh --confirm
```

See [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) and [docs/UNINSTALL.md](UNINSTALL.md).

---

## Why Debian 12 or later?

Nexus Screen requires Debian 12 (Bookworm) or Raspberry Pi OS based on Bookworm.
Debian 11 (Bullseye) is explicitly rejected by the installer. Here is why:

| Requirement | Debian 11 (Bullseye) | Debian 12 (Bookworm) |
|---|---|---|
| `python3-pyqt6` in apt | **Not available** | ✓ 6.4.2 |
| Python default version | 3.9 | ✓ 3.11 |
| glibc version | 2.31 | 2.36 |
| Bullseye LTS support | **Ended April 2024** | Active |

**Why not install PyQt6 via pip on Bullseye?**

A pip installation path technically exists: PyQt6 6.7.1 (`manylinux_2_28_aarch64`) is the
last release compatible with Bullseye's glibc 2.31 (PyQt6 6.8.0 and later require glibc 2.39).
PyQt6 6.8.0+ are not installable on Bullseye — so the version would be permanently frozen at 6.7.x.

The more important reason: the framebuffer hardware rendering path (Qt linuxfb plugin from the
pip-bundled Qt) has **not been validated on Bullseye hardware**. Working Qt rendering on the
framebuffer depends on the linuxfb plugin, its `libdrm.so.2` dependency, and the kernel DRM
interface. Without physical hardware testing on a Bullseye machine connected to a real
framebuffer display, the interaction between the pip-bundled Qt 6.7 and the older Bullseye
kernel/driver stack cannot be guaranteed.

**Recommended action:** upgrade to Raspberry Pi OS Bookworm (or Debian 12). MainsailOS and
FluiddOS both offer Bookworm images. Upgrading in-place from Bullseye to Bookworm is possible
but a fresh image is more reliable. See the MainsailOS or FluiddOS documentation for upgrade paths.
