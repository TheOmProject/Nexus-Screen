"""Vector icons drawn with QPainter. Each draws inside `r` (a QRectF) in colour `c`."""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen


def _pen(c, w=1.6):
    pen = QPen(c, w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _stroke(p, c, w=1.6):
    p.setPen(_pen(c, w))
    p.setBrush(Qt.BrushStyle.NoBrush)


def home(p, r, c):
    g = r.width() * 0.12
    s = (r.width() - g) / 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    for i in range(2):
        for j in range(2):
            p.drawRoundedRect(QRectF(r.x() + i * (s + g), r.y() + j * (s + g), s, s), s * 0.18, s * 0.18)


def print_(p, r, c):
    """Floppy-disk style 'Print' glyph from the reference."""
    _stroke(p, c, r.width() * 0.085)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    path = QPainterPath()
    path.moveTo(x + w * 0.12, y + h * 0.08)
    path.lineTo(x + w * 0.74, y + h * 0.08)
    path.lineTo(x + w * 0.92, y + h * 0.26)
    path.lineTo(x + w * 0.92, y + h * 0.92)
    path.lineTo(x + w * 0.08, y + h * 0.92)
    path.lineTo(x + w * 0.08, y + h * 0.12)
    path.closeSubpath()
    p.drawPath(path)
    p.drawRect(QRectF(x + w * 0.28, y + h * 0.08, w * 0.40, h * 0.24))
    p.drawRoundedRect(QRectF(x + w * 0.24, y + h * 0.52, w * 0.52, h * 0.40), 1.5, 1.5)
    p.drawLine(QPointF(x + w * 0.36, y + h * 0.66), QPointF(x + w * 0.64, y + h * 0.66))
    p.drawLine(QPointF(x + w * 0.36, y + h * 0.78), QPointF(x + w * 0.64, y + h * 0.78))


def filament(p, r, c):
    """Extruder drive: gear + idler with a filament strand passing through."""
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    cx, cy, rr = x + w * 0.40, y + h * 0.42, w * 0.26
    gear = QPainterPath()
    teeth = 8
    for i in range(teeth * 2):
        a = math.pi * i / teeth
        rad = rr if i % 2 == 0 else rr * 0.78
        pt = QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a))
        gear.moveTo(pt) if i == 0 else gear.lineTo(pt)
    gear.closeSubpath()
    hole = QPainterPath()
    hole.addEllipse(QPointF(cx, cy), rr * 0.32, rr * 0.32)
    p.drawPath(gear.subtracted(hole))
    p.drawEllipse(QPointF(x + w * 0.78, y + h * 0.30), w * 0.12, w * 0.12)
    _stroke(p, c, w * 0.09)
    p.drawLine(QPointF(x + w * 0.62, y + h * 0.02), QPointF(x + w * 0.62, y + h * 0.66))
    p.drawLine(QPointF(x + w * 0.62, y + h * 0.66), QPointF(x + w * 0.30, y + h * 0.96))


def control(p, r, c):
    """Dial with pointer."""
    _stroke(p, c, r.width() * 0.085)
    cx, cy = r.center().x(), r.center().y()
    rad = r.width() * 0.44
    p.drawEllipse(QPointF(cx, cy), rad, rad)
    p.drawLine(QPointF(cx, cy - rad * 0.62), QPointF(cx, cy + rad * 0.62))
    p.setBrush(c)
    p.drawEllipse(QPointF(cx, cy - rad * 0.12), rad * 0.22, rad * 0.22)


def gear(p, r, c):
    cx, cy = r.center().x(), r.center().y()
    ro, ri = r.width() * 0.5, r.width() * 0.37
    teeth = 8
    path = QPainterPath()
    for i in range(teeth):
        a0 = 2 * math.pi * i / teeth
        for da, rad in ((-0.20, ri), (-0.13, ro), (0.13, ro), (0.20, ri), (0.39, ri)):
            pt = QPointF(cx + rad * math.cos(a0 + da), cy + rad * math.sin(a0 + da))
            if path.elementCount() == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
    path.closeSubpath()
    hole = QPainterPath()
    hole.addEllipse(QPointF(cx, cy), ro * 0.36, ro * 0.36)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawPath(path.subtracted(hole))


def printer(p, r, c):
    _stroke(p, c, 1.4)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawRoundedRect(QRectF(x + w * 0.06, y + h * 0.10, w * 0.88, h * 0.66), 2.5, 2.5)
    p.drawLine(QPointF(x + w * 0.06, y + h * 0.34), QPointF(x + w * 0.94, y + h * 0.34))
    p.drawLine(QPointF(x + w * 0.22, y + h * 0.76), QPointF(x + w * 0.22, y + h * 0.92))
    p.drawLine(QPointF(x + w * 0.78, y + h * 0.76), QPointF(x + w * 0.78, y + h * 0.92))
    p.drawRect(QRectF(x + w * 0.40, y + h * 0.34, w * 0.20, h * 0.18))


def nozzle(p, r, c):
    _stroke(p, c, r.width() * 0.08)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    path = QPainterPath()
    path.moveTo(x + w * 0.14, y + h * 0.06)
    path.lineTo(x + w * 0.86, y + h * 0.06)
    path.lineTo(x + w * 0.86, y + h * 0.42)
    path.lineTo(x + w * 0.62, y + h * 0.72)
    path.lineTo(x + w * 0.38, y + h * 0.72)
    path.lineTo(x + w * 0.14, y + h * 0.42)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(x + w * 0.14, y + h * 0.36), QPointF(x + w * 0.86, y + h * 0.36))
    p.drawLine(QPointF(x + w * 0.50, y + h * 0.72), QPointF(x + w * 0.50, y + h * 0.96))


def bed(p, r, c):
    _stroke(p, c, r.width() * 0.075)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    for i in range(3):
        bx = x + w * (0.30 + 0.20 * i)
        wave = QPainterPath()
        wave.moveTo(bx, y + h * 0.48)
        wave.cubicTo(bx - w * 0.09, y + h * 0.38, bx + w * 0.09, y + h * 0.26, bx, y + h * 0.14)
        wave.cubicTo(bx - w * 0.07, y + h * 0.06, bx, y + h * 0.02, bx, y + h * 0.02)
        p.drawPath(wave)
    p.drawLine(QPointF(x + w * 0.02, y + h * 0.60), QPointF(x + w * 0.98, y + h * 0.60))
    bowl = QPainterPath()
    bowl.moveTo(x + w * 0.10, y + h * 0.60)
    bowl.cubicTo(x + w * 0.14, y + h * 0.92, x + w * 0.86, y + h * 0.92, x + w * 0.90, y + h * 0.60)
    p.drawPath(bowl)


def chamber(p, r, c):
    _stroke(p, c, r.width() * 0.07)
    cx = r.center().x()
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    top = QPointF(cx, y + h * 0.04)
    left = QPointF(x + w * 0.08, y + h * 0.27)
    right = QPointF(x + w * 0.92, y + h * 0.27)
    mid = QPointF(cx, y + h * 0.50)
    p.drawPolygon([top, right, mid, left])
    p.drawLine(left, QPointF(x + w * 0.08, y + h * 0.74))
    p.drawLine(right, QPointF(x + w * 0.92, y + h * 0.74))
    p.drawLine(mid, QPointF(cx, y + h * 0.98))
    p.drawLine(QPointF(x + w * 0.08, y + h * 0.74), QPointF(cx, y + h * 0.98))
    p.drawLine(QPointF(x + w * 0.92, y + h * 0.74), QPointF(cx, y + h * 0.98))


def check_ring(p, r, c):
    w = r.width()
    _stroke(p, c, w * 0.065)
    inset = w * 0.04
    p.drawEllipse(r.adjusted(inset, inset, -inset, -inset))
    path = QPainterPath()
    path.moveTo(r.x() + w * 0.30, r.y() + w * 0.52)
    path.lineTo(r.x() + w * 0.44, r.y() + w * 0.65)
    path.lineTo(r.x() + w * 0.71, r.y() + w * 0.37)
    p.drawPath(path)


def pause_ring(p, r, c):
    w = r.width()
    _stroke(p, c, w * 0.065)
    inset = w * 0.04
    p.drawEllipse(r.adjusted(inset, inset, -inset, -inset))
    p.drawLine(QPointF(r.x() + w * 0.41, r.y() + w * 0.33), QPointF(r.x() + w * 0.41, r.y() + w * 0.67))
    p.drawLine(QPointF(r.x() + w * 0.59, r.y() + w * 0.33), QPointF(r.x() + w * 0.59, r.y() + w * 0.67))


def play_ring(p, r, c):
    w = r.width()
    _stroke(p, c, w * 0.065)
    inset = w * 0.04
    p.drawEllipse(r.adjusted(inset, inset, -inset, -inset))
    p.drawPolygon([QPointF(r.x() + w * 0.42, r.y() + w * 0.32),
                   QPointF(r.x() + w * 0.70, r.y() + w * 0.50),
                   QPointF(r.x() + w * 0.42, r.y() + w * 0.68)])


def alert_ring(p, r, c):
    w = r.width()
    _stroke(p, c, w * 0.065)
    inset = w * 0.04
    p.drawEllipse(r.adjusted(inset, inset, -inset, -inset))
    p.drawLine(QPointF(r.x() + w * 0.5, r.y() + w * 0.28), QPointF(r.x() + w * 0.5, r.y() + w * 0.58))
    p.drawPoint(QPointF(r.x() + w * 0.5, r.y() + w * 0.72))


def wrench(p, r, c):
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.save()
    p.translate(r.center())
    p.rotate(-45)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    head = QPainterPath()
    head.addEllipse(QPointF(0, -h * 0.30), w * 0.22, w * 0.22)
    jaw = QPainterPath()
    jaw.addRect(QRectF(-w * 0.07, -h * 0.56, w * 0.14, h * 0.26))
    shaft = QPainterPath()
    shaft.addRoundedRect(QRectF(-w * 0.075, -h * 0.20, w * 0.15, h * 0.68), w * 0.07, w * 0.07)
    p.drawPath(head.subtracted(jaw).united(shaft))
    p.restore()


def toolhead(p, r, c, filled=True):
    """Small toolhead glyph used on the StealthChanger T0–T4 tiles."""
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    path = QPainterPath()
    path.addRoundedRect(QRectF(x + w * 0.10, y, w * 0.80, h * 0.50), 1.5, 1.5)
    body = QPainterPath()
    body.moveTo(x + w * 0.24, y + h * 0.50)
    body.lineTo(x + w * 0.76, y + h * 0.50)
    body.lineTo(x + w * 0.62, y + h * 0.74)
    body.lineTo(x + w * 0.38, y + h * 0.74)
    body.closeSubpath()
    tip = QPainterPath()
    tip.moveTo(x + w * 0.42, y + h * 0.74)
    tip.lineTo(x + w * 0.58, y + h * 0.74)
    tip.lineTo(x + w * 0.50, y + h * 0.96)
    tip.closeSubpath()
    shape = path.united(body).united(tip)
    if filled:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
    else:
        _stroke(p, c, 1.2)
    p.drawPath(shape)
    # cooling slots
    p.setPen(_pen(QColor(0, 0, 0, 110), 1.0))
    for i in range(3):
        sy = y + h * (0.13 + 0.12 * i)
        p.drawLine(QPointF(x + w * 0.24, sy), QPointF(x + w * 0.76, sy))


def spool(p, r, c):
    _stroke(p, c, r.width() * 0.08)
    cx, cy = r.center().x(), r.center().y()
    rad = r.width() * 0.46
    p.drawEllipse(QPointF(cx, cy), rad, rad)
    p.drawEllipse(QPointF(cx, cy), rad * 0.62, rad * 0.62)
    p.setBrush(c)
    p.drawEllipse(QPointF(cx, cy), rad * 0.22, rad * 0.22)


def chevron(p, r, c, w=1.5):
    _stroke(p, c, w)
    p.drawPolyline([QPointF(r.x() + r.width() * 0.3, r.y()),
                    QPointF(r.x() + r.width() * 0.75, r.center().y()),
                    QPointF(r.x() + r.width() * 0.3, r.bottom())])


def pause_bars(p, r, c):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    w = r.width() * 0.36
    p.drawRoundedRect(QRectF(r.x(), r.y(), w, r.height()), 1.5, 1.5)
    p.drawRoundedRect(QRectF(r.right() - w, r.y(), w, r.height()), 1.5, 1.5)


def play(p, r, c):
    p.setPen(_pen(c, 1.0))
    p.setBrush(c)
    p.drawPolygon([QPointF(r.x() + r.width() * 0.12, r.y()),
                   QPointF(r.right(), r.center().y()),
                   QPointF(r.x() + r.width() * 0.12, r.bottom())])


def stop_square(p, r, c):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawRoundedRect(r, 2.5, 2.5)


def house(p, r, c):
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    roof = QPainterPath()
    roof.moveTo(x, y + h * 0.48)
    roof.lineTo(x + w * 0.5, y)
    roof.lineTo(x + w, y + h * 0.48)
    roof.lineTo(x + w * 0.88, y + h * 0.60)
    roof.lineTo(x + w * 0.5, y + h * 0.24)
    roof.lineTo(x + w * 0.12, y + h * 0.60)
    roof.closeSubpath()
    body = QPainterPath()
    body.moveTo(x + w * 0.20, y + h * 0.54)
    body.lineTo(x + w * 0.5, y + h * 0.30)
    body.lineTo(x + w * 0.80, y + h * 0.54)
    body.lineTo(x + w * 0.80, y + h)
    body.lineTo(x + w * 0.20, y + h)
    body.closeSubpath()
    door = QPainterPath()
    door.addRect(QRectF(x + w * 0.41, y + h * 0.68, w * 0.18, h * 0.32))
    chimney = QPainterPath()
    chimney.addRect(QRectF(x + w * 0.70, y + h * 0.06, w * 0.12, h * 0.26))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawPath(roof.united(body.subtracted(door)).united(chimney.subtracted(body)))


def chevron_up(p, r, c, w=2.0):
    _stroke(p, c, w)
    p.drawPolyline([QPointF(r.x(), r.bottom()), QPointF(r.center().x(), r.y()), QPointF(r.right(), r.bottom())])


def chevron_down(p, r, c, w=2.0):
    _stroke(p, c, w)
    p.drawPolyline([QPointF(r.x(), r.y()), QPointF(r.center().x(), r.bottom()), QPointF(r.right(), r.y())])


def warning(p, r, c):
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    _stroke(p, c, w * 0.07)
    p.drawPolygon([QPointF(x + w * 0.5, y + h * 0.04), QPointF(x + w * 0.97, y + h * 0.92),
                   QPointF(x + w * 0.03, y + h * 0.92)])
    p.setPen(_pen(c, w * 0.09))
    p.drawLine(QPointF(x + w * 0.5, y + h * 0.36), QPointF(x + w * 0.5, y + h * 0.62))
    p.drawPoint(QPointF(x + w * 0.5, y + h * 0.77))


def spool_side(p, r, c):
    """Filament spool seen from the side (BoxTurtle lanes), filled with the lane colour."""
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    dark = QColor(c).darker(170)
    light = QColor(c).lighter(135)
    p.setPen(Qt.PenStyle.NoPen)
    # far flange
    p.setBrush(dark)
    p.drawEllipse(QRectF(x + w * 0.48, y, w * 0.40, h))
    # filament body
    from PyQt6.QtGui import QLinearGradient
    g = QLinearGradient(QPointF(x, y), QPointF(x, y + h))
    g.setColorAt(0.0, dark)
    g.setColorAt(0.35, light)
    g.setColorAt(1.0, dark)
    p.setBrush(g)
    p.drawRect(QRectF(x + w * 0.30, y + h * 0.08, w * 0.38, h * 0.84))
    # near flange with hub
    p.setBrush(QColor(c))
    p.drawEllipse(QRectF(x + w * 0.10, y, w * 0.40, h))
    p.setBrush(dark)
    p.drawEllipse(QRectF(x + w * 0.20, y + h * 0.30, w * 0.20, h * 0.40))
    p.setBrush(QColor(15, 16, 18))
    p.drawEllipse(QRectF(x + w * 0.25, y + h * 0.40, w * 0.10, h * 0.20))


def load(p, r, c):
    _stroke(p, c, r.width() * 0.09)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawLine(QPointF(x + w * 0.5, y), QPointF(x + w * 0.5, y + h * 0.62))
    p.drawPolyline([QPointF(x + w * 0.26, y + h * 0.40), QPointF(x + w * 0.5, y + h * 0.64),
                    QPointF(x + w * 0.74, y + h * 0.40)])
    p.drawPolyline([QPointF(x + w * 0.06, y + h * 0.70), QPointF(x + w * 0.06, y + h * 0.94),
                    QPointF(x + w * 0.94, y + h * 0.94), QPointF(x + w * 0.94, y + h * 0.70)])


def unload(p, r, c):
    _stroke(p, c, r.width() * 0.09)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawLine(QPointF(x + w * 0.5, y + h * 0.04), QPointF(x + w * 0.5, y + h * 0.66))
    p.drawPolyline([QPointF(x + w * 0.26, y + h * 0.28), QPointF(x + w * 0.5, y + h * 0.04),
                    QPointF(x + w * 0.74, y + h * 0.28)])
    p.drawPolyline([QPointF(x + w * 0.06, y + h * 0.70), QPointF(x + w * 0.06, y + h * 0.94),
                    QPointF(x + w * 0.94, y + h * 0.94), QPointF(x + w * 0.94, y + h * 0.70)])


def advance(p, r, c):
    _stroke(p, c, r.width() * 0.10)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    for dx in (0.08, 0.48):
        p.drawPolyline([QPointF(x + w * dx, y + h * 0.12), QPointF(x + w * (dx + 0.36), y + h * 0.5),
                        QPointF(x + w * dx, y + h * 0.88)])


def retract(p, r, c):
    _stroke(p, c, r.width() * 0.10)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    for dx in (0.56, 0.16):
        p.drawPolyline([QPointF(x + w * (dx + 0.36), y + h * 0.12), QPointF(x + w * dx, y + h * 0.5),
                        QPointF(x + w * (dx + 0.36), y + h * 0.88)])


def refresh(p, r, c):
    _stroke(p, c, r.width() * 0.09)
    rr = r.adjusted(r.width() * 0.1, r.height() * 0.1, -r.width() * 0.1, -r.height() * 0.1)
    p.drawArc(rr, 30 * 16, 150 * 16)
    p.drawArc(rr, 210 * 16, 150 * 16)
    cx, cy, rad = rr.center().x(), rr.center().y(), rr.width() / 2
    for a in (30, 210):
        t = math.radians(a)
        px, py = cx + rad * math.cos(t), cy - rad * math.sin(t)
        d = 1 if a == 30 else -1
        p.drawPolyline([QPointF(px - d * r.width() * 0.20, py - d * r.height() * 0.02), QPointF(px, py),
                        QPointF(px + d * r.width() * 0.02, py - d * r.height() * 0.20)])


def check(p, r, c):
    _stroke(p, c, r.width() * 0.11)
    p.drawPolyline([QPointF(r.x() + r.width() * 0.08, r.y() + r.height() * 0.52),
                    QPointF(r.x() + r.width() * 0.38, r.y() + r.height() * 0.82),
                    QPointF(r.x() + r.width() * 0.92, r.y() + r.height() * 0.20)])


def swap(p, r, c):
    _stroke(p, c, r.width() * 0.09)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawLine(QPointF(x + w * 0.06, y + h * 0.32), QPointF(x + w * 0.90, y + h * 0.32))
    p.drawPolyline([QPointF(x + w * 0.70, y + h * 0.12), QPointF(x + w * 0.92, y + h * 0.32),
                    QPointF(x + w * 0.70, y + h * 0.52)])
    p.drawLine(QPointF(x + w * 0.94, y + h * 0.70), QPointF(x + w * 0.10, y + h * 0.70))
    p.drawPolyline([QPointF(x + w * 0.30, y + h * 0.50), QPointF(x + w * 0.08, y + h * 0.70),
                    QPointF(x + w * 0.30, y + h * 0.90)])


def thermometer(p, r, c):
    _stroke(p, c, r.width() * 0.10)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawRoundedRect(QRectF(x + w * 0.36, y, w * 0.28, h * 0.66), w * 0.14, w * 0.14)
    p.setBrush(c)
    p.drawEllipse(QPointF(x + w * 0.5, y + h * 0.78), w * 0.24, w * 0.24)
    p.drawLine(QPointF(x + w * 0.5, y + h * 0.30), QPointF(x + w * 0.5, y + h * 0.70))


def palette(p, r, c):
    _stroke(p, c, r.width() * 0.08)
    p.drawEllipse(r.adjusted(1, 1, -1, -1))
    p.setPen(Qt.PenStyle.NoPen)
    for i, col in enumerate(("#ff2a22", "#ffd21a", "#33d14f", "#2f9bff")):
        a = math.radians(200 + i * 45)
        p.setBrush(QColor(col))
        p.drawEllipse(QPointF(r.center().x() + r.width() * 0.25 * math.cos(a),
                              r.center().y() - r.height() * 0.25 * math.sin(a)), r.width() * 0.1, r.width() * 0.1)


def eject(p, r, c):
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawPolygon([QPointF(x + w * 0.5, y + h * 0.06), QPointF(x + w * 0.94, y + h * 0.60),
                   QPointF(x + w * 0.06, y + h * 0.60)])
    p.drawRect(QRectF(x + w * 0.06, y + h * 0.74, w * 0.88, h * 0.18))


def backspace(p, r, c, w=None):
    _stroke(p, c, r.width() * 0.08)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawPolygon([QPointF(x, y + h * 0.5), QPointF(x + w * 0.30, y + h * 0.1), QPointF(x + w, y + h * 0.1),
                   QPointF(x + w, y + h * 0.9), QPointF(x + w * 0.30, y + h * 0.9)])
    p.drawLine(QPointF(x + w * 0.48, y + h * 0.32), QPointF(x + w * 0.78, y + h * 0.68))
    p.drawLine(QPointF(x + w * 0.78, y + h * 0.32), QPointF(x + w * 0.48, y + h * 0.68))


def back_arrow(p, r, c, w=2.0):
    chevron_left = [QPointF(r.right(), r.y()), QPointF(r.x(), r.center().y()), QPointF(r.right(), r.bottom())]
    _stroke(p, c, w)
    p.drawPolyline(chevron_left)


def fan(p, r, c):
    """Three-blade fan glyph (gauge hubs)."""
    cx, cy = r.center().x(), r.center().y()
    rad = r.width() / 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        blade = QPainterPath()
        blade.moveTo(cx, cy)
        tip = QPointF(cx + rad * math.cos(a), cy - rad * math.sin(a))
        side = QPointF(cx + rad * 0.95 * math.cos(a + 0.9), cy - rad * 0.95 * math.sin(a + 0.9))
        blade.cubicTo(QPointF(cx + rad * 0.5 * math.cos(a - 0.5), cy - rad * 0.5 * math.sin(a - 0.5)), tip, tip)
        blade.cubicTo(side, side, QPointF(cx, cy))
        p.drawPath(blade)
    p.setBrush(QColor(28, 30, 35))
    p.drawEllipse(QPointF(cx, cy), rad * 0.22, rad * 0.22)
    p.setBrush(c)
    p.drawEllipse(QPointF(cx, cy), rad * 0.12, rad * 0.12)


def bulb(p, r, c):
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    _stroke(p, c, w * 0.08)
    p.drawEllipse(QRectF(x + w * 0.2, y, w * 0.6, h * 0.6))
    p.drawLine(QPointF(x + w * 0.38, y + h * 0.62), QPointF(x + w * 0.38, y + h * 0.8))
    p.drawLine(QPointF(x + w * 0.62, y + h * 0.62), QPointF(x + w * 0.62, y + h * 0.8))
    p.drawLine(QPointF(x + w * 0.36, y + h * 0.86), QPointF(x + w * 0.64, y + h * 0.86))
    p.drawLine(QPointF(x + w * 0.42, y + h * 0.97), QPointF(x + w * 0.58, y + h * 0.97))


def snowflake(p, r, c):
    _stroke(p, c, r.width() * 0.08)
    cx, cy, rad = r.center().x(), r.center().y(), r.width() / 2
    for k in range(3):
        a = math.radians(90 + 60 * k)
        p.drawLine(QPointF(cx + rad * math.cos(a), cy - rad * math.sin(a)),
                   QPointF(cx - rad * math.cos(a), cy + rad * math.sin(a)))


def crosshair(p, r, c):
    _stroke(p, c, r.width() * 0.08)
    p.drawEllipse(r.adjusted(r.width() * 0.15, r.height() * 0.15, -r.width() * 0.15, -r.height() * 0.15))
    cx, cy = r.center().x(), r.center().y()
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        p.drawLine(QPointF(cx + dx * r.width() * 0.2, cy + dy * r.height() * 0.2),
                   QPointF(cx + dx * r.width() * 0.5, cy + dy * r.height() * 0.5))


def corner(p, r, c):
    """Dashed square (bed-position presets)."""
    pen = _pen(c, r.width() * 0.08)
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(2, 2, -2, -2))


def save(p, r, c):
    print_(p, r, c)


def terminal(p, r, c):
    _stroke(p, c, r.width() * 0.08)
    p.drawRoundedRect(r.adjusted(1, 2, -1, -2), 2, 2)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawPolyline([QPointF(x + w * 0.22, y + h * 0.36), QPointF(x + w * 0.40, y + h * 0.52),
                    QPointF(x + w * 0.22, y + h * 0.68)])
    p.drawLine(QPointF(x + w * 0.48, y + h * 0.70), QPointF(x + w * 0.76, y + h * 0.70))


def mesh_grid(p, r, c):
    _stroke(p, c, r.width() * 0.07)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    for k in range(4):
        t = k / 3
        p.drawLine(QPointF(x + w * (0.05 + 0.3 * t), y + h * (0.2 + 0.6 * t)),
                   QPointF(x + w * (0.65 + 0.3 * t), y + h * (0.2 + 0.6 * t)))
        p.drawLine(QPointF(x + w * (0.05 + 0.6 * t), y + h * 0.2), QPointF(x + w * (0.35 + 0.6 * t), y + h * 0.8))


def z_arrows(p, r, c):
    _stroke(p, c, r.width() * 0.09)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawLine(QPointF(x + w * 0.5, y + h * 0.06), QPointF(x + w * 0.5, y + h * 0.94))
    p.drawPolyline([QPointF(x + w * 0.28, y + h * 0.26), QPointF(x + w * 0.5, y + h * 0.06), QPointF(x + w * 0.72, y + h * 0.26)])
    p.drawPolyline([QPointF(x + w * 0.28, y + h * 0.74), QPointF(x + w * 0.5, y + h * 0.94), QPointF(x + w * 0.72, y + h * 0.74)])


def camera(p, r, c):
    _stroke(p, c, r.width() * 0.08)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawRoundedRect(QRectF(x + w * 0.04, y + h * 0.26, w * 0.92, h * 0.62), 3, 3)
    p.drawRect(QRectF(x + w * 0.34, y + h * 0.12, w * 0.32, h * 0.14))
    p.drawEllipse(QPointF(x + w * 0.5, y + h * 0.57), w * 0.18, w * 0.18)


def clock(p, r, c):
    _stroke(p, c, r.width() * 0.08)
    p.drawEllipse(r.adjusted(1, 1, -1, -1))
    cx, cy = r.center().x(), r.center().y()
    p.drawLine(QPointF(cx, cy), QPointF(cx, cy - r.height() * 0.30))
    p.drawLine(QPointF(cx, cy), QPointF(cx + r.width() * 0.22, cy + r.height() * 0.12))
