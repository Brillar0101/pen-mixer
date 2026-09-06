"""Serial reader thread for the pen board firmware.

Auto-discovers the XIAO's USB CDC port, reconnects if the board is
unplugged, and emits parsed TouchFrames as Qt signals.
"""

import time

import serial
from PySide6.QtCore import QThread, Signal
from serial.tools import list_ports

from .frames import TouchFrame, parse_line

BAUD = 115200
PORT_HINTS = ("usbmodem", "usbserial", "ttyACM")


def find_port() -> str | None:
    for port in list_ports.comports():
        if any(hint in port.device for hint in PORT_HINTS):
            return port.device
        # Windows names ports COM3-style; accept any COM port that reports a
        # USB vendor id (a real attached device, not a legacy phantom port).
        if port.device.upper().startswith("COM") and port.vid is not None:
            return port.device
    return None


class SerialReader(QThread):
    frame_received = Signal(object)  # TouchFrame
    status_changed = Signal(str)
    connected_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        while not self._stop:
            port = find_port()
            if port is None:
                self.connected_changed.emit(False)
                self.status_changed.emit("Pen board not detected")
                time.sleep(1.0)
                continue
            try:
                with serial.Serial(port, BAUD, timeout=1.0) as conn:
                    self.connected_changed.emit(True)
                    self.status_changed.emit(f"Pen board connected on {port}")
                    while not self._stop:
                        raw = conn.readline().decode("ascii", errors="ignore")
                        frame = parse_line(raw)
                        if frame is not None:
                            self.frame_received.emit(frame)
            except (serial.SerialException, OSError):
                self.connected_changed.emit(False)
                self.status_changed.emit("Pen board not detected (disconnected)")
                time.sleep(1.0)


class SimulatedReader(QThread):
    """Hardware-free stand-in: sweeps the pads so the demo runs untethered."""

    frame_received = Signal(object)
    status_changed = Signal(str)
    connected_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        import math

        self.connected_changed.emit(True)
        self.status_changed.emit("simulated input (no board)")
        t = 0.0
        while not self._stop:
            d0 = max(0.0, math.sin(t * 0.9))          # slow bass strokes
            d1 = max(0.0, math.sin(t * 0.53 + 1.7))   # offset treble strokes
            frame = TouchFrame(
                tilt=-45.0 + d0 * 90.0,
                roll=-90.0 + d1 * 180.0,
                energy=abs(math.cos(t)) * 0.5,
            )
            self.frame_received.emit(frame)
            t += 0.03
            time.sleep(0.03)
