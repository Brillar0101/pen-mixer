"""TCP line reader: consumes the same frame stream over a socket.

Used when the app runs inside Docker, where the container cannot open
/dev/cu.usbmodem* directly. A host-side socat bridge exposes the serial
port as TCP (see scripts/host_bridges.sh) and this reader connects to it.
"""

import socket
import time

from PySide6.QtCore import QThread, Signal

from .frames import parse_line


class TcpReader(QThread):
    frame_received = Signal(object)
    status_changed = Signal(str)
    connected_changed = Signal(bool)

    def __init__(self, host: str, port: int) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        while not self._stop:
            try:
                with socket.create_connection((self._host, self._port), timeout=3.0) as conn:
                    self.connected_changed.emit(True)
                    self.status_changed.emit(f"Pen board connected via bridge {self._host}:{self._port}")
                    conn.settimeout(1.0)
                    buffer = b""
                    while not self._stop:
                        try:
                            chunk = conn.recv(1024)
                        except TimeoutError:
                            continue
                        if not chunk:
                            break
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            frame = parse_line(line.decode("ascii", errors="ignore"))
                            if frame is not None:
                                self.frame_received.emit(frame)
            except OSError:
                self.connected_changed.emit(False)
                self.status_changed.emit("Pen board not detected (bridge unreachable)")
                time.sleep(1.5)
