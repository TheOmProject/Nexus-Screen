"""Nexus theme: colour tokens, Rajdhani font loading and the QSS sheet."""
import os

from PyQt6.QtGui import QColor, QFont, QFontDatabase

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_QSS = os.path.join(os.path.dirname(__file__), "nexus.qss")

FAMILY = "Rajdhani"

# ── colour tokens (sampled from the approved Home reference) ────────────────
BG          = QColor("#07080a")
PANEL_TOP   = QColor("#16191d")
PANEL_BOT   = QColor("#0c0e11")
TILE        = QColor("#111317")
BORDER      = QColor("#262a30")
BORDER_HI   = QColor("#3a3f47")
DIVIDER     = QColor("#1f2328")
FG          = QColor("#f1f3f5")
FG_SOFT     = QColor("#c9ced5")
DIM         = QColor("#8d939b")
MUTED       = QColor("#5d636b")
RED         = QColor("#ff2a22")
RED_MID     = QColor("#d81c18")
RED_DEEP    = QColor("#5a0807")
GREEN       = QColor("#27d052")
AMBER       = QColor("#ffae1a")

LANE_COLOURS = {
    "red": QColor("#ff2a22"), "blue": QColor("#2f9bff"),
    "yellow": QColor("#ffd21a"), "green": QColor("#33d14f"),
}


# ── Typography scale: Rajdhani, pixel sizes for the 800x480 panel, one size per UI role ──
# Screens use these names instead of literal sizes. Large numeric readouts (temperatures, Z offset,
# progress %, keypad) are sized to their boxes and stay as they were approved; the top bar, sidebar,
# Back key and Emergency Stop keep their approved sizes.
TITLE = 30     # page title (main pages and submenus) — approved size, kept
SUBTITLE = 15  # line under the page title
HEADING = 17   # panel / section heading ("Step Distance (mm)", "Presets")
CAPS = 16      # uppercase card / group heading ("TEMPERATURES", "PRINT PROGRESS", "CONTROLS")
NAME = 19      # primary item name in a card (file being printed), preset names
CARD = 18      # card title (heater, fan, tool, lane names)
FIELD = 18     # value inside a stepper / field
BUTTON = 17    # button, tile and list-row label
LABEL = 16     # emphasised secondary text: key/value rows, row values
BODY = 15      # secondary information (details, descriptions, list metadata)
CAPTION = 14   # small labels: units, "Current", axis names
SMALL = 13     # minimum: tile subtitles, dense spots (tool T0–T4, lane numbers, chart axes)
JOG = 18       # X± / Y± labels on the jog wheel
JOG_Z = 20     # Z± labels on the Z keys


def load_fonts():
    for name in ("Regular", "Medium", "SemiBold", "Bold"):
        QFontDatabase.addApplicationFont(os.path.join(ASSETS, "fonts", f"Rajdhani-{name}.ttf"))


def font(px, weight=QFont.Weight.Medium, spacing=0.0):
    f = QFont(FAMILY)
    f.setPixelSize(px)
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def qss():
    with open(_QSS) as fh:
        return fh.read()
