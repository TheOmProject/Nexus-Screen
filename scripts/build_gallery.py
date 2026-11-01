#!/usr/bin/env python3
"""Final review gallery: runs the real application once per entry on a private Xvfb
display, saves genuine 800x480 captures and writes index.html (sections, status labels,
navigation inventory). Usage: scripts/build_gallery.py OUT_DIR [--live]"""
import html
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.expanduser("~/nexus-screen-env/bin/python")
XVFB = os.environ.get("NEXUS_XVFB") or (subprocess.run(["which", "Xvfb"], capture_output=True, text=True).stdout.strip() or "Xvfb")
DISPLAY = ":98"
A, R, P = "Approved", "From reference — new", "Provisional — new"

# section, file, title, status, how it is reached, note, app args
E = [
 ("Home", "home-ready", "Home — Ready", A, "Sidebar › Home", "", ["--state", "standby"]),
 ("Home", "home-printing", "Home during a print", A, "Print Status › Home", "Return to Print card", ["--state", "printing", "--review", "home"]),
 ("Home", "home-no-addons", "Home — no add-ons", A, "Sidebar › Home", "Add-ons card hidden", ["--addons", "none"]),
 ("Print", "print-page", "Print (main page)", P, "Sidebar › Print", "No reference: tile pattern of the approved Control page", ["--review", "open:print"]),
 ("Print", "print-files", "Print Files", R, "Print › Print Files", "Folders, sort, preview, rename, delete", ["--review", "open:print_files"]),
 ("Print", "file-preview", "File Preview", P, "Print Files › Preview  ·  Print › Recent file", "No reference", ["--review", "preview-file"]),
 ("Print", "printing", "Printing", A, "Automatic when a print starts", "Real G-code thumbnail", ["--state", "printing", "--sim-file", "Lid_PLA_4h34m.gcode"]),
 ("Print", "paused", "Paused", A, "Pause on Print Status", "Real G-code thumbnail", ["--state", "paused", "--sim-file", "[TPU] NH36Sock_PLA_1h2m.gcode"]),
 ("Print", "baby-step", "Baby Step", P, "Print Status › Baby Step", "Z offset during the print", ["--state", "printing", "--review", "baby-step"]),
 ("Print", "printing-no-preview", "Printing — file without thumbnail", A, "", "'No Preview Available'", ["--state", "printing"]),
 ("Print", "print-complete", "Print Complete", R, "Automatic when a print finishes", "", ["--state", "complete", "--sim-file", "Lid_PLA_4h34m.gcode", "--review", "complete"]),
 ("Filament", "filament-page", "Filament (main page)", A, "Sidebar › Filament", "", ["--review", "open:filament"]),
 ("Filament", "filament", "Filament", A, "Filament › Filament", "", ["--review", "filament"]),
 ("Filament", "filament-heating", "Filament — load heats first", A, "Filament › Load (cold nozzle)", "", ["--review", "filament-heating"]),
 ("Filament", "profiles", "Filament Profiles", A, "Filament › Filament Profiles", "", ["--review", "profiles"]),
 ("Filament", "profiles-edit", "Filament Profiles — edit", A, "Profiles › Edit", "", ["--review", "profiles-edit"]),
 ("Control", "control", "Control (main page)", A, "Sidebar › Control", "Macros, Webcam, Timelapse, Calibrate now enabled", ["--review", "open:control"]),
 ("Control", "move", "Move", A, "Control › Move", "", ["--review", "move"]),
 ("Control", "temperature", "Temperature", A, "Control › Temperature  ·  Temperatures card ›", "", ["--review", "temperature"]),
 ("Control", "fans", "Fans", A, "Control › Fans", "", ["--review", "fans"]),
 ("Control", "lighting", "Lighting", A, "Control › Lighting", "", ["--review", "lighting"]),
 ("Control", "extruder", "Extruder", A, "Control › Extruder", "", ["--review", "extruder"]),
 ("Control", "macros", "Macros", R, "Control › Macros", "Printer's own macros; Run asks first", ["--review", "open:macros"]),
 ("Control", "webcam", "Webcam", R, "Control › Webcam  ·  Tools › Webcam", "Simulated test image (this printer has no webcam configured)", ["--review", "open:webcam"]),
 ("Control", "timelapse", "Timelapse", R, "Control › Timelapse  ·  Settings › Timelapse", "moonraker-timelapse is not loaded on this printer", ["--review", "open:timelapse"]),
 ("Calibration", "calibrate", "Calibrate", R, "Control › Calibrate", "Undefined entries disabled", ["--review", "open:calibrate"]),
 ("Calibration", "z-offset", "Z Offset", R, "Control › Z Offset  ·  Calibrate", "", ["--review", "z-offset"]),
 ("Calibration", "bed-screws", "Bed Screws", R, "Control › Bed Screws", "", ["--review", "bed-screws"]),
 ("Calibration", "bed-mesh", "Bed Mesh", A, "Control › Bed Mesh  ·  Calibrate", "", ["--review", "bed-mesh"]),
 ("Calibration", "input-shaper", "Input Shaper", R, "Calibrate › Input Shaper", "", ["--review", "open:input_shaper"]),
 ("Calibration", "limits", "Limits", R, "Calibrate › Axis Limits", "", ["--review", "open:limits"]),
 ("Calibration", "maintenance", "Maintenance", R, "Settings › Maintenance", "Undefined entries disabled", ["--review", "open:maintenance"]),
 ("Settings", "settings-page", "Settings (main page)", P, "Sidebar › Settings", "Reference shows these tiles as a submenu", ["--review", "open:settings"]),
 ("Settings", "screen", "Screen", R, "Settings › Screen", "Brightness (real backlight on the Pi)", ["--review", "open:screen"]),
 ("Settings", "screen-timeout", "Screen — timeout", R, "Screen › Screen Timeout", "", ["--review", "screen-timeout"]),
 ("Settings", "printer-settings", "Printer Settings", R, "Settings › Printer", "Runtime limits only", ["--review", "open:printer"]),
 ("Settings", "network", "Network", R, "Settings › Network", "Read-only", ["--review", "open:network"]),
 ("Settings", "camera-settings", "Camera Settings", R, "Settings › Camera", "", ["--review", "open:camera"]),
 ("Settings", "firmware", "Firmware", R, "Settings › Firmware  ·  Tools › Firmware", "", ["--review", "open:firmware"]),
 ("Settings", "system", "System", R, "Settings › System  ·  Tools › System", "", ["--review", "open:system"]),
 ("Settings", "tools", "Tools", R, "Settings › Tools", "", ["--review", "open:tools"]),
 ("Settings", "console", "Console", R, "Tools › Console", "", ["--review", "open:console"]),
 ("Settings", "logs", "Logs", R, "Tools › Logs  ·  Error › View Logs", "", ["--review", "open:logs"]),
 ("Settings", "help", "Help", R, "Settings › Help", "Only About and doc links have content", ["--review", "open:help"]),
 ("Settings", "about", "About", P, "Help › About  ·  Settings › About", "No reference", ["--review", "open:about"]),
 ("BoxTurtle", "bt-dashboard", "BoxTurtle Dashboard", A, "Add-ons card  ·  Filament › BoxTurtle", "", ["--review", "bt-dashboard"]),
 ("BoxTurtle", "bt-8-lanes", "BoxTurtle Dashboard — 8 lanes", A, "", "", ["--review", "bt-dashboard", "--lanes", "8"]),
 ("BoxTurtle", "bt-controls", "BoxTurtle Controls", A, "Dashboard › Manage", "", ["--review", "bt-controls"]),
 ("StealthChanger", "sc-dashboard", "StealthChanger Dashboard", A, "Add-ons card  ·  Filament › StealthChanger", "", ["--review", "sc-dashboard"]),
 ("StealthChanger", "sc-controls", "StealthChanger Controls", A, "Dashboard › Manage", "Selected tool highlight (fix)", ["--review", "sc-controls"]),
 ("Dialogs and error states", "stop-confirm", "Stop Print?", A, "Print Status › Stop", "", ["--state", "printing", "--review", "stop-dialog"]),
 ("Dialogs and error states", "error-detected", "Error Detected", R, "Automatic on a Klipper error", "", ["--state", "error"]),
 ("Dialogs and error states", "print-confirm", "Start print?", P, "Preview › Start Print", "Approved dialog style", ["--review", "print-confirm"]),
 ("Dialogs and error states", "keypad", "Temperature keypad", A, "Tap Nozzle / Bed", "", ["--review", "keypad-nozzle"]),
 ("Dialogs and error states", "keypad-invalid", "Keypad — out of range", A, "", "", ["--review", "keypad-bed"]),
 ("Dialogs and error states", "keyboard", "On-screen keyboard", P, "Console entry · Rename · Macro search", "No reference", ["--review", "keyboard"]),
 ("Dialogs and error states", "pid-confirm", "PID tune confirmation", A, "", "", ["--review", "pid-confirm"]),
 ("Dialogs and error states", "zoffset-confirm", "Z offset preset confirmation", R, "", "", ["--review", "zoffset-confirm"]),
 ("Dialogs and error states", "macro-confirm", "Run macro confirmation", R, "", "", ["--review", "macro-confirm"]),
 ("Dialogs and error states", "colour-picker", "Colour picker", A, "", "", ["--review", "colour-picker"]),
 ("Dialogs and error states", "material-picker", "Material picker", A, "", "", ["--review", "material-picker"]),
 ("Dialogs and error states", "disconnected", "Moonraker disconnected", A, "Automatic", "Controls disabled, screen kept", ["--state", "printing", "--review", "disconnected"]),
]
LIVE = [
 ("Live (real printer, read-only)", "live-home", "Home — live", "", "", "", ["--live", "--delay", "3500"]),
 ("Live (real printer, read-only)", "live-print-files", "Print Files — live", "", "", "Your 38 G-code files", ["--live", "--delay", "4000", "--review", "open:print_files"]),
 ("Live (real printer, read-only)", "live-macros", "Macros — live", "", "", "Your printer's macros", ["--live", "--delay", "4000", "--review", "open:macros"]),
 ("Live (real printer, read-only)", "live-bed-mesh", "Bed Mesh — live", "", "", "", ["--live", "--delay", "5000", "--review", "bed-mesh-default"]),
 ("Live (real printer, read-only)", "live-system", "System — live", "", "", "", ["--live", "--delay", "4500", "--review", "open:system"]),
 ("Live (real printer, read-only)", "live-logs", "Logs — live", "", "", "klippy.log tail", ["--live", "--delay", "4500", "--review", "open:logs"]),
 ("Live (real printer, read-only)", "live-network", "Network — live", "", "", "", ["--live", "--delay", "4000", "--review", "open:network"]),
 ("Live (real printer, read-only)", "live-webcam", "Webcam — live", "", "", "No webcam configured", ["--live", "--delay", "4000", "--review", "open:webcam"]),
]


def main():
    out = os.path.abspath(sys.argv[1])
    entries = E + (LIVE if "--live" in sys.argv else [])
    os.makedirs(out, exist_ok=True)
    build = subprocess.run(["git", "-C", HERE, "describe", "--always", "--dirty"], capture_output=True, text=True).stdout.strip()
    xvfb = subprocess.Popen([XVFB, DISPLAY, "-screen", "0", "800x480x24", "-nolisten", "tcp", "-noreset"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    env = dict(os.environ, DISPLAY=DISPLAY, QT_QPA_PLATFORM="xcb")
    errors = 0
    try:
        with open(os.path.join(out, "app-stderr.log"), "w") as err:
            for sec, name, *_rest, args in entries:
                r = subprocess.run([PY, os.path.join(HERE, "main.py"), "--capture", os.path.join(out, name + ".png"), *args],
                                   env=env, stdout=subprocess.PIPE, stderr=err, text=True)
                ok = "capture saved" in r.stdout
                errors += not ok
                print(("ok   " if ok else "FAIL ") + name, flush=True)
    finally:
        xvfb.terminate()
    write_index(out, entries, build)
    print(f"{len(entries) - errors}/{len(entries)} captures, build {build}")


def write_index(out, entries, build):
    badge = {A: "ok", R: "ref", P: "prov"}
    sections = list(dict.fromkeys(e[0] for e in entries))
    toc = " · ".join(f'<a href="#s{i}">{i + 1}. {html.escape(s)}</a>' for i, s in enumerate(sections))
    body = []
    for i, sec in enumerate(sections):
        body.append(f'<h2 id="s{i}">{i + 1}. {html.escape(sec)}</h2><div class="grid">')
        for s, name, title, status, path, note, _ in entries:
            if s != sec:
                continue
            tag = f'<em class="{badge.get(status, "live")}">{html.escape(status or "Live · read-only")}</em>'
            sub = " · ".join(html.escape(x) for x in (path, note) if x)
            body.append(f'<figure><a href="{name}.png"><img src="{name}.png" alt="{html.escape(title)}" loading="lazy"></a>'
                        f'<figcaption>{html.escape(title)} {tag}<span>{sub}</span></figcaption></figure>')
        body.append("</div>")
    inv = "".join(f"<tr><td>{html.escape(s)}</td><td>{html.escape(t)}</td><td>{html.escape(p or '—')}</td>"
                  f'<td><em class="{badge[st]}">{st}</em></td></tr>'
                  for s, n, t, st, p, _, _ in E)
    counts = {k: sum(1 for e in E if e[3] == k) for k in (A, R, P)}
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Nexus Screen Review</title><style>
:root{{--bg:#0b0c0e;--card:#14171b;--line:#262a30;--fg:#e9ecef;--dim:#8d939b}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;padding:24px 16px}}
main{{max-width:1680px;margin:0 auto}}h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:15px;margin:36px 0 12px;color:var(--dim);text-transform:uppercase;letter-spacing:.08em}}
p{{color:var(--dim);margin:4px 0}}a{{color:var(--fg)}}code{{color:var(--fg)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,520px),1fr));gap:16px}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px}}
figure img{{display:block;width:100%;height:auto;border-radius:4px}}figcaption{{margin-top:6px;font-weight:600}}
figcaption span{{display:block;font-weight:400;color:var(--dim);font-size:13px}}
em{{font-style:normal;font-size:11px;font-weight:700;padding:1px 6px;border-radius:4px;margin-left:6px;white-space:nowrap}}
.ok{{background:#12361f;color:#5ee08a}}.ref{{background:#162a44;color:#8cc4ff}}.prov{{background:#4a3208;color:#ffc35a}}.live{{background:#2a2d33;color:#c9ced5}}
table{{border-collapse:collapse;width:100%;max-width:1100px}}td,th{{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}}th{{color:var(--dim)}}
</style></head><body><main>
<h1>Nexus Screen — complete interface review</h1>
<p>Genuine 800×480 captures of the running PyQt6 application (one run per screen, X screen grab on a private
Xvfb display, Raspberry Pi 4). Build <code>{html.escape(build)}</code>. Simulated data unless in the Live section
(real Moonraker, printer commands disabled).</p>
<p><em class="ok">{A}</em> {counts[A]} · <em class="ref">{R}</em> {counts[R]} · <em class="prov">{P}</em> {counts[P]} — new
screens need your approval; provisional ones had no reference image.</p>
<p>{toc} · <a href="#inventory">Navigation inventory</a></p>
{''.join(body)}
<h2 id="inventory">Navigation inventory</h2>
<p>Every screen below is reachable through the normal interface; an automated test taps through the UI from the
sidebar and fails if any registered screen cannot be reached.</p>
<table><tr><th>Section</th><th>Screen / state</th><th>How it is reached</th><th>Status</th></tr>{inv}</table>
</main></body></html>"""
    with open(os.path.join(out, "index.html"), "w") as fh:
        fh.write(page)


if __name__ == "__main__":
    main()
