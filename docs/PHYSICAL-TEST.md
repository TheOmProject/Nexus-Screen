# Nexus Screen — physical touchscreen test

Manual, temporary test of the PyQt6 app on the printer's own 7" DSI screen (800 × 480).
Nothing is installed, no service is enabled or changed, KlipperScreen is not touched, and
**no printer command can be sent** (`launch-test.sh` refuses `--allow-commands`).

## What was verified without using the screen

| Item | Result |
|---|---|
| Display | DSI-1 connected (vc4-drm), framebuffer `/dev/fb0` 800 × 480 @ 16 bpp |
| Touch | `ft5x06` on `/dev/input/event3`, axes 0–799 × 0–479 → 1:1, no rotation or calibration needed |
| Permissions | user `omar` is in `video` and `input` → no root needed |
| Qt | PyQt6 6.4.2, `linuxfb` platform plugin, libinput + evdev touch plugins present |
| Backlight | `/sys/class/backlight/10-0045` (0–255), group `video` may write |
| Conflicts | X is not running; `KlipperScreen.service` is `failed` (left as is) |

Physical display runs: 2026-10-28 (build b043e8e) and after the four corrections (build 09b7dd7 and
later). Synthetic (programmatic) taps were used there; they do not replace real finger testing.

## Procedure

1. **Free the screen** if anything else is drawing on it (the preflight lists such processes).
2. **Preflight:** `~/nexus-screen/scripts/launch-test.sh --check` → must end with `Preflight OK`.
3. **Simulation run** (no printer involvement at all):
   `~/nexus-screen/scripts/launch-test.sh sim`
4. **Live, read-only run** (real temperatures, files, macros; every printer command disabled):
   `~/nexus-screen/scripts/launch-test.sh live`
5. **Stop:** Ctrl+C in that terminal, or `scripts/launch-test.sh --stop` from another one. A
   dead-man timer stops the app after 30 minutes anyway (`--minutes N` to change).

Options: `--evdev` uses Qt's evdev touch driver if touches misbehave with libinput;
`--display-writes` lets Settings › Screen change the real backlight (off by default).

Each run writes `logs/test-<time>-<mode>.log` and a CPU / RAM sample every 5 s to
`logs/test-<time>-<mode>-stats.csv`.

## Owner finger test (real touches — only you can do this part)

1. In an SSH terminal: `~/nexus-screen/scripts/launch-test.sh --stop` (stops a test app left
   running for you), then `~/nexus-screen/scripts/launch-test.sh --check` → `Preflight OK`.
2. **Touch accuracy and latency:** `~/nexus-screen/scripts/touch_check.py`
   - Tap the centre of each red crosshair: top-left, top-right, bottom-right, bottom-left, centre.
   - Then tap anywhere 10 times (the screen flashes on each tap).
   - The result appears on the screen and in `logs/touch-check-<time>.json`; press Ctrl+C to exit.
3. **The interface:** `~/nexus-screen/scripts/launch-test.sh sim` and work through the checklist
   below with your finger. Stop with Ctrl+C.
4. Optionally `scripts/launch-test.sh live` (read-only) for the live-data items.
5. Tell me which items passed or failed; I read the touch-check JSON and the run logs.

## Checklist

**Touch accuracy**
- [ ] Sidebar: all five sections respond, including the top (Home) and bottom (Settings) items
- [ ] Back button in the top-left corner works on every submenu
- [ ] Temperature keypad: every key (0–9, ".", backspace) registers once, no double entries
- [ ] On-screen keyboard (Control › Macros › Search): edge keys Q, P, Z, "." and backspace
- [ ] Small keys: Z offset ±0.005, Move step distances; Baby Step submenu keys (±0.005 … ±0.05)
- [ ] Jog wheel: X+, X-, Y+, Y- segments and the centre Home key hit the intended part
- [ ] touch_check.py: every target error small (a few px); touch-to-display median noted
- [ ] Pagination: Print Files (Print › Print Files) and Macros › / ‹ buttons; Logs ▲ ▼

**Simulation flows**
- [ ] Print › Print Files › pick a file › Preview (thumbnail) › Start Print › Confirm
- [ ] Print Status: no sidebar; Pause → Resume; Stop opens confirmation (Cancel keeps printing)
- [ ] Baby Step opens its submenu; +0.005 / +0.01 / +0.025 / +0.05 and the negative row change Z; Back returns to Print Status; Home goes to Home, Return to Print comes back
- [ ] Filament › BoxTurtle and StealthChanger: select lanes / tools, colour and material pickers

**Scaling and appearance**
- [ ] Whole UI fills the panel exactly; nothing clipped at the edges
- [ ] Text is sharp; Rajdhani is used everywhere (no fallback font)
- [ ] Colours: note any visible banding in glows/gradients (the panel framebuffer is 16-bit)
- [ ] No console cursor or kernel text showing through

**Navigation**
- [ ] Every tile on Print, Filament, Control and Settings opens its screen; Back returns
- [ ] Settings › Tools / Maintenance / Help hubs open their screens
- [ ] Modal dialogs (Stop, confirmations, keypad, keyboard) block taps behind them and close correctly

**Responsiveness**
- [ ] Taps respond immediately (no perceptible delay); screen changes feel instant
- [ ] Webcam screen (simulated image) updates without slowing other taps
- [ ] Screen timeout (Settings › Screen, set 1 min): screen blanks; first touch only wakes it

**Live (read-only) data**
- [ ] Top bar temperatures match Mainsail
- [ ] Print Files lists the printer's files with thumbnails; File Preview shows metadata
- [ ] Macros, Logs (klippy.log), System, Network and Firmware show real information
- [ ] Unplugging network is not required; if Moonraker restarts, the bar shows Disconnected and recovers

**CPU / RAM and stability**
- [ ] After the run, check the `-stats.csv`: CPU stays low on idle screens; RSS stays flat (~100 MiB)
- [ ] 30-minute run without crash or freeze (dead-man timer ends it)

## Rollback

There is nothing to roll back: the test installs nothing and changes no configuration. Stopping
the app (Ctrl+C / `--stop` / dead-man) ends the test; the launcher restores the tty1 cursor it
hid. There is nothing to roll back.
