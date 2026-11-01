#!/usr/bin/env bash
# Collect evidence for a Nexus Screen problem into logs/bug-<time>.tar.gz (no root needed).
#   scripts/bug-report.sh "what happened (screen, action, expected vs actual)"
# Contents: recent command log (screen, command, Moonraker/Klipper message, printer state), service journal,
# klippy.log / moonraker.log tails, printer state snapshot, versions. Lines that look like credentials are dropped.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ts="$(date +%Y%m%d-%H%M%S)"; D="$HERE/logs/bug-$ts"; mkdir -p "$D"
scrub() { grep -viE 'api[_-]?key|token|passw|secret|authorization|cookie'; }
printf '%s\n' "${1:-(no description given)}" > "$D/description.txt"
date >> "$D/description.txt"
tail -n 200 "$HERE/logs/commands.jsonl" 2>/dev/null | scrub > "$D/commands.jsonl"
journalctl -u nexus-screen -n 300 --no-pager 2>&1 | scrub > "$D/nexus-screen.journal"
grep -v '^Stats ' "$HOME/printer_data/logs/klippy.log" 2>/dev/null | tail -n 200 | scrub > "$D/klippy.tail.log"
tail -n 300 "$HOME/printer_data/logs/moonraker.log" 2>/dev/null | scrub > "$D/moonraker.tail.log"
curl -s -m 5 "http://localhost:7125/printer/objects/query?webhooks&print_stats&toolhead&extruder&heater_bed&gcode_move&virtual_sdcard&idle_timeout" \
    | python3 -m json.tool > "$D/printer-state.json" 2>&1
curl -s -m 5 "http://localhost:7125/server/gcode_store?count=100" | python3 -m json.tool > "$D/gcode-store.json" 2>&1
{ echo "nexus-screen $(git -C "$HERE" describe --always --dirty)"; systemctl show nexus-screen -p ActiveState,NRestarts,ExecMainStartTimestamp
  systemctl cat nexus-screen 2>/dev/null | grep -E '^ExecStart='; for s in klipper moonraker; do echo "$s $(systemctl is-active $s)"; done; } > "$D/versions.txt"
tar czf "$D.tar.gz" -C "$HERE/logs" "bug-$ts" && rm -r -- "$D"
echo "Bug report: $D.tar.gz"
