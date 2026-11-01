# Nexus Screen — Uninstall Guide

All commands work over SSH — no physical access to the screen is required.

---

## Standard rollback (preserves Nexus Screen files)

This stops and disables Nexus Screen and restores KlipperScreen to its state before
Nexus Screen was installed. The `~/nexus-screen` directory is not deleted.

```bash
# Dry run first — shows what would happen, makes no changes
sudo ~/nexus-screen/deploy/rollback.sh

# Apply the rollback
sudo ~/nexus-screen/deploy/rollback.sh --confirm
```

To also start KlipperScreen immediately after rollback:
```bash
sudo ~/nexus-screen/deploy/rollback.sh --confirm --start-klipperscreen
```

To also remove the systemd unit file (`/etc/systemd/system/nexus-screen.service`):
```bash
sudo ~/nexus-screen/deploy/rollback.sh --confirm --remove-unit
```

---

## Complete removal

After rolling back, delete the Nexus Screen files and virtual environment:

```bash
# Rollback first (see above) — ensure nexus-screen.service is stopped and disabled

# Remove the repository
rm -rf ~/nexus-screen

# Remove the Python virtual environment
rm -rf ~/nexus-screen-env

# Optional: remove backups
rm -rf ~/nexus-screen-backups
```

---

## Without the rollback script

If `rollback.sh` is not available, use these manual commands:

```bash
# Stop and disable Nexus Screen
sudo systemctl disable --now nexus-screen

# Remove the unit file
sudo rm -f /etc/systemd/system/nexus-screen.service
sudo systemctl daemon-reload

# Restore the text console
sudo chvt 1

# Re-enable KlipperScreen (only if you want it back)
sudo systemctl enable --now KlipperScreen
```

---

## Removing the boot splash

If the boot splash is installed:

```bash
sudo ~/nexus-screen/deploy/splash.sh disable --confirm
```

Remove the splash media directory:
```bash
rm -rf ~/nexus-splash
```
