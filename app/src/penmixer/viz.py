"""Dot-grid spectrum widget: a speaker-grille of recessed dots that light up
per band, cava-style rise/decay driving how many rows are lit per column.
"""

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QGradient,
    QPainter,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from . import theme
from .spectrum import BASS_EDGE_HZ, TREBLE_EDGE_HZ, bar_frequencies

BAR_COUNT = 32
ROWS = 15  # dot size is the grid pitch, so more rows means smaller dots
DECAY = 0.82
DOT_TO_PITCH = 0.36  # dot radius as a fraction of the grid pitch
SIDE_MARGIN = 0.10  # inset the grid this fraction of the width on each side

BASS_COLOR = QColor(0xFF, 0xC3, 0x00)  # yellow
MID_COLOR = QColor(0x7E, 0xD3, 0x21)  # lime green
TREBLE_COLOR = QColor(0x29, 0xB6, 0xE8)  # light blue
BAND_COLOR = {"bass": BASS_COLOR, "mid": MID_COLOR, "treble": TREBLE_COLOR}

BACKGROUND = QColor(theme.CARD_BG)
DOT_FILL = QColor(0xCD, 0xCD, 0xCD)
LABEL_COLOR = QColor(theme.TEXT_MUTED)


def _inset_gradient(fill: QColor) -> QRadialGradient:
    # fill: <color>; box-shadow: 0 1px 3.7px 0 rgba(0,0,0,.30) inset -- the
    # dot's own color everywhere, darkening toward the rim (rgba black at
    # 0.30 over the fill), the gradient center nudged down so the shadow
    # reads slightly heavier along the top edge, per the 1px y-offset.
    gradient = QRadialGradient(0.5, 0.56, 0.6)
    gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
    shadow = QColor(int(fill.red() * 0.7), int(fill.green() * 0.7), int(fill.blue() * 0.7))
    gradient.setColorAt(0.0, fill)
    gradient.setColorAt(0.55, fill)
    gradient.setColorAt(1.0, shadow)
    return gradient


class SpectrumWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(208)
        self._levels = np.zeros(BAR_COUNT)
        freqs = bar_frequencies(BAR_COUNT)
        self._bands = [
            "bass" if f < BASS_EDGE_HZ else "mid" if f < TREBLE_EDGE_HZ else "treble"
            for f in freqs
        ]
        self._off_gradient = _inset_gradient(DOT_FILL)
        self._on_gradients = {
            name: _inset_gradient(color) for name, color in BAND_COLOR.items()
        }

    def update_levels(self, levels: np.ndarray) -> None:
        # Rise fast, fall smoothly: reads like an instrument, not a strobe.
        self._levels = np.maximum(levels, self._levels * DECAY)
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), BACKGROUND)
        painter.setPen(Qt.PenStyle.NoPen)

        label_h = 16
        grid_h = self.height() - label_h

        # Inset the grid from both edges, then fit whole columns in what is
        # left; the labels below line up with the same inset.
        inset = self.width() * SIDE_MARGIN
        width = self.width() - 2 * inset

        # One pitch for both axes so the gaps match evenly x and y; columns
        # are however many fit at that pitch, centered in the leftover width.
        pitch = grid_h / ROWS
        cols = max(int(width // pitch), 1)
        x_margin = inset + (width - cols * pitch) / 2
        radius = pitch * DOT_TO_PITCH

        for col in range(cols):
            band_index = min(int(col / cols * BAR_COUNT), BAR_COUNT - 1)
            lit_rows = self._levels[band_index] * ROWS
            on_gradient = self._on_gradients[self._bands[band_index]]
            cx = x_margin + col * pitch + pitch / 2
            for row in range(ROWS):
                cy = grid_h - row * pitch - pitch / 2
                rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
                painter.setBrush(self._off_gradient)
                painter.drawEllipse(rect)
                amount = min(max(lit_rows - row, 0.0), 1.0)
                if amount > 0:
                    painter.setOpacity(amount)
                    painter.setBrush(on_gradient)
                    painter.drawEllipse(rect)
                    painter.setOpacity(1.0)

        painter.setClipping(False)
        font = self.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(LABEL_COLOR)
        metrics = QFontMetrics(font)
        y = self.height() - 4
        painter.drawText(round(inset), y, "bass")
        painter.drawText(
            round(self.width() / 2 - metrics.horizontalAdvance("mid") / 2), y, "mid"
        )
        painter.drawText(
            round(self.width() - inset - metrics.horizontalAdvance("treble")), y, "treble"
        )
        painter.end()

    def sizeHint(self):
        from PySide6.QtCore import QSize

        return QSize(420, 250)
