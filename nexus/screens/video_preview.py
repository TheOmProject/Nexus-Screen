"""In-app video preview screen for the Startup Video settings.

Plays a pack's intro.mp4 (then its loop.mp4) inside a Qt QLabel using QProcess
to pipe ffmpeg RGB24 frames without touching /dev/fb0.  The preview is completely
isolated from the active splash service.

Frame pipeline:  ffmpeg → stdout (rgb24, PREV_W×PREV_H) → QByteArray buffer →
                  QImage(Format_RGB888) → QPixmap → QLabel

All geometry uses the adaptive sx()/sy()/smin() helpers from nexus.config so the
screen renders correctly at any supported display resolution.
"""
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QByteArray, QProcess, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget

import importlib.util as _imu
if _imu.find_spec("nexus_video") is None:
    _prod = Path.home() / "nexus-video"
    _dev  = Path(__file__).resolve().parent.parent.parent.parent
    _nv   = _prod if (_prod / "nexus_video").exists() else _dev
    if str(_nv) not in sys.path:
        sys.path.insert(0, str(_nv))
del _imu

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.widgets.buttons import SmallButton
from nexus.widgets.panels import SubScreen

# ── preview frame geometry (design space: 800×480) ───────────────────────────
PREV_W      = sx(640)
PREV_H      = sy(360)
FRAME_BYTES = PREV_W * PREV_H * 3   # RGB24

FPS        = 24
_CANVAS_X  = sx(80)
_CANVAS_Y  = sy(58)


class VideoPreviewScreen(SubScreen):
    """Settings > Startup Video > Preview: plays intro then loops loop.mp4 in-app."""

    TITLE    = "Video Preview"
    SUBTITLE = "In-app boot animation preview"

    def __init__(self, intro_path: Optional[Path] = None,
                 loop_path: Optional[Path] = None,
                 pack_name: str = "", ctl=None, parent=None):
        super().__init__(parent)
        self._ctl          = ctl
        self._intro_path   = intro_path
        self._loop_path    = loop_path
        self._pack_name    = pack_name or "Unknown Pack"

        self._proc: Optional[QProcess] = None
        self._buf          = QByteArray()
        self._playing_loop = False
        self._frame_count  = 0
        self._error_text   = ""
        self._stopped      = False

        # ── video canvas label ────────────────────────────────────────────────
        self._canvas = QLabel(self)
        self._canvas.setGeometry(_CANVAS_X, _CANVAS_Y, PREV_W, PREV_H)
        self._canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas.setStyleSheet("background: #000;")

        # ── control bar ───────────────────────────────────────────────────────
        ctrl_y  = _CANVAS_Y + PREV_H + smin(8)
        btn_w   = sx(100)
        btn_h   = sy(44)
        gap     = smin(8)
        total_w = 3 * btn_w + 2 * gap
        bx      = _CANVAS_X + (PREV_W - total_w) // 2

        self._btn_play = SmallButton("Play",  parent=self, font_px=theme.BUTTON)
        self._btn_stop = SmallButton("Stop",  parent=self, font_px=theme.BUTTON)
        self._btn_back = SmallButton("Back",  parent=self, font_px=theme.BUTTON)

        self._btn_play.setGeometry(bx,                 ctrl_y, btn_w, btn_h)
        self._btn_stop.setGeometry(bx + btn_w + gap,   ctrl_y, btn_w, btn_h)
        self._btn_back.setGeometry(bx + 2*(btn_w+gap), ctrl_y, btn_w, btn_h)

        self._btn_play.clicked.connect(self._on_play)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_back.clicked.connect(self._on_back)
        self._update_buttons(playing=False)

        # ── status label ─────────────────────────────────────────────────────
        self._status = QLabel("", self)
        self._status.setGeometry(_CANVAS_X, ctrl_y + btn_h + sy(4), PREV_W, sy(20))
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            f"color: {theme.DIM}; font-size: {theme.CAPTION}px;")
        self._set_status(f"Pack: {self._pack_name}  —  press Play to preview")

        # Frame-pacing timer (fires at FPS to stay at target rate)
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(1000 // FPS)
        self._frame_timer.timeout.connect(self._on_frame_tick)

    # ── controls ──────────────────────────────────────────────────────────────

    def _on_play(self):
        self._stopped    = False
        self._error_text = ""
        self._start_intro()

    def _on_stop(self):
        self._stopped = True
        self._kill_proc()
        self._set_status("Stopped.")
        self._update_buttons(playing=False)

    def _on_back(self):
        self._on_stop()
        if self._ctl is not None:
            self._ctl.back()

    def _update_buttons(self, *, playing: bool) -> None:
        self._btn_play.setEnabled(not playing)
        self._btn_stop.setEnabled(playing)

    # ── playback ──────────────────────────────────────────────────────────────

    def _start_intro(self):
        if not self._intro_path or not self._intro_path.exists():
            self._show_error("intro.mp4 not found")
            return
        self._playing_loop = False
        self._frame_count  = 0
        self._buf.clear()
        self._set_status(f"Playing intro  —  {self._pack_name}")
        self._update_buttons(playing=True)
        self._launch(self._intro_path, loop=False)

    def _start_loop(self):
        if not self._loop_path or not self._loop_path.exists():
            self._show_error("loop.mp4 not found")
            return
        self._playing_loop = True
        self._frame_count  = 0
        self._buf.clear()
        self._set_status(f"Playing loop  —  {self._pack_name}")
        self._launch(self._loop_path, loop=True)

    def _launch(self, path: Path, *, loop: bool) -> None:
        self._kill_proc()
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._on_data_ready)
        self._proc.finished.connect(self._on_proc_finished)
        self._proc.errorOccurred.connect(self._on_proc_error)

        args = ["-nostdin", "-v", "error", "-threads", "2"]
        if loop:
            args += ["-stream_loop", "-1"]
        args += ["-i", str(path),
                 "-an", "-vf", f"scale={PREV_W}:{PREV_H}",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]

        self._proc.start("ffmpeg", args)
        self._frame_timer.start()

    def _kill_proc(self) -> None:
        self._frame_timer.stop()
        if self._proc is not None:
            if self._proc.state() != QProcess.ProcessState.NotRunning:
                self._proc.kill()
                self._proc.waitForFinished(500)
            self._proc = None
        self._buf.clear()

    # ── ffmpeg data handling ──────────────────────────────────────────────────

    def _on_data_ready(self) -> None:
        if self._proc:
            self._buf.append(self._proc.readAllStandardOutput())

    def _on_frame_tick(self) -> None:
        if len(self._buf) < FRAME_BYTES:
            return
        raw = bytes(self._buf[:FRAME_BYTES])
        self._buf = self._buf[FRAME_BYTES:]
        img = QImage(raw, PREV_W, PREV_H, PREV_W * 3, QImage.Format.Format_RGB888)
        px  = QPixmap.fromImage(img)
        self._canvas.setPixmap(px)
        self._frame_count += 1

    def _on_proc_finished(self, exit_code: int, _) -> None:
        self._frame_timer.stop()
        if self._stopped:
            return
        if not self._playing_loop and exit_code == 0:
            # intro finished cleanly → start loop
            self._start_loop()
        elif exit_code != 0 and self._frame_count == 0:
            self._show_error(f"ffmpeg exited with code {exit_code}")
        else:
            self._set_status("Preview finished.")
            self._update_buttons(playing=False)

    def _on_proc_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._show_error("ffmpeg not found")
        else:
            self._show_error("ffmpeg error")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _show_error(self, msg: str) -> None:
        self._error_text = msg
        self._kill_proc()
        self._set_status(f"Error: {msg}")
        self._update_buttons(playing=False)
        pm = QPixmap(PREV_W, PREV_H)
        pm.fill(QColor(10, 10, 12))
        p = QPainter(pm)
        p.setPen(QColor(theme.AMBER))
        p.setFont(QFont("system-ui", smin(14)))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, f"Preview Error\n{msg}")
        p.end()
        self._canvas.setPixmap(pm)

    def _set_status(self, msg: str) -> None:
        self._status.setText(msg)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        # Auto-play when navigated to
        if not self._stopped:
            QTimer.singleShot(50, self._on_play)
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._kill_proc()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._kill_proc()
        super().closeEvent(event)

    def load_pack(self, intro_path: Optional[Path], loop_path: Optional[Path],
                  pack_name: str) -> None:
        """Reset state for a new pack. Call before pushing this screen."""
        self._kill_proc()
        self._intro_path   = intro_path
        self._loop_path    = loop_path
        self._pack_name    = pack_name or "Unknown Pack"
        self._stopped      = False
        self._error_text   = ""
        self._frame_count  = 0
        self._playing_loop = False
        pm = QPixmap(PREV_W, PREV_H)
        pm.fill(QColor(10, 10, 12))
        self._canvas.setPixmap(pm)
        self._set_status(f"Pack: {self._pack_name}  —  press Play to preview")
        self._update_buttons(playing=False)
