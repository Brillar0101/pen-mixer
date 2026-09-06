"""Main window: the single source of truth for the whole instrument.

The window owns the audio engine, the touch reader, and the gain state.
Touch drives the sliders; the sliders drive the DSP; nothing else holds
state. Untick "Touch control" to drive the EQ by hand.
"""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import routing
from .audio import AudioEngine, default_input_index, list_devices, rescan_devices
from .bleio import BleReader
from .frames import TouchFrame
from .mapping import BandGains, gains_from_frame, gains_from_frame_signed, smooth
from .serialio import SerialReader, SimulatedReader
from .spectrum import bar_spectrum
from .tcpio import TcpReader
from .viz import SpectrumWidget

SLIDER_SCALE = 10  # slider units per dB
SILENCE_TICKS = 60  # ~2 s of silence at the 33 ms refresh before we hint
GAIN_LIMIT_DB = 12.0
BANDS = ("Bass\n60-250 Hz", "Mid\n250 Hz-2 kHz", "Treble\n2-20 kHz")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pen Mixer EQ")
        self.engine = AudioEngine()
        self.reader: SerialReader | SimulatedReader | TcpReader | BleReader | None = None
        self._touch_gains = BandGains(0.0, 0.0, 0.0)
        self._silent_ticks = 0

        root = QWidget()
        layout = QVBoxLayout(root)

        # Board status banner: always visible, never overwritten by audio messages.
        self.board_label = QLabel()
        self.board_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._set_board_status(False, "Pen board not detected")
        layout.addWidget(self.board_label)

        # Device row
        device_row = QHBoxLayout()
        self.input_box = QComboBox()
        self.output_box = QComboBox()
        self._populate_devices()
        device_row.addWidget(QLabel("Input"))
        device_row.addWidget(self.input_box, 1)
        device_row.addWidget(QLabel("Output"))
        device_row.addWidget(self.output_box, 1)
        self.rescan_button = QPushButton("Rescan")
        self.rescan_button.setToolTip(
            "Re-detect audio devices (use after installing VB-CABLE/BlackHole "
            "or plugging in headphones)"
        )
        self.rescan_button.clicked.connect(self._rescan_devices)
        device_row.addWidget(self.rescan_button)
        layout.addLayout(device_row)

        # Live spectrum
        self.spectrum = SpectrumWidget()
        layout.addWidget(self.spectrum)

        # Sliders
        slider_row = QHBoxLayout()
        self.sliders: list[QSlider] = []
        self.readouts: list[QLabel] = []
        for name in BANDS:
            column = QVBoxLayout()
            readout = QLabel("0.0 dB")
            readout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(int(-GAIN_LIMIT_DB * SLIDER_SCALE), int(GAIN_LIMIT_DB * SLIDER_SCALE))
            slider.setValue(0)
            slider.setMinimumHeight(220)
            slider.valueChanged.connect(self._sliders_changed)
            label = QLabel(name)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(readout)
            column.addWidget(slider, alignment=Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(label)
            slider_row.addLayout(column)
            self.sliders.append(slider)
            self.readouts.append(readout)
        layout.addLayout(slider_row)

        # Controls
        control_row = QHBoxLayout()
        self.start_button = QPushButton("Start audio")
        self.start_button.clicked.connect(self._toggle_audio)
        self.touch_toggle = QCheckBox("Touch control")
        self.touch_toggle.setChecked(True)
        self.source_box = QComboBox()
        self.source_box.addItems(["USB serial (cable)", "Bluetooth (pen board)", "Simulate (no board)"])
        self.source_box.currentIndexChanged.connect(self._restart_reader)
        control_row.addWidget(self.start_button)
        control_row.addWidget(self.touch_toggle)
        control_row.addWidget(QLabel("Source"))
        control_row.addWidget(self.source_box)
        layout.addLayout(control_row)

        # Cross-platform: pick the loopback input and real speakers, start the
        # engine, so the routed music is audible through this computer.
        self.hear_button = QPushButton("Hear music here")
        self.hear_button.setToolTip(
            "Select the loopback input (CABLE Output / BlackHole), select real "
            "speakers, and start the audio so you hear the routed music"
        )
        self.hear_button.clicked.connect(self._hear_music)
        control_row.addWidget(self.hear_button)

        # One-click system routing (SwitchAudioSource): send the Mac's output
        # into BlackHole so the app hears the music; restored on exit.
        self._previous_output: str | None = None
        if routing.available():
            self.route_button = QPushButton("Route system audio here")
            self.route_button.clicked.connect(self._toggle_routing)
            control_row.addWidget(self.route_button)

        # Live pad meters (F1: show the hand input as it moves)
        pad_row = QHBoxLayout()
        self.pad_bars: list[QProgressBar] = []
        for name in ("Pad A0 (bass)", "Pad A1 (treble)"):
            pad_row.addWidget(QLabel(name))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setMaximumHeight(10)
            pad_row.addWidget(bar, 1)
            self.pad_bars.append(bar)
        layout.addLayout(pad_row)

        # Level + status
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        layout.addWidget(self.level_bar)
        self.status = QLabel("stopped")
        layout.addWidget(self.status)

        self.setCentralWidget(root)

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(33)

        self._restart_reader()

    # ---- devices -------------------------------------------------------
    def _populate_devices(self) -> None:
        self.input_box.clear()
        self.output_box.clear()
        for dev in list_devices():
            if dev.inputs >= 2:
                self.input_box.addItem(f"{dev.name}", dev.index)
            if dev.outputs >= 2 and "blackhole" not in dev.name.lower():
                self.output_box.addItem(f"{dev.name}", dev.index)
        preferred = default_input_index()
        if preferred is not None:
            pos = self.input_box.findData(preferred)
            if pos >= 0:
                self.input_box.setCurrentIndex(pos)

    def _rescan_devices(self) -> None:
        was_running = self.engine.running
        if was_running:
            self.engine.stop()
            self.start_button.setText("Start audio")
        rescan_devices()
        self._populate_devices()
        self.status.setText(
            f"devices rescanned: {self.input_box.count()} inputs, "
            f"{self.output_box.count()} outputs"
            + ("; press Start audio again" if was_running else "")
        )

    # ---- readers -------------------------------------------------------
    def _restart_reader(self) -> None:
        if self.reader is not None:
            self.reader.stop()
            self.reader.wait(2000)
        tcp_target = os.environ.get("PENMIXER_SERIAL_TCP", "")
        source = self.source_box.currentText()
        if "Simulate" in source:
            self.reader = SimulatedReader()
        elif "Bluetooth" in source:
            self.reader = BleReader()
        elif tcp_target:
            host, _, port = tcp_target.partition(":")
            self.reader = TcpReader(host or "host.docker.internal", int(port or "7777"))
        else:
            self.reader = SerialReader()
        self.reader.frame_received.connect(self._on_frame)
        self.reader.status_changed.connect(self._on_reader_status)
        self.reader.connected_changed.connect(self._on_board_connected)
        self._board_connected = False
        self._last_board_text = "Pen board not detected"
        self.reader.start()

    def _on_reader_status(self, text: str) -> None:
        self._last_board_text = text
        self._set_board_status(self._board_connected, text)

    def _on_board_connected(self, connected: bool) -> None:
        self._board_connected = connected
        self._set_board_status(connected, self._last_board_text)

    def _set_board_status(self, connected: bool, text: str) -> None:
        simulated = "simulated" in text
        color = "#b58900" if simulated else "#2e8b57" if connected else "#c0392b"
        dot = "\u25cf"
        self.board_label.setText(f'<b style="color:{color}">{dot} {text}</b>')

    def _on_frame(self, frame: TouchFrame) -> None:
        self.pad_bars[0].setValue(int((frame.tilt + 45.0) / 90.0 * 100))
        self.pad_bars[1].setValue(int((frame.roll + 90.0) / 180.0 * 100))
        if not self.touch_toggle.isChecked():
            return
        mapper = (
            gains_from_frame_signed
            if "Bluetooth" in self.source_box.currentText()
            else gains_from_frame
        )
        self._touch_gains = smooth(self._touch_gains, mapper(frame))
        gains = self._touch_gains
        for slider, value in zip(
            self.sliders, (gains.bass_db, gains.mid_db, gains.treble_db)
        ):
            slider.blockSignals(True)
            slider.setValue(int(value * SLIDER_SCALE))
            slider.blockSignals(False)
        self._push_gains()

    # ---- gains ---------------------------------------------------------
    def _sliders_changed(self) -> None:
        self._push_gains()

    def _current_gains(self) -> BandGains:
        values = [s.value() / SLIDER_SCALE for s in self.sliders]
        return BandGains(bass_db=values[0], mid_db=values[1], treble_db=values[2])

    def _push_gains(self) -> None:
        gains = self._current_gains()
        self.engine.set_gains(gains)
        for readout, value in zip(
            self.readouts, (gains.bass_db, gains.mid_db, gains.treble_db)
        ):
            readout.setText(f"{value:+.1f} dB")

    def _hear_music(self) -> None:
        preferred = default_input_index()
        if preferred is not None:
            pos = self.input_box.findData(preferred)
            if pos >= 0:
                self.input_box.setCurrentIndex(pos)
        else:
            self.status.setText(
                "no loopback input found (CABLE Output / BlackHole); "
                "install it, then click Rescan"
            )
            return
        self._select_preferred_output()
        if self.engine.running:
            self.engine.stop()
            self.start_button.setText("Start audio")
        self._toggle_audio()

    # ---- system routing ------------------------------------------------
    def _toggle_routing(self) -> None:
        if self._previous_output is None:
            current = routing.current_output()
            if current and routing.BLACKHOLE_NAME not in current:
                if routing.set_output(routing.BLACKHOLE_NAME):
                    self._previous_output = current
                    self.route_button.setText(f"Restore output to {current}")
                    # Keep the music audible: play it out of the device that
                    # was just displaced, and start the engine right away.
                    self._select_output_by_name(current)
                    if not self.engine.running:
                        self._toggle_audio()
                    self.status.setText(
                        f"system audio flows through this app to {current}"
                    )
                else:
                    self.status.setText("could not switch system output")
            else:
                self._select_preferred_output()
                fallback = self.output_box.currentText()
                self._previous_output = fallback
                self.route_button.setText(f"Restore output to {fallback}")
                if not self.engine.running:
                    self._toggle_audio()
                self.status.setText(
                    f"system audio flows through this app to {fallback}"
                )
        else:
            routing.set_output(self._previous_output)
            self.status.setText(f"system output restored to {self._previous_output}")
            self.route_button.setText("Route system audio here")
            self._previous_output = None

    def _select_preferred_output(self) -> None:
        for hint in ("bose", "airpod", "headphone", "speaker"):
            for i in range(self.output_box.count()):
                if hint in self.output_box.itemText(i).lower():
                    self.output_box.setCurrentIndex(i)
                    return

    def _select_output_by_name(self, name: str) -> None:
        for i in range(self.output_box.count()):
            item = self.output_box.itemText(i)
            if name in item or item in name:
                self.output_box.setCurrentIndex(i)
                return

    def _restore_routing(self) -> None:
        if self._previous_output is not None:
            routing.set_output(self._previous_output)
            self._previous_output = None

    # ---- audio ---------------------------------------------------------
    def _toggle_audio(self) -> None:
        if self.engine.running:
            self.engine.stop()
            self.start_button.setText("Start audio")
            # Hand the system audio back so stopping never means silence.
            if self._previous_output is not None:
                restored = self._previous_output
                self._restore_routing()
                self.route_button.setText("Route system audio here")
                self.status.setText(f"stopped; system output restored to {restored}")
            else:
                self.status.setText("stopped")
            return
        try:
            self.engine.start(
                input_index=self.input_box.currentData(),
                output_index=self.output_box.currentData(),
            )
            self.start_button.setText("Stop audio")
            self.status.setText("audio running")
        except Exception as exc:  # noqa: BLE001 - any start failure is surfaced to the user
            self.status.setText(f"audio failed to start: {exc}")

    def _check_silence(self) -> None:
        if self.engine.output_level < 1e-5:
            self._silent_ticks += 1
        else:
            if self._silent_ticks >= SILENCE_TICKS:
                self.status.setText("audio running")
            self._silent_ticks = 0
        if self._silent_ticks == SILENCE_TICKS:
            self.status.setText(
                "audio running but input is silent: set System Settings -> Sound -> "
                "Output to BlackHole 2ch, then play music"
            )

    def _refresh(self) -> None:
        level = min(int(self.engine.output_level * 300), 100)
        self.level_bar.setValue(level if self.engine.running else 0)
        if self.engine.running:
            window = self.engine.latest_window()
            bars = bar_spectrum(window, self.engine.samplerate)
            self.spectrum.update_levels(bars, window)
            self._check_silence()

    def closeEvent(self, event: object) -> None:
        if self.reader is not None:
            self.reader.stop()
            self.reader.wait(2000)
        self.engine.stop()
        self._restore_routing()
        super().closeEvent(event)
