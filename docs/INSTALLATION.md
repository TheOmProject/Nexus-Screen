# Nexus Screen — Installation Guide

This guide covers a fresh installation of Nexus Screen on a compatible Raspberry Pi.

**Tested configurations:** Raspberry Pi 4 (2 GB) with 800×480 DSI touchscreen;
BigTreeTech CB1 with 480×320 DSI touchscreen. OS: 64-bit Raspberry Pi OS (Bookworm, aarch64),
Klipper + Moonraker (MainsailOS or FluiddOS).

**Display requirement:** the framebuffer must be 16-bit RGB565 (`/sys/class/graphics/fb0/bits_per_pixel = 16`).
The installer rejects other depths. Nexus Screen auto-detects the resolution and scales to fit;
800×480 is the reference resolution.

---

## Prerequisites

Before you begin:

1. **Klipper and Moonraker must be running.** Verify with:
   ```bash
   systemctl is-active klipper moonraker
   ```
   Both should report `active`.

2. **Klipper must be in the `ready` state** (not error/disconnected):
   ```bash
   curl -s http://localhost:7125/printer/info | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["state"])'
   ```
   Should print `ready`.

3. **A 16-bit RGB565 framebuffer display at `/dev/fb0`:**
   ```bash
   ls /dev/fb0
   cat /sys/class/graphics/fb0/bits_per_pixel   # must print 16
   cat /sys/class/graphics/fb0/virtual_size      # prints W,H — detected automatically
   ```

4. **64-bit Raspberry Pi OS (aarch64):**
   ```bash
   uname -m   # should print aarch64
   ```

---

## Step 1 — Install Dependencies

PyQt6 and NumPy are available from the Raspberry Pi OS package repository:

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
