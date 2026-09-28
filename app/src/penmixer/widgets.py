"""Custom-painted dashboard widgets: the tick-dot equalizer slider and the
circular track-art disc with its center ring.
"""

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLayout, QLayoutItem, QPushButton, QSizePolicy, QWidget

from . import theme

# A record turns at 33 rpm (200 deg/s); that reads as frantic on a small
# disc, but much under this and the motion is easy to miss entirely.
# 45 deg/s is one turn every eight seconds: clearly moving, not busy.
SPIN_DEGREES_PER_SECOND = 45.0
SPIN_INTERVAL_MS = 33

GRAIN_TILE = 192
GRAIN_OPACITY = 0.05

TICKS = 5
CAPSULE_WIDTH = 30.0
TICK_RADIUS = 3.5
THUMB_RADIUS = 13.0
TICK_INSET = 20.0  # keeps the dot line clear of the capsule's rounded ends
FILL_COLOR = "#AEAEB3"  # darker than the track, per the reference
TICK_COLOR = "#BFBFC5"


def svg_pixmap(path: str, height: int, ratio: float = 1.0) -> QPixmap | None:
    """Rasterise an SVG to a pixmap of the given logical height.

    Rendered at the screen's device pixel ratio so the result stays crisp on
    a scaled display; returns None if the file will not parse, letting the
    caller fall back to type.
    """
    renderer = QSvgRenderer(path)
    size = renderer.defaultSize()
    if not renderer.isValid() or size.height() <= 0:
        return None
    width = round(size.width() * height / size.height())
    pixmap = QPixmap(round(width * ratio), round(height * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


class GrainOverlay(QWidget):
    """A fixed film grain laid over everything, for a bit of vintage texture.

    Click-through, and the noise is generated once from a fixed seed: a tile
    regenerated per frame would crawl, which reads as noise rather than as
    grain on a photograph.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        rng = np.random.default_rng(7)
        noise = np.ascontiguousarray(
            rng.integers(0, 256, size=(GRAIN_TILE, GRAIN_TILE), dtype=np.uint8)
        )
        image = QImage(
            noise.data, GRAIN_TILE, GRAIN_TILE, GRAIN_TILE, QImage.Format.Format_Grayscale8
        )
        self._tile = QPixmap.fromImage(image.copy())

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setOpacity(GRAIN_OPACITY)
        painter.drawTiledPixmap(self.rect(), self._tile)
        painter.end()


class OverlapColumn(QLayout):
    """A top-aligned vertical stack whose gaps may be negative.

    Shadow wrappers and SVG canvases carry transparent room around the face
    they draw, and QVBoxLayout can only add space on top of that. A negative
    gap lets neighbours overlap in that empty room, so the gap between faces
    can be set directly. Items no wider than their maximum sit on the left;
    the rest take the full width.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._gaps: dict[int, int] = {}

    def set_gap(self, index: int, gap: int) -> None:
        """Set the signed space between item index and the one after it."""
        if self._gaps.get(index) != gap:
            self._gaps[index] = gap
            self.invalidate()

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def addLayout(self, layout: QLayout) -> None:
        self.addChildLayout(layout)
        self.addItem(layout)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def _total(self, sizes: list[QSize]) -> QSize:
        height = sum(size.height() for size in sizes)
        height += sum(self._gaps.get(i, 0) for i in range(len(sizes) - 1))
        width = max((size.width() for size in sizes), default=0)
        margins = self.contentsMargins()
        return QSize(
            width + margins.left() + margins.right(),
            max(0, height) + margins.top() + margins.bottom(),
        )

    def sizeHint(self) -> QSize:
        return self._total([item.sizeHint() for item in self._items])

    def minimumSize(self) -> QSize:
        return self._total([item.minimumSize() for item in self._items])

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        area = self.contentsRect()
        y = area.y()
        for index, item in enumerate(self._items):
            hint = item.sizeHint()
            width = min(area.width(), item.maximumSize().width())
            if width < area.width():
                width = min(width, hint.width())
            height = max(item.minimumSize().height(), hint.height())
            item.setGeometry(QRect(area.x(), y, width, height))
            y += height + self._gaps.get(index, 0)


class SvgButton(QPushButton):
    """A button whose whole face is an SVG, with an optional glyph centred.

    The artwork already carries the shape, fill and inset shading, so nothing
    is painted under it and the usual QPushButton chrome is switched off. The
    The widget is sized to the drawing's own aspect ratio so the artwork is
    never skewed.
    """

    def __init__(
        self,
        svg_path: str,
        glyph: str = "",
        glyph_ratio: float = 0.30,
        height: int = 64,
        face_color: str | None = None,
        face_radius: float = 10.0,
        glyph_offset: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        super().__init__()
        self._renderer = QSvgRenderer(svg_path)
        self._glyph = glyph
        self._glyph_ratio = glyph_ratio
        self._face_color = QColor(face_color) if face_color else None
        self._face_radius = face_radius
        self._glyph_offset = glyph_offset
        size = self._renderer.defaultSize()
        self._aspect = size.width() / size.height() if size.height() > 0 else 1.0
        self.setFlat(True)
        self.setAutoDefault(False)
        self.setDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")
        # Fixed to the drawing's own ratio. Letting the width stretch skewed
        # the rounded corners, and heightForWidth does not survive the shadow
        # wrapper, so the size is pinned on both axes instead.
        self.setFixedSize(round(height * self._aspect), height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_width(self, width: int) -> None:
        """Resize to this width, deriving height from the drawing's ratio."""
        width = max(1, width)
        if width == self.width():
            return
        self.setFixedSize(width, max(1, round(width / self._aspect)))

    def set_glyph(self, glyph: str) -> None:
        if glyph != self._glyph:
            self._glyph = glyph
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.40)
        if self._face_color is not None:
            # The skip artwork fills its face with 3% black over whatever is
            # behind it, which on the page background is almost invisible.
            # Lay a solid face under it so the key reads as a raised surface.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._face_color)
            painter.drawRoundedRect(
                QRectF(self.rect()), self._face_radius, self._face_radius
            )
        if self._renderer.isValid():
            self._renderer.render(painter, QRectF(self.rect()))
        if self._glyph:
            font = self.font()
            font.setPointSizeF(max(self.height() * self._glyph_ratio, 6.0))
            painter.setFont(theme.medium_font(font))
            painter.setPen(QColor(theme.TEXT_PRIMARY))
            # The artwork's shape is not always centred in its own canvas, so
            # the glyph is nudged onto the shape's centre rather than the
            # widget's.
            target = self.rect().translated(
                round(self._glyph_offset[0] * self.width()),
                round(self._glyph_offset[1] * self.height()),
            )
            painter.drawText(target, Qt.AlignmentFlag.AlignCenter, self._glyph)
        painter.end()


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
        self.setMinimumWidth(54)
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
        tick_top = top + TICK_INSET
        tick_span = max(bottom - top - 2 * TICK_INSET, 1.0)
        for i in range(TICKS):
            ty = tick_top + tick_span * i / (TICKS - 1)
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
        self._angle = 0.0
        self._spin = QTimer(self)
        self._spin.setInterval(SPIN_INTERVAL_MS)
        self._spin.timeout.connect(self._advance)
        self.setFixedSize(diameter, diameter)

    def set_spinning(self, spinning: bool) -> None:
        """Start or stop the turntable. Stopping keeps the current angle, so
        resuming carries on from where it paused rather than snapping back."""
        if spinning and not self._spin.isActive():
            self._spin.start()
        elif not spinning and self._spin.isActive():
            self._spin.stop()

    def _advance(self) -> None:
        self._angle = (
            self._angle + SPIN_DEGREES_PER_SECOND * SPIN_INTERVAL_MS / 1000.0
        ) % 360.0
        self.update()

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
            # Scale to physical pixels and tag the ratio, so a hi-dpi screen
            # gets the detail instead of a logical-size pixmap stretched up.
            ratio = self.devicePixelRatioF()
            edge = round(self._diameter * ratio)
            scaled = self._pixmap.scaled(
                edge,
                edge,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(ratio)
            x = (scaled.width() / ratio - self._diameter) / 2
            y = (scaled.height() / ratio - self._diameter) / 2
            # Spin about the disc's centre. The clip is a circle, so it is
            # unaffected by the rotation and the edge stays put.
            centre = self._diameter / 2
            painter.save()
            painter.translate(centre, centre)
            painter.rotate(self._angle)
            painter.translate(-centre, -centre)
            painter.drawPixmap(QPointF(-x, -y), scaled)
            painter.restore()
        else:
            painter.fillRect(rect, QColor(theme.DIVIDER))
        painter.setClipping(False)

        ring_d = self._diameter * 0.272  # 20% smaller than the old 0.34
        ring_rect = QRectF(
            (self._diameter - ring_d) / 2, (self._diameter - ring_d) / 2, ring_d, ring_d
        )
        painter.setBrush(QColor("#E5E6E7"))
        pen = QPen(QColor("#A0A1B2"))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.drawEllipse(ring_rect)
        painter.end()
