"""Shared look for the dashboard: IBM Plex Mono loading, the palette, and
the two-shadow neumorphic card every panel sits in.
"""

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QWidget

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
# Artwork lives in the repo's docs/images rather than inside the package, so
# resolve up out of app/src/penmixer to the project root.
IMAGE_DIR = Path(__file__).resolve().parents[3] / "docs" / "images"
FONT_FAMILY = "IBM Plex Mono"
# Qt registers the Medium weight as a separate family rather than as a weight
# of the Regular one, so asking for bold synthesises a fake bold off Regular
# instead of using the real Medium file. Ask for it by name.
FONT_FAMILY_MEDIUM = "IBM Plex Mono Medium"

PAGE_BG = "#F1F1F2"
CARD_BG = "#EDEDEF"
CARD_RADIUS = 10
BUTTON_FACE = "#F7F7F8"  # solid face under the skip-button artwork

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
    """Register every font file in the asset folders; fall back to a system
    monospace family if none are there.

    IMAGE_DIR is searched too because the project's IBM Plex Mono files live
    beside the artwork rather than in the package's own assets folder, which
    is why this used to silently fall through to Consolas.
    """
    families: set[str] = set()
    for folder in (FONT_DIR, IMAGE_DIR):
        if not folder.is_dir():
            continue
        for path in list(folder.glob("*.ttf")) + list(folder.glob("*.otf")):
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id >= 0:
                families.update(QFontDatabase.applicationFontFamilies(font_id))
    _register_medium(families)
    return FONT_FAMILY if FONT_FAMILY in families else "Consolas"


_MEDIUM_AVAILABLE = False


def _register_medium(families: set[str]) -> None:
    global _MEDIUM_AVAILABLE
    _MEDIUM_AVAILABLE = FONT_FAMILY_MEDIUM in set(QFontDatabase.families()) | families


def medium_font(base: QFont, point_size: float | None = None) -> QFont:
    """The Medium face at the same size, falling back to synthetic bold."""
    font = QFont(base)
    if point_size is not None:
        font.setPointSizeF(point_size)
    if _MEDIUM_AVAILABLE:
        font.setFamily(FONT_FAMILY_MEDIUM)
    else:
        font.setBold(True)
    return font


class Card(QFrame):
    """A rounded panel in the card background color."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(f"#card {{ background: {CARD_BG}; border-radius: {CARD_RADIUS}px; }}")


def dual_shadow_padding(
    dark_offset: tuple[int, int] = (5, 8),
    dark_blur: int = 12,
    light_offset: tuple[int, int] = (-5, -7),
    light_blur: int = 9,
) -> tuple[int, int, int, int]:
    """Left, top, right, bottom room with_dual_shadow adds around its widget,
    so callers placing the wrapper by hand can line up the face inside it."""
    return (
        max(0, dark_blur - dark_offset[0]) + light_blur - light_offset[0],
        max(0, dark_blur - dark_offset[1]) + light_blur - light_offset[1],
        dark_offset[0] + dark_blur + max(0, light_blur + light_offset[0]),
        dark_offset[1] + dark_blur + max(0, light_blur + light_offset[1]),
    )


def with_dual_shadow(
    widget: QWidget,
    dark_offset: tuple[int, int] = (5, 8),
    dark_blur: int = 12,
    light_offset: tuple[int, int] = (-5, -7),
    light_blur: int = 9,
) -> QWidget:
    """Wrap a card with the two drop shadows the design calls for: a white
    highlight cast from the top-left and a soft black shadow from the
    bottom-right. Qt allows only one QGraphicsEffect per widget, so each
    shadow gets its own transparent wrapper layer.
    """
    dark_wrap = QWidget()
    dark_layout = QVBoxLayout(dark_wrap)
    # A QGraphicsDropShadowEffect is clipped to its widget's rect, so without
    # room on the shadow's side the falloff is cut mid-gradient and lands as
    # a hard dark smear instead of fading out. Offset plus blur is the reach.
    dark_layout.setContentsMargins(
        max(0, dark_blur - dark_offset[0]),
        max(0, dark_blur - dark_offset[1]),
        dark_offset[0] + dark_blur,
        dark_offset[1] + dark_blur,
    )
    dark_layout.addWidget(widget)
    dark_shadow = QGraphicsDropShadowEffect(dark_wrap)
    dark_shadow.setColor(SHADOW_DARK)
    dark_shadow.setBlurRadius(dark_blur)
    dark_shadow.setOffset(*dark_offset)
    dark_wrap.setGraphicsEffect(dark_shadow)

    light_wrap = QWidget()
    light_layout = QVBoxLayout(light_wrap)
    light_layout.setContentsMargins(
        light_blur - light_offset[0],
        light_blur - light_offset[1],
        max(0, light_blur + light_offset[0]),
        max(0, light_blur + light_offset[1]),
    )
    light_layout.addWidget(dark_wrap)
    light_shadow = QGraphicsDropShadowEffect(light_wrap)
    light_shadow.setColor(SHADOW_LIGHT)
    light_shadow.setBlurRadius(light_blur)
    light_shadow.setOffset(*light_offset)
    light_wrap.setGraphicsEffect(light_shadow)
    return light_wrap
