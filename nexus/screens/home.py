"""Home screen — hero hotend, Temperatures, Printer Status, Active Add-Ons.

Geometry follows the approved Home reference (800×480). When a print is active
or paused the Return to Print card occupies the bottom strip; otherwise the
hero and cards extend to fill it.
"""
import os

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QAbstractButton, QWidget

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.widgets import icons
from nexus.widgets.glow_widget import paint_panel, paint_red_fill, panel_path, red_glow
from nexus.widgets.text import degree_width, draw_degrees

HOTEND_PNG = os.path.join(theme.ASSETS, "hotend_r52.png")
PRINTER_PNG = {k: os.path.join(theme.ASSETS, "printers", f"printer_{k}.png") for k in ("corexy", "cartesian", "delta")}
# Klipper [printer] kinematics -> Home image (owner's mapping); anything else: the hotend fallback
KINEMATICS_IMAGE = {"corexy": "corexy", "coreyz": "corexy", "corexz": "cartesian",
                    "cartesian": "cartesian", "delta": "delta"}
_pixmaps = {}


def hero_image(kinematics):
    """Image path for a kinematics value (None / unknown -> hotend)."""
    key = KINEMATICS_IMAGE.get(str(kinematics or "").strip().lower())
    return PRINTER_PNG[key] if key else HOTEND_PNG


def load_pixmap(path):
    """Decoded once per process (assets are local files)."""
    px = _pixmaps.get(path)
    if px is None:
        px = _pixmaps[path] = QPixmap(path)
    return px

MARGIN = smin(8)         # gap below the top bar / right of the sidebar
RIGHT_MARGIN = sx(10)
HERO_W = sx(364)
CARD_GAP = smin(8)
HEADER_H = sy(30)
BOTTOM_STRIP_H = sy(54)  # Return to Print card height


def _header(p, w, title):
    p.setFont(theme.font(theme.CAPS, QFont.Weight.DemiBold, 0.6))
    p.setPen(theme.DIM)
    p.drawText(QRectF(14, 0, w - 40, HEADER_H), Qt.AlignmentFlag.AlignVCenter, title.upper())
    icons.chevron(p, QRectF(w - 22, HEADER_H / 2 - 5.5, 8, 11), QColor(theme.DIM), 1.6)
    p.setPen(QPen(QColor(theme.DIVIDER), 1.0))
    p.drawLine(QPointF(10, HEADER_H + 0.5), QPointF(w - 10, HEADER_H + 0.5))
    p.setPen(QPen(QColor(255, 255, 255, 10), 1.0))
    p.drawLine(QPointF(10, HEADER_H + 1.5), QPointF(w - 10, HEADER_H + 1.5))


class HeroView(QWidget):
    """The exact supplied hotend PNG, clipped to a rounded panel.

    Default is cover-fit. `height_zoom` instead scales the image to that multiple
    of the panel height (keeps the nozzle tip visible on wide, short panels);
    `x_shift` nudges it horizontally and the sides fade into the panel.
    """

    def __init__(self, parent=None, height_zoom=None, x_shift=0):
        super().__init__(parent)
        self.image_path = HOTEND_PNG
        self._source = load_pixmap(HOTEND_PNG)
        self._scaled = None
        self._fills = None
        self._zoom = height_zoom
        self._x_shift = x_shift

    def set_image(self, path):
        if path != self.image_path:
            self.image_path, self._source = path, load_pixmap(path)
            self._scaled = self._fills = None
            self.update()

    def _printer_fit(self):
        """Printer renders: proportional fit, centred; the space beside them is filled with the render's
        own background (its edge columns, smoothed vertically) so no new artwork is introduced."""
        if self._scaled is None and not self._source.isNull():
            self._scaled = self._source.scaled(self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
            img = self._scaled.toImage()
            fills = []
            for x0 in (0, img.width() - 3):
                strip = img.copy(x0, 0, 3, img.height()).scaled(1, max(1, img.height() // 24),
                                                                 Qt.AspectRatioMode.IgnoreAspectRatio,
                                                                 Qt.TransformationMode.SmoothTransformation)
                fills.append(QPixmap.fromImage(strip.scaled(1, img.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                                                            Qt.TransformationMode.SmoothTransformation)))
            self._fills = fills
        return self._scaled

    def resizeEvent(self, e):
        self._scaled = None
        super().resizeEvent(e)

    def _cover(self):
        if self._scaled is None and not self._source.isNull():
            if self._zoom:
                side = round(self.height() * self._zoom)
                self._scaled = self._source.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
            else:
                self._scaled = self._source.scaled(
                    self.width(), self.height(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
        return self._scaled

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        path = panel_path(r, 10)
        p.setClipPath(path)
        p.fillRect(r, QColor(0, 0, 0))
        img = self._cover() if self.image_path == HOTEND_PNG else None
        if self.image_path != HOTEND_PNG:
            fit = self._printer_fit()
            if fit is not None:
                x, y = int((r.width() - fit.width()) / 2), int((r.height() - fit.height()) / 2)
                left, right = self._fills
                p.drawPixmap(QRectF(0, y, x + 1, fit.height()), left, QRectF(left.rect()))
                p.drawPixmap(QRectF(x + fit.width() - 1, y, r.width() - x - fit.width() + 1, fit.height()),
                             right, QRectF(right.rect()))
                p.drawPixmap(x, y, fit)
        if img is not None:
            x = (r.width() - img.width()) / 2 + self._x_shift
            # zoomed images crop 30 % of the overflow at the top, 70 % at the bottom
            y = (r.height() - img.height()) * (0.3 if self._zoom else 0.5)
            p.drawPixmap(int(x), int(y), img)
            if self._zoom:
                for x0, x1 in ((x, x + 40), (x + img.width(), x + img.width() - 40)):
                    g = QLinearGradient(x0, 0, x1, 0)
                    g.setColorAt(0, QColor(0, 0, 0, 255))
                    g.setColorAt(1, QColor(0, 0, 0, 0))
                    p.fillRect(r, g)
        # blend the photo edges into the graphite panel
        for x0, x1, horiz in ((0, 26, True), (r.width(), r.width() - 26, True)):
            g = QLinearGradient(x0, 0, x1, 0)
            g.setColorAt(0, QColor(7, 8, 10, 150))
            g.setColorAt(1, QColor(7, 8, 10, 0))
            p.fillRect(r, g)
        g = QLinearGradient(0, r.height(), 0, r.height() - 34)
        g.setColorAt(0, QColor(7, 8, 10, 170))
        g.setColorAt(1, QColor(7, 8, 10, 0))
        p.fillRect(r, g)
        p.setClipping(False)
        p.setPen(QPen(QColor(48, 52, 59), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        p.end()


class TemperaturesCard(QWidget):
    TILES = (("nozzle", "Nozzle", icons.nozzle, True),
             ("bed", "Bed", icons.bed, True),
             ("chamber", "Chamber", icons.chamber, False))
    EDITABLE = {"nozzle": "extruder", "bed": "heater_bed"}  # tap opens the keypad
    heater_requested = pyqtSignal(str)
    open_requested = pyqtSignal()  # header (›) opens the Temperature screen

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vals = {}

    def _tile_rect(self, i):
        pad, gap = 10, 6
        top = HEADER_H + 8
        tile_w = (self.width() - 2 * pad - 2 * gap) / 3
        return QRectF(pad + i * (tile_w + gap), top, tile_w, self.height() - top - pad)

    def mouseReleaseEvent(self, e):
        if e.position().y() < HEADER_H:
            self.open_requested.emit()
            return
        for i, (key, *_) in enumerate(self.TILES):
            if key in self.EDITABLE and self._tile_rect(i).contains(e.position()):
                self.heater_requested.emit(self.EDITABLE[key])

    def set_data(self, data):
        vals = {}
        for key, *_ in self.TILES:
            t = data.get(key)
            vals[key] = None if t is None else (round(t[0]), None if t[1] is None else round(t[1]))
        if vals != self._vals:
            self._vals = vals
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        paint_panel(p, QRectF(0, 0, w, h))
        _header(p, w, "Temperatures")
        for i, (key, label, icon, red) in enumerate(self.TILES):
            t = self._tile_rect(i)
            paint_panel(p, t, 6, top=QColor(22, 25, 29), bottom=QColor(14, 16, 19), border=QColor(40, 44, 50))
            colour = QColor(255, 44, 34) if red else QColor(theme.FG_SOFT)
            isz = 26
            icon(p, QRectF(t.x() + 11, t.center().y() - isz / 2 - 1, isz, isz), colour)
            col = QRectF(t.x() + 40, t.y(), t.width() - 44, t.height())
            val = self._vals.get(key)
            cy = t.center().y()
            p.setFont(theme.font(theme.SMALL, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            p.drawText(QRectF(col.x() - 8, cy - 31, col.width() + 16, 16), Qt.AlignmentFlag.AlignCenter, label)
            p.setPen(theme.FG)
            number = "--" if val is None else str(val[0])
            size = 31
            while size > 22 and degree_width(theme.font(size, QFont.Weight.Bold), number) > col.width() - 6:
                size -= 1
            draw_degrees(p, QRectF(col.x(), cy - 18, col.width(), 32), number, theme.font(size, QFont.Weight.Bold))
            p.setFont(theme.font(theme.SMALL, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            target = "Target --°" if val is None or val[1] is None else (
                "Target Off" if val[1] == 0 else f"Target {val[1]}°")
            # same centre as the reading; may extend under the icon column (dense card)
            p.drawText(QRectF(col.x() - 8, cy + 15, col.width() + 16, 16), Qt.AlignmentFlag.AlignCenter, target)
        p.end()


class StatusCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None

    def set_data(self, data):
        if not data.get("connected"):
            view = ("offline", "Disconnected", data.get("message") or "Waiting for Moonraker")
        else:
            s = data["state"]
            name = os.path.basename(data.get("filename") or "")
            pct = int(round((data.get("progress") or 0) * 100))
            view = {
                "printing": ("printing", "Printing", f"{name} · {pct}%"),
                "paused":   ("paused", "Paused", f"{name} · {pct}%"),
                "complete": ("complete", "Complete", name or "Print finished"),
                "cancelled": ("cancelled", "Cancelled", name),
                "error":    ("error", "Error", data.get("message") or "Klipper reported an error"),
            }.get(s, ("standby", "Ready", "Idle - Ready to print"))
        if view != self._view:
            self._view = view
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        paint_panel(p, QRectF(0, 0, w, h))
        _header(p, w, "Printer Status")
        if self._view is None:
            p.end()
            return
        kind, title, sub = self._view
        icon, colour = {
            "printing": (icons.play_ring, theme.RED),
            "paused":   (icons.pause_ring, theme.AMBER),
            "error":    (icons.alert_ring, theme.RED),
            "offline":  (icons.alert_ring, theme.MUTED),
            "cancelled": (icons.alert_ring, theme.DIM),
        }.get(kind, (icons.check_ring, theme.GREEN))
        cy = HEADER_H + (h - HEADER_H) / 2
        icon(p, QRectF(20, cy - 20, 40, 40), QColor(colour))
        p.setFont(theme.font(smin(21), QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(74, cy - 22, w - 90, 24), Qt.AlignmentFlag.AlignVCenter, title)
        f = theme.font(theme.BODY, QFont.Weight.Medium)
        p.setFont(f)
        p.setPen(theme.DIM)
        sub = QFontMetricsF(f).elidedText(sub, Qt.TextElideMode.ElideMiddle, w - 90)
        p.drawText(QRectF(74, cy + 2, w - 90, 18), Qt.AlignmentFlag.AlignVCenter, sub)
        p.end()


class AddonsCard(QWidget):
    """Shown only for add-ons detected on the printer (StealthChanger, BoxTurtle).
    Tapping a section opens that add-on's dashboard."""
    addon_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None

    def mouseReleaseEvent(self, e):
        if not self.has_content():
            return
        sc, bt = self._view
        split = round(176 * max(1.0, self.width() / 332)) if (sc and bt) else self.width()
        if sc and (e.position().x() < split or not bt):
            self.addon_requested.emit("stealthchanger")
        elif bt:
            self.addon_requested.emit("boxturtle")

    def has_content(self):
        return bool(self._view and (self._view[0] or self._view[1]))

    def set_data(self, data):
        sc, bt = data.get("stealthchanger"), data.get("boxturtle")
        view = (
            None if not sc else (tuple(sc["tools"]), sc.get("active")),
            None if not bt else tuple((l["name"], l["color"], l.get("loaded", True)) for l in bt["lanes"]),
        )
        if view != self._view:
            self._view = view
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        paint_panel(p, QRectF(0, 0, w, h))
        _header(p, w, "Active Add-Ons")
        if not self.has_content():
            p.end()
            return
        sc, bt = self._view
        # title row + tiles (52 px, less on short cards), centred as one group in the card body
        body_y = HEADER_H + 2
        th = min(52, h - body_y - 34)
        group_h = 32 + th
        top = body_y + max(2.0, (h - body_y - group_h) / 2)
        body = QRectF(0, top, w, group_h)
        scale = max(1.0, w / 332)  # 332 px = Home card width; wider cards spread the tools
        if sc and bt:
            split = round(176 * scale)
            self._paint_stealthchanger(p, QRectF(10, body.y(), split - 10, body.height()), *sc, th, scale)
            p.setPen(QPen(QColor(theme.DIVIDER), 1.0))
            p.drawLine(QPointF(split + 0.5, body.y() + 4), QPointF(split + 0.5, body.bottom() - 2))
            self._paint_boxturtle(p, QRectF(split + 10, body.y(), w - split - 20, body.height()), bt, th)
        elif sc:
            self._paint_stealthchanger(p, QRectF(10, body.y(), w - 20, body.height()), *sc, th, scale)
        else:
            self._paint_boxturtle(p, QRectF(10, body.y(), w - 20, body.height()), bt, th)
        p.end()

    @staticmethod
    def _section_title(p, r, icon, title):
        icon(p, QRectF(r.x() + 4, r.y() + 4, 17, 17), QColor(theme.FG_SOFT))
        p.setFont(theme.font(theme.LABEL, QFont.Weight.DemiBold))
        p.setPen(theme.FG)
        p.drawText(QRectF(r.x() + 28, r.y() + 2, r.width() - 28, 20), Qt.AlignmentFlag.AlignVCenter, title)

    def _paint_stealthchanger(self, p, r, tools, active, th=52, scale=1.0):
        self._section_title(p, r, icons.wrench, "StealthChanger")
        n = len(tools)
        pitch = min(31.0 * scale, (r.width() - 4) / max(n, 1))
        tw = pitch - 3
        top = r.y() + 30
        for i, name in enumerate(tools):
            t = QRectF(r.x() + 2 + i * pitch, top, tw, th)
            on = i == active
            if on:
                halo = red_glow(int(tw), int(th), 5.0, 6, 0.7)
                p.drawPixmap(int(t.x()) - 6, int(t.y()) - 6, halo)
                paint_red_fill(p, t, 5.0, 0.85)
            colour = QColor(255, 50, 38) if on else QColor(112, 118, 126)
            icons.toolhead(p, QRectF(t.center().x() - 8, t.y() + 7, 16, 21), colour)
            p.setFont(theme.font(theme.CAPTION, QFont.Weight.DemiBold))
            p.setPen(QColor(255, 70, 58) if on else theme.DIM)
            p.drawText(QRectF(t.x(), t.bottom() - 18, t.width(), 14), Qt.AlignmentFlag.AlignCenter, name)

    def _paint_boxturtle(self, p, r, lanes, th=52):
        self._section_title(p, r, icons.spool, "BoxTurtle")
        n = len(lanes)
        pitch = min(34.0, (r.width() - 4) / max(n, 1))
        d = min(28.0, pitch - 5)
        top = r.y() + 32
        for i, (name, colour, loaded) in enumerate(lanes):
            cx = r.x() + 4 + pitch * i + pitch / 2
            cy = top + 4 + d / 2 - (52 - th) * 0.6
            c = QColor(colour)
            if not loaded:
                c = QColor(theme.MUTED)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(10, 11, 13))
            p.drawEllipse(QPointF(cx, cy), d / 2 + 1, d / 2 + 1)
            p.setPen(QPen(c, 2.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), d / 2 - 1.5, d / 2 - 1.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(cx, cy), d * 0.30, d * 0.30)
            p.setBrush(QColor(12, 13, 15))
            p.drawEllipse(QPointF(cx, cy), d * 0.11, d * 0.11)
            p.setFont(theme.font(theme.CAPTION, QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(QRectF(cx - 12, cy + d / 2 + 4 - (52 - th) * 0.5, 24, 14), Qt.AlignmentFlag.AlignCenter, name)


class ReturnToPrintCard(QAbstractButton):
    """Bottom strip shown only while a print is active or paused."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None

    def set_data(self, data):
        view = (data["state"], os.path.basename(data.get("filename") or ""),
                round((data.get("progress") or 0) * 100), data.get("eta"))
        if view != self._view:
            self._view = view
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = QRectF(0, 0, w, h)
        paint_panel(p, r, 8, border=QColor(120, 22, 18))
        if self.isDown():
            p.fillPath(panel_path(r, 8), QColor(255, 40, 30, 28))
        if not self._view:
            p.end()
            return
        state, name, pct, eta = self._view
        paused = state == "paused"
        accent = QColor(theme.AMBER) if paused else QColor(255, 44, 34)
        (icons.pause_ring if paused else icons.play_ring)(p, QRectF(14, h / 2 - 15, 30, 30), accent)
        p.setFont(theme.font(smin(18), QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(56, 7, 200, 22), Qt.AlignmentFlag.AlignVCenter, "Return to Print")
        f = theme.font(theme.CAPTION, QFont.Weight.Medium)
        p.setFont(f)
        p.setPen(theme.DIM)
        sub = ("Paused · " if paused else "Printing · ") + name
        p.drawText(QRectF(56, 28, 220, 18), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetricsF(f).elidedText(sub, Qt.TextElideMode.ElideMiddle, 220))
        # progress bar
        bar = QRectF(296, h / 2 - 3, w - 296 - 150, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(30, 33, 38))
        p.drawRoundedRect(bar, 3, 3)
        fill = QRectF(bar.x(), bar.y(), bar.width() * pct / 100, bar.height())
        g = QLinearGradient(fill.topLeft(), fill.topRight())
        g.setColorAt(0, accent.darker(170))
        g.setColorAt(1, accent)
        p.setBrush(g)
        p.drawRoundedRect(fill, 3, 3)
        p.setFont(theme.font(smin(20), QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(w - 142, 6, 60, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{pct}%")
        p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(w - 148, 28, 66, 18), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   eta or "")
        icons.chevron(p, QRectF(w - 34, h / 2 - 8, 11, 16), QColor(theme.FG_SOFT), 2.0)
        p.end()


class HomeScreen(QWidget):
    return_to_print = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hero = HeroView(self)
        self.temps = TemperaturesCard(self)
        self.status = StatusCard(self)
        self.addons = AddonsCard(self)
        self.resume = ReturnToPrintCard(self)
        self.resume.clicked.connect(self.return_to_print)
        self._layout_key = None

    def set_data(self, data):
        for card in (self.temps, self.status, self.addons):
            card.set_data(data)
        # printer image from Klipper's configured kinematics; disconnected / unknown -> hotend
        kin = (data.get("config") or {}).get("kinematics") if data.get("connected") else None
        self.hero.set_image(hero_image(kin))
        active = data.get("connected") and data["state"] in ("printing", "paused")
        if active:
            self.resume.set_data(data)
        key = (bool(active), self.addons.has_content(), self.width(), self.height())
        if key != self._layout_key:
            self._layout_key = key
            self._apply_layout(*key[:2])

    def resizeEvent(self, e):
        self._layout_key = None
        super().resizeEvent(e)

    def _apply_layout(self, print_active, has_addons):
        W, H = self.width(), self.height()
        bottom = H - MARGIN - (BOTTOM_STRIP_H + CARD_GAP if print_active else 0)
        main_h = bottom - MARGIN
        self.hero.setGeometry(MARGIN, MARGIN, HERO_W, main_h)
        cx = MARGIN + HERO_W + 6
        cw = W - cx - RIGHT_MARGIN
        if has_addons:
            # reference proportions 122 : 86 : 138 when the bottom strip is shown
            avail = main_h - 2 * CARD_GAP
            th = round(avail * 122 / 346)
            sh = round(avail * 86 / 346)
            ah = avail - th - sh
        else:
            avail = main_h - CARD_GAP
            th = sh = avail // 2
            sh = avail - th
            ah = 0
        self.temps.setGeometry(cx, MARGIN, cw, th)
        self.status.setGeometry(cx, MARGIN + th + CARD_GAP, cw, sh)
        self.addons.setVisible(has_addons)
        if has_addons:
            self.addons.setGeometry(cx, MARGIN + th + sh + 2 * CARD_GAP, cw, ah)
        self.resume.setVisible(print_active)
        if print_active:
            self.resume.setGeometry(MARGIN, bottom + CARD_GAP, W - MARGIN - RIGHT_MARGIN, BOTTOM_STRIP_H)
