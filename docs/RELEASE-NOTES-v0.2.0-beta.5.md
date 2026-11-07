# Nexus Screen v0.2.0-beta.5 — Draft Release Notes

> **Status:** Release Candidate — awaiting owner approval before tag creation.

---

## What's New

### One-command installation

Nexus Screen now installs with a single command that handles everything:

```bash
curl -fsSL https://raw.githubusercontent.com/omarmunoz5371/Nexus-Screen/main/deploy/bootstrap.sh | bash
```

The bootstrap installer (`deploy/bootstrap.sh`):
- Checks hardware compatibility before making any changes
- Offers to automatically install missing packages (`python3-pyqt6`, `git`)
- Installs Nexus Screen
- Optionally installs Nexus Video in the same session
- Registers both repos with Moonraker Update Manager

Non-interactive flags: `--yes`, `--with-video`, `--without-video`, `--dry-run`.

### Nexus Video integration — Settings → Startup Video

The **Settings → Startup Video** screen (`nexus/screens/startup_video.py`) is now
included in this release. It allows users to browse, preview, and switch Nexus Video
packs from within the app. When Nexus Video is not installed, the screen shows a
"not installed" notice rather than crashing.

### Installer improvements

- `--repair` mode now creates a timestamped backup before removing the installation directory
- Nexus Video install now correctly invokes `deploy/public-install.sh` as root
- Dependency auto-install: PyQt6 and git are offered for installation rather than hard-blocking

### Hardware compatibility

Installer blocks have been updated with clearer per-reason "INSTALLATION BLOCKED" messages.
Minimum display resolution (480×320), unsupported architectures, and unsupported OS versions
each produce a specific message rather than a generic failure.

---

## Upgrade from v0.2.0-beta.4

```bash
cd ~/nexus-screen && git pull
sudo systemctl restart nexus-screen
```

If installing Nexus Video for the first time, use the bootstrap installer with `--with-video`.

---

## Known Limitations

- Nexus Video `public-install.sh` has not been run on a fresh clean machine; the
  convert step (FFmpeg + `/dev/fb0`) is code-validated but not physically tested end-to-end
- Moonraker Update Manager integration documented but not end-to-end tested (verified
  update path: `git pull` + `sudo systemctl restart nexus-screen`)
- Webcam and Timelapse screens are UI placeholders only — no stream or timelapse control
- No multi-printer support — connects to a single Moonraker instance on `localhost:7125`
- Nexus Sounds: not yet available in this release

---

## Rollback

To revert to the previous installation:
```bash
# From the most recent backup in ~/nexus-screen-backups/
sudo ~/nexus-screen/deploy/rollback.sh --confirm
```

---

## Supported Hardware

See [docs/HARDWARE-COMPATIBILITY.md](HARDWARE-COMPATIBILITY.md) for the full matrix.

Physically tested configurations:
- Raspberry Pi 4 (2 GB), 800×480 RGB565 DSI, Debian 12 Bookworm
- Raspberry Pi 4 (4 GB) on Voron 2.4, 800×480 BGRA8888, Raspberry Pi OS Bookworm
- BigTreeTech CB1, 480×320 RGB565 DSI, CB1 OS (Bookworm-based)

---

## Bug Reports

[Open a Bug Report](https://github.com/omarmunoz5371/Nexus-Screen/issues/new?template=bug_report.yml)

Attach the output of:
```bash
~/nexus-screen/scripts/bug-report.sh "brief description of the problem"
```
