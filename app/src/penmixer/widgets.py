"""Custom-painted dashboard widgets: the tick-dot equalizer slider and the
circular track-art disc with its center ring.
"""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from . import theme

TICKS = 5
CAPSULE_WIDTH = 40.0
TICK_RADIUS = 4.5
THUMB_RADIUS = 17.0
FILL_COLOR = "#C7C7CC"
TICK_COLOR = "#B2B2B9"


class EqSlider(QWidget):
    """A vertical slider styled as a wide capsule track with tick-dots and a
    large round thumb; a bipolar fill runs from the center (0 dB) out to the
    thumb so boost/cut direction and depth both read at a glance. Exposes the
    same value()/setValue()/setRange()/valueChanged subset the rest of the
    app already drives a QSlider with, so it drops in as a straight
    replacement.
    """

    valueChanged = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._min = -120
        self._max = 120
        self._value = 0
        self.setMinimumWidth(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setRange(self, lo: int, hi: int) -> None:
        self._min, self._max = lo, hi

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:
        value = max(self._min, min(self._max, value))
        if value == self._value:
            return
        self._value = value
        self.update()
        self.valueChanged.emit(value)

    def _track_span(self) -> tuple[float, float]:
        margin = THUMB_RADIUS + 4.0
        return margin, self.height() - margin

    def _set_from_y(self, y: float) -> None:
        top, bottom = self._track_span()
        fraction = 1.0 - (y - top) / max(bottom - top, 1.0)
        fraction = max(0.0, min(1.0, fraction))
        self.setValue(round(self._min + fraction * (self._max - self._min)))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._set_from_y(event.position().y())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._set_from_y(event.position().y())

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        cx = self.width() / 2
        top, bottom = self._track_span()
        half = CAPSULE_WIDTH / 2

        capsule = QRectF(cx - half, top, CAPSULE_WIDTH, bottom - top)
        gradient = QLinearGradient(0, top, 0, bottom)
        gradient.setColorAt(0.0, QColor("#E3E3E6"))
        gradient.setColorAt(1.0, QColor("#D3D3D7"))
        painter.setBrush(gradient)
        painter.drawRoundedRect(capsule, half, half)

        center_y = (top + bottom) / 2
        fraction = (self._value - self._min) / (self._max - self._min)
        thumb_y = bottom - fraction * (bottom - top)
        if abs(thumb_y - center_y) > 1.0:
            fill_top, fill_bottom = sorted((thumb_y, center_y))
            fill_rect = QRectF(cx - half, fill_top, CAPSULE_WIDTH, fill_bottom - fill_top)
            painter.setBrush(QColor(FILL_COLOR))
            painter.drawRoundedRect(fill_rect, half, half)

        painter.setBrush(QColor(TICK_COLOR))
        for i in range(TICKS):
            ty = top + (bottom - top) * i / (TICKS - 1)
            painter.drawEllipse(QPointF(cx, ty), TICK_RADIUS, TICK_RADIUS)

        painter.setBrush(QColor(theme.TEXT_PRIMARY))
        painter.drawEllipse(QPointF(cx, thumb_y), THUMB_RADIUS, THUMB_RADIUS)
        painter.end()


class TrackArt(QWidget):
    """Circular album art with a light ring over the center, vinyl-label
    style. Falls back to a flat placeholder disc when there's no image.
    """

    def __init__(self, diameter: int = 132) -> None:
        super().__init__()
        self._diameter = diameter
        self._pixmap: QPixmap | None = None
        self.setFixedSize(diameter, diameter)

    def set_image(self, data: bytes) -> None:
        pixmap = QPixmap()
        self._pixmap = pixmap if data and pixmap.loadFromData(data) else None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, 0, self._diameter, self._diameter)
        clip = QPainterPath()
        clip.addEllipse(rect)
        painter.setClipPath(clip)
        if self._pixmap is not None:
            scaled = self._pixmap.scaled(
                self._diameter,
                self._diameter,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - self._diameter) / 2
            y = (scaled.height() - self._diameter) / 2
            painter.drawPixmap(-int(x), -int(y), scaled)
        else:
            painter.fillRect(rect, QColor(theme.DIVIDER))
        painter.setClipping(False)

        ring_d = self._diameter * 0.34
        ring_rect = QRectF(
            (self._diameter - ring_d) / 2, (self._diameter - ring_d) / 2, ring_d, ring_d
        )
        painter.setBrush(QColor("#E5E6E7"))
        pen = QPen(QColor("#A0A1B2"))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.drawEllipse(ring_rect)
        painter.end()
