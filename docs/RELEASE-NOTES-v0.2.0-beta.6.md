# Nexus Screen v0.2.0-beta.6

---

## What's New

### Nexus Sounds UI integration — Settings → Sounds

The **Settings → Sounds** screen is now included. It provides full control of the optional
[Nexus Sounds](https://github.com/TheOmProject/Nexus-Sounds) add-on from the touchscreen.

When Nexus Sounds is not installed, the screen shows an installation notice rather than crashing.
No configuration is required; the screen degrades gracefully.

**Four new screens:**

- **Sounds** — master enable/mute toggle cards, volume row (−/+), Event Sounds and Sound Packs navigation
- **Event Sounds** — scrollable list of seven events with icons, assigned filenames, and chevrons;
  tap any event to configure it
- **Event Sound selector** — per-event file browser, Enable toggle, Preview/Apply/Cancel
- **Sound Packs** — two-column browser: pack list on the left, pack details (metadata, Browse Sounds,
  Set as Active) on the right

---

## Upgrade from v0.2.0-beta.5

```bash
cd ~/nexus-screen && git pull
sudo systemctl restart nexus-screen
```

To add Nexus Sounds:

```bash
git clone https://github.com/TheOmProject/Nexus-Sounds.git ~/nexus-sounds-src
sudo bash ~/nexus-sounds-src/deploy/install.sh
```

---

## Known Limitations

All limitations from v0.2.0-beta.5 carry forward:

- Nexus Video `public-install.sh` has not been run on a fresh clean machine
- Moonraker Update Manager integration documented but not end-to-end tested
- Webcam and Timelapse screens are UI placeholders only
- No multi-printer support — single Moonraker instance on `localhost:7125`

New in v0.2.0-beta.6:

- Settings → Sounds requires Nexus Sounds to be installed for audio functionality; the UI
  is present regardless, with graceful degradation when Nexus Sounds is absent
- Nexus Sounds clean install not separately confirmed on a fresh machine

---

## Rollback

```bash
sudo ~/nexus-screen/deploy/rollback.sh --confirm
```

---

## Supported Hardware

See [docs/HARDWARE-COMPATIBILITY.md](HARDWARE-COMPATIBILITY.md) for the full matrix.

Physically verified in this release:

- **Raspberry Pi 4 (Voron Micron), 800×480 RGB565, Debian 12** — Sounds UI with JMTek USB audio,
  full event playback, preview, volume control, and pack browser verified on hardware

---

## Bug Reports

[Open a Bug Report](https://github.com/TheOmProject/Nexus-Screen/issues/new?template=bug_report.yml)

Attach the output of:

```bash
~/nexus-screen/scripts/bug-report.sh "brief description of the problem"
```
