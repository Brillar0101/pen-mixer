"""Spectrum + waveform widget: cava-style bars with the live wave drawn behind."""

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .spectrum import BASS_EDGE_HZ, TREBLE_EDGE_HZ, bar_frequencies

BAR_COUNT = 32
DECAY = 0.82

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
        self._wave = np.zeros(256)
        freqs = bar_frequencies(BAR_COUNT)
        self._colors = [
            BASS_COLOR if f < BASS_EDGE_HZ else MID_COLOR if f < TREBLE_EDGE_HZ else TREBLE_COLOR
            for f in freqs
        ]

    def update_levels(self, levels: np.ndarray, wave: np.ndarray | None = None) -> None:
        # Rise fast, fall smoothly, hold a peak cap: reads like an instrument.
        self._levels = np.maximum(levels, self._levels * DECAY)
        self._peaks = np.maximum(self._levels, self._peaks * 0.97)
        if wave is not None and len(wave):
            step = max(len(wave) // 256, 1)
            self._wave = wave[::step][:256]
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKGROUND)
        width = self.width()
        height = self.height()
        # Waveform behind the bars: the music's wave, drawn live.
        if len(self._wave):
            mid_y = height / 2
            amp = height * 0.45
            xs = np.linspace(0, width, len(self._wave))
            points = QPolygonF(
                [QPointF(float(x), float(mid_y - w * amp)) for x, w in zip(xs, self._wave)]
            )
            pen = QPen(QColor(0x8A, 0x8D, 0x93, 150))
            pen.setWidthF(1.4)
            painter.setPen(pen)
            painter.drawPolyline(points)
        gap = 2
        bar_width = max((width - gap * (BAR_COUNT + 1)) / BAR_COUNT, 1)
        x = float(gap)
        for level, peak, color in zip(self._levels, self._peaks, self._colors):
            bar_height = max(int(level * (height - 8)), 2)
            painter.fillRect(
                int(x), height - bar_height, int(bar_width), bar_height, color
            )
            peak_y = height - max(int(peak * (height - 8)), 2) - 2
            painter.fillRect(int(x), peak_y, int(bar_width), 2, color.lighter(150))
            x += bar_width + gap
        painter.setPen(QColor(0x6A, 0x6E, 0x73))
        painter.drawText(6, 14, "bass")
        painter.drawText(width // 2 - 10, 14, "mid")
        painter.drawText(width - 44, 14, "treble")
        painter.end()

    def sizeHint(self):
        from PySide6.QtCore import QSize

        return QSize(420, 150)
