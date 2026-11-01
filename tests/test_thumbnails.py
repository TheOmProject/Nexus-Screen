"""Regression: G-code thumbnails for file names with '+' (OrcaSlicer: 'Lady+of+Guadalupe+…gcode').

Moonraker (Tornado) decodes a literal '+' in a query string as a space, so the metadata request
must send '%2B'. A local fake Moonraker decodes requests the same way; nothing reaches a printer.
Light: no main window, one small server, ~1 s.

    QT_QPA_PLATFORM=offscreen python3 tests/test_thumbnails.py
"""
import http.server
import json
import os
import socketserver
import sys
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QBuffer, QByteArray, QEventLoop, QIODevice, QTimer
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from nexus import theme
from nexus.moonraker.client import MoonrakerClient, api_url, file_url
from nexus.screens.print_files import FilePreviewScreen
from nexus.screens.print_status import ThumbnailView

app = QApplication(sys.argv)
theme.load_fonts()
failures = []
FN = "Lady+of+Guadalupe+100mm_PLA_1h22m.gcode"
STEM = FN[:-len(".gcode")]


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def wait_for(cond, ms=4000):
    end = time.monotonic() + ms / 1000
    while not cond() and time.monotonic() < end:
        loop = QEventLoop(); QTimer.singleShot(20, loop.quit); loop.exec()
    return cond()


def png(size, colour):
    img = QImage(size, size, QImage.Format.Format_RGB32)
    img.fill(QColor(colour))
    buf = QBuffer(ba := QByteArray()); buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


THUMBS = {48: png(48, "#00ff00"), 300: png(300, "#ff0000")}


class FakeMoonraker(http.server.BaseHTTPRequestHandler):
    """Decodes like Tornado: query via parse_qs ('+' = space), path via unquote ('+' literal)."""
    seen = []

    def log_message(self, *a):
        pass

    def _reply(self, code, data, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        u = urlsplit(self.path)
        path, q = unquote(u.path), {k: v[0] for k, v in parse_qs(u.query).items()}
        FakeMoonraker.seen.append((self.command, path, q))
        if path == "/server/files/metadata":
            name = q.get("filename", "")
            if os.path.basename(name) != FN:
                return self._reply(404, json.dumps({"error": {"code": 404, "message": f"File not found {name}"}}).encode())
            meta = {"filename": name, "modified": 1.0, "size": 123, "layer_height": 0.2,
                    "thumbnails": [{"width": w, "height": w, "size": len(b),
                                    "relative_path": f".thumbs/{STEM}-{w}x{w}.png"} for w, b in THUMBS.items()]}
            return self._reply(200, json.dumps({"result": meta}).encode())
        for w, b in THUMBS.items():
            if path.endswith(f"/.thumbs/{STEM}-{w}x{w}.png"):
                return self._reply(200, b, "image/png")
        self._reply(404, b"{}")

    def do_POST(self):
        u = urlsplit(self.path)
        FakeMoonraker.seen.append((self.command, unquote(u.path), {k: v[0] for k, v in parse_qs(u.query).items()}))
        self._reply(200, json.dumps({"result": "ok"}).encode())


# URL building (what goes on the wire)
url = api_url("http://h", "/server/files/metadata", {"filename": FN}).toEncoded().data().decode()
check(url.endswith("filename=Lady%2Bof%2BGuadalupe%2B100mm_PLA_1h22m.gcode"), f"metadata query keeps '+' ({url})")
url = api_url("http://h", "/x", {"filename": "a b&c=d#e.gcode"}).toEncoded().data().decode()
check(url.endswith("filename=a%20b%26c%3Dd%23e.gcode"), f"space, &, =, # encoded ({url})")
url = file_url("http://h", f"/server/files/gcodes/PLA parts/.thumbs/{STEM}-300x300.png").toEncoded().data().decode()
check("/PLA%20parts/.thumbs/Lady%2Bof%2BGuadalupe" in url, f"thumbnail path segments encoded, '/' kept ({url})")

srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeMoonraker)
threading.Thread(target=srv.serve_forever, daemon=True).start()
c = MoonrakerClient("127.0.0.1", srv.server_address[1], 60000, allow_commands=True)

# Print Status: the client fetches metadata + the largest thumbnail for the printing file
for name in (FN, f"PLA parts/{FN}"):
    c._meta = {}
    c._meta_for = name
    c._fetch_metadata(name)
    wait_for(lambda: c._meta.get("thumbnail_state") in ("ready", "none"))
    check(c._meta.get("thumbnail_state") == "ready" and c._meta.get("thumbnail") == THUMBS[300],
          f"Print Status: 300x300 thumbnail loaded for '{name}' ({c._meta.get('thumbnail_state')})")
meta_reqs = [q.get("filename") for m, p, q in FakeMoonraker.seen if p == "/server/files/metadata"]
check(meta_reqs[:2] == [FN, f"PLA parts/{FN}"], f"Moonraker received the exact file names ({meta_reqs})")
view = ThumbnailView()
view.resize(404, 336)
view.set_data({"filename": FN, "thumbnail": c._meta.get("thumbnail"), "thumbnail_state": "ready"})
check(view.state == "ready" and view._source is not None and view._source.width() == 300,
      "Print Status view decodes the PNG (300 px)")
view.grab()  # paints without errors
n = len(FakeMoonraker.seen)
c._meta_for = FN
c._fetch_metadata(FN)
wait_for(lambda: c._meta.get("thumbnail_state") == "ready")
check(not any(p.endswith(".png") for _, p, _ in FakeMoonraker.seen[n:]), "same file again: thumbnail from cache")


# File selection: File Preview loads metadata + thumbnail through the controller
class Ctl:
    get_json, get_bytes = c.get_json, c.get_bytes

    def __getattr__(self, _):
        return lambda *a, **k: False


preview = FilePreviewScreen(Ctl())
preview.resize(800, 444)
preview.load(FN)
wait_for(lambda: preview.thumb.state != "loading")
check(preview.thumb.state == "ready" and preview.thumb._source.width() == 300,
      f"File Preview: 300x300 thumbnail shown ({preview.thumb.state})")
preview.grab()

# Print Start sends the exact name too (query parameter, same encoding)
c._last = {"connected": True, "state": "standby"}
c.call("print_start", query={"filename": FN})
wait_for(lambda: any(p == "/printer/print/start" for _, p, _ in FakeMoonraker.seen))
starts = [q.get("filename") for m, p, q in FakeMoonraker.seen if p == "/printer/print/start"]
check(starts == [FN], f"Print Start (fake server only) receives the exact file name ({starts})")

srv.shutdown()
print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
