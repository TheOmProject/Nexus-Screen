# Nexus Screen + Nexus Video — Hardware Compatibility

This document describes known hardware configurations and their compatibility status.

---

## Evidence classification

| Status | Meaning |
|---|---|
| **PHYSICALLY VERIFIED** | Installed and confirmed working on actual hardware, with evidence from real device execution (service active, install backup present, real bugs found and fixed) |
| **ISOLATED EXECUTION** | Software component tested in isolated environment (conversion, test suite) without full hardware path |
| **CODE / SIMULATION VERIFIED** | Installer logic verified by source analysis and automated tests; not run on real hardware |
| **NOT TESTED** | Unknown; may work or may not; community reports welcome |
| **NOT SUPPORTED** | Installer blocks; not compatible |

> **Note on clean install vs. runtime:**
> - "Runtime" = Nexus Screen app executed and displayed on a physical framebuffer
> - "Clean install" = `deploy/install.sh` (or `bootstrap.sh`) run from start to finish on real hardware
> - These are distinct claims. A device physically running Nexus Screen does not automatically
>   prove a clean install was verified, and vice versa.

---

## Raspberry Pi 4 (2 GB) — 800×480 RGB565 — Debian 12 Bookworm

**This machine.**

| Item | Evidence | Status |
|---|---|---|
| NS runtime | Service active (`nexus-screen.service`), running since 2026-11-06, PID 9677. App actively serving the touchscreen UI. | **PHYSICALLY VERIFIED** |
| NS clean install | Backup dir `nexus-screen-backups/deploy-20261029-155849` confirms `deploy/install.sh` ran on 2026-10-29. | **PHYSICALLY VERIFIED** |
| NS touch input | PHYSICAL-TEST.md documents ft5x06 on /dev/input/event3, axes 0–799×0–479, tested 2026-10-28 | **PHYSICALLY VERIFIED** |
| NS display | /dev/fb0 800×480 bpp=16, vc4-drm, verified live at this session | **PHYSICALLY VERIFIED** |
| NS bootstrap (`bootstrap.sh`) | Dry-run passes all 11 preflight checks on this machine | **ISOLATED EXECUTION** |
| NV runtime (framebuffer playback) | No evidence of `nexus-video.service` running on this machine | **NOT TESTED** |
| NV clean install (`public-install.sh`) | No evidence of NV being installed on this machine | **NOT TESTED** |
| NV FFmpeg conversion | Real conversion executed on this machine: nexus_signature, mechanical_core, system_init all converted successfully to 800×480 h264, still.rgb565 = 768000 bytes | **ISOLATED EXECUTION** |

---

## Raspberry Pi 4 (4 GB) — 800×480 BGRA8888 (32-bit) — Voron 2.4

**A separate physical device (Voron 2.4 printer), not accessible in this session.**

| Item | Evidence | Status |
|---|---|---|
| NS runtime | CHANGELOG v0.2.0-beta.4: "v0.2.0-beta.3 was installed and physically tested on a Voron 2.4 with an 800×480 display. The BCM2708 framebuffer reported BGRA8888 (32-bit, `bits_per_pixel = 32`, `RGBA: 8/16, 8/8, 8/0, 8/24`). Installation completed without errors; the interface and touchscreen worked correctly; StealthChanger was auto-detected." | **PHYSICALLY VERIFIED** |
| NS clean install | CHANGELOG uses "installed and physically tested" — word "installed" is consistent with `install.sh` having run, with specific hardware details (BGRA8888 channel layout) only obtainable from a real device | **PHYSICALLY VERIFIED** |
| NV runtime | No evidence | **NOT TESTED** |
| NV clean install | No evidence | **NOT TESTED** |

---

## BigTreeTech CB1 — 480×320 RGB565

**A separate physical device, not accessible in this session.**

| Item | Evidence | Status |
|---|---|---|
| NS runtime | CHANGELOG v0.2.0-beta.2: "Physical CB1 testing after v0.2.0-beta.1 revealed that buttons...extended 7 px beyond the right edge of the screen at 480×320, making the rightmost column of tiles unreachable by touch." Real hardware bug found and fixed. | **PHYSICALLY VERIFIED** |
| NS clean install | CHANGELOG does not explicitly state `install.sh` was run on CB1; "physical CB1 testing" may refer to running the app directly. Evidence insufficient to claim clean install. | **CODE / SIMULATION VERIFIED** |
| NV runtime | No evidence | **NOT TESTED** |
| NV clean install | No evidence | **NOT TESTED** |

---

## Other hardware

| Hardware | NS Runtime | NS Clean Install | NV Runtime | NV Clean Install | Notes |
|---|---|---|---|---|---|
| Raspberry Pi 3 (B/B+) | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | 64-bit OS required; preflight accepts armv8 (aarch64) |
| Raspberry Pi 5 | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | Community reports welcome |
| Raspberry Pi Zero 2 W | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | 512 MB RAM; installer blocks (minimum 900 MB) |
| HDMI displays | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | `/dev/fb0` must exist; depends on driver |
| SPI displays | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | `/dev/fb0` required; most SPI drivers do not expose one |
| Debian 11 Bullseye | NOT SUPPORTED | NOT SUPPORTED | NOT SUPPORTED | NOT SUPPORTED | Installer blocks; `python3-pyqt6` not in Bullseye apt |
| 32-bit ARM (armv7l) | NOT SUPPORTED | NOT SUPPORTED | NOT SUPPORTED | NOT SUPPORTED | Installer blocks; 64-bit aarch64 required |
| Ubuntu 22.04 / other | CODE / SIMULATION | NOT TESTED | NOT TESTED | NOT TESTED | Preflight accepts; not physically tested |
| Any display < 480×320 | NOT SUPPORTED | NOT SUPPORTED | NOT SUPPORTED | NOT SUPPORTED | Installer blocks with INSTALLATION BLOCKED |

---

## Display format requirements

The display must expose a Linux framebuffer device at `/dev/fb0` in one of:

| Format | bits_per_pixel | Notes |
|---|---|---|
| RGB565 | 16 | Most DSI panels; Raspberry Pi OS default |
| BGRA8888 | 32 | BCM2708 framebuffer (Voron 2.4 / RPi) |
| RGBA8888, ARGB8888, ABGR8888 | 32 | Supported; not physically tested |

Verify on your machine:
```bash
cat /sys/class/graphics/fb0/bits_per_pixel   # 16 or 32
cat /sys/class/graphics/fb0/virtual_size      # W,H
```

---

## Report a hardware configuration

If you test on hardware not listed here, please file a report:

[Open a Hardware Compatibility Report](https://github.com/TheOmProject/Nexus-Screen/issues/new?template=hardware_report.yml)
