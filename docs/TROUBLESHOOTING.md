# Nexus Screen — Troubleshooting

---

## Screen stays black after install

**Causes and fixes:**

1. **Service not started** — check status:
   ```bash
   systemctl status nexus-screen
   ```
   If `Active: failed`, see the journal:
   ```bash
   journalctl -u nexus-screen -b --no-pager
   ```

2. **Wrong virtual terminal** — Nexus Screen runs on tty7. Check:
   ```bash
   sudo chvt 7
   ```
   If the screen comes on, the boot splash or another service may be holding a different VT.

3. **`/dev/fb0` in use by another process** — check:
   ```bash
   fuser /dev/fb0
   ```
   If another process holds the framebuffer, it must be stopped before Nexus Screen can start.

4. **Screen timeout / blanking** — the display may have blanked. Touch the screen or press a key.

---

## nexus-screen.service fails to start

Check the journal:
```bash
journalctl -u nexus-screen -b --no-pager -n 50
```

Common causes:

| Error | Fix |
|---|---|
| `PyQt6 not importable` | Run `sudo apt install python3-pyqt6` |
| `/dev/fb0: No such file or directory` | DSI display not detected — check `display_auto_detect=1` in `config.txt` |
| `precheck: /dev/fb0 in use` | Another display client is running — stop it first |
| `moonraker.service` not started | Start Moonraker: `sudo systemctl start moonraker` |
| Crash loop (5 failures) | Check full journal; service stops retrying and text console is shown on tty1 |

---

## App shows "Disconnected"

Nexus Screen polls Moonraker on `localhost:7125`. If it shows "Disconnected":

1. Verify Moonraker is running:
   ```bash
   systemctl is-active moonraker
   curl -s http://localhost:7125/printer/info
   ```

2. If Moonraker is running but Klipper is in error state, check Klipper:
   ```bash
   systemctl status klipper
   journalctl -u klipper -b -n 30
   ```

3. Nexus Screen will reconnect automatically once Moonraker becomes available — no restart needed.

---

## Touch not responding

1. Verify the touch device is present:
   ```bash
   ls /dev/input/event*
   ```

2. Check which events are being generated:
   ```bash
   cat /dev/input/event3 | xxd | head  # replace event3 with the correct device
   ```

3. Run the touch accuracy check tool (no root needed, no printer commands):
   ```bash
   ~/nexus-screen-env/bin/python ~/nexus-screen/scripts/touch_check.py
   ```

4. Verify the `input` group:
   ```bash
   groups $USER    # should include 'input'
   ```

---

## Printer commands not working

Printer commands (Pause, Resume, Stop, Baby Step) are **disabled by default**.
Enable them:

```bash
sudo ~/nexus-screen/deploy/commands.sh enable --confirm
```

---

## How to restore KlipperScreen

If you had KlipperScreen installed before Nexus Screen, you can restore it over SSH
even if the touchscreen is black:

```bash
# Restore KlipperScreen to its pre-install state
sudo ~/nexus-screen/deploy/rollback.sh --confirm

# Restore AND start KlipperScreen
sudo ~/nexus-screen/deploy/rollback.sh --confirm --start-klipperscreen
```

Without the script:
```bash
sudo systemctl disable --now nexus-screen
sudo chvt 1
sudo systemctl enable --now KlipperScreen
```

---

## Collecting logs for a bug report

```bash
~/nexus-screen/scripts/bug-report.sh "brief description of the problem"
```

This creates `logs/bug-<timestamp>.tar.gz` with service journals, printer state, and version
information. Credentials are automatically scrubbed. Attach this file to your
[GitHub issue](https://github.com/omarmunoz5371/Nexus-Screen/issues).

---

## SSH recovery when the screen is black

All recovery commands work over SSH — a working network connection is enough:

```bash
# Show the text console
sudo chvt 1

# Check what is using the framebuffer
fuser /dev/fb0

# Start nexus-screen manually
sudo systemctl start nexus-screen

# Full rollback to pre-install state
sudo ~/nexus-screen/deploy/rollback.sh --confirm
```
