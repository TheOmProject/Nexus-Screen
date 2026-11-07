"""Nexus Sounds settings screen for Nexus Screen.

Allows users to configure the Nexus Sounds audio notification addon from the
Nexus Screen Settings menu. Controls master enable, volume, mute, sound theme
selection, per-event sound selection, and sound preview.

Nexus Sounds is an optional dependency. When not installed the screen shows an
installation notice rather than the controls.
"""
import os
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QScrollArea, QWidget

from nexus import theme
try:
    from nexus.config import sx, sy, smin, SCREEN_W, SCREEN_H
except ImportError:
    SCREEN_W, SCREEN_H = 800, 480
    def sx(v: float) -> int: return round(v)
    def sy(v: float) -> int: return round(v)
    def smin(v: float) -> int: return round(v)
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.glow_widget import paint_panel, panel_path, red_glow
from nexus.widgets.panels import SubScreen, Panel, ListPanel, text_row, ActionTile

# Locate nexus_sounds: production install at ~/nexus-sounds/, dev override via env.
import importlib.util as _imu
if _imu.find_spec("nexus_sounds") is None:
    _prod = Path.home() / "nexus-sounds"
    _dev_override = os.environ.get("NEXUS_SOUNDS_DIR", "")
    _ns = Path(_dev_override) if _dev_override and Path(_dev_override).exists() else _prod
    if str(_ns) not in sys.path:
        sys.path.insert(0, str(_ns))
del _imu

try:
    from nexus_sounds.settings_bridge import (
        is_installed,
        get_config,
        set_enabled,
        set_muted,
        set_volume,
        list_packs,
        set_theme,
        set_event_enabled,
        get_event_sounds,
        set_event_sound,
        list_sounds_for_pack,
        preview_file,
    )
    _BRIDGE_OK = True
except ImportError:
    _BRIDGE_OK = False


# ── event display metadata ────────────────────────────────────────────────────
_EVENTS = [
    ("startup",         "Startup"),
    ("print_start",     "Print Start"),
    ("print_complete",  "Print Complete"),
    ("print_error",     "Print Error"),
    ("print_cancelled", "Print Cancelled"),
    ("print_paused",    "Print Paused"),
    ("print_resumed",   "Print Resumed"),
]
_EVENTS_BY_KEY = dict(_EVENTS)

_EVENT_ICONS = {
    "startup":          icons.gear,
    "print_start":      icons.play,
    "print_complete":   icons.check_ring,
    "print_error":      icons.alert_ring,
    "print_cancelled":  icons.stop_square,
    "print_paused":     icons.pause_ring,
    "print_resumed":    icons.play_ring,
}

_CONTENT_Y = 58
_BTN_H     = 48
_GAP       = 8
_MX        = 16


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


def _pack_info_str(pack_id: str) -> str:
    """Return '4 sounds · 123 KB' for a pack."""
    if not _BRIDGE_OK:
        return ""
    sounds = list_sounds_for_pack(pack_id)
    count = len(sounds)
    base = Path.home() / "nexus-sounds"
    env = os.environ.get("NEXUS_SOUNDS_DIR", "")
    if env and Path(env).is_dir():
        base = Path(env)
    total_bytes = 0
    for sub in ("builtin", "custom"):
        pack_dir = base / "packs" / sub / pack_id
        if pack_dir.exists():
            for f in pack_dir.glob("*.wav"):
                try:
                    total_bytes += f.stat().st_size
                except OSError:
                    pass
            break
    if total_bytes < 1024 * 1024:
        size_str = f"{total_bytes // 1024} KB"
    else:
        size_str = f"{total_bytes / (1024 * 1024):.1f} MB"
    return f"{count} sound{'s' if count != 1 else ''} · {size_str}"


# ── _draw_toggle ──────────────────────────────────────────────────────────────

def _draw_toggle(p: QPainter, x: float, y: float, w: float, h: float, on: bool) -> None:
    """Draw an inline toggle pill at (x,y) size (w×h). ON=red, OFF=grey."""
    r = QRectF(x, y, w, h)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(200, 28, 22) if on else QColor(50, 55, 64))
    p.drawRoundedRect(r, h / 2, h / 2)
    tr = h * 0.42
    margin = h * 0.09
    tx = x + w - margin - tr * 2 if on else x + margin
    ty = y + (h - tr * 2) / 2
    p.setBrush(QColor(235, 237, 240))
    p.drawEllipse(QRectF(tx, ty, tr * 2, tr * 2))


# ── _ToggleCard ───────────────────────────────────────────────────────────────

class _ToggleCard(QAbstractButton):
    """Dark rectangular panel with icon, label, ON/OFF state, and toggle switch."""

    def __init__(self, icon_fn, label: str, state: bool = False, parent=None):
        super().__init__(parent)
        self._icon_fn = icon_fn
        self._label = label
        self._on = state
        self.setCheckable(True)
        self.setChecked(state)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.toggled.connect(self._sync)

    def _sync(self, checked: bool) -> None:
        self._on = checked
        self.update()

    def set_state(self, on: bool) -> None:
        if on != self._on:
            self._on = on
            self.setChecked(on)
            self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = QRectF(2, 2, w - 4, h - 4)
        on = self.isEnabled()

        if self._on and on:
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, QColor(70, 8, 8, 200))
            grad.setColorAt(1, QColor(28, 4, 4, 200))
            p.fillPath(panel_path(r, 6), grad)
            p.setPen(QPen(QColor(255, 42, 32), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.7, 0.7, -0.7, -0.7), 6, 6)
        else:
            paint_panel(p, r, 6, top=QColor(22, 25, 29), bottom=QColor(13, 15, 18),
                        border=QColor(46, 50, 57))

        pad = 10.0
        isz = min(20.0, h * 0.33)
        ic_col = (QColor(theme.FG) if (self._on and on)
                  else QColor(theme.FG_SOFT) if on else QColor(theme.MUTED))
        self._icon_fn(p, QRectF(r.x() + pad, r.y() + pad, isz, isz), ic_col)

        p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
        label_col = QColor(theme.FG_SOFT) if on else QColor(theme.MUTED)
        p.setPen(label_col)
        p.drawText(QRectF(r.x() + pad + isz + 6, r.y() + pad - 2, r.width() - pad - isz - 16, isz + 4),
                   Qt.AlignmentFlag.AlignVCenter, self._label)

        sw_w = sx(44)
        sw_h = sy(22)
        sw_x = r.right() - sw_w - 6
        sw_y = r.bottom() - sw_h - 7
        _draw_toggle(p, sw_x, sw_y, sw_w, sw_h, bool(self._on and on))

        p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
        p.setPen(QColor(theme.FG) if (self._on and on) else QColor(theme.DIM))
        p.drawText(QRectF(r.x() + pad, sw_y, sw_x - r.x() - pad - 4, sw_h),
                   Qt.AlignmentFlag.AlignVCenter, "ON" if self._on else "OFF")
        p.end()


# ── _LargeVolLabel ────────────────────────────────────────────────────────────

class _LargeVolLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 70

    def set_pct(self, pct: int) -> None:
        pct = max(0, min(100, pct))
        if pct != self._pct:
            self._pct = pct
            self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(theme.font(28, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(0, 0, self.width(), self.height()),
                   Qt.AlignmentFlag.AlignCenter, f"{self._pct}%")
        p.end()


# ── _event_row ────────────────────────────────────────────────────────────────

def _event_row(p: QPainter, r: QRectF, item: dict, _selected: bool) -> None:
    """Row painter: event icon + bold name + filename right-aligned + chevron."""
    icon_fn = _EVENT_ICONS.get(item["key"], icons.play)
    isz = min(18.0, r.height() * 0.36)
    icon_fn(p, QRectF(r.x() + 10, r.center().y() - isz / 2, isz, isz), QColor(theme.FG_SOFT))

    p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
    p.setPen(QColor(theme.FG))
    name_x = r.x() + 10 + isz + 8
    name_w = r.width() * 0.38
    p.drawText(QRectF(name_x, r.y(), name_w, r.height()), Qt.AlignmentFlag.AlignVCenter, item["label"])

    fn = item["filename"]
    p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
    p.setPen(QColor(theme.DIM))
    fn_right = r.right() - sx(26)
    fn_x = name_x + name_w + sx(4)
    fn_w = fn_right - fn_x
    if fn and fn_w > 20:
        p.drawText(QRectF(fn_x, r.y(), fn_w, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   _truncate(fn, 22))

    icons.chevron(p, QRectF(r.right() - 20, r.center().y() - 6, 8, 12), QColor(theme.FG_SOFT), 1.8)


# ── PackSoundsScreen ──────────────────────────────────────────────────────────

class PackSoundsScreen(SubScreen):
    """Browse sounds in one pack. Tap a sound to preview it."""

    TITLE = "Pack"
    SUBTITLE = "Tap a sound to preview"

    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self._app = app
        self._pack_id: Optional[str] = None
        self._list = ListPanel(
            "",
            painter=text_row(name=lambda item: item["filename"], sub=None, chevron=False),
            rows=8,
            parent=self,
            top=4,
            empty_text="No sounds in this pack",
        )
        self._list.key = lambda item: item["filename"]
        self._list.chosen.connect(self._on_choose)
        if app is not None and hasattr(app, "stack"):
            app.stack.addWidget(self)

    def load_pack(self, pack_id: str, pack_name: str) -> None:
        self._pack_id = pack_id
        self.TITLE = pack_name
        self.SUBTITLE = "Tap a sound to preview"
        sounds = list_sounds_for_pack(pack_id) if _BRIDGE_OK else []
        self._list.set_items([{"filename": s["filename"]} for s in sounds])
        self.update()
        if self._app is not None:
            self._app.push(self)

    def _on_choose(self, item: dict) -> None:
        if _BRIDGE_OK and item.get("filename"):
            preview_file(item["filename"])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return
        mx = sx(_MX)
        self._list.setGeometry(mx, sy(_CONTENT_Y), w - 2 * mx, h - sy(_CONTENT_Y) - sy(_GAP))


# ── SoundPacksScreen ──────────────────────────────────────────────────────────

class SoundPacksScreen(SubScreen):
    """Two-column pack browser: left scrollable list, right detail + actions."""

    TITLE = "Sound Packs"
    SUBTITLE = "Browse and manage installed packs"

    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self._app = app
        self._pack_sounds = PackSoundsScreen(app=app)
        self._packs: list[dict] = []
        self._selected: Optional[dict] = None
        self._info_str: str = ""
        self._right_x: int = 0
        self._right_w: int = 0

        self._pack_list = ListPanel(
            "",
            painter=text_row(
                name=lambda item: item["name"],
                sub=lambda item: "Active" if item["is_active"] else "",
                chevron=False,
                colour=lambda item: "#ff2a20" if item["is_active"] else None,
            ),
            rows=6,
            parent=self,
            top=4,
            empty_text="No packs found",
        )
        self._pack_list.key = lambda item: item["id"]
        self._pack_list.chosen.connect(self._on_pack_select)

        self._btn_browse = SmallButton("Browse Sounds", parent=self, font_px=theme.BUTTON, checkable=False)
        self._btn_browse.clicked.connect(self._on_browse)

        self._btn_activate = SmallButton("Set as Active", parent=self, font_px=theme.BUTTON, checkable=False)
        self._btn_activate.clicked.connect(self._on_activate)

        if app is not None and hasattr(app, "stack"):
            app.stack.addWidget(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if not _BRIDGE_OK:
            return
        self._packs = list_packs()
        active_id = next((p["id"] for p in self._packs if p["is_active"]), None)
        self._pack_list.set_items(self._packs, selected=active_id)
        if not self._selected or not any(p["id"] == self._selected["id"] for p in self._packs):
            self._selected = next((p for p in self._packs if p["is_active"]),
                                  self._packs[0] if self._packs else None)
        self._sync_selection()

    def _on_pack_select(self, item: dict) -> None:
        self._selected = item
        self._sync_selection()

    def _sync_selection(self) -> None:
        if self._selected:
            self._info_str = _pack_info_str(self._selected["id"])
            is_active = self._selected["is_active"]
            self._btn_activate.setEnabled(not is_active)
        else:
            self._info_str = ""
            self._btn_activate.setEnabled(False)
        self.update()

    def _on_browse(self) -> None:
        if self._selected:
            self._pack_sounds.load_pack(self._selected["id"], self._selected["name"])

    def _on_activate(self) -> None:
        if _BRIDGE_OK and self._selected:
            set_theme(self._selected["id"])
            self._refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return
        mx = sx(_MX)
        gap = sy(_GAP)
        bh = sy(_BTN_H)
        cw = w - 2 * mx
        left_w = int(cw * 0.44)
        right_x = mx + left_w + gap
        right_w = cw - left_w - gap
        content_y = sy(_CONTENT_Y)
        content_h = h - content_y - gap

        self._right_x = right_x
        self._right_w = right_w

        self._pack_list.setGeometry(mx, content_y, left_w, content_h)
        self._btn_activate.setGeometry(right_x, h - bh - gap, right_w, bh)
        self._btn_browse.setGeometry(right_x, h - 2 * bh - 2 * gap, right_w, bh)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._selected or not self._right_x:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rx = self._right_x
        rw = self._right_w
        y = sy(_CONTENT_Y)
        gap = sy(_GAP)

        # Pack name
        p.setFont(theme.font(theme.HEADING, QFont.Weight.DemiBold))
        p.setPen(QColor(theme.FG))
        name_h = sy(28)
        p.drawText(QRectF(rx, y, rw, name_h), Qt.AlignmentFlag.AlignVCenter,
                   _truncate(self._selected["name"], 24))
        y += name_h + gap

        # Active badge
        if self._selected["is_active"]:
            badge_text = "Active"
            p.setFont(theme.font(theme.SMALL, QFont.Weight.DemiBold))
            fm = p.fontMetrics()
            bw = fm.horizontalAdvance(badge_text) + sx(14)
            bh2 = sy(20)
            br = QRectF(rx, y, bw, bh2)
            p.setBrush(QColor(100, 10, 8))
            p.setPen(QPen(QColor(255, 42, 32), 1.0))
            p.drawRoundedRect(br, bh2 / 2, bh2 / 2)
            p.setPen(QColor(255, 42, 32))
            p.drawText(br, Qt.AlignmentFlag.AlignCenter, badge_text)
            y += bh2 + gap

        # Info line
        if self._info_str:
            p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(rx, y, rw, sy(22)), Qt.AlignmentFlag.AlignVCenter, self._info_str)

        p.end()


# ── EventSoundScreen ──────────────────────────────────────────────────────────

class EventSoundScreen(SubScreen):
    """Per-event sound selection — two-column layout.

    Left (~58%): scrollable sound list.
    Right (~42%): Enable toggle + SELECTED SOUND header + filename + Preview/Apply/Cancel.
    All geometry derived from self.rect() in _layout_widgets().
    """

    TITLE = "Event Sound"
    SUBTITLE = "Select a sound or turn off"

    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self._app = app
        self._event_key: str = "startup"
        self._pending_filename: Optional[str] = None
        self._sound_btns: list[tuple[Optional[str], QWidget]] = []
        self._btn_enable: Optional[SmallButton] = None
        self._btn_preview: Optional[SmallButton] = None
        self._btn_apply: Optional[ActionTile] = None
        self._btn_cancel: Optional[SmallButton] = None
        self._scroll: Optional[QScrollArea] = None
        self._scroll_container: Optional[QWidget] = None
        self._right_x: int = 0
        self._right_w: int = 0
        self._sel_y: int = 0
        self._sel_h: int = 0
        if app is not None and hasattr(app, "stack"):
            app.stack.addWidget(self)

    def set_event(self, event_key: str) -> None:
        self._event_key = event_key
        self.TITLE = _EVENTS_BY_KEY.get(event_key, event_key)
        self.SUBTITLE = "Select a sound or turn off"
        if _BRIDGE_OK:
            self._pending_filename = get_event_sounds().get(event_key)
        else:
            self._pending_filename = None
        self._rebuild()
        if self._app is not None:
            self._app.push(self)

    def _rebuild(self) -> None:
        for _, btn in self._sound_btns:
            btn.setParent(None)
            btn.deleteLater()
        self._sound_btns.clear()
        for w in (self._btn_enable, self._btn_preview, self._btn_apply, self._btn_cancel):
            if w:
                w.setParent(None)
                w.deleteLater()
        self._btn_enable = self._btn_preview = self._btn_apply = self._btn_cancel = None
        if self._scroll:
            self._scroll.setParent(None)
            self._scroll.deleteLater()
            self._scroll = None
            self._scroll_container = None

        # Determine enable state
        enabled = True
        if _BRIDGE_OK:
            enabled = get_config().get("events", {}).get(self._event_key, True)

        # Enable toggle button (top of right column)
        self._btn_enable = SmallButton(
            f"Enable: {'ON' if enabled else 'OFF'}",
            parent=self, font_px=theme.BUTTON, checkable=True,
        )
        self._btn_enable.setChecked(enabled)
        self._btn_enable.clicked.connect(self._on_toggle_enable)

        # Sound choices list
        choices: list[tuple[Optional[str], str]] = [(None, "— OFF —")]
        if _BRIDGE_OK:
            for item in list_sounds_for_pack():
                choices.append((item["filename"], item["filename"]))

        self._scroll = QScrollArea(parent=self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        self._scroll_container = QWidget()
        self._scroll_container.setStyleSheet("background: transparent;")

        item_h = sy(52)
        item_gap = sy(6)
        y_in = 0
        for filename, display in choices:
            is_sel = (filename == self._pending_filename)
            btn = SmallButton(
                f"{'▶  ' if is_sel else '    '}{display}",
                parent=self._scroll_container,
                font_px=theme.BUTTON,
                checkable=True,
            )
            btn.setChecked(is_sel)
            btn.setGeometry(0, y_in, 200, item_h)

            def _handler(checked, fn=filename):
                self._on_select(fn)

            btn.clicked.connect(_handler)
            self._sound_btns.append((filename, btn))
            y_in += item_h + item_gap

        self._scroll_container.setMinimumHeight(y_in)
        self._scroll.setWidget(self._scroll_container)

        self._btn_preview = SmallButton("▶  Preview", parent=self, font_px=theme.BUTTON)
        self._btn_preview.clicked.connect(self._on_preview)

        self._btn_apply = ActionTile(icons.check, "Apply", primary=True, parent=self)
        self._btn_apply.clicked.connect(self._on_apply)

        self._btn_cancel = SmallButton("Cancel", parent=self, font_px=theme.BUTTON)
        self._btn_cancel.clicked.connect(self._on_cancel)

        self._layout_widgets()
        self.update()

    def _layout_widgets(self) -> None:
        if not self._scroll or not self._btn_preview or not self._btn_enable:
            return
        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return

        mx = sx(_MX)
        top = sy(_CONTENT_Y)
        mb = sy(_GAP)
        gap = sy(_GAP)
        bh = sy(_BTN_H)

        avail_w = w - 2 * mx
        left_w = int(avail_w * 0.58)
        right_x = mx + left_w + gap
        right_w = avail_w - left_w - gap
        list_h = h - top - mb

        self._right_x = right_x
        self._right_w = right_w

        self._scroll.setGeometry(mx, top, left_w, list_h)
        item_w = max(60, left_w - sx(20))
        for _, btn in self._sound_btns:
            g = btn.geometry()
            btn.setGeometry(g.x(), g.y(), item_w, g.height())

        # Right column layout from top
        enable_h = bh
        self._btn_enable.setGeometry(right_x, top, right_w, enable_h)
        after_enable = top + enable_h + gap

        # SELECTED SOUND label area (painted in paintEvent)
        sel_label_h = sy(18)
        sel_text_h = sy(40)
        self._sel_y = after_enable
        self._sel_h = sel_label_h + sel_text_h

        # Buttons: distributed in remaining space
        btns_top = after_enable + sel_label_h + sel_text_h + gap
        btn_zone_h = h - mb - btns_top
        n = 3
        slot = btn_zone_h / n
        offset = max(0.0, (slot - bh) / 2)

        self._btn_preview.setGeometry(right_x, int(btns_top + slot * 0 + offset), right_w, bh)
        self._btn_apply.setGeometry(right_x,   int(btns_top + slot * 1 + offset), right_w, bh)
        self._btn_cancel.setGeometry(right_x,  int(btns_top + slot * 2 + offset), right_w, bh)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_widgets()

    def _on_toggle_enable(self, checked: bool) -> None:
        if self._btn_enable:
            self._btn_enable.setText(f"Enable: {'ON' if checked else 'OFF'}")

    def _on_select(self, filename: Optional[str]) -> None:
        self._pending_filename = filename
        for fn, btn in self._sound_btns:
            is_sel = (fn == filename)
            btn.setChecked(is_sel)
            display = "— OFF —" if fn is None else fn
            btn.setText(f"{'▶  ' if is_sel else '    '}{display}")
        self.update()

    def _on_preview(self) -> None:
        if _BRIDGE_OK and self._pending_filename is not None:
            preview_file(self._pending_filename)

    def _on_apply(self) -> None:
        if _BRIDGE_OK:
            set_event_sound(self._event_key, self._pending_filename)
            if self._btn_enable:
                set_event_enabled(self._event_key, self._btn_enable.isChecked())
        if self._app is not None:
            self._app.back()

    def _on_cancel(self) -> None:
        if self._app is not None:
            self._app.back()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._right_x or not self._btn_enable:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        sel_label_h = sy(18)
        sel_text_h = sy(40)
        label_y = self._sel_y
        text_y = label_y + sel_label_h

        # "SELECTED SOUND" dim label
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.DemiBold, 0.8))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(self._right_x, label_y, self._right_w, sel_label_h),
                   Qt.AlignmentFlag.AlignVCenter, "SELECTED SOUND")

        # Selected filename (large bold)
        sel_text = "— OFF —" if self._pending_filename is None else _truncate(self._pending_filename, 20)
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
        p.setPen(QColor(theme.FG))
        p.drawText(QRectF(self._right_x, text_y, self._right_w, sel_text_h),
                   Qt.AlignmentFlag.AlignVCenter, sel_text)

        p.end()


# ── EventSoundsScreen ─────────────────────────────────────────────────────────

class EventSoundsScreen(SubScreen):
    """List of all 7 events with current sound assignment. Tap to configure."""

    TITLE = "Event Sounds"
    SUBTITLE = "Select an event to configure its sound"

    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self._app = app
        self._event_sound_screen = EventSoundScreen(app=app)
        self._list = ListPanel(
            "",
            painter=_event_row,
            rows=7,
            parent=self,
            top=4,
            empty_text="",
        )
        self._list.key = lambda item: item["key"]
        self._list.chosen.connect(self._on_choose)
        if app is not None and hasattr(app, "stack"):
            app.stack.addWidget(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        event_sounds = get_event_sounds() if _BRIDGE_OK else {}
        rows = [
            {"key": key, "label": label, "filename": event_sounds.get(key)}
            for key, label in _EVENTS
        ]
        self._list.set_items(rows)

    def _on_choose(self, item: dict) -> None:
        self._event_sound_screen.set_event(item["key"])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return
        mx = sx(_MX)
        self._list.setGeometry(mx, sy(_CONTENT_Y), w - 2 * mx, h - sy(_CONTENT_Y) - sy(_GAP))


# ── SoundsScreen ──────────────────────────────────────────────────────────────

class SoundsScreen(SubScreen):
    """Settings screen for Nexus Sounds addon.

    Row A (y=58):  Sounds enable | Mute  — two toggle cards, h=70
    Row B:         Volume — full-width, h=60
    Row C:         Event Sounds | Sound Packs  — nav tiles, fills to bottom
    """

    TITLE = "Sounds"
    SUBTITLE = "Audio notifications"

    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self._app = app
        self._card_enable: Optional[_ToggleCard] = None
        self._card_mute: Optional[_ToggleCard] = None
        self._btn_vol_dn: Optional[SmallButton] = None
        self._vol_label: Optional[_LargeVolLabel] = None
        self._btn_vol_up: Optional[SmallButton] = None
        self._tile_events: Optional[ActionTile] = None
        self._tile_packs: Optional[ActionTile] = None
        self._events_screen: Optional[EventSoundsScreen] = None
        self._packs_screen: Optional[SoundPacksScreen] = None
        self._vol_row_rect: QRectF = QRectF()

        if _BRIDGE_OK and is_installed():
            self._build_installed()

    def _build_installed(self) -> None:
        cfg = get_config()
        enabled = cfg.get("enabled", True)
        muted = cfg.get("muted", False)
        volume = cfg.get("volume", 70)

        if self._app is not None:
            self._events_screen = EventSoundsScreen(app=self._app)
            self._packs_screen = SoundPacksScreen(app=self._app)

        self._card_enable = _ToggleCard(icons.play, "Sounds", state=enabled, parent=self)
        self._card_enable.toggled.connect(self._on_toggle_enable)

        self._card_mute = _ToggleCard(icons.pause_bars, "Mute", state=muted, parent=self)
        self._card_mute.toggled.connect(self._on_toggle_mute)

        self._btn_vol_dn = SmallButton("−", parent=self, font_px=24, checkable=False)
        self._btn_vol_dn.clicked.connect(self._on_vol_down)

        self._vol_label = _LargeVolLabel(parent=self)
        self._vol_label.set_pct(volume)

        self._btn_vol_up = SmallButton("+", parent=self, font_px=24, checkable=False)
        self._btn_vol_up.clicked.connect(self._on_vol_up)

        self._tile_events = ActionTile(
            icons.play, "Event Sounds", "Configure 7 notifications", parent=self)
        self._tile_events.clicked.connect(self._on_open_events)

        self._tile_packs = ActionTile(
            icons.palette, "Sound Packs", "Browse installed packs", parent=self)
        self._tile_packs.clicked.connect(self._on_open_packs)

    def _layout_widgets_installed(self) -> None:
        w, h = self.width(), self.height()
        if w == 0 or h == 0 or not self._card_enable:
            return

        mx = sx(_MX)
        bh = sy(_BTN_H)
        gap = sy(_GAP)
        cw = w - 2 * mx
        half = (cw - gap) // 2
        y = sy(_CONTENT_Y)

        # Row A: Toggle cards
        card_h = sy(70)
        self._card_enable.setGeometry(mx, y, half, card_h)
        self._card_mute.setGeometry(mx + half + gap, y, cw - half - gap, card_h)
        y += card_h + gap

        # Row B: Volume row
        vol_row_h = sy(60)
        self._vol_row_rect = QRectF(mx, y, cw, vol_row_h)
        vol_reserve = sx(100)   # space for "Volume" label on the left
        btn_w = sx(60)
        lbl_w = sx(80)
        gap2 = sx(6)
        trio_w = btn_w + lbl_w + btn_w + 2 * gap2
        trio_x = mx + vol_reserve + (cw - vol_reserve - trio_w) // 2
        self._btn_vol_dn.setGeometry(trio_x, y + (vol_row_h - bh) // 2, btn_w, bh)
        self._vol_label.setGeometry(trio_x + btn_w + gap2, y, lbl_w, vol_row_h)
        self._btn_vol_up.setGeometry(trio_x + btn_w + gap2 + lbl_w + gap2,
                                     y + (vol_row_h - bh) // 2, btn_w, bh)
        y += vol_row_h + gap

        # Row C: Nav tiles
        tile_h = max(bh, h - y - gap)
        if self._tile_events:
            self._tile_events.setGeometry(mx, y, half, tile_h)
        if self._tile_packs:
            self._tile_packs.setGeometry(mx + half + gap, y, cw - half - gap, tile_h)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if _BRIDGE_OK and is_installed():
            self._layout_widgets_installed()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if _BRIDGE_OK and is_installed():
            self._refresh_state()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not _BRIDGE_OK or not is_installed():
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setFont(theme.font(theme.BODY))
            p.setPen(theme.DIM)
            p.drawText(
                QRectF(0, sy(_CONTENT_Y), self.width(), self.height() - sy(_CONTENT_Y)),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Nexus Sounds is not installed.\n"
                "Install nexus-sounds to enable audio notifications.",
            )
            p.end()
            return

        if not self._vol_row_rect.isEmpty():
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            paint_panel(p, self._vol_row_rect, 6,
                        top=QColor(22, 25, 29), bottom=QColor(13, 15, 18), border=QColor(46, 50, 57))
            isz = min(20.0, self._vol_row_rect.height() * 0.38)
            ic_x = self._vol_row_rect.x() + sx(12)
            ic_y = self._vol_row_rect.center().y() - isz / 2
            icons.play(p, QRectF(ic_x, ic_y, isz, isz), QColor(theme.FG_SOFT))
            p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(ic_x + isz + 6, self._vol_row_rect.y(),
                              sx(70), self._vol_row_rect.height()),
                       Qt.AlignmentFlag.AlignVCenter, "Volume")
            p.end()

    # ── handlers ─────────────────────────────────────────────────────────────

    def _on_toggle_enable(self, checked: bool) -> None:
        if _BRIDGE_OK:
            set_enabled(checked)

    def _on_toggle_mute(self, checked: bool) -> None:
        if _BRIDGE_OK:
            set_muted(checked)

    def _on_vol_up(self) -> None:
        if not _BRIDGE_OK:
            return
        cfg = get_config()
        new_vol = min(100, cfg.get("volume", 70) + 5)
        set_volume(new_vol)
        if self._vol_label:
            self._vol_label.set_pct(new_vol)

    def _on_vol_down(self) -> None:
        if not _BRIDGE_OK:
            return
        cfg = get_config()
        new_vol = max(0, cfg.get("volume", 70) - 5)
        set_volume(new_vol)
        if self._vol_label:
            self._vol_label.set_pct(new_vol)

    def _on_open_events(self) -> None:
        if self._events_screen is not None and self._app is not None:
            self._app.push(self._events_screen)

    def _on_open_packs(self) -> None:
        if self._packs_screen is not None and self._app is not None:
            self._app.push(self._packs_screen)

    def _refresh_state(self) -> None:
        if not _BRIDGE_OK or not self._card_enable:
            return
        cfg = get_config()
        self._card_enable.set_state(cfg.get("enabled", True))
        self._card_mute.set_state(cfg.get("muted", False))
        if self._vol_label:
            self._vol_label.set_pct(cfg.get("volume", 70))
