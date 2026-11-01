#!/usr/bin/env bash
# Run capture.sh at four reference resolutions for Phase C adaptive display validation.
#   scripts/capture-multi.sh OUT_DIR
# Each resolution gets its own subdirectory: OUT_DIR/800x480/, OUT_DIR/480x320/, etc.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${1:?usage: capture-multi.sh OUT_DIR}"

RESOLUTIONS="800x480 480x320 1024x600 1920x1080"
DISPLAY_NUMS="93 94 95 96"

i=0
for RES in $RESOLUTIONS; do
    W="${RES%x*}"
    H="${RES#*x}"
    DNUM=$(echo "$DISPLAY_NUMS" | cut -d' ' -f$((i + 1)))
    echo "=== Capturing at ${W}×${H} (display :${DNUM}) ==="
    NEXUS_SCREEN_W="$W" NEXUS_SCREEN_H="$H" NEXUS_DISPLAY="$DNUM" \
        "$HERE/scripts/capture.sh" "$BASE/${RES}"
    echo "    Done → $BASE/${RES}/"
    i=$((i + 1))
done

echo
echo "All resolutions complete.  Output: $BASE"
echo "  800x480/  ← compare against baseline; must be pixel-identical at 800×480"
echo "  480x320/"
echo "  1024x600/"
echo "  1920x1080/"
