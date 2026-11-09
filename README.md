# Nexus Screen

> A cinematic touchscreen interface for Klipper 3D printers.

Nexus Screen is an independent, touch-optimized UI for printers running
[Klipper](https://klipper3d.org) and [Moonraker](https://moonraker.readthedocs.io).
It runs directly on the framebuffer (no desktop environment required) and is
designed for embedded 800×480 DSI touchscreen panels on Raspberry Pi.

**Status: Public Beta — v0.2.0-beta.6**  
See [Beta Limitations](#beta-limitations) before installing.

---

## Screenshots

| | |
|:---:|:---:|
| ![Home screen — ready state with temperatures and add-ons](docs/images/home.png) | ![Print Status — active print with thumbnail and progress](docs/images/print-status.png) |
| *Home — temperatures, printer status, and active add-ons* | *Print Status — live thumbnail, progress bar, and print controls* |
| ![Print paused — Baby Step Z offset controls](docs/images/print-paused.png) | ![Print Files — file browser with thumbnails](docs/images/print-files.png) |
| *Print paused — Baby Step Z offset adjustment* | *Print Files — file browser with gcode thumbnails* |
| ![Control section hub](docs/images/control.png) | ![Temperature — live heater tiles](docs/images/temperature.png) |
| *Control — motion, temperature, fans, lighting, and calibration* | *Temperature — live heater tiles with numeric keypad* |
| ![Filament management](docs/images/filament.png) | ![Settings section overview](docs/images/settings.png) |
| *Filament — load, profiles, BoxTurtle, and StealthChanger* | *Settings — configuration and tools overview* |

---

## Features

- **Adaptive display scaling** — auto-detects framebuffer resolution at startup; scales all layouts, fonts, and touch targets to fit; identity at 800×480
- **5 main sections** — Home, Print, Filament, Control, Settings
- **34 screens** reachable from a persistent sidebar
- **Print management** — full-screen print status, progress, thumbnail preview, Pause/Resume/Stop, Baby Step Z offset
- **Temperature control** — live heater tiles, numeric keypad, presets
- **Motion control** — Move (XYZ+E), Z Offset, Bed Screws, Bed Mesh visualization
- **Filament management** — filament profiles stored in Moonraker database, heat-then-load workflow
- **Add-on support** — BoxTurtle multi-material unit (AFC), StealthChanger toolchanger
- **Cinematic boot splash** — optional animated intro sequence (separate setup step)
- **Safe command gating** — printer commands (pause, resume, stop, baby step) are only sent when the app runs with `--allow-commands`; read-only mode is the default
- **Crash-safe deployment** — automatic health check and rollback on install failure

---

## Hardware Compatibility

| Hardware | Nexus Screen | Nexus Video | Notes |
|---|---|---|---|
| Raspberry Pi 4 (2 GB), 800×480 RGB565, Debian 12 | **PHYSICALLY VERIFIED** | NOT TESTED | Reference configuration; NS runtime + clean install verified |
| Raspberry Pi 4 (4 GB), Voron 2.4, 800×480 BGRA8888 | **PHYSICALLY VERIFIED** | NOT TESTED | 32-bit framebuffer path, v0.2.0-beta.4 |
| BigTreeTech CB1, 480×320 RGB565 | **PHYSICALLY VERIFIED** (runtime) | NOT TESTED | Real hardware bug found + fixed at v0.2.0-beta.2; clean install not separately verified |
| Raspberry Pi 3 | NOT TESTED | NOT TESTED | 64-bit OS required; preflight accepts |
| Raspberry Pi 5 | NOT TESTED | NOT TESTED | Community reports welcome |
| Raspberry Pi Zero 2 W | NOT TESTED | NOT TESTED | 512 MB RAM below installer minimum (900 MB) |
| HDMI displays | NOT TESTED | NOT TESTED | `/dev/fb0` must exist; depends on driver |
| SPI displays | NOT TESTED | NOT TESTED | `/dev/fb0` required; most SPI drivers don't expose one |
| Debian 11 Bullseye | **NOT SUPPORTED** | **NOT SUPPORTED** | Installer blocks; `python3-pyqt6` not in Bullseye apt |
| 32-bit ARM (armv7l) | **NOT SUPPORTED** | **NOT SUPPORTED** | Installer blocks; 64-bit aarch64 required |

**PHYSICALLY VERIFIED** = installed and confirmed working on real hardware with traceable evidence (not just code analysis).
**NOT TESTED** = may work but no hardware evidence; community reports welcome.
**NOT SUPPORTED** = installer explicitly blocks.

See **[docs/HARDWARE-COMPATIBILITY.md](docs/HARDWARE-COMPATIBILITY.md)** for full per-item evidence detail.

### Display Resolution

**Minimum supported resolution: 480×320.**

Nexus Screen and Nexus Video use adaptive scaling (`sx()`, `sy()` helpers) so all
layouts, fonts and touch targets scale to any display from 480×320 upward. The
interface was originally designed at 800×480, which remains the reference resolution
and delivers the best visual experience, but 480×320 is fully tested and all primary
controls remain touch-accessible at that size.

Displays below 480×320 are not supported. The installer will block with
"INSTALLATION BLOCKED" if the framebuffer reports a smaller size.

**For the best visual experience, an 800×480 display or larger is recommended.**

**Framebuffer requirement:** the display must expose a supported framebuffer at
`/dev/fb0`: **16-bit RGB565** (`bits_per_pixel = 16`) or a **32-bit framebuffer
with 8-bit R, G, B channels** (e.g. BGRA8888 as used by the BCM2708 driver on
Voron 2.4). Verify the bit depth with:

```bash
cat /sys/class/graphics/fb0/bits_per_pixel
```

Community reports of working or failing configurations are welcome via
[GitHub Issues](https://github.com/TheOmProject/Nexus-Screen/issues).

---

## Requirements

- Raspberry Pi 4 or BigTreeTech CB1, **Debian 12 (Bookworm) or Raspberry Pi OS (Bookworm), 64-bit**
  — Debian 11 (Bullseye) is **not supported** (see [docs/INSTALLATION.md](docs/INSTALLATION.md))
- Klipper and Moonraker installed and running
- Python 3.11 or later (included with Bookworm)
- PyQt6 ≥ 6.4 — installed via `apt`:
  ```bash
  sudo apt install python3-pyqt6
  ```
- NumPy — required for the health-check framebuffer read:
  ```bash
  sudo apt install python3-numpy
  # or: ~/nexus-screen-env/bin/pip install numpy
  ```
- A supported framebuffer at `/dev/fb0`: 16-bit RGB565 or a 32-bit framebuffer with
  8-bit R, G, B channels (BGRA8888, RGBA8888, or equivalent)

---

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/TheOmProject/Nexus-Screen/main/deploy/bootstrap.sh | bash
```

That's it. The installer will:

1. Check hardware compatibility — blocks with a clear message if requirements are not met
2. Offer to install missing packages automatically (`python3-pyqt6`, `git`, etc.)
3. Install Nexus Screen
4. Ask whether to also install **Nexus Video** (optional animated boot splash)
5. Register both repos with Moonraker Update Manager

> Run as your normal user, not as root. The script uses `sudo` only where it's required.

**Non-interactive (headless / CI):**

```bash
# Nexus Screen only
curl -fsSL https://raw.githubusercontent.com/TheOmProject/Nexus-Screen/main/deploy/bootstrap.sh | bash -s -- --yes

# Nexus Screen + Nexus Video
curl -fsSL https://raw.githubusercontent.com/TheOmProject/Nexus-Screen/main/deploy/bootstrap.sh | bash -s -- --yes --with-video

# Compatibility check only — no changes made
curl -fsSL https://raw.githubusercontent.com/TheOmProject/Nexus-Screen/main/deploy/bootstrap.sh | bash -s -- --dry-run
```

For manual installation, repair, rollback, and advanced options see
**[docs/INSTALLATION.md](docs/INSTALLATION.md)**.

---

## Optional Addons

### Nexus Video — Startup Animations

[Nexus Video](https://github.com/TheOmProject/Nexus-Video) is an independent, optional addon
that replaces the default static boot splash with animated video packs. It is **not required**
for Nexus Screen to function.

When Nexus Video is not installed, Nexus Screen displays an installation notice in the
**Settings → Startup Video** screen rather than crashing.

**Install via bootstrap (easiest):**
```bash
curl -fsSL https://raw.githubusercontent.com/TheOmProject/Nexus-Screen/main/deploy/bootstrap.sh | bash -s -- --with-video
```

**Add Nexus Video to an existing Nexus Screen installation:**
```bash
git clone https://github.com/TheOmProject/Nexus-Video.git ~/nexus-video
sudo bash ~/nexus-video/deploy/public-install.sh
```

See the [Nexus Video repository](https://github.com/TheOmProject/Nexus-Video) for custom pack
documentation, hardware requirements, and troubleshooting.

### Nexus Sounds — Audio Notifications

[Nexus Sounds](https://github.com/TheOmProject/Nexus-Sounds) is an **optional add-on** that
plays WAV notification sounds for printer events (startup, print start, print complete, print error,
and more). It is configured through the **Settings → Sounds** screen added in this release.

```bash
git clone https://github.com/TheOmProject/Nexus-Sounds.git ~/nexus-sounds
sudo bash ~/nexus-sounds/deploy/install.sh
```

When Nexus Sounds is not installed, the Sounds screen shows an installation notice
rather than crashing. Nexus Screen functions normally without it.

---

## Updating

### Via Moonraker Update Manager (recommended)

Add the following to your `moonraker.conf`, then restart Moonraker:

```ini
[update_manager nexus-screen]
type: git_repo
path: ~/nexus-screen
origin: https://github.com/TheOmProject/Nexus-Screen.git
primary_branch: main
is_system_service: False
```

If Nexus Video is installed, add its block separately:

```ini
[update_manager nexus-video]
type: git_repo
path: ~/nexus-video
origin: https://github.com/TheOmProject/Nexus-Video.git
primary_branch: main
is_system_service: False
managed_services: nexus-video
```

You can then update from the **Update Manager** panel in Mainsail or Fluidd.
After updating Nexus Screen, restart the service:

```bash
sudo systemctl restart nexus-screen
```

Custom packs and your selected startup video are preserved across all updates.

### Manual update

```bash
cd ~/nexus-screen && git pull
sudo systemctl restart nexus-screen
```

See [docs/moonraker-update-manager.md](docs/moonraker-update-manager.md) for details.

---

## Uninstalling

See **[docs/UNINSTALL.md](docs/UNINSTALL.md)**.

```bash
# Stop and disable Nexus Screen; restore KlipperScreen to its pre-install state
sudo ~/nexus-screen/deploy/rollback.sh --confirm
```

---

## Troubleshooting

See **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** for common problems and solutions.

```bash
# Check service status
systemctl status nexus-screen
journalctl -u nexus-screen -b

# Run the built-in health check
~/nexus-screen-env/bin/python ~/nexus-screen/deploy/healthcheck.py
```

---

## Beta Limitations

This is a **public beta**. The following are known limitations in v0.2.0-beta.6:

- **Physically verified on three hardware configurations** — see [Hardware Compatibility](#hardware-compatibility)
- **Minimum supported display resolution is 480×320** — all menus, buttons and popups are verified touch-accessible at 480×320 and above; 800×480 is the reference resolution and delivers the best visual density
- **Printer commands require explicit opt-in** — enabled separately with `deploy/commands.sh enable`
- **Boot splash requires separate media build** — see `docs/SPLASH.md`; the splash media is not
  distributed in the repository and must be built from the source assets
- **Webcam and Timelapse screens are present but non-functional** — UI placeholder only; no stream or timelapse control in this release
- **Moonraker Update Manager integration is documented but not end-to-end tested** — the verified update path in this release is `git pull` + `sudo systemctl restart nexus-screen`
- **No multi-printer support** — connects to a single Moonraker instance on `localhost:7125`

---

## Bug Reports and Contributing

- **Report a bug:** [Open an issue](https://github.com/TheOmProject/Nexus-Screen/issues/new?template=bug_report.yml)
- **Request a feature:** [Open an issue](https://github.com/TheOmProject/Nexus-Screen/issues/new?template=feature_request.yml)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

Include the output of `scripts/bug-report.sh "description of the problem"` with your bug report.

---

## License

Nexus Screen is released under the [GNU General Public License v3.0](LICENSE).

Bundled fonts (Rajdhani) are licensed under the [SIL Open Font License 1.1](https://openfontlicense.org/).
