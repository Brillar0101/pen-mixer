"""Entry point: python -m penmixer.app"""

import sys

from PySide6.QtWidgets import QApplication

from .ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(560, 600)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
