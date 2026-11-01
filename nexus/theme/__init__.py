"""Nexus theme: colour tokens, Rajdhani font loading and the QSS sheet."""
import os

from PyQt6.QtGui import QColor, QFont, QFontDatabase

from nexus.config import smin

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


# ── Typography scale: Rajdhani, design pixel sizes for the 800×480 panel ──────
# All sizes pass through smin() so they scale down on smaller displays while
# never going below the legibility minimum (10 px, enforced in config.smin).
# At 800×480 smin(v) == v exactly — no visual change on the reference display.
TITLE    = smin(30)   # page title (main pages and submenus)
SUBTITLE = smin(15)   # line under the page title
HEADING  = smin(17)   # panel / section heading
CAPS     = smin(16)   # uppercase card / group heading
NAME     = smin(19)   # primary item name in a card
CARD     = smin(18)   # card title (heater, fan, tool, lane names)
FIELD    = smin(18)   # value inside a stepper / field
BUTTON   = smin(17)   # button, tile and list-row label
LABEL    = smin(16)   # emphasised secondary text: key/value rows
BODY     = smin(15)   # secondary information
CAPTION  = smin(14)   # small labels: units, "Current", axis names
SMALL    = smin(13)   # minimum: tile subtitles, dense spots
JOG      = smin(18)   # X± / Y± labels on the jog wheel
JOG_Z    = smin(20)   # Z± labels on the Z keys


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
