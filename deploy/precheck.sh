#!/usr/bin/env bash
# ExecStartPre: refuse to start while another program (e.g. a manual test session) draws on the screen.
# The boot splash (splash/player.py) is expected: it hands the screen over to Nexus Screen itself.
FB="${NEXUS_FB:-/dev/fb0}"
holders=""
for pid in $(fuser "$FB" 2>/dev/null); do
    tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q "splash/player.py" && continue
    holders="$holders $pid"
done
if [ -n "${holders// /}" ]; then
    echo "nexus-screen: $FB in use by pid(s):$holders — not starting a second display client" >&2
    exit 1
fi
exit 0
