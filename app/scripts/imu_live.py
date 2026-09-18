"""Live IMU angle viewer: connects to PenMixer-Lexy over BLE and shows
the streamed values as big numbers, updating in real time.

Run with the app's venv python. Close the window to disconnect.
Note: only one program can hold the BLE link, so the main app must not
be connected to the board (set its Source away from Bluetooth) while
this window is open.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QVBoxLayout, QWidget

from penmixer.bleio import BleReader

VALUE_STYLE = "font-size: 42px; font-weight: bold; font-family: Consolas;"
NAME_STYLE = "font-size: 14px; color: #888;"


class Viewer(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pen board IMU, live")
        layout = QVBoxLayout(self)

        self.status = QLabel("starting...")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        grid = QGridLayout()
        layout.addLayout(grid)
        self.values = []
        names = ["Tilt (deg)", "Twist/roll (deg)", "Sway (-1..1)", "Energy (0..1)"]
        for i, name in enumerate(names):
            label = QLabel(name)
            label.setStyleSheet(NAME_STYLE)
            value = QLabel("--")
            value.setStyleSheet(VALUE_STYLE)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(label, i, 0)
            grid.addWidget(value, i, 1)
            self.values.append(value)

        self.reader = BleReader()
        self.reader.frame_received.connect(self.on_frame)
        self.reader.status_changed.connect(self.status.setText)
        self.reader.start()

    def on_frame(self, frame) -> None:
        for widget, number in zip(
            self.values, (frame.tilt, frame.roll, frame.sway, frame.energy)
        ):
            widget.setText(f"{number:+8.2f}")

    def closeEvent(self, event) -> None:
        self.reader.stop()
        self.reader.wait(3000)
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = Viewer()
    window.resize(420, 320)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
