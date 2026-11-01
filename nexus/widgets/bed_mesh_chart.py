"""2D bed-mesh heat map (front of the bed at the bottom). Rendered once per mesh into a
cached pixmap — no continuous redraw. Blue = low, graphite = 0, red = high."""
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QWidget

from nexus import theme

LOW, MID, HIGH = QColor("#2f8bff"), QColor("#262a30"), QColor("#ff2a22")


def mesh_colour(v, scale):
    t = max(-1.0, min(1.0, v / scale)) if scale else 0.0
    end = HIGH if t > 0 else LOW
    t = abs(t)
    return QColor(round(MID.red() + (end.red() - MID.red()) * t), round(MID.green() + (end.green() - MID.green()) * t),
                  round(MID.blue() + (end.blue() - MID.blue()) * t))


def mesh_stats(matrix):
    flat = [v for row in matrix for v in row]
    lo, hi = min(flat), max(flat)
    return lo, hi, hi - lo


class BedMeshChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._matrix = None
        self._cache = None

    def set_matrix(self, matrix):
        if matrix != self._matrix:
            self._matrix = matrix
            self._cache = None
            self.update()

    def resizeEvent(self, e):
        self._cache = None
        super().resizeEvent(e)

    def scale(self):
        if not self._matrix:
            return 0.0
        lo, hi, _ = mesh_stats(self._matrix)
        return max(abs(lo), abs(hi), 0.05)

    def _render(self):
        px = QPixmap(self.size())
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rows, cols = len(self._matrix), len(self._matrix[0])
        side = min(self.width() / cols, self.height() / rows)
        ox, oy = (self.width() - side * cols) / 2, (self.height() - side * rows) / 2
        scale = self.scale()
        labels = cols <= 9 and rows <= 9
        p.setFont(theme.font(max(10, int(side * 0.26)), QFont.Weight.DemiBold))
        for j, row in enumerate(self._matrix):        # row 0 = front (min Y) -> drawn at the bottom
            for i, v in enumerate(row):
                cell = QRectF(ox + i * side, oy + (rows - 1 - j) * side, side, side).adjusted(1, 1, -1, -1)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(mesh_colour(v, scale))
                p.drawRoundedRect(cell, 2, 2)
                if labels:
                    p.setPen(QColor(255, 255, 255, 220))
                    p.drawText(cell, Qt.AlignmentFlag.AlignCenter, f"{v:+.2f}")
        p.end()
        return px

    def paintEvent(self, _):
        p = QPainter(self)
        if not self._matrix:
            p.setFont(theme.font(theme.CARD, QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No mesh loaded")
        else:
            if self._cache is None:
                self._cache = self._render()
            p.drawPixmap(0, 0, self._cache)
        p.end()
