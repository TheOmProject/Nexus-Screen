"""Shared building blocks for submenu screens: titled panels, info rows,
selectable tiles and two-line action tiles. Same graphite/red language as Home."""
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QWidget

from nexus import theme
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.glow_widget import paint_panel, paint_red_fill, panel_path, red_glow

PANEL_TITLE_H = 24


def wrap_lines(font, text, width, max_lines):
    """Word-wrap `text` into at most `max_lines` lines of `width`; the last one is elided if needed."""
    fm = QFontMetricsF(font)
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and fm.horizontalAdvance(trial) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    return [fm.elidedText(line, Qt.TextElideMode.ElideRight, width) for line in lines]


def paint_titled_panel(p, rect, title):
    paint_panel(p, rect, 7)
    if title:
        p.setFont(theme.font(theme.HEADING, QFont.Weight.DemiBold))
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(rect.x() + 10, rect.y() + 2, rect.width() - 20, PANEL_TITLE_H),
                   Qt.AlignmentFlag.AlignVCenter, title)


def paint_rows(p, rect, rows, label_w=None, font_px=theme.LABEL):
    """Key/value rows on alternating dark strips; rows = [(label, value, colour|None)]."""
    if not rows:
        return
    n = len(rows)
    gap = 2
    rh = (rect.height() - gap * (n - 1)) / n
    label_w = label_w or rect.width() * 0.48
    f = theme.font(font_px, QFont.Weight.Medium)
    fv = theme.font(font_px, QFont.Weight.DemiBold)
    for i, (label, value, colour) in enumerate(rows):
        row = QRectF(rect.x(), rect.y() + i * (rh + gap), rect.width(), rh)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 9 if i % 2 == 0 else 4))
        p.drawRoundedRect(row, 3, 3)
        p.setFont(f)
        p.setPen(theme.DIM)
        p.drawText(row.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)
        p.setFont(fv)
        p.setPen(QColor(colour) if colour else theme.FG)
        vr = row.adjusted(max(label_w, 8 + QFontMetricsF(f).horizontalAdvance(label) + 10), 0, -6, 0)
        p.drawText(vr, Qt.AlignmentFlag.AlignVCenter,
                   QFontMetricsF(fv).elidedText(str(value), Qt.TextElideMode.ElideRight, vr.width()))


class Panel(QWidget):
    """Graphite panel with a mixed-case section title (as in the submenu references)."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title

    def body(self):
        return QRectF(8, PANEL_TITLE_H + 2, self.width() - 16, self.height() - PANEL_TITLE_H - 10)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_titled_panel(p, QRectF(0, 0, self.width(), self.height()), self.title)
        self.paint_body(p)
        p.end()

    def paint_body(self, p):
        pass


class RowsPanel(Panel):
    def __init__(self, title, parent=None, label_w=None):
        super().__init__(title, parent)
        self._rows = []
        self._label_w = label_w

    def set_rows(self, rows):
        if rows != self._rows:
            self._rows = rows
            self.update()

    def paint_body(self, p):
        paint_rows(p, self.body(), self._rows, self._label_w)


class Tile(QAbstractButton):
    """Selectable tile; `painter(p, rect, selected)` draws its contents."""

    def __init__(self, painter, parent=None):
        super().__init__(parent)
        self._painter = painter
        self.highlight = False  # selected look driven by data, not by taps (non-checkable tiles)
        self.setCheckable(True)
        self.toggled.connect(lambda _: self.update())

    def set_highlight(self, on):
        if on != self.highlight:
            self.highlight = on
            self.update()

    def set_painter(self, painter):
        self._painter = painter
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(5, 5, self.width() - 10, self.height() - 10)
        selected = self.isChecked() or self.highlight
        if selected:
            p.drawPixmap(0, 0, red_glow(int(r.width()), int(r.height()), 6.0, 5, 0.8))
            paint_red_fill(p, r, 6.0, 0.9)
        else:
            top = QColor(30, 33, 38) if self.isDown() else QColor(22, 25, 29)
            paint_panel(p, r, 6, top=top, bottom=QColor(13, 15, 18), border=QColor(44, 48, 55))
        self._painter(p, r, selected)
        p.end()


class ActionTile(QAbstractButton):
    """Icon + title + subtitle action (Load / Unload / Select Tool …). `primary` = red."""

    def __init__(self, icon, title, subtitle="", primary=False, parent=None, stacked=False):
        super().__init__(parent)
        self._icon, self._title, self._subtitle, self._primary = icon, title, subtitle, primary
        self._stacked = stacked  # icon above title, subtitle hidden

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = 5
        r = QRectF(g, g, self.width() - 2 * g, self.height() - 2 * g)
        on = self.isEnabled()
        if on and self._primary:
            p.drawPixmap(0, 0, red_glow(int(r.width()), int(r.height()), 6.0, g, 0.7))
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, QColor(110, 14, 12) if self.isDown() else QColor(78, 10, 9))
            grad.setColorAt(1, QColor(36, 5, 5))
            p.fillPath(panel_path(r, 6), grad)
            p.setPen(QPen(QColor(255, 42, 32), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.7, 0.7, -0.7, -0.7), 6, 6)
        else:
            top = QColor(32, 35, 40) if self.isDown() else QColor(22, 25, 29)
            paint_panel(p, r, 6, top=top, bottom=QColor(13, 15, 18), border=QColor(46, 50, 57))
        ic = (QColor(255, 255, 255) if self._primary else QColor(theme.FG_SOFT)) if on else QColor(theme.MUTED)
        if self._stacked or (not self._subtitle and r.width() < 130):  # narrow tile: icon above the title
            isz = min(24.0, r.height() * 0.34)
            self._icon(p, QRectF(r.center().x() - isz / 2, r.center().y() - isz - 2, isz, isz), ic)
            tf = theme.font(theme.BUTTON, QFont.Weight.DemiBold)
            if QFontMetricsF(tf).horizontalAdvance(self._title) > r.width() - 6:
                tf = theme.font(theme.BODY, QFont.Weight.DemiBold)  # long title on a narrow tile
            p.setFont(tf)
            p.setPen(theme.FG if on else theme.MUTED)
            p.drawText(QRectF(r.x(), r.center().y() + 3, r.width(), 22), Qt.AlignmentFlag.AlignCenter, self._title)
            p.end()
            return
        isz = min(22.0, r.height() * 0.5)
        self._icon(p, QRectF(r.x() + 12, r.center().y() - isz / 2, isz, isz), ic)
        tx = r.x() + 22 + isz
        tw = r.right() - tx - 4
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
        p.setPen(theme.FG if on else theme.MUTED)
        if self._subtitle:
            sf = theme.font(theme.SMALL, QFont.Weight.Medium)
            sub = wrap_lines(sf, self._subtitle, tw, 2 if r.height() >= 64 else 1)
            th, lh = 21, QFontMetricsF(sf).height()
            y = r.center().y() - (th + 1 + lh * len(sub)) / 2  # title + subtitle centred as one block
            p.drawText(QRectF(tx, y, tw, th), Qt.AlignmentFlag.AlignVCenter,
                       QFontMetricsF(p.font()).elidedText(self._title, Qt.TextElideMode.ElideRight, tw))
            p.setFont(sf)
            p.setPen(QColor(255, 170, 160) if on and self._primary else (theme.DIM if on else theme.MUTED))
            for i, line in enumerate(sub):
                p.drawText(QRectF(tx, y + th + 1 + i * lh, tw, lh), Qt.AlignmentFlag.AlignVCenter, line)
        else:
            if QFontMetricsF(p.font()).horizontalAdvance(self._title) > tw:
                p.setFont(theme.font(theme.BODY, QFont.Weight.DemiBold))  # long title on a narrow tile
            p.drawText(QRectF(tx, r.y(), tw, r.height()), Qt.AlignmentFlag.AlignVCenter,
                       QFontMetricsF(p.font()).elidedText(self._title, Qt.TextElideMode.ElideRight, tw))
        p.end()


class SubScreen(QWidget):
    """Submenu: approved top bar + Back button (MainWindow), no sidebar, large title."""
    fullscreen = True
    submenu = True
    TITLE = ""
    SUBTITLE = ""
    CONTENT_Y = 58

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(theme.font(theme.TITLE, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(12, 2, 600, 34), Qt.AlignmentFlag.AlignVCenter, self.TITLE)
        p.setFont(theme.font(theme.SUBTITLE, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(13, 33, 600, 18), Qt.AlignmentFlag.AlignVCenter, self.SUBTITLE)
        p.end()


class ListPanel(Panel):
    """Paged list of selectable rows (touch-friendly, no scrolling).
    `painter(p, rect, item, selected)` draws a row; emits `chosen(item)`."""

    chosen = pyqtSignal(object)

    LOADING = "Loading…"

    def __init__(self, title, painter, rows=8, parent=None, top=26, empty_text="Nothing to show"):
        super().__init__(title, parent)
        self._painter, self._rows, self._top = painter, rows, top
        self.items, self.page, self.selected = [], 0, None
        self.empty_text = empty_text
        self.message = self.LOADING  # shown instead of rows until data arrives
        self.key = lambda item: item
        self.tiles = []
        for i in range(rows):
            t = Tile(lambda p, r, s: None, self)
            t.setCheckable(False)
            t.clicked.connect(lambda _=False, i=i: self._pick(i))
            self.tiles.append(t)
        self.prev = SmallButton(icon=icons.back_arrow, parent=self, checkable=False)
        self.next = SmallButton(icon=icons.chevron, parent=self, checkable=False)
        self.prev.clicked.connect(lambda: self._turn(-1))
        self.next.clicked.connect(lambda: self._turn(1))
        self._refresh()  # no row frames or page buttons before the first data

    def resizeEvent(self, e):
        self._layout()
        super().resizeEvent(e)

    def set_loading(self, text=None):
        """Show a loading (or failure) message instead of rows, e.g. when opening a folder."""
        self.items, self.page = [], 0
        self.message = text or self.LOADING
        self._layout()
        self._refresh()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.message:
            p = QPainter(self)
            p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(QRectF(10, self._top, self.width() - 20, self.height() - self._top - 10),
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)
            p.end()

    def _layout(self):
        w, h = self.width(), self.height()
        pages = self.pages() > 1
        bottom = h - (38 if pages else 6)
        rh = (bottom - self._top) / self._rows
        for i, t in enumerate(self.tiles):
            t.setGeometry(2, int(self._top + i * rh), w - 4, int(rh))
        half = (w - 24) / 2
        self.prev.setGeometry(8, h - 34, int(half), 28)
        self.next.setGeometry(int(16 + half), h - 34, int(half), 28)

    def pages(self):
        return max(1, (len(self.items) + self._rows - 1) // self._rows)

    def set_items(self, items, selected=None):
        self.items = list(items)
        self.message = "" if self.items else self.empty_text
        if selected is not None:
            self.selected = selected
        self.page = max(0, min(self.page, self.pages() - 1))
        self._layout()
        self._refresh()

    def _refresh(self):
        shown = self.items[self.page * self._rows:(self.page + 1) * self._rows]
        for t, item in zip(self.tiles, shown + [None] * self._rows):
            t.setVisible(item is not None)
            if item is not None:
                sel = self.selected is not None and self.key(item) == self.selected
                t.set_painter(lambda p, r, s, it=item: self._painter(p, r, it, s))
                t.set_highlight(sel)
        many = self.pages() > 1 and bool(self.items)
        self.update()
        self.prev.setVisible(many)
        self.next.setVisible(many)
        self.prev.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < self.pages() - 1)

    def _turn(self, d):
        self.page = max(0, min(self.pages() - 1, self.page + d))
        self._refresh()

    def _pick(self, i):
        idx = self.page * self._rows + i
        if idx < len(self.items):
            self.selected = self.key(self.items[idx])
            self._refresh()
            self.chosen.emit(self.items[idx])


def text_row(name, sub="", chevron=False, colour=None):
    """Row painter: name (+ dim right-hand text) and optional chevron."""
    def paint(p, r, item, selected):
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
        p.setPen(QColor(colour(item)) if colour and colour(item) else theme.FG)
        right = 30 if chevron else 10
        p.drawText(r.adjusted(12, 0, -(right + 90 if sub else right), 0), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetricsF(p.font()).elidedText(name(item), Qt.TextElideMode.ElideMiddle,
                                                      r.width() - 24 - (right + 90 if sub else right)))
        if sub:
            p.setFont(theme.font(theme.CAPTION, QFont.Weight.Medium))
            p.setPen(theme.DIM)
            p.drawText(r.adjusted(0, 0, -right, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, sub(item))
        if chevron:
            icons.chevron(p, QRectF(r.right() - 20, r.center().y() - 6, 8, 12), QColor(theme.FG_SOFT), 1.8)
    return paint
