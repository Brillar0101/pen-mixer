"""Shared look for the dashboard: IBM Plex Mono loading, the palette, and
the two-shadow neumorphic card every panel sits in.
"""

from pathlib import Path

from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QWidget

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
FONT_FAMILY = "IBM Plex Mono"

PAGE_BG = "#F1F1F2"
CARD_BG = "#EDEDEF"
CARD_RADIUS = 22

BAR_BG = "#141416"
BAR_TEXT = "#C9C9CE"
BAR_TITLE = "#F5F5F6"

TEXT_PRIMARY = "#1B1B1F"
TEXT_MUTED = "#9A9AA2"
DIVIDER = "#DCDCDF"

GREEN = "#34C979"
RED = "#D65D5D"
ORANGE = "#F3A83A"
BLUE = "#3D4FE0"

SHADOW_LIGHT = QColor(255, 255, 255, 160)  # ~63% opacity, faded from the spec's 100%
SHADOW_DARK = QColor(0, 0, 0, 38)  # 15% of 255


def load_fonts() -> str:
    """Register every font file dropped in assets/fonts; fall back to a
    system monospace family if none are there yet."""
    families: set[str] = set()
    if FONT_DIR.is_dir():
        for path in list(FONT_DIR.glob("*.ttf")) + list(FONT_DIR.glob("*.otf")):
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id >= 0:
                families.update(QFontDatabase.applicationFontFamilies(font_id))
    return FONT_FAMILY if FONT_FAMILY in families else "Consolas"


class Card(QFrame):
    """A rounded panel in the card background color."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(f"#card {{ background: {CARD_BG}; border-radius: {CARD_RADIUS}px; }}")


def with_dual_shadow(widget: QWidget) -> QWidget:
    """Wrap a card with the two drop shadows the design calls for: a white
    highlight cast from the top-left and a soft black shadow from the
    bottom-right. Qt allows only one QGraphicsEffect per widget, so each
    shadow gets its own transparent wrapper layer.
    """
    dark_wrap = QWidget()
    dark_layout = QVBoxLayout(dark_wrap)
    dark_layout.setContentsMargins(0, 0, 0, 0)
    dark_layout.addWidget(widget)
    dark_shadow = QGraphicsDropShadowEffect(dark_wrap)
    dark_shadow.setColor(SHADOW_DARK)
    dark_shadow.setBlurRadius(15)
    dark_shadow.setOffset(9, 8)
    dark_wrap.setGraphicsEffect(dark_shadow)

    light_wrap = QWidget()
    light_layout = QVBoxLayout(light_wrap)
    light_layout.setContentsMargins(0, 0, 0, 0)
    light_layout.addWidget(dark_wrap)
    light_shadow = QGraphicsDropShadowEffect(light_wrap)
    light_shadow.setColor(SHADOW_LIGHT)
    light_shadow.setBlurRadius(10)
    light_shadow.setOffset(-10, -7)
    light_wrap.setGraphicsEffect(light_shadow)
    return light_wrap
