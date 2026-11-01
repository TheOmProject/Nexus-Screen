# Nexus Screen — real printing tests (owner)

Printer commands are enabled only after `sudo ~/nexus-screen/deploy/commands.sh enable --confirm`.
Everything below is done by you at the printer; nothing is started remotely.

## What each control sends

`~/nexus-screen/scripts/command_audit.py` lists every operation with its exact G-code / Moonraker
request, whether this printer supports it, when it is allowed and whether it asks for confirmation
(read-only; it sends nothing).

## Safety behaviour to expect

- Moves, homing, extrusion, PID tune, mesh, input shaper, probe tests and SAVE_CONFIG only when the
  printer is idle; X/Y jog and bed presets only when those axes are homed.
- Print start, Stop, Z offset presets / Reset / Save, PID tune, Save to Config, bed mesh calibrate,
  input shaper, probe accuracy, macros, file delete and all restarts / reboot / shutdown ask first.
- While a command runs (e.g. homing, a macro) the other controls are greyed out until Klipper finishes.
- If Klipper or Moonraker rejects a command, a "Command failed" message shows Klipper's own text
  (for example "Must home axis first"), and it is logged in `logs/commands.jsonl`.
- In the Klipper error state only recovery actions remain (Restart Klipper / firmware, logs).
- **Emergency stop**: a red **EMERGENCY STOP** key in the top bar, between the printer state and the
  temperatures, on every screen (Print Status included). It appears whenever there is something to
  stop: printing or paused, Klipper executing commands (homing, moves, macros), any heater target
  above 0, or a Nexus command still running. Hidden when idle and cold, disconnected, read-only, or
  already in the error state. **Press and hold ~0.5 s** (the key fills while held); a short touch or
  sliding off does nothing; there is no confirmation dialog. It sends Moonraker
  `POST /printer/emergency_stop`: Klipper shuts down immediately and the error dialog shows
  "Shutdown due to webhooks request"; recover with Restart Firmware. Dialogs, when open, cover the key.

## Suggested order

1. Home (Control › Move › Home All), then small jogs at 1 mm / 10 mm.
2. Temperatures: tap Nozzle / Bed on Home (keypad), watch the values rise; Cooldown.
3. Fans and lighting.
4. Filament › Load with a cold nozzle (heats first), Extrude / Retract when hot.
5. Print › Print Files › choose a small file › Preview (thumbnail) › Start Print › confirm.
6. During the print: progress, Pause → Resume, Baby Step › +0.01 / -0.01 (then Back), Home and Return to Print.
7. Let it finish → Print Complete; or Stop → confirm.
8. Emergency stop (when you choose; it shuts Klipper down): e.g. with the nozzle heating, hold the
   red key in the top bar → heaters off, error dialog → Restart Firmware.

## When something is wrong

Right after it happens, in SSH:

```bash
~/nexus-screen/scripts/bug-report.sh "Move screen: Z+ did nothing, expected 1 mm up"
```

It saves `~/nexus-screen/logs/bug-<time>.tar.gz` (commands with screen, Moonraker/Klipper message and
printer state, service journal, klippy/moonraker log tails, printer state). Tell me the file name.
