"""Text helpers. Rajdhani's degree sign carries a wide left bearing, so
temperatures are set as number + kerned '°' to match the references."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QFontMetricsF

DEG_KERN = 0.12  # fraction of pixel size pulled back before the degree sign


def degree_width(font, number):
    fm = QFontMetricsF(font)
    return fm.horizontalAdvance(number) + fm.horizontalAdvance("°") - font.pixelSize() * DEG_KERN


def draw_degrees(p, rect, number, font, align=Qt.AlignmentFlag.AlignCenter):
    fm = QFontMetricsF(font)
    total = degree_width(font, number)
    if align & Qt.AlignmentFlag.AlignRight:
        x = rect.right() - total
    elif align & Qt.AlignmentFlag.AlignLeft:
        x = rect.left()
    else:
        x = rect.center().x() - total / 2
    p.setFont(font)
    nw = fm.horizontalAdvance(number)
    flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    p.drawText(QRectF(x, rect.y(), nw + 1, rect.height()), flags, number)
    x += nw - font.pixelSize() * DEG_KERN
    p.drawText(QRectF(x, rect.y(), fm.horizontalAdvance("°") + 1, rect.height()), flags, "°")
