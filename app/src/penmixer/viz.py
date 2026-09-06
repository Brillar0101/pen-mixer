"""Spectrum widget: cava-style bars with per-bar gradients and peak caps."""

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from .spectrum import BASS_EDGE_HZ, TREBLE_EDGE_HZ, bar_frequencies

BAR_COUNT = 64
# Tuned for the 16 ms refresh: bars snap up on transients and fall back in
# roughly a third of a second, with the peak caps hanging above them.
DECAY = 0.88
PEAK_DECAY = 0.985

BASS_COLOR = QColor(0x3B, 0x82, 0xF6)
MID_COLOR = QColor(0x10, 0xB9, 0x81)
TREBLE_COLOR = QColor(0xF5, 0x9E, 0x0B)
BACKGROUND = QColor(0x12, 0x12, 0x14)


class SpectrumWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(140)
        self._levels = np.zeros(BAR_COUNT)
        self._peaks = np.zeros(BAR_COUNT)
        freqs = bar_frequencies(BAR_COUNT)
        self._colors = [
            BASS_COLOR if f < BASS_EDGE_HZ else MID_COLOR if f < TREBLE_EDGE_HZ else TREBLE_COLOR
            for f in freqs
        ]

    def update_levels(self, levels: np.ndarray) -> None:
        # Rise fast, fall smoothly, hold a peak cap: reads like an instrument.
        self._levels = np.maximum(levels, self._levels * DECAY)
        self._peaks = np.maximum(self._levels, self._peaks * PEAK_DECAY)
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKGROUND)
        width = self.width()
        height = self.height()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        gap = 1.0 if BAR_COUNT > 40 else 2.0
        span = height - 8
        bar_width = max((width - gap * (BAR_COUNT + 1)) / BAR_COUNT, 1.0)
        radius = min(bar_width * 0.35, 2.5)
        x = gap
        for level, peak, color in zip(self._levels, self._peaks, self._colors):
            bar_height = max(level * span, 2.0)
            top = height - bar_height
            # Vertical gradient per bar: the tip reads brighter than the base,
            # so tall bars stand out instead of becoming a flat slab.
            grad = QLinearGradient(0.0, height, 0.0, top)
            grad.setColorAt(0.0, color.darker(160))
            grad.setColorAt(0.55, color)
            grad.setColorAt(1.0, color.lighter(155))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(
                QRectF(x, top, bar_width, bar_height), radius, radius
            )
            # Peak cap floats above and falls slower than the bar under it.
            peak_height = max(peak * span, 2.0)
            cap = QColor(color.lighter(185))
            cap.setAlpha(220)
            painter.setBrush(cap)
            painter.drawRect(QRectF(x, height - peak_height - 2.0, bar_width, 2.0))
            x += bar_width + gap
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor(0x6A, 0x6E, 0x73))
        painter.drawText(6, 14, "bass")
        painter.drawText(width // 2 - 10, 14, "mid")
        painter.drawText(width - 44, 14, "treble")
        painter.end()

    def sizeHint(self):
        from PySide6.QtCore import QSize

        return QSize(420, 150)
