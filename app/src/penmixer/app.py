"""Entry point: python -m penmixer.app"""

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from . import theme
from .ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    family = theme.load_fonts()
    font = QFont(family)
    # -3%: the mono face sets wide by default and the dashboard reads tighter.
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 97.0)
    app.setFont(font)
    window = MainWindow()
    # Fit the work area rather than trusting a fixed size: the layout's own
    # size hint had been opening the window taller than the screen, which put
    # the bottom row under the taskbar.
    available = app.primaryScreen().availableGeometry()
    window.resize(
        min(1360, available.width() - 40),
        min(900, available.height() - 40),
    )
    window.show()
    # availableGeometry covers the whole frame, but resize() sets the client
    # area, so the title bar and borders have to come out of the budget or
    # the window lands taller than the work area.
    frame_extra = window.frameGeometry().height() - window.height()
    max_client = available.height() - frame_extra
    if window.height() > max_client:
        window.resize(window.width(), max_client)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
