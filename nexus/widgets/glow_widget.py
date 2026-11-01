"""Panel and red-glow painting helpers shared by Nexus surfaces.

Glows are rendered once into a pixmap per size/intensity and reused, so a
repaint is only a blit — nothing animates unless a property animation runs.
"""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

from nexus import theme

_glow_cache = {}


def panel_path(rect, radius=8.0):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def paint_panel(p, rect, radius=8.0, top=None, bottom=None, border=None, alpha=232):
    """Graphite card: vertical gradient over the brushed backdrop + hairline rim."""
    top = QColor(top or theme.PANEL_TOP)
    bottom = QColor(bottom or theme.PANEL_BOT)
    top.setAlpha(alpha)
    bottom.setAlpha(alpha)
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0.0, top)
    g.setColorAt(1.0, bottom)
    path = panel_path(rect, radius)
    p.fillPath(path, g)
    rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    rim.setColorAt(0.0, QColor(border or theme.BORDER_HI))
    rim.setColorAt(0.35, QColor(border or theme.BORDER))
    rim.setColorAt(1.0, QColor(theme.BORDER).darker(130))
    p.setPen(QPen(rim, 1.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)


def red_glow(w, h, radius=8.0, spread=10, strength=1.0):
    """Soft red halo around a w×h rounded rect, returned with `spread` px margin."""
    key = (w, h, radius, spread, round(strength, 2))
    px = _glow_cache.get(key)
    if px is not None:
        return px
    px = QPixmap(w + spread * 2, h + spread * 2)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(spread, 0, -1):
        a = int(150 * strength * (1 - i / spread) ** 2.2)
        p.setPen(QPen(QColor(255, 30, 20, a), 2.0))
        p.drawRoundedRect(QRectF(spread - i, spread - i, w + 2 * i, h + 2 * i), radius + i, radius + i)
    p.end()
    _glow_cache[key] = px
    return px


def paint_red_fill(p, rect, radius=6.0, strength=1.0):
    """Active-state fill: deep red vertical gradient with a bright inner rim."""
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0.0, QColor(150, 12, 10, int(235 * strength)))
    g.setColorAt(0.55, QColor(92, 6, 6, int(225 * strength)))
    g.setColorAt(1.0, QColor(54, 4, 4, int(215 * strength)))
    path = panel_path(rect, radius)
    p.fillPath(path, g)
    hot = QRadialGradient(QPointF(rect.left(), rect.center().y()), rect.width() * 0.9)
    hot.setColorAt(0.0, QColor(255, 40, 25, int(90 * strength)))
    hot.setColorAt(1.0, QColor(255, 40, 25, 0))
    p.fillPath(path, hot)
    p.setPen(QPen(QColor(255, 50, 35, int(200 * strength)), 1.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
