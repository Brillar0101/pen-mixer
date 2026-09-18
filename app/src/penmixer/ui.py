"""Main window: the single source of truth for the whole instrument.

The window owns the audio engine, the motion reader, and the gain state.
Pen motion drives the sliders; the sliders drive the DSP; nothing else
holds state. Untick "Pen control" (in Settings) to drive the EQ by hand.

The dashboard shows the dot-grid spectrum, a session card (device I/O,
volume, engine start/stop, Spotify transport), a track card, and the
equalizer. Board status, Bluetooth, audio routing, Rescan, and the raw
motion meters live behind the gear icon in the top bar.
"""

import math
import os
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import routing, spotifyio, sysvol, theme
from .audio import (
    AudioEngine,
    default_input_index,
    is_virtual_sink,
    list_devices,
    preferred_hostapi,
    preferred_output_index,
    rescan_devices,
)
from .bleio import BleReader, BleScanThread
from .frames import TouchFrame
from .mapping import BandGains, gains_from_frame, smooth
from .serialio import SerialReader, SimulatedReader
from .spectrum import bar_spectrum
from .spotifyio import SpotifyPoller
from .tcpio import TcpReader
from .viz import BAR_COUNT, SpectrumWidget
from .widgets import EqSlider, TrackArt

SLIDER_SCALE = 10  # slider units per dB
SILENCE_TICKS = 60  # ~2 s of silence at the 33 ms refresh before we hint
GAIN_LIMIT_DB = 12.0
EQ_BANDS = (("60-250 Hz", "Bass"), ("250 Hz-2 kHz", "Mid"), ("2-20 kHz", "Treble"))

SLIDER_QSS = f"""
QSlider::groove:horizontal {{
    height: 6px;
    background: {theme.DIVIDER};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {theme.TEXT_PRIMARY};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: {theme.TEXT_PRIMARY};
}}
"""

TRANSPORT_BUTTON_QSS = f"""
QPushButton {{
    background: {theme.PAGE_BG};
    color: {theme.TEXT_PRIMARY};
    border: 1px solid {theme.DIVIDER};
    border-radius: 12px;
    outline: none;
}}
QPushButton:focus {{
    background: {theme.PAGE_BG};
    border: 1px solid {theme.DIVIDER};
    outline: none;
}}
QPushButton:pressed {{
    background: {theme.DIVIDER};
}}
QPushButton:disabled {{
    color: {theme.TEXT_MUTED};
}}
"""


def _format_mmss(ms: int) -> str:
    total_seconds = max(ms, 0) // 1000
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def _muted_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
    return label


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Write FM")
        self.engine = AudioEngine()
        self.reader: SerialReader | SimulatedReader | TcpReader | BleReader | None = None
        self._touch_gains = BandGains(0.0, 0.0, 0.0)
        self._silent_ticks = 0
        self._spotify_progress_ms = 0
        self._spotify_duration_ms = 0
        self._spotify_has_track = False

        self.spotify_poller: SpotifyPoller | None = (
            SpotifyPoller() if spotifyio.available() else None
        )

        central = QWidget()
        central.setObjectName("dashboard")
        central.setStyleSheet(f"#dashboard {{ background: {theme.PAGE_BG}; }}")
        root = QVBoxLayout(central)
        # Margins/spacing have to clear each card's own shadow bleed (offset
        # + blur, ~24px on the dark bottom-right side) or the next card/the
        # window edge cuts the shadow off instead of letting it fade out.
        root.setContentsMargins(32, 28, 40, 40)
        root.setSpacing(36)

        self._build_settings_dialog()
        root.addWidget(self._build_top_bar())

        self.spectrum = SpectrumWidget()
        root.addWidget(self.spectrum)

        row = QHBoxLayout()
        row.setSpacing(36)
        row.addWidget(theme.with_dual_shadow(self._build_session_card()), 3)
        row.addWidget(theme.with_dual_shadow(self._build_track_card()), 4)
        row.addWidget(theme.with_dual_shadow(self._build_equalizer_card()), 4)
        root.addLayout(row)

        self.setCentralWidget(central)

        if self.spotify_poller is not None:
            self.spotify_poller.track_changed.connect(self._on_spotify_track)
            self.spotify_poller.art_changed.connect(self._on_spotify_art)
            self.spotify_poller.status_changed.connect(self._on_spotify_status)
            self.spotify_poller.start()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(16)

        self._sys_vol_last: tuple[float, bool] | None = None
        self._sysvol_timer = QTimer(self)
        self._sysvol_timer.timeout.connect(self._sync_system_volume)
        self._sysvol_timer.start(300)

        # Start hearing music without a click: once the window is up, pick
        # the loopback input and real speakers and start the engine, exactly
        # what the "Hear music here" button does.
        QTimer.singleShot(300, self._hear_music)

        self._restart_reader()

    # ---- dashboard construction -----------------------------------------
    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setStyleSheet(f"#topbar {{ background: {theme.BAR_BG}; border-radius: 26px; }}")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 14, 28, 14)

        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"color: {theme.BAR_TEXT};")
        layout.addWidget(self.clock_label, 1)

        title = QLabel("WRITE FM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(13)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {theme.BAR_TITLE};")
        layout.addWidget(title, 1)

        right = QHBoxLayout()
        right.addStretch(1)
        version = QLabel("VER 2026")
        version.setStyleSheet(f"color: {theme.BAR_TEXT};")
        right.addWidget(version)

        self.settings_button = QPushButton("S")
        self.settings_button.setFixedSize(26, 26)
        self.settings_button.setToolTip("Board status, Bluetooth, routing, motion meters")
        self.settings_button.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {theme.BAR_TEXT}; "
            f"border: 1px solid {theme.BAR_TEXT}; border-radius: 13px; }}"
        )
        self.settings_button.clicked.connect(self._open_settings)
        right.addWidget(self.settings_button)

        self.help_button = QPushButton("?")
        self.help_button.setFixedSize(26, 26)
        self.help_button.setStyleSheet(
            f"QPushButton {{ background: {theme.BLUE}; color: white; "
            f"border-radius: 13px; font-weight: 700; }}"
        )
        self.help_button.clicked.connect(self._show_help)
        right.addWidget(self.help_button)

        layout.addLayout(right, 1)
        return bar

    def _build_session_card(self) -> QWidget:
        card = theme.Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(26, 24, 26, 26)
        layout.setSpacing(14)

        status_row = QHBoxLayout()
        self.session_dot = QLabel()
        self.session_dot.setFixedSize(10, 10)
        status_row.addWidget(self.session_dot)
        self.session_status_label = QLabel("Stopped")
        status_font = self.session_status_label.font()
        status_font.setBold(True)
        self.session_status_label.setFont(status_font)
        self.session_status_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        status_row.addWidget(self.session_status_label)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {theme.DIVIDER}; border: none;")
        layout.addWidget(divider)

        self.input_box = QComboBox()
        self.output_box = QComboBox()
        for box in (self.input_box, self.output_box):
            # Long labels ("CABLE Output ... [Windows WASAPI]") must ellipsize
            # instead of forcing the window wider than a laptop screen.
            box.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            box.setMinimumContentsLength(16)
        self.input_box.currentIndexChanged.connect(self._on_input_changed)
        # Device names ("CABLE Output (VB-Audio Virtual...") are long enough
        # to force the card wide if the combo sizes to fit them; cap the
        # visible width to a character count and let Qt elide the rest.
        for combo in (self.input_box, self.output_box):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
        layout.addWidget(_muted_label("INPUT"))
        layout.addWidget(self.input_box)
        layout.addWidget(_muted_label("OUTPUT"))
        layout.addWidget(self.output_box)
        self._populate_devices()

        vol_head = QHBoxLayout()
        vol_head.addWidget(_muted_label("VOLUME"))
        vol_head.addStretch(1)
        self.volume_readout = QLabel("+9.0 dB")
        self.volume_readout.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        vol_head.addWidget(self.volume_readout)
        layout.addLayout(vol_head)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        # -60 dB to +24 dB in tenths; the bottom of the fader is a true mute.
        # Past unity (+9) the gain eats the EQ boost headroom and can clip
        # loud tracks.
        self.volume_slider.setRange(-600, 240)
        self.volume_slider.setValue(90)
        self.volume_slider.valueChanged.connect(self._volume_changed)
        self.volume_slider.setStyleSheet(SLIDER_QSS)
        layout.addWidget(self.volume_slider)

        layout.addStretch(1)

        # Spotify transport: a big orange pause/play pill plus back/skip below,
        # matching the reference exactly. The EQ engine's own start/stop lives
        # in Settings now instead of duplicating a second "play" control here.
        self.spotify_play_pause_button = QPushButton()
        self.spotify_play_pause_button.setFixedHeight(54)
        self.spotify_play_pause_button.setStyleSheet(
            f"QPushButton {{ background: {theme.ORANGE}; color: {theme.TEXT_PRIMARY}; "
            f"border-radius: 27px; font-weight: 700; font-size: 16px; border: none; "
            f"outline: none; }}"
            f"QPushButton:focus {{ background: {theme.ORANGE}; border: none; outline: none; }}"
            f"QPushButton:disabled {{ background: {theme.DIVIDER}; color: {theme.TEXT_MUTED}; }}"
        )
        self.spotify_play_pause_button.setAutoDefault(False)
        self.spotify_play_pause_button.setDefault(False)
        layout.addWidget(self.spotify_play_pause_button)

        transport_row = QHBoxLayout()
        transport_row.setSpacing(10)
        self.prev_button = QPushButton("|◀")
        self.next_button = QPushButton("▶|")
        for button in (self.prev_button, self.next_button):
            button.setFixedHeight(44)
            button.setStyleSheet(TRANSPORT_BUTTON_QSS)
            # Without this, Windows paints a native blue "default button"
            # highlight behind whichever of these gets autoDefault first.
            button.setAutoDefault(False)
            button.setDefault(False)
            transport_row.addWidget(button)
        layout.addLayout(transport_row)
        if self.spotify_poller is not None:
            self.prev_button.clicked.connect(self.spotify_poller.previous_track)
            self.spotify_play_pause_button.clicked.connect(self.spotify_poller.play_pause)
            self.next_button.clicked.connect(self.spotify_poller.next_track)
        else:
            for button in (self.prev_button, self.spotify_play_pause_button, self.next_button):
                button.setEnabled(False)

        self._sync_session_ui()
        card.setMaximumWidth(400)
        return card

    def _build_track_card(self) -> QWidget:
        card = theme.Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(26, 24, 26, 26)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header = QLabel("TRACK")
        header_font = header.font()
        header_font.setBold(True)
        header_font.setPointSize(12)
        header.setFont(header_font)
        header.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        header_row.addWidget(header)
        header_row.addStretch(1)
        header_row.addWidget(_muted_label("+"))
        layout.addLayout(header_row)

        self.track_art = TrackArt()
        art_row = QHBoxLayout()
        art_row.addStretch(1)
        art_row.addWidget(self.track_art)
        art_row.addStretch(1)
        layout.addLayout(art_row)

        self.track_artist_label = QLabel()
        self.track_artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track_artist_label.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        layout.addWidget(self.track_artist_label)

        self.track_title_label = QLabel(
            "Not connected" if self.spotify_poller is None else "Connecting..."
        )
        self.track_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track_title_label.setWordWrap(True)
        title_font = self.track_title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(13)
        self.track_title_label.setFont(title_font)
        self.track_title_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        layout.addWidget(self.track_title_label)

        self.track_progress = QProgressBar()
        self.track_progress.setRange(0, 1000)
        self.track_progress.setTextVisible(False)
        self.track_progress.setFixedHeight(4)
        self.track_progress.setStyleSheet(
            f"QProgressBar {{ background: {theme.DIVIDER}; border: none; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {theme.TEXT_PRIMARY}; border-radius: 2px; }}"
        )
        layout.addWidget(self.track_progress)

        self.track_time_label = QLabel("0:00 / 0:00")
        self.track_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track_time_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self.track_time_label)

        layout.addStretch(1)

        source_row = QHBoxLayout()
        source_row.addWidget(_muted_label("PLAYING FROM"))
        spotify_tag = QLabel("Spotify")
        spotify_tag.setStyleSheet(f"color: {theme.GREEN}; font-weight: 700;")
        source_row.addWidget(spotify_tag)
        source_row.addStretch(1)
        layout.addLayout(source_row)

        return card

    def _build_equalizer_card(self) -> QWidget:
        card = theme.Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(26, 24, 26, 26)
        layout.setSpacing(16)

        header = QLabel("EQUALIZER")
        header_font = header.font()
        header_font.setBold(True)
        header_font.setPointSize(12)
        header.setFont(header_font)
        header.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        layout.addWidget(header)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(40)
        self.sliders: list[EqSlider] = []
        for freq_text, band_name in EQ_BANDS:
            column = QVBoxLayout()
            slider = EqSlider()
            slider.setRange(int(-GAIN_LIMIT_DB * SLIDER_SCALE), int(GAIN_LIMIT_DB * SLIDER_SCALE))
            slider.setValue(0)
            slider.setMinimumHeight(220)
            slider.valueChanged.connect(self._sliders_changed)
            column.addWidget(slider, alignment=Qt.AlignmentFlag.AlignHCenter)
            freq_label = QLabel(freq_text)
            freq_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            freq_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10px;")
            column.addWidget(freq_label)
            name_label = QLabel(band_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            name_font = name_label.font()
            name_font.setBold(True)
            name_label.setFont(name_font)
            name_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
            column.addWidget(name_label)
            slider_row.addLayout(column)
            self.sliders.append(slider)
        layout.addLayout(slider_row)
        layout.addStretch(1)
        return card

    def _build_settings_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        layout = QVBoxLayout(dialog)

        self.board_label = QLabel()
        self.board_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._set_board_status(False, "Pen board not detected")
        layout.addWidget(self.board_label)

        source_row = QHBoxLayout()
        self.touch_toggle = QCheckBox("Pen control")
        self.touch_toggle.setChecked(True)
        self.source_box = QComboBox()
        self.source_box.addItems(
            ["USB serial (cable)", "Bluetooth (pen board)", "Simulate (no board)"]
        )
        self.source_box.currentIndexChanged.connect(self._restart_reader)
        source_row.addWidget(self.touch_toggle)
        source_row.addWidget(QLabel("Source"))
        source_row.addWidget(self.source_box)
        self.scan_bt_button = QPushButton("Scan Bluetooth")
        self.scan_bt_button.setToolTip(
            "List every Bluetooth device in range and connect to the one you pick"
        )
        self.scan_bt_button.clicked.connect(self._scan_bluetooth)
        source_row.addWidget(self.scan_bt_button)
        layout.addLayout(source_row)

        routing_row = QHBoxLayout()
        self.audio_toggle_button = QPushButton("Start audio")
        self.audio_toggle_button.setToolTip("Start/stop the pen-controlled EQ engine")
        self.audio_toggle_button.clicked.connect(self._toggle_audio)
        routing_row.addWidget(self.audio_toggle_button)
        self.hear_button = QPushButton("Hear music here")
        self.hear_button.setToolTip(
            "Select the loopback input (CABLE Output / BlackHole), select real "
            "speakers, and start the audio so you hear the routed music"
        )
        self.hear_button.clicked.connect(self._hear_music)
        routing_row.addWidget(self.hear_button)
        self._previous_output: str | None = None
        if routing.available():
            self.route_button = QPushButton("Route system audio here")
            self.route_button.clicked.connect(self._toggle_routing)
            routing_row.addWidget(self.route_button)
        self.rescan_button = QPushButton("Rescan")
        self.rescan_button.setToolTip(
            "Re-detect audio devices (use after installing VB-CABLE/BlackHole "
            "or plugging in headphones)"
        )
        self.rescan_button.clicked.connect(self._rescan_devices)
        routing_row.addWidget(self.rescan_button)
        layout.addLayout(routing_row)

        pad_row = QHBoxLayout()
        self.pad_bars: list[QProgressBar] = []
        for name in ("Tilt (bass)", "Sway (mid)", "Twist (treble)"):
            pad_row.addWidget(QLabel(name))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setMaximumHeight(10)
            pad_row.addWidget(bar, 1)
            self.pad_bars.append(bar)
        layout.addLayout(pad_row)

        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        layout.addWidget(self.level_bar)

        self.status = QLabel("stopped")
        layout.addWidget(self.status)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        self._settings_dialog = dialog

    def _open_settings(self) -> None:
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "Pen Mixer",
            "Move the pen to shape a live 3-band EQ over your system audio.\n\n"
            "Board status, Bluetooth, audio routing, Rescan, and the raw "
            "motion meters live behind the gear icon.",
        )

    def _update_clock(self) -> None:
        now = datetime.now().astimezone()
        text = f"{now.strftime('%b')} {now.day}, {now.year}   "
        hour = now.hour % 12 or 12
        ampm = "AM" if now.hour < 12 else "PM"
        text += f"{hour}:{now.minute:02d} {ampm}"
        tz = now.strftime("%Z")
        if tz:
            text += f" {tz}"
        self.clock_label.setText(text)

    # ---- devices -------------------------------------------------------
    def _populate_devices(self) -> None:
        self.input_box.blockSignals(True)
        self.output_box.blockSignals(True)
        self.input_box.clear()
        self.output_box.clear()
        api = preferred_hostapi()
        for dev in list_devices():
            # Show each endpoint once, on the host API everything runs on,
            # instead of the four-per-device list Windows enumerates.
            if api is not None and dev.hostapi != api:
                continue
            if dev.inputs >= 2:
                self.input_box.addItem(dev.name, dev.index)
            if dev.outputs >= 2 and not is_virtual_sink(dev.name):
                self.output_box.addItem(dev.name, dev.index)
        preferred = default_input_index()
        if preferred is not None:
            pos = self.input_box.findData(preferred)
            if pos >= 0:
                self.input_box.setCurrentIndex(pos)
        self.input_box.blockSignals(False)
        self.output_box.blockSignals(False)
        self._select_preferred_output()

    def _on_input_changed(self) -> None:
        """Keep the output on the input's host API, or the stream won't open."""
        devices = list_devices()
        in_index = self.input_box.currentData()
        out_index = self.output_box.currentData()
        if in_index is None or out_index is None:
            return
        if devices[in_index].hostapi == devices[out_index].hostapi:
            return
        self._select_preferred_output()

    def _rescan_devices(self) -> None:
        was_running = self.engine.running
        if was_running:
            self.engine.stop()
            self._sync_session_ui()
        rescan_devices()
        self._populate_devices()
        self.status.setText(
            f"devices rescanned: {self.input_box.count()} inputs, "
            f"{self.output_box.count()} outputs"
            + ("; press Play again" if was_running else "")
        )

    # ---- bluetooth scan ------------------------------------------------
    def _scan_bluetooth(self) -> None:
        self.scan_bt_button.setEnabled(False)
        self.scan_bt_button.setText("Scanning...")
        self._scan_thread = BleScanThread()
        self._scan_thread.devices_found.connect(self._show_scan_results)
        self._scan_thread.scan_failed.connect(self._scan_failed)
        self._scan_thread.start()

    def _scan_failed(self, message: str) -> None:
        self.scan_bt_button.setEnabled(True)
        self.scan_bt_button.setText("Scan Bluetooth")
        self.status.setText(f"Bluetooth scan failed: {message}")

    def _show_scan_results(self, devices: list) -> None:
        self.scan_bt_button.setEnabled(True)
        self.scan_bt_button.setText("Scan Bluetooth")
        dialog = QDialog(self)
        dialog.setWindowTitle("Bluetooth devices in range")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{len(devices)} devices found. Pick one and Connect:"))
        listing = QListWidget()
        pen_row = -1
        for i, (name, address) in enumerate(sorted(devices, key=lambda d: d[0].lower())):
            listing.addItem(f"{name}  [{address}]")
            listing.item(i).setData(Qt.ItemDataRole.UserRole, address)
            if "penmixer" in name.lower():
                pen_row = i
        if pen_row >= 0:
            listing.setCurrentRow(pen_row)
        elif devices:
            listing.setCurrentRow(0)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Connect")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        listing.itemDoubleClicked.connect(lambda _: dialog.accept())
        if dialog.exec() == QDialog.DialogCode.Accepted and listing.currentItem():
            address = listing.currentItem().data(Qt.ItemDataRole.UserRole)
            self._ble_address = address
            pos = self.source_box.findText("Bluetooth (pen board)")
            if self.source_box.currentIndex() == pos:
                self._restart_reader()
            else:
                self.source_box.setCurrentIndex(pos)  # triggers restart
            self.status.setText(f"connecting to {listing.currentItem().text()}")

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
            self.reader = BleReader(address=getattr(self, "_ble_address", None))
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
        dot = "●"
        self.board_label.setText(f'<b style="color:{color}">{dot} {text}</b>')

    def _on_frame(self, frame: TouchFrame) -> None:
        self.pad_bars[0].setValue(int((frame.tilt + 45.0) / 90.0 * 100))
        self.pad_bars[1].setValue(int((frame.sway + 1.0) / 2.0 * 100))
        self.pad_bars[2].setValue(int((frame.roll + 90.0) / 180.0 * 100))
        if not self.touch_toggle.isChecked():
            return
        self._touch_gains = smooth(self._touch_gains, gains_from_frame(frame))
        gains = self._touch_gains
        for slider, value in zip(
            self.sliders, (gains.bass_db, gains.mid_db, gains.treble_db)
        ):
            slider.blockSignals(True)
            slider.setValue(int(value * SLIDER_SCALE))
            slider.blockSignals(False)
        self._push_gains()

    # ---- spotify ---------------------------------------------------------
    def _on_spotify_track(
        self, title: str, artist: str, is_playing: bool, progress_ms: int, duration_ms: int
    ) -> None:
        self.spotify_play_pause_button.setText("||" if is_playing else "▶")
        if not title:
            self._spotify_has_track = False
            self.track_artist_label.setText("")
            self.track_title_label.setText("Nothing playing")
            self.track_progress.setValue(0)
            self.track_time_label.setText("0:00 / 0:00")
            return
        self._spotify_has_track = True
        self.track_artist_label.setText(artist)
        self.track_title_label.setText(title)
        self._spotify_progress_ms = progress_ms
        self._spotify_duration_ms = duration_ms
        if duration_ms > 0:
            self.track_progress.setValue(int(min(progress_ms / duration_ms, 1.0) * 1000))
        else:
            self.track_progress.setValue(0)
        self.track_time_label.setText(f"{_format_mmss(progress_ms)} / {_format_mmss(duration_ms)}")

    def _on_spotify_art(self, data: bytes) -> None:
        self.track_art.set_image(data)

    def _on_spotify_status(self, text: str) -> None:
        self.status.setText(text)
        if not self._spotify_has_track:
            self.track_title_label.setText(text)

    # ---- gains ---------------------------------------------------------
    def _sliders_changed(self) -> None:
        self._push_gains()

    def _current_gains(self) -> BandGains:
        values = [s.value() / SLIDER_SCALE for s in self.sliders]
        return BandGains(bass_db=values[0], mid_db=values[1], treble_db=values[2])

    def _push_gains(self) -> None:
        gains = self._current_gains()
        self.engine.set_gains(gains)

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
            self._sync_session_ui()
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
        index = preferred_output_index(self.input_box.currentData())
        if index is None:
            return
        pos = self.output_box.findData(index)
        if pos >= 0:
            self.output_box.setCurrentIndex(pos)

    def _select_output_by_name(self, name: str) -> None:
        """Pick the named output, preferring the input's host API."""
        devices = list_devices()
        in_index = self.input_box.currentData()
        api = devices[in_index].hostapi if in_index is not None else None
        fallback = None
        for dev in devices:
            if dev.outputs < 2:
                continue
            if name not in dev.name and dev.name not in name:
                continue
            if api is not None and dev.hostapi == api:
                fallback = dev.index
                break
            if fallback is None:
                fallback = dev.index
        if fallback is None:
            return
        pos = self.output_box.findData(fallback)
        if pos >= 0:
            self.output_box.setCurrentIndex(pos)

    def _restore_routing(self) -> None:
        if self._previous_output is not None:
            routing.set_output(self._previous_output)
            self._previous_output = None

    # ---- audio ---------------------------------------------------------
    def _sync_session_ui(self) -> None:
        running = self.engine.running
        self.audio_toggle_button.setText("Stop audio" if running else "Start audio")
        color = theme.GREEN if running else theme.TEXT_MUTED
        self.session_dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        self.session_status_label.setText("Playing" if running else "Stopped")

    def _toggle_audio(self) -> None:
        if self.engine.running:
            self.engine.stop()
            self._sync_session_ui()
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
            self._sync_session_ui()
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

    def _sync_system_volume(self) -> None:
        state = sysvol.get_volume()
        if state is None:
            self._sysvol_timer.stop()  # not available on this machine
            return
        if state == self._sys_vol_last:
            return
        first = self._sys_vol_last is None
        self._sys_vol_last = state
        scalar, muted = state
        if muted or scalar <= 0.001:
            self.volume_slider.setValue(self.volume_slider.minimum())
            return
        # Full system volume lands on the slider's own maximum, so computer
        # max and app max are the same thing; lower volumes scale down from
        # there. Past +9 the gain eats the EQ boost headroom, so loud tracks
        # at full volume can hit the clip.
        db = 20.0 * math.log10(scalar) + self.volume_slider.maximum() / 10.0
        value = max(self.volume_slider.minimum(), min(self.volume_slider.maximum(), int(db * 10)))
        if first and value == self.volume_slider.value():
            return
        self.volume_slider.setValue(value)

    def _volume_changed(self, value: int) -> None:
        if value <= self.volume_slider.minimum():
            self.engine.set_makeup_db(-999.0)  # gain of ~0: a true mute
            self.volume_readout.setText("muted")
            return
        db = value / 10.0
        self.engine.set_makeup_db(db)
        self.volume_readout.setText(f"{db:+.1f} dB")

    def _refresh(self) -> None:
        level = min(int(self.engine.output_level * 300), 100)
        self.level_bar.setValue(level if self.engine.running else 0)
        if self.engine.running:
            window = self.engine.latest_window()
            bars = bar_spectrum(window, self.engine.samplerate, bars=BAR_COUNT)
            self.spectrum.update_levels(bars)
            self._check_silence()

    def closeEvent(self, event: object) -> None:
        if self.reader is not None:
            self.reader.stop()
            self.reader.wait(2000)
        if self.spotify_poller is not None:
            self.spotify_poller.stop()
            self.spotify_poller.wait(2000)
        self.engine.stop()
        self._restore_routing()
        super().closeEvent(event)
