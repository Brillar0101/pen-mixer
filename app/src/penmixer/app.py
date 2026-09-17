"""Entry point: python -m penmixer.app"""

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from . import theme
from .ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    family = theme.load_fonts()
    app.setFont(QFont(family))
    window = MainWindow()
    window.resize(1360, 760)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
