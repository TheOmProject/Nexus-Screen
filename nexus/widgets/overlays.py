"""Modal overlays drawn over the whole window: temperature keypad, colour and
material pickers. Nothing is applied until the user confirms."""
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QButtonGroup, QWidget

from nexus import theme
from nexus.widgets import icons
from nexus.widgets.buttons import SmallButton
from nexus.widgets.dialog import _DialogButton
from nexus.widgets.glow_widget import paint_panel, red_glow
from nexus.widgets.panels import Tile

MATERIALS = ["PLA", "PETG", "ABS", "ASA", "TPU", "PC", "PA", "PVA", "HIPS"]
MATERIAL_TEMPS = {"PLA": 220, "PETG": 240, "ABS": 250, "ASA": 255, "TPU": 230,
                  "PC": 270, "PA": 260, "PVA": 200, "HIPS": 240}
COLOURS = [("White", "#FFFFFF"), ("Black", "#1A1A1A"), ("Grey", "#8A8D91"), ("Silver", "#C9CED5"),
           ("Red", "#FF2A22"), ("Orange", "#FF7A1A"), ("Yellow", "#FFD21A"), ("Beige", "#E8D3A5"),
           ("Green", "#33D14F"), ("Teal", "#14C8B4"), ("Blue", "#2F9BFF"), ("Navy", "#1F3B8C"),
           ("Purple", "#A04BFF"), ("Pink", "#FF5FB0"), ("Brown", "#8B5A2B"), ("Natural", "#EDE6D6")]


def validate_range(text, lo, hi, unit=""):
    """Generic keypad value: lo <= v <= hi. Returns (value, error)."""
    if not text or text == ".":
        return None, ""
    try:
        value = float(text)
    except ValueError:
        return None, "Invalid number"
    if lo <= value <= hi:
        return value, ""
    return None, f"Must be {lo:g}–{hi:g}{(' ' + unit) if unit else ''}"


def validate_target(text, limits):
    """Klipper accepts target 0 (off) or min_temp..max_temp. Returns (value, error)."""
    if not text or text == ".":
        return None, ""
    try:
        value = float(text)
    except ValueError:
        return None, "Invalid number"
    lo, hi = limits
    if value == 0 or lo <= value <= hi:
        return value, ""
    return None, f"Must be 0 or {lo:g}–{hi:g}°C"


class Overlay(QWidget):
    BOX = (560, 360)

    def __init__(self, parent):
        super().__init__(parent)
        self.hide()

    def box(self):
        w, h = self.BOX
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def present(self):
        self.setGeometry(self.parentWidget().rect())
        self.layout_children(self.box())
        self.raise_()
        self.show()
        self.update()

    def layout_children(self, b):
        pass

    def mousePressEvent(self, e):
        e.accept()  # modal: taps outside the box do nothing

    def paint_box(self, p, title):
        p.fillRect(self.rect(), QColor(0, 0, 0, 175))
        b = self.box()
        p.drawPixmap(int(b.x()) - 10, int(b.y()) - 10, red_glow(int(b.width()), int(b.height()), 10.0, 10, 0.5))
        paint_panel(p, b, 10, alpha=250, border=QColor(120, 24, 20))
        p.setFont(theme.font(24, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(b.x() + 24, b.y() + 12, b.width() - 48, 34), Qt.AlignmentFlag.AlignVCenter, title)
        return b


class TemperatureKeypad(Overlay):
    """Numeric keypad for a heater target. Emits confirmed(heater, value) only on Confirm."""
    BOX = (600, 404)
    confirmed = pyqtSignal(str, float)

    KEYS = ["7", "8", "9", "4", "5", "6", "1", "2", "3", ".", "0", "back"]

    def __init__(self, parent):
        super().__init__(parent)
        self._heater = ""
        self._label = ""
        self._limits = (0.0, 0.0)
        self._current = None
        self._target = None
        self._text = ""
        self._allowed = True
        self._spec = None      # None = heater mode (approved); dict = generic value mode
        self._callback = None
        self.keys = {}
        for k in self.KEYS:
            b = SmallButton("" if k == "back" else k, icon=icons.backspace if k == "back" else None,
                            parent=self, font_px=26, checkable=False)
            b.clicked.connect(lambda _=False, key=k: self.press(key))
            self.keys[k] = b
        self.clear_btn = _DialogButton("Clear", False, self)
        self.cancel_btn = _DialogButton("Cancel", False, self)
        self.confirm_btn = _DialogButton("Confirm", True, self)
        self.clear_btn.clicked.connect(lambda: self.press("clear"))
        self.cancel_btn.clicked.connect(self.hide)
        self.confirm_btn.clicked.connect(self._confirm)

    def open_for(self, heater, label, current, target, limits, allowed=True):
        self._spec = None
        self._heater, self._label, self._limits = heater, label, limits
        self._allowed = allowed
        self._current, self._target = current, target
        self._text = ""
        self._refresh()
        self.present()

    def open_value(self, title, unit, current, lo, hi, int_digits, decimals, callback, allowed=True):
        """Generic numeric entry (flow rate, pressure advance, profile values)."""
        self._spec = {"title": title, "unit": unit, "lo": lo, "hi": hi,
                      "int_digits": int_digits, "decimals": decimals}
        self._callback = callback
        self._allowed = allowed
        self._current, self._target = current, None
        self._text = ""
        self._refresh()
        self.present()

    def set_readings(self, current, target):
        if (current, target) != (self._current, self._target):
            self._current, self._target = current, target
            self.update()

    def layout_children(self, b):
        kx, ky, kw, kh, g = b.x() + 282, b.y() + 62, 94, 56, 9
        for i, k in enumerate(self.KEYS):
            self.keys[k].setGeometry(int(kx + (i % 3) * (kw + g)), int(ky + (i // 3) * (kh + 8)), kw, kh)
        by = int(b.bottom() - 20 - 54)
        self.clear_btn.setGeometry(int(b.x() + 24), by, 116, 54)
        self.cancel_btn.setGeometry(int(b.x() + 150), by, 116, 54)
        self.confirm_btn.setGeometry(int(kx), by, 3 * kw + 2 * g, 54)

    def press(self, key):
        t = self._text
        if key == "back":
            t = t[:-1]
        elif key == "clear":
            t = ""
        int_digits, decimals = (self._spec["int_digits"], self._spec["decimals"]) if self._spec else (3, 1)
        if key == "." and decimals:
            if "." not in t:
                t = (t or "0") + "."
        elif key.isdigit():  # heater mode: up to 3 integer digits and 1 decimal, no leading zero
            if "." in t:
                if len(t.split(".")[1]) < decimals:
                    t += key
            elif len(t) < int_digits:
                t = key if t == "0" else t + key
        self._text = t
        self._refresh()

    def _refresh(self):
        if self._spec:
            sp = self._spec
            value, err = validate_range(self._text, sp["lo"], sp["hi"], sp["unit"])
        else:
            value, err = validate_target(self._text, self._limits)
        self._value, self._error = value, err
        self.confirm_btn.setEnabled(value is not None and self._allowed)
        self.update()

    def _confirm(self):
        if self._value is not None:
            self.hide()
            if self._spec:
                self._callback(self._value)
            else:
                self.confirmed.emit(self._heater, self._value)

    def _paint_value_mode(self, p):
        sp = self._spec
        b = self.paint_box(p, sp["title"])
        x = b.x() + 24
        fmt = (lambda v: "--" if v is None else f"{v:.{sp['decimals']}f}{(' ' + sp['unit']) if sp['unit'] else ''}")
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(x, b.y() + 62, 100, 26), Qt.AlignmentFlag.AlignVCenter, "Current")
        p.setFont(theme.font(20, QFont.Weight.Bold))
        p.setPen(theme.FG)
        p.drawText(QRectF(x + 100, b.y() + 62, 140, 26), Qt.AlignmentFlag.AlignVCenter, fmt(self._current))
        e = QRectF(x, b.y() + 132, 242, 76)
        paint_panel(p, e, 6, top=QColor(8, 9, 11), bottom=QColor(14, 16, 19),
                    border=QColor(255, 42, 32) if self._text else QColor(48, 52, 59))
        p.setFont(theme.font(46, QFont.Weight.Bold))
        p.setPen(theme.FG if self._text else theme.MUTED)
        shown = self._text or ("0" if self._current is None else f"{self._current:.{sp['decimals']}f}")
        unit_w = 52 if sp["unit"] else 10
        p.drawText(e.adjusted(10, 0, -unit_w, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, shown)
        if sp["unit"]:
            p.setFont(theme.font(20, QFont.Weight.DemiBold))
            p.setPen(theme.DIM)
            p.drawText(e.adjusted(0, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, sp["unit"])
        p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(x, b.y() + 214, 242, 20), Qt.AlignmentFlag.AlignVCenter,
                   f"Allowed: {sp['lo']:g}–{sp['hi']:g}{(' ' + sp['unit']) if sp['unit'] else ''}")
        note = self._error or ("" if self._allowed else "Printer commands are disabled")
        if note:
            p.setFont(theme.font(theme.LABEL, QFont.Weight.DemiBold))
            p.setPen(theme.RED if self._error else theme.AMBER)
            p.drawText(QRectF(x, b.y() + 236, 242, 20), Qt.AlignmentFlag.AlignVCenter, note)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._spec:
            self._paint_value_mode(p)
            p.end()
            return
        b = self.paint_box(p, f"{self._label} Temperature")
        x = b.x() + 24
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(x, b.y() + 62, 100, 26), Qt.AlignmentFlag.AlignVCenter, "Current")
        p.drawText(QRectF(x, b.y() + 92, 100, 26), Qt.AlignmentFlag.AlignVCenter, "Target")
        p.setFont(theme.font(20, QFont.Weight.Bold))
        p.setPen(theme.FG)
        fmt = lambda v: "--" if v is None else ("Off" if v == 0 else f"{v:.0f}°C")
        p.drawText(QRectF(x + 100, b.y() + 62, 140, 26), Qt.AlignmentFlag.AlignVCenter, fmt(self._current))
        p.drawText(QRectF(x + 100, b.y() + 92, 140, 26), Qt.AlignmentFlag.AlignVCenter, fmt(self._target))
        # entry display
        e = QRectF(x, b.y() + 132, 242, 76)
        paint_panel(p, e, 6, top=QColor(8, 9, 11), bottom=QColor(14, 16, 19),
                    border=QColor(255, 42, 32) if self._text else QColor(48, 52, 59))
        p.setFont(theme.font(46, QFont.Weight.Bold))
        p.setPen(theme.FG if self._text else theme.MUTED)
        shown = self._text or ("0" if self._target is None else f"{self._target:g}")
        p.drawText(e.adjusted(10, 0, -52, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, shown)
        p.setFont(theme.font(20, QFont.Weight.DemiBold))
        p.setPen(theme.DIM)
        p.drawText(e.adjusted(0, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "°C")
        lo, hi = self._limits
        lo = max(lo, 0.0)  # e.g. chamber min_temp -273.15 is a sensor bound, not a useful target
        p.setFont(theme.font(theme.BODY, QFont.Weight.Medium))
        p.setPen(theme.DIM)
        p.drawText(QRectF(x, b.y() + 214, 242, 20), Qt.AlignmentFlag.AlignVCenter,
                   f"Allowed: 0 (off) or {lo:g}–{hi:g}°C")
        note = self._error or ("" if self._allowed else "Printer commands are disabled")
        if note:
            p.setFont(theme.font(theme.LABEL, QFont.Weight.DemiBold))
            p.setPen(theme.RED if self._error else theme.AMBER)
            p.drawText(QRectF(x, b.y() + 236, 242, 20), Qt.AlignmentFlag.AlignVCenter, note)
        p.end()


class ChoiceOverlay(Overlay):
    """Grid of choices with Cancel / Apply. Emits applied(value)."""
    applied = pyqtSignal(str)

    def __init__(self, title, options, columns, parent):
        super().__init__(parent)
        self._title = title
        self._columns = columns
        self._subject = ""
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.tiles = {}
        self.set_options(options)
        self.cancel_btn = _DialogButton("Cancel", False, self)
        self.apply_btn = _DialogButton("Apply", True, self)
        self.cancel_btn.clicked.connect(self.hide)
        self.apply_btn.clicked.connect(self._apply)

    def set_options(self, options):
        """Replace the choices (e.g. the current filament profile names)."""
        for t in self.tiles.values():
            self.group.removeButton(t)
            t.deleteLater()
        self.tiles = {}
        for value, label, colour in options:
            t = Tile(self._tile_painter(label, colour), self)
            self.group.addButton(t)
            self.tiles[value] = t

    @staticmethod
    def _tile_painter(label, colour):
        def paint(p, r, selected):
            if colour:
                c = QColor(colour)
                d = min(r.height() - 26, 30.0)
                p.setPen(QPen(QColor(0, 0, 0, 120), 1.2))
                p.setBrush(c)
                p.drawEllipse(QRectF(r.center().x() - d / 2, r.y() + 6, d, d))
                p.setFont(theme.font(theme.BODY, QFont.Weight.DemiBold))
                p.setPen(theme.FG)
                p.drawText(QRectF(r.x(), r.bottom() - 20, r.width(), 16), Qt.AlignmentFlag.AlignCenter, label)
            else:
                p.setFont(theme.font(20, QFont.Weight.Bold))
                p.setPen(theme.FG)
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
        return paint

    def open_for(self, subject, current):
        self._subject = subject
        self.group.setExclusive(False)
        for t in self.tiles.values():
            t.setChecked(False)
        self.group.setExclusive(True)
        if current in self.tiles:
            self.tiles[current].setChecked(True)
        self.present()

    def layout_children(self, b):
        n = len(self.tiles)
        cols = self._columns
        rows = (n + cols - 1) // cols
        top, bottom = b.y() + 54, b.bottom() - 20 - 54 - 10
        tw = (b.width() - 40) / cols
        th = (bottom - top) / rows
        for i, t in enumerate(self.tiles.values()):
            t.setGeometry(int(b.x() + 20 + (i % cols) * tw), int(top + (i // cols) * th), int(tw), int(th))
        by = int(b.bottom() - 20 - 54)
        self.cancel_btn.setGeometry(int(b.x() + 24), by, int(b.width() / 2 - 34), 54)
        self.apply_btn.setGeometry(int(b.center().x() + 10), by, int(b.width() / 2 - 34), 54)

    def _apply(self):
        chosen = next((v for v, t in self.tiles.items() if t.isChecked()), None)
        if chosen is not None:
            self.hide()
            self.applied.emit(chosen)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        b = self.paint_box(p, self._title)
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.DemiBold))
        p.setPen(theme.DIM)
        p.drawText(QRectF(b.x() + 24, b.y() + 12, b.width() - 48, 34),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self._subject)
        p.end()


class HeaterPicker(ChoiceOverlay):
    BOX = (460, 250)

    def __init__(self, parent):
        super().__init__("Run PID Tune", [("extruder", "Nozzle", None), ("heater_bed", "Bed", None)], 2, parent)


class ProfilePicker(ChoiceOverlay):
    BOX = (520, 340)

    def __init__(self, parent):
        super().__init__("Material", [], 3, parent)

    def open_for(self, subject, current, names=()):
        self.set_options([(n, n, None) for n in names])
        super().open_for(subject, current)


class ColourPicker(ChoiceOverlay):
    BOX = (600, 404)

    def __init__(self, parent):
        super().__init__("Filament Colour", [(hx, name, hx) for name, hx in COLOURS], 4, parent)


class MaterialPicker(ChoiceOverlay):
    BOX = (520, 340)

    def __init__(self, parent):
        super().__init__("Material", [(m, m, None) for m in MATERIALS], 3, parent)


MONO = "DejaVu Sans Mono"


class Keyboard(Overlay):
    """On-screen keyboard (PROVISIONAL): G-code friendly — digits, letters, = - _ . / and space.
    Emits nothing itself; open_for(title, text, callback) calls back with the text on Done."""
    BOX = (780, 432)
    ROWS = ["1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM-_.", ["shift", "=", "/", "space", "back"]]

    def __init__(self, parent):
        super().__init__(parent)
        self._title, self._text, self._cb, self._upper = "", "", None, True
        self.keys = []
        for row in self.ROWS:
            for k in row:
                label = {"shift": "Aa", "space": "Space", "back": ""}.get(k, k)
                b = SmallButton(label, icon=icons.backspace if k == "back" else None, parent=self,
                                font_px=20, checkable=False)
                b.clicked.connect(lambda _=False, key=k: self.press(key))
                b.key = k
                self.keys.append(b)
        self.cancel_btn = _DialogButton("Cancel", False, self)
        self.done_btn = _DialogButton("Done", True, self)
        self.cancel_btn.clicked.connect(self.hide)
        self.done_btn.clicked.connect(self._done)

    def open_for(self, title, text, callback):
        self._title, self._text, self._cb = title, text, callback
        self.present()

    def layout_children(self, b):
        kw, kh, g, top = 70, 44, 5, b.y() + 108  # 5 rows end above the Cancel / Done row
        i = 0
        for r, row in enumerate(self.ROWS):
            widths = [kw * (3.6 if k == "space" else 1.5 if k in ("shift", "back") else 1) for k in row]
            total = sum(widths) + g * (len(row) - 1)
            x = b.x() + (b.width() - total) / 2
            for wdt in widths:
                self.keys[i].setGeometry(int(x), int(top + r * (kh + g)), int(wdt), kh)
                x += wdt + g
                i += 1
        by = int(b.bottom() - 16 - 50)
        self.cancel_btn.setGeometry(int(b.x() + 20), by, 200, 50)
        self.done_btn.setGeometry(int(b.right() - 220), by, 200, 50)

    def press(self, key):
        if key == "back":
            self._text = self._text[:-1]
        elif key == "shift":
            self._upper = not self._upper
            for b in self.keys:
                if len(b.key) == 1 and b.key.isalpha():
                    b._text = b.key if self._upper else b.key.lower()
                    b.update()
        elif key == "space":
            self._text += " "
        else:
            self._text += key if self._upper or not key.isalpha() else key.lower()
        self.update()

    def _done(self):
        self.hide()
        if self._cb:
            self._cb(self._text)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        b = self.paint_box(p, self._title)
        e = QRectF(b.x() + 20, b.y() + 54, b.width() - 40, 48)
        paint_panel(p, e, 6, top=QColor(8, 9, 11), bottom=QColor(14, 16, 19), border=QColor(255, 42, 32))
        f = QFont(MONO)
        f.setPixelSize(20)
        p.setFont(f)
        p.setPen(theme.FG)
        p.drawText(e.adjusted(12, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter, self._text + "▏")
        p.end()


class ErrorDialog(Overlay):
    """'Error Detected' (reference): Klipper's message, Restart Klipper / View Logs / Close."""
    BOX = (560, 330)

    def __init__(self, parent):
        super().__init__(parent)
        self.message = ""
        self.restart_btn = _DialogButton("Restart Klipper", True, self)
        self.logs_btn = _DialogButton("View Logs", False, self)
        self.close_btn = _DialogButton("Close", False, self)
        self.close_btn.clicked.connect(self.hide)

    def open_for(self, message):
        self.message = message
        self.present()

    def layout_children(self, b):
        bw = (b.width() - 48 - 16) / 3
        by = int(b.bottom() - 18 - 52)
        for i, btn in enumerate((self.restart_btn, self.logs_btn, self.close_btn)):
            btn.setGeometry(int(b.x() + 24 + i * (bw + 8)), by, int(bw), 52)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        b = self.paint_box(p, "")
        icons.warning(p, QRectF(b.x() + 26, b.y() + 20, 50, 44), QColor(theme.RED))
        p.setFont(theme.font(28, QFont.Weight.Bold))
        p.setPen(theme.RED)
        p.drawText(QRectF(b.x() + 92, b.y() + 14, 400, 34), Qt.AlignmentFlag.AlignVCenter, "Error Detected")
        p.setFont(theme.font(theme.BUTTON, QFont.Weight.Medium))
        p.setPen(theme.FG_SOFT)
        p.drawText(QRectF(b.x() + 92, b.y() + 46, 440, 20), Qt.AlignmentFlag.AlignVCenter,
                   "Klipper reported an error")
        box = QRectF(b.x() + 20, b.y() + 80, b.width() - 40, b.height() - 80 - 88)
        paint_panel(p, box, 6, top=QColor(6, 7, 9), bottom=QColor(12, 13, 15), border=QColor(52, 56, 62))
        f = QFont(MONO)
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(theme.FG_SOFT)
        text = "\n".join("!! " + l for l in self.message.splitlines() if l.strip())
        p.drawText(box.adjusted(10, 8, -10, -8), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, text)
        p.end()
