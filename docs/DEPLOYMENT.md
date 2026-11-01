# Nexus Screen V1 — permanent deployment

## Install (one command, run by the owner)

```bash
sudo ~/nexus-screen/deploy/install.sh            # dry run first: checks and plan, changes nothing
sudo ~/nexus-screen/deploy/install.sh --confirm  # install and start
```

What `--confirm` does, in order:

1. Preflight — application code identical to approved `d2bfe8d`, tag `nexus-v1-approved` present, clean
   repository, Klipper and Moonraker active and Klipper `ready`, PyQt6 importable, unit file verifies.
2. Backup to `~/nexus-screen-backups/deploy-<time>/`: `KlipperScreen.service`, its `systemctl cat`, the
   enabled/active state of KlipperScreen (`state.env`), the new unit, `RESTORE.md`, `SHA256SUMS`.
3. Stops a manual test session (`launch-test.sh`), refuses if anything else draws on the screen.
4. Stops and disables `KlipperScreen.service` — the installation itself is left in place.
5. Installs `/etc/systemd/system/nexus-screen.service`, enables and starts it.
6. Health check for up to 40 s (`deploy/healthcheck.py`). If it fails, the installer **rolls back
   automatically**: Nexus Screen disabled and its unit removed, KlipperScreen restored to its previous
   enabled/active state, text console shown again, journal saved in the backup folder.

## The service

`nexus-screen.service` (source: `deploy/nexus-screen.service`):

| Setting | Value / reason |
|---|---|
| User | `omar` (+ groups video, input, tty, render) |
| Start | at boot (`multi-user.target`), after Moonraker |
| Command | `main.py --hardware-display --live` — real Moonraker data; **printer commands disabled** (no `--allow-commands`) until the owner authorizes them |
| Console | own VT `tty7` as controlling terminal (`TTYPath`, `StandardInput=tty`), `chvt 7` before start, Qt `tty=/dev/tty` → console in graphics mode, no text or cursor; `chvt 1` after stop |
| Crashes | `Restart=always`, 3 s delay; after 5 failures within 2 min systemd stops retrying and the text console stays visible |
| One display client | `Conflicts=KlipperScreen.service`; pre-start check refuses if anything else holds `/dev/fb0` |
| Stop | SIGTERM → clean Qt exit (console restored), 10 s timeout |
| Test timeout | none — the dead-man timer belongs to `launch-test.sh` only |

## Recovery over SSH (also when the screen is black)

```bash
sudo ~/nexus-screen/deploy/rollback.sh --confirm                        # restore the state before install
sudo ~/nexus-screen/deploy/rollback.sh --confirm --start-klipperscreen  # ... and run KlipperScreen OM
```

Add `--remove-unit` to delete the unit file as well. Without the scripts:

```bash
sudo systemctl disable --now nexus-screen
sudo chvt 1
sudo systemctl enable --now KlipperScreen      # only if KlipperScreen OM should come back
```

Status and logs: `systemctl status nexus-screen`, `journalctl -u nexus-screen -b`,
`~/nexus-screen/deploy/healthcheck.py` (no root needed).

Code recovery points (tags in `~/nexus-screen`): `nexus-v1-approved` (b043e8e gallery baseline),
`nexus-deployed-9457243` (approved Home image + Back, before printer control). To return the running
app to a tag (no root needed; systemd restarts only this service):

```bash
cd ~/nexus-screen && git checkout -B main <tag>
kill -TERM "$(systemctl show -p MainPID --value nexus-screen)"
~/nexus-screen/deploy/healthcheck.py --wait 40 --max-restarts 99   # add --commands if commands are on
```

## Development and tests (Raspberry Pi memory)

Develop in the worktree `~/nexus-screen-dev`, never in `~/nexus-screen` (the service runs that tree).
Run the suite only through `scripts/run_tests.py`: one run at a time (lock file), offscreen, refused
when memory is already low, killed if available memory drops below 350 MiB; it prints the peak.

## Printer commands (enable / disable)

Commands are switched with a systemd drop-in (`/etc/systemd/system/nexus-screen.service.d/allow-commands.conf`,
source `deploy/allow-commands.conf`, which adds `--allow-commands`). Use the guarded script:

```bash
sudo ~/nexus-screen/deploy/commands.sh enable              # dry run
sudo ~/nexus-screen/deploy/commands.sh enable --confirm    # commands on (restarts only nexus-screen)
sudo ~/nexus-screen/deploy/commands.sh disable --confirm   # back to read-only
```

It backs up the effective unit to `~/nexus-screen-backups/commands-*`, restarts only `nexus-screen`, and checks
health (`deploy/healthcheck.py --commands`); if that fails after enabling, it removes the drop-in again.
Sending nothing to the printer itself. Without the script: `sudo rm /etc/systemd/system/nexus-screen.service.d/allow-commands.conf
&& sudo systemctl daemon-reload && sudo systemctl restart nexus-screen`.
