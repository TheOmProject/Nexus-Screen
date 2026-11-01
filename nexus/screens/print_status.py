"""Print Status — fullscreen (no sidebar) while a print is printing or paused.

Reuses the approved Home widgets (hero, Temperatures, Active Add-Ons) and adds
Print Progress plus the Pause/Resume · Stop · Baby Step · Home control bar
(Baby Step opens its own submenu, screens/baby_step.py).
The screen only emits requests; MainWindow routes them to the data source,
which decides whether anything is actually sent to the printer.
"""
import os

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.screens.home import HEADER_H, AddonsCard, TemperaturesCard, _header
from nexus.widgets import icons
from nexus.widgets.buttons import ActionButton
from nexus.widgets.glow_widget import paint_panel

# geometry measured from the approved Printing reference (screen y = 36 + local y)
HERO = (sx(7), sy(4), sx(404), sy(343))
CARD_X, CARD_W = sx(420), sx(373)
BAR = (sx(5), sy(354), sx(788), sy(77))
PAUSE = (sx(15), sy(363), sx(153), sy(58))
STOP = (sx(177), sy(363), sx(141), sy(58))
BABY = (sx(327), sy(363), sx(296), sy(58))  # the slot of the former inline baby-step controls
HOME = (sx(632), sy(363), sx(153), sy(58))


class ThumbnailView(QWidget):
    """Large preview of the file being printed (Moonraker thumbnail), centred on the
    graphite hero panel; neutral placeholder when the file has no thumbnail."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._key = None
        self._source = None
        self._scaled = None
        self.state = "none"  # loading | ready | none — exposed for tests

    def set_data(self, data):
        raw = data.get("thumbnail")
        state = data.get("thumbnail_state") or ("ready" if raw else "none")
        key = (data.get("filename"), id(raw) if raw else None, len(raw) if raw else 0, state)
        if key == self._key:
            return
        self._key = key
        self._source, self._scaled = None, None
        if raw:
            px = QPixmap()
            if px.loadFromData(raw):
                self._source = px
        self.state = "ready" if self._source else ("loading" if state == "loading" else "none")
        self.update()

    def resizeEvent(self, e):
        self._scaled = None
        super().resizeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        paint_panel(p, r, 10, top=QColor(18, 20, 24), bottom=QColor(6, 7, 9), border=QColor(48, 52, 59), alpha=255)
        if self._source is not None:
            if self._scaled is None:
                self._scaled = self._source.scaled(int(r.width()) - 28, int(r.height()) - 28,
                                                   Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
            img = self._scaled
            p.drawPixmap(int((r.width() - img.width()) / 2), int((r.height() - img.height()) / 2), img)
        elif self.state == "none":
            icons.chamber(p, QRectF(r.center().x() - 26, r.center().y() - 46, 52, 56), QColor(theme.MUTED))
            p.setFont(theme.font(smin(18), QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(QRectF(r.x(), r.center().y() + 20, r.width(), 26), Qt.AlignmentFlag.AlignCenter,
                       "No Preview Available")
        p.end()


class PrintProgressCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None

    def set_data(self, data):
        layer = data.get("layer")
        view = (os.path.basename(data.get("filename") or ""), round((data.get("progress") or 0) * 100),
                data.get("eta") or "", tuple(layer) if layer else None, data.get("layer_height"),
                data["state"])
        if view != self._view:
            self._view = view
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        paint_panel(p, QRectF(0, 0, w, h))
        _header(p, w, "Print Progress")
        if not self._view:
            p.end()
            return
        name, pct, eta, layer, layer_h, state = self._view
        body_top = HEADER_H + 2
        bh = 68
        top = body_top + (h - body_top - bh) / 2
        # the file's thumbnail is the large hero on the left; this card is text and progress only
        x = 15
        right = w - 17
        f = theme.font(theme.NAME, QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(theme.FG)
        p.drawText(QRectF(x, top, right - x, 24), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetricsF(f).elidedText(name, Qt.TextElideMode.ElideMiddle, right - x))
        # percentage + bar
        pf = theme.font(smin(28), QFont.Weight.Bold)
        p.setFont(pf)
        pct_text = f"{pct}%"
        pw = QFontMetricsF(pf).horizontalAdvance(pct_text)
        p.drawText(QRectF(right - pw - 2, top + 21, pw + 2, 32), Qt.AlignmentFlag.AlignVCenter, pct_text)
        bar = QRectF(x, top + 34, right - pw - 14 - x, 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(38, 41, 47))
        p.drawRoundedRect(bar, 4, 4)
        accent = QColor(theme.AMBER) if state == "paused" else QColor(255, 36, 26)
        fill = QRectF(bar.x(), bar.y(), bar.width() * pct / 100, bar.height())
        g = QLinearGradient(fill.topLeft(), fill.topRight())
        g.setColorAt(0, accent.darker(140))
        g.setColorAt(1, accent)
        p.setBrush(g)
        p.drawRoundedRect(fill, 4, 4)
        # eta (left) · layer info (right)
        sf = theme.font(theme.BODY, QFont.Weight.Medium)
        p.setFont(sf)
        p.setPen(theme.DIM)
        line = QRectF(x, top + 48, right - x, 20)
        p.drawText(line, Qt.AlignmentFlag.AlignVCenter, eta)
        parts = []
        if layer and layer[1]:
            parts.append(f"Layer {layer[0]} / {layer[1]}")
        if layer_h:
            parts.append(f"{layer_h:.2f} mm")
        fm = QFontMetricsF(sf)
        rx = right
        for i, part in enumerate(reversed(parts)):
            tw = fm.horizontalAdvance(part)
            p.setPen(theme.DIM)
            p.drawText(QRectF(rx - tw, line.y(), tw + 1, line.height()), Qt.AlignmentFlag.AlignVCenter, part)
            rx -= tw
            if i < len(parts) - 1:
                p.setPen(QPen(QColor(theme.MUTED), 1.0))
                p.drawLine(QPointF(rx - 8.5, line.y() + 4), QPointF(rx - 8.5, line.bottom() - 4))
                rx -= 17
        p.end()


class PrintStatusScreen(QWidget):
    fullscreen = True  # MainWindow hides the sidebar for this screen

    go_home = pyqtSignal()
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    baby_step_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hero = ThumbnailView(self)  # the print file's own thumbnail replaces the hotend here
        self.hero.setGeometry(*HERO)
        self.temps = TemperaturesCard(self)
        self.progress = PrintProgressCard(self)
        self.addons = AddonsCard(self)
        self.pause = ActionButton(icons.pause_bars, "Pause", (23, 26), self)
        self.pause.place(*PAUSE)
        self.stop = ActionButton(icons.stop_square, "Stop", (22, 22), self, emphasis=False)
        self.stop.place(*STOP)
        self.baby = ActionButton(icons.z_arrows, "Baby Step", (24, 26), self, emphasis=False)
        self.baby.place(*BABY)
        self.home = ActionButton(icons.house, "Home", (30, 27), self)
        self.home.place(*HOME)
        self._state = None
        self._layout_addons = None
        self.pause.clicked.connect(self._on_pause)
        self.stop.clicked.connect(self.stop_requested)
        self.home.clicked.connect(self.go_home)
        self.baby.clicked.connect(self.baby_step_requested)

    def _on_pause(self):
        (self.resume_requested if self._state == "paused" else self.pause_requested).emit()

    def set_data(self, data, commands_enabled, busy=False):
        connected = bool(data.get("connected"))
        if connected:
            self._state = data["state"]
            for card in (self.hero, self.temps, self.progress, self.addons):
                card.set_data(data)
            has_addons = self.addons.has_content()
            if has_addons != self._layout_addons:
                self._layout_addons = has_addons
                self._apply_layout(has_addons)
        paused = self._state == "paused"
        if paused:
            self.pause.set_content(icons.play, "Resume", (22, 26))
        else:
            self.pause.set_content(icons.pause_bars, "Pause", (23, 26))
        active = connected and commands_enabled and not busy and self._state in ("printing", "paused")
        self.pause.setEnabled(active)
        self.stop.setEnabled(active)

    def _apply_layout(self, has_addons):
        x, y, _, h = HERO
        if has_addons:
            self.temps.setGeometry(CARD_X, y, CARD_W, sy(112))
            self.progress.setGeometry(CARD_X, y + sy(119), CARD_W, sy(105))
            self.addons.setGeometry(CARD_X, y + sy(231), CARD_W, sy(112))
        else:
            half = (h - sy(7)) // 2
            self.temps.setGeometry(CARD_X, y, CARD_W, half)
            self.progress.setGeometry(CARD_X, y + half + sy(7), CARD_W, h - half - sy(7))
        self.addons.setVisible(has_addons)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_panel(p, QRectF(*BAR), 8, top=QColor(17, 19, 23), bottom=QColor(9, 10, 12))
        p.end()
