"""Modal confirmation overlay painted over the whole window."""
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QWidget

from nexus import theme
from nexus.config import sx, sy, smin
from nexus.widgets import icons
from nexus.widgets.glow_widget import paint_panel, panel_path, red_glow

BOX_W, BOX_H = sx(460), sy(236)


class _DialogButton(QAbstractButton):
    def __init__(self, label, danger, parent):
        super().__init__(parent)
        self._label = label
        self._danger = danger

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        if self._danger:
            p.fillPath(panel_path(r, 6), QColor(150, 14, 12) if self.isDown() else QColor(118, 10, 9))
            p.setPen(QPen(QColor(255, 42, 32), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.8, 0.8, -0.8, -0.8), 6, 6)
        else:
            paint_panel(p, r, 6, top=QColor(36, 39, 45) if self.isDown() else QColor(26, 29, 33))
        p.setFont(theme.font(smin(18), QFont.Weight.DemiBold))
        p.setPen(theme.FG)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


class ConfirmDialog(QWidget):
    """Two-step confirmation: nothing happens until the danger button is tapped."""
    confirmed = pyqtSignal()

    def __init__(self, title, message, cancel_label, confirm_label, parent):
        super().__init__(parent)
        self._title = title
        self._message = message
        self._detail = ""
        self._box = QRectF()
        self.cancel_btn = _DialogButton(cancel_label, False, self)
        self.confirm_btn = _DialogButton(confirm_label, True, self)
        self.cancel_btn.clicked.connect(self.hide)
        self.confirm_btn.clicked.connect(self._confirm)
        self.hide()

    def _layout(self):
        self.setGeometry(self.parentWidget().rect())  # cover the whole window
        self._box = QRectF((self.width() - BOX_W) / 2, (self.height() - BOX_H) / 2, BOX_W, BOX_H)
        bh = sy(50)
        bw = (BOX_W - 3 * sx(20)) / 2
        by = self._box.bottom() - sy(20) - bh
        self.cancel_btn.setGeometry(int(self._box.x() + sx(20)), int(by), int(bw), bh)
        self.confirm_btn.setGeometry(int(self._box.x() + sx(40) + bw), int(by), int(bw), bh)

    def ask(self, title, message, confirm_label, detail="", info=False):
        """Reuse the dialog for another two-step confirmation (info=True: a notice with only OK)."""
        self._title, self._message = title, message
        self.confirm_btn._label = confirm_label
        self.cancel_btn.setVisible(not info)
        self.open(detail)

    def open(self, detail=""):
        self._detail = detail
        self._layout()
        self.raise_()
        self.show()
        self.update()

    def _confirm(self):
        self.hide()
        self.confirmed.emit()

    def mousePressEvent(self, e):
        e.accept()  # swallow taps outside the box; only the two buttons act

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 175))
        b = self._box
        p.drawPixmap(int(b.x()) - 10, int(b.y()) - 10, red_glow(int(b.width()), int(b.height()), 10.0, 10, 0.55))
        paint_panel(p, b, 10, alpha=250, border=QColor(120, 24, 20))
        icons.warning(p, QRectF(b.x() + sx(24), b.y() + sy(24), smin(40), smin(36)), QColor(theme.AMBER))
        p.setFont(theme.font(smin(26), QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(b.x() + sx(80), b.y() + sy(22), b.width() - sx(100), sy(40)), Qt.AlignmentFlag.AlignVCenter, self._title)
        f = theme.font(theme.LABEL, QFont.Weight.Medium)
        p.setFont(f)
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(b.x() + sx(24), b.y() + sy(76), b.width() - sx(48), sy(44)),
                   Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self._message)
        if self._detail:
            f = theme.font(theme.BODY, QFont.Weight.Medium)
            p.setFont(f)
            p.setPen(theme.DIM)
            p.drawText(QRectF(b.x() + sx(24), b.y() + sy(120), b.width() - sx(48), sy(22)), Qt.AlignmentFlag.AlignVCenter,
                       QFontMetricsF(f).elidedText(self._detail, Qt.TextElideMode.ElideMiddle, b.width() - sx(48)))
        p.end()
