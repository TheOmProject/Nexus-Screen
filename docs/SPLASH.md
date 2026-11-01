# Boot Splash (Optional)

Nexus Screen supports an optional cinematic boot splash: an animated intro plays
once at power-on, followed by a looping animation that fills the screen while
Nexus Screen loads. When Nexus Screen is ready, it takes over the display
seamlessly. The splash is fully optional — Nexus Screen starts normally without it.

> **Advanced feature.** The splash requires you to supply your own video files and
> build the media locally. It is not required for normal use.

---

## How it works

The splash runs as a separate lightweight service (`nexus-splash.service`) that
starts early in the boot sequence, before Nexus Screen. It decodes video frames
directly into the framebuffer using `ffmpeg` — no desktop environment or Qt
required. When Nexus Screen connects to Moonraker and is ready to show its
interface, it signals the splash, which exits and hands over the display.

If anything goes wrong — the splash crashes, the media is missing, or Nexus
Screen never starts — the system falls back safely: the text console (tty1) is
shown and SSH remains available.

---

## Files

| Path | Purpose |
|---|---|
| `splash/build_media.sh` | Converts your source videos to 800×480 H.264 for the player |
| `splash/player.py` | Plays the media into `/dev/fb0`; ~23% of one CPU core, ≤ 125 MB RAM |
| `deploy/nexus-splash.service.in` | Service unit template (instantiated by `deploy/splash.sh install`) |
| `deploy/splash.sh` | Manages the splash: `install`, `test`, `enable`, `disable`, `status` |
| `nexus/splash.py` | Nexus Screen's handover logic (keeps the window hidden until the splash exits) |

---

## Prerequisites

- `ffmpeg` installed: `sudo apt install ffmpeg`
- Two source video files placed in `~/nexus-splash/`:
  - `intro.mp4` — played once at boot (e.g. a logo animation, any duration)
  - `loop.mp4` — looped while Nexus Screen loads (5–15 s recommended)
- Nexus Screen already installed and running (`nexus-screen.service` active)

---

## Setup

### Step 1 — Build the media

```bash
# Build 800×480 copies of your videos into ~/nexus-splash/build/
# (originals in ~/nexus-splash/ are only read, never modified)
~/nexus-screen/splash/build_media.sh
```

This creates `intro.mp4`, `loop.mp4`, `still.rgb565` (fallback frame), and
`SHA256SUMS` inside `~/nexus-splash/build/`.

### Step 2 — Install the unit (no boot change yet)

```bash
sudo ~/nexus-screen/deploy/splash.sh install --confirm
```

### Step 3 — Test without rebooting

```bash
sudo ~/nexus-screen/deploy/splash.sh test --confirm
```

This stops Nexus Screen, plays the full splash sequence, starts Nexus Screen, and
runs a health check. If the health check fails, Nexus Screen is restarted without
the splash.

### Step 4 — Enable at boot

```bash
sudo ~/nexus-screen/deploy/splash.sh enable --confirm
```

The splash will play on every subsequent boot.

---

## Disabling the splash

**Without root** (takes effect at the next boot):

```bash
touch ~/nexus-splash/DISABLED
```

**Immediately** (stops the splash and removes it from boot):

```bash
sudo ~/nexus-screen/deploy/splash.sh disable --confirm
```

Nexus Screen does not depend on the splash. Disabling or removing it does not
affect Nexus Screen.

---

## Failure modes

| Situation | Result |
|---|---|
| Splash media missing or corrupt | Nexus Screen starts normally; still frame if only one video is broken |
| Splash crashes or times out | Nexus Screen shows its window within 2 s of being ready |
| Nexus Screen does not start | Splash exits after 90 s; text console (tty1) is restored |
| `/dev/fb0` never appears | Splash gives up after 10 s without drawing anything |
| Another program holds the screen | Splash draws nothing; Nexus Screen starts as normal |
| Moonraker never connects | Nexus Screen takes the screen after 30 s regardless |

In every case SSH is unaffected. To disable the splash over SSH:

```bash
touch ~/nexus-splash/DISABLED          # no root needed; takes effect at next boot
# or immediately:
sudo ~/nexus-screen/deploy/splash.sh disable --confirm
```

---

## Status

```bash
~/nexus-screen/deploy/splash.sh status
```
