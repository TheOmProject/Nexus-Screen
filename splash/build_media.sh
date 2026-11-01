#!/bin/sh
# Build the panel-ready splash media from the owner's originals; the originals are only read.
#   splash/build_media.sh [SOURCE_DIR] [OUT_DIR]     (defaults: ~/nexus-splash, ~/nexus-splash/build)
# 800x480 with the whole picture kept (black bands), no audio, H.264 for low-cost decoding.
set -eu
SRC=${1:-$HOME/nexus-splash}
OUT=${2:-$SRC/build}
mkdir -p "$OUT"
# Required inputs (place your video files in SRC):
#   intro.mp4  — played once at boot (e.g. a logo animation)
#   loop.mp4   — looped while Nexus Screen loads
VF="scale=800:480:force_original_aspect_ratio=decrease,pad=800:480:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
enc() {
    nice -n 10 ffmpeg -nostdin -v error -y -i "$1" -an -vf "$VF" -c:v libx264 -preset slow -crf 18 \
        -profile:v high -pix_fmt yuv420p -g 24 -movflags +faststart "$2"
}
[ -f "$SRC/intro.mp4" ] || { echo "Missing: $SRC/intro.mp4 (place your intro video there)"; exit 1; }
[ -f "$SRC/loop.mp4"  ] || { echo "Missing: $SRC/loop.mp4  (place your loop video there)"; exit 1; }
enc "$SRC/intro.mp4" "$OUT/intro.mp4"
enc "$SRC/loop.mp4"  "$OUT/loop.mp4"
# fallback still: last frame of the wait loop; PNG to look at, raw RGB565 for the player (no decoding needed)
nice -n 10 ffmpeg -nostdin -v error -y -sseof -0.2 -i "$SRC/voron_micron_wait_loop.mp4" -vf "$VF" \
    -update 1 -frames:v 1 "$OUT/still.png"
nice -n 10 ffmpeg -nostdin -v error -y -i "$OUT/still.png" -vf format=rgb565le -f rawvideo "$OUT/still.rgb565"
cd "$OUT" && sha256sum intro.mp4 loop.mp4 still.png still.rgb565 > SHA256SUMS
