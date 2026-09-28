"""Main window: the single source of truth for the whole instrument.

The window owns the audio engine, the motion reader, and the gain state.
Pen motion drives the sliders; the sliders drive the DSP; nothing else
holds state. Untick "Pen control" (in Settings) to drive the EQ by hand.

The dashboard shows the dot-grid spectrum, a session card (device I/O,
volume, engine start/stop, Spotify transport), a track card, and the
equalizer. Board status, Bluetooth, audio routing, Rescan, and the raw
motion meters live behind the gear icon in the top bar.
"""

import os
import time
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

from . import routing, spotifyio, theme
from .audio import (
    AudioEngine,
    default_input_index,
    hostapi_names,
    hostapi_rank,
    list_devices,
    rescan_devices,
)
from .bleio import BleReader, BleScanThread
from .frames import TouchFrame
from .mapping import BandGains, gains_from_frame, smooth
from .serialio import SerialReader, SimulatedReader
from .spectrum import bar_spectrum
from .spotifyio import SpotifyPoller
from .tcpio import TcpReader
from .viz import SpectrumWidget
from .widgets import EqSlider, GrainOverlay, OverlapColumn, SvgButton, TrackArt, svg_pixmap

SLIDER_SCALE = 10  # slider units per dB
TRACK_HEADER_HEIGHT = 32  # rendered height of the TRACK lettering
EQ_HEADER_HEIGHT = 28
BUTTON_DARK_OFFSET = (3, 3)
BUTTON_DARK_BLUR = 6
BUTTON_LIGHT_OFFSET = (-3, -2)
BUTTON_LIGHT_BLUR = 5
PLAY_BUTTON_HEIGHT = 88
PLAY_BUTTON_FRACTION = 0.9  # a little narrower than the column allows
# play-btn.svg draws its pill inset inside a 344x138 canvas, centred at
# (167.8, 62.8) rather than (172, 69), so the glyph needs this nudge to
# sit in the middle of the pill instead of the middle of the widget.
PLAY_GLYPH_OFFSET = (-0.012, -0.045)
# Tighter than the buttons': the wrapper reserves offset+blur as padding,
# and three sliders' worth of that is what pushed the window off-screen.
SLIDER_DARK_OFFSET = (3, 3)
SLIDER_DARK_BLUR = 6
SLIDER_LIGHT_OFFSET = (-3, -2)
SLIDER_LIGHT_BLUR = 5
SKIP_BUTTON_HEIGHT = 62
SKIP_MAX_WIDTH = 138  # keeps the skips from eating the pill's height gain
CARD_ROW_MARGIN_FRACTION = 0.12  # side inset of the three cards
# play-btn.svg leaves transparent room around its pill: 17.3 of 138 above
# it and 29.6 below. The gaps are measured between drawn faces, not canvases.
PLAY_PILL_TOP_FRACTION = 17.3 / 138.0
PLAY_PILL_BOTTOM_ROOM_FRACTION = (138.0 - 17.3 - 91.0) / 138.0
TRANSPORT_FACE_GAP = 10  # visible gap between session card, play and skips
TRANSPORT_SPACING = 6
EQ_SLIDER_HEIGHT = 330  # elongated track, per the reference
CARD_STRETCHES = (36, 22, 42)  # session / track / equalizer
# Widened from 20 to make room for the 2x play pill: the pill cannot be
# broader than the column that holds it.
EQ_LABEL_SPACING = 2  # gap between bar, Hz range, band name and gesture
CARD_MAX_WIDTH = 400
SHADOW_WIDTH_COST = 32  # left+right padding the dual-shadow wrappers add
MOTION_DEADBAND_DEG = 0.6  # below this the pen counts as held still
MOTION_DEADBAND_SWAY = 0.012
TRACK_ART_DIAMETER = 270  # 1.8x
SPOTIFY_LOGO_HEIGHT = 20
SILENCE_TICKS = 60  # ~2 s of silence at the 33 ms refresh before we hint
GAIN_LIMIT_DB = 12.0
EQ_BANDS = (
    ("60-250 Hz", "Bass", "tilt"),
    ("250 Hz-2 kHz", "Mid", "sway"),
    ("2-20 kHz", "Treble", "twist"),
)

CALIBRATE_BUTTON_QSS = f"""
QPushButton {{
    background: {theme.PAGE_BG};
    color: {theme.TEXT_PRIMARY};
    border: 1px solid {theme.DIVIDER};
    border-radius: 8px;
    font-size: 11px;
    outline: none;
}}
QPushButton:hover {{ background: {theme.CARD_BG}; }}
QPushButton:pressed {{ background: {theme.DIVIDER}; }}
"""

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
        self._last_motion: TouchFrame | None = None
        self._latest_frame: TouchFrame | None = None
        self._motion_origin: TouchFrame | None = None
        self._silent_ticks = 0
        self._spotify_progress_ms = 0
        self._spotify_duration_ms = 0
        self._spotify_playing = False
        self._spotify_progress_ts = time.monotonic()
        self._spotify_has_track = False

        self.spotify_poller: SpotifyPoller | None = (
            SpotifyPoller() if spotifyio.available() else None
        )

        central = QWidget()
        central.setObjectName("dashboard")
        central.setStyleSheet(f"#dashboard {{ background: {theme.PAGE_BG}; }}")
        root = QVBoxLayout(central)
        # Each shadow wrapper now carries its own padding for the bleed, so
        # these only need to keep the outermost cards off the window edge.
        # Doubling up here is what pushed the window past the screen height.
        root.setContentsMargins(10, 10, 12, 10)
        root.setSpacing(10)

        self._build_settings_dialog()
        root.addWidget(self._build_top_bar())

        self.spectrum = SpectrumWidget()
        # 1 : 2 against the card row, so the visualiser claims a third of
        # whatever vertical space is going spare once the cards have their
        # minimums. On a short work area the cards win and it gets less.
        root.addWidget(self.spectrum, 1)
        self._card_row_margin_fraction = CARD_ROW_MARGIN_FRACTION

        row = QHBoxLayout()
        row.setSpacing(4)  # the wrappers already leave ~26px between cards
        self._card_row = row
        # Overlapping rather than stacked, so the session card's shadow room
        # and the play canvas's empty top can share space; gaps are set in
        # _match_transport_to_card once the play button's height is known.
        left_column = OverlapColumn()
        self._left_column = left_column
        left_column.addWidget(theme.with_dual_shadow(self._build_session_card()))
        left_column.addWidget(self._build_transport())
        row.addLayout(left_column, CARD_STRETCHES[0])
        row.addWidget(theme.with_dual_shadow(self._build_track_card()), CARD_STRETCHES[1])
        row.addWidget(
            theme.with_dual_shadow(self._build_equalizer_card()), CARD_STRETCHES[2]
        )
        root.addLayout(row, 2)

        self.setCentralWidget(central)

        # Grain sits above every card, click-through, resized with the window.
        self._grain = GrainOverlay(central)
        self._grain.setGeometry(central.rect())
        self._grain.raise_()

        if self.spotify_poller is not None:
            self.spotify_poller.track_changed.connect(self._on_spotify_track)
            self.spotify_poller.art_changed.connect(self._on_spotify_art)
            self.spotify_poller.status_changed.connect(self._on_spotify_status)
            self.spotify_poller.start()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.timeout.connect(self._update_track_progress_display)
        self._clock_timer.start(1000)
        self._update_clock()

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(33)

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
        title_font = theme.medium_font(title_font)
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
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(14)

        status_row = QHBoxLayout()
        self.session_dot = QLabel()
        self.session_dot.setFixedSize(10, 10)
        status_row.addWidget(self.session_dot)
        self.session_status_label = QLabel("Stopped")
        status_font = self.session_status_label.font()
        status_font = theme.medium_font(status_font)
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
        self.volume_readout = QLabel("+0.0 dB")
        self.volume_readout.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        vol_head.addWidget(self.volume_readout)
        layout.addLayout(vol_head)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 240)  # 0 to +24 dB, tenths
        self.volume_slider.setValue(0)
        self.volume_slider.valueChanged.connect(self._volume_changed)
        self.volume_slider.setStyleSheet(SLIDER_QSS)
        layout.addWidget(self.volume_slider)

        layout.addStretch(1)

        self._sync_session_ui()
        card.setMaximumWidth(CARD_MAX_WIDTH)
        self._session_card = card
        return card

    def _build_transport(self) -> QWidget:
        """Spotify transport, sitting below the session card rather than in it.

        Each button is its own SVG with its own pair of shadows, so they read
        as separate physical keys instead of controls printed on the panel.
        """
        holder = QWidget()
        column = OverlapColumn(holder)
        column.setContentsMargins(0, 0, 0, 0)
        self._transport_column = column

        # Glyph set here, not only from _on_spotify_track: with no poller that
        # handler never runs, and a blank pill reads as a missing button.
        self.spotify_play_pause_button = SvgButton(
            str(theme.IMAGE_DIR / "play-btn.svg"),
            "▶",
            glyph_ratio=0.13,
            height=PLAY_BUTTON_HEIGHT,
            glyph_offset=PLAY_GLYPH_OFFSET,
        )
        # play-btn.svg bakes in its own pair of drop shadows (filter0_ddi), so
        # wrapping it again would double them; the skip buttons carry only an
        # inset and get theirs from Qt.
        column.addWidget(self.spotify_play_pause_button)

        transport_row = QHBoxLayout()
        transport_row.setSpacing(TRANSPORT_SPACING)
        self.prev_button = SvgButton(
            str(theme.IMAGE_DIR / "skip-backward.svg"),
            height=SKIP_BUTTON_HEIGHT,
            face_color=theme.BUTTON_FACE,
        )
        self.next_button = SvgButton(
            str(theme.IMAGE_DIR / "skip-forward.svg"),
            height=SKIP_BUTTON_HEIGHT,
            face_color=theme.BUTTON_FACE,
        )
        for button in (self.prev_button, self.next_button):
            transport_row.addWidget(
                theme.with_dual_shadow(
                    button,
                    dark_offset=BUTTON_DARK_OFFSET,
                    dark_blur=BUTTON_DARK_BLUR,
                    light_offset=BUTTON_LIGHT_OFFSET,
                    light_blur=BUTTON_LIGHT_BLUR,
                ),
                0,
                Qt.AlignmentFlag.AlignLeft,
            )
        transport_row.addStretch(1)
        column.addLayout(transport_row)

        if self.spotify_poller is not None:
            self.prev_button.clicked.connect(self.spotify_poller.previous_track)
            self.spotify_play_pause_button.clicked.connect(self.spotify_poller.play_pause)
            self.next_button.clicked.connect(self.spotify_poller.next_track)
        else:
            for button in (self.prev_button, self.spotify_play_pause_button, self.next_button):
                button.setEnabled(False)
        return holder

    def _build_track_card(self) -> QWidget:
        card = theme.Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        # The heading is artwork, not type: the stencil lettering keeps its own
        # face whatever font the app ends up loading. Fall back to text so a
        # missing file leaves a readable card rather than a blank corner.
        header = QLabel()
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lettering = svg_pixmap(
            str(theme.IMAGE_DIR / "track-text.svg"),
            TRACK_HEADER_HEIGHT,
            self.devicePixelRatioF(),
        )
        if lettering is None:
            header.setText("TRACK")
            header_font = header.font()
            header_font = theme.medium_font(header_font)
            header_font.setPointSize(12)
            header.setFont(header_font)
            header.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        else:
            header.setPixmap(lettering)
        layout.addWidget(header)

        plus = _muted_label("+")
        plus.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(plus)

        self.track_art = TrackArt(diameter=TRACK_ART_DIAMETER)
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
            spotifyio.unavailable_reason() or "Connecting..."
        )
        self.track_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track_title_label.setWordWrap(True)
        title_font = self.track_title_label.font()
        title_font = theme.medium_font(title_font)
        title_font.setPointSize(13)
        self.track_title_label.setFont(title_font)
        self.track_title_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        layout.addWidget(self.track_title_label)

        self.track_progress = QProgressBar()
        self.track_progress.setRange(0, 1000)
        self.track_progress.setTextVisible(False)
        self.track_progress.setFixedHeight(6)
        self.track_progress.setStyleSheet(
            f"QProgressBar {{ background: {theme.DIVIDER}; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {theme.TEXT_PRIMARY}; border-radius: 3px; }}"
        )
        layout.addWidget(self.track_progress)

        self.track_time_label = QLabel("0:00/0:00")
        self.track_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track_time_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self.track_time_label)

        layout.addStretch(1)

        source_row = QHBoxLayout()
        source_row.addWidget(_muted_label("PLAYING FROM"))
        spotify_tag = QLabel()
        logo = svg_pixmap(
            str(theme.IMAGE_DIR / "spotify logo.svg"),
            SPOTIFY_LOGO_HEIGHT,
            self.devicePixelRatioF(),
        )
        if logo is None:
            spotify_tag.setText("Spotify")
            spotify_tag.setStyleSheet(f"color: {theme.GREEN}; font-weight: 700;")
        else:
            spotify_tag.setPixmap(logo)
        source_row.addWidget(spotify_tag)
        source_row.addStretch(1)
        layout.addLayout(source_row)

        return card

    def _build_equalizer_card(self) -> QWidget:
        card = theme.Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 6, 18, 6)
        layout.setSpacing(8)

        header = QLabel()
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lettering = svg_pixmap(
            str(theme.IMAGE_DIR / "equalizer-text.svg"),
            EQ_HEADER_HEIGHT,
            self.devicePixelRatioF(),
        )
        if lettering is None:
            header.setText("EQUALIZER")
            header_font = header.font()
            header_font = theme.medium_font(header_font)
            header_font.setPointSize(12)
            header.setFont(header_font)
            header.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        else:
            header.setPixmap(lettering)
        layout.addWidget(header)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(40)
        self.sliders: list[EqSlider] = []
        for freq_text, band_name, gesture in EQ_BANDS:
            column = QVBoxLayout()
            slider = EqSlider()
            slider.setRange(int(-GAIN_LIMIT_DB * SLIDER_SCALE), int(GAIN_LIMIT_DB * SLIDER_SCALE))
            slider.setValue(0)
            slider.setMinimumHeight(EQ_SLIDER_HEIGHT)
            slider.valueChanged.connect(self._sliders_changed)
            column.addWidget(
                theme.with_dual_shadow(
                    slider,
                    dark_offset=SLIDER_DARK_OFFSET,
                    dark_blur=SLIDER_DARK_BLUR,
                    light_offset=SLIDER_LIGHT_OFFSET,
                    light_blur=SLIDER_LIGHT_BLUR,
                ),
                alignment=Qt.AlignmentFlag.AlignHCenter,
            )
            freq_label = QLabel(freq_text)
            freq_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            freq_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10px;")
            column.addWidget(freq_label)
            name_label = QLabel(band_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            name_font = name_label.font()
            name_font = theme.medium_font(name_font)
            name_label.setFont(name_font)
            name_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
            column.addWidget(name_label)
            gesture_label = QLabel(gesture)
            gesture_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            gesture_label.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            )
            column.addWidget(gesture_label)
            # The readings sit right under their own bar, so the column packs
            # tight; the taller bars are paid for out of these gaps.
            column.setSpacing(EQ_LABEL_SPACING)
            slider_row.addLayout(column)
            self.sliders.append(slider)
        layout.addLayout(slider_row)

        self.calibrate_button = QPushButton("Reset / calibrate")
        self.calibrate_button.setToolTip(
            "Take the pen's current position as home and flatten the EQ. "
            "Safe to use mid-song."
        )
        self.calibrate_button.setFixedHeight(22)
        self.calibrate_button.setStyleSheet(CALIBRATE_BUTTON_QSS)
        self.calibrate_button.setAutoDefault(False)
        self.calibrate_button.setDefault(False)
        self.calibrate_button.clicked.connect(self._calibrate)
        layout.addWidget(self.calibrate_button)
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
        self.input_box.clear()
        self.output_box.clear()
        for dev in list_devices():
            name = dev.name.lower()
            # "Microsoft Sound Mapper" is a virtual meta-device; PortAudio
            # frequently refuses to pair it for a duplex stream with a real
            # device (paBadIODeviceCombination / PaErrorCode -9993), so it's
            # never a safe choice here even though it looks like a device.
            if "sound mapper" in name:
                continue
            if dev.inputs >= 2:
                self.input_box.addItem(f"{dev.name}", dev.index)
            if dev.outputs >= 2 and "blackhole" not in name:
                self.output_box.addItem(f"{dev.name}", dev.index)
        preferred = default_input_index()
        if preferred is not None:
            pos = self.input_box.findData(preferred)
            if pos >= 0:
                self.input_box.setCurrentIndex(pos)
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
        # Kept raw, so Calibrate can take whatever pose is being held right
        # now as the new zero. The meters above stay raw for the same reason.
        self._latest_frame = frame
        if not self.touch_toggle.isChecked():
            return
        frame = self._relative_to_origin(frame)
        # Sensor noise and integrator drift arrive as a stream of frames that
        # differ by a hair, and following those made the sliders crawl while
        # the pen sat still. Only act on motion big enough to be deliberate;
        # the meters above still show every frame.
        previous = self._last_motion
        if previous is not None and (
            abs(frame.tilt - previous.tilt) < MOTION_DEADBAND_DEG
            and abs(frame.roll - previous.roll) < MOTION_DEADBAND_DEG
            and abs(frame.sway - previous.sway) < MOTION_DEADBAND_SWAY
        ):
            return
        self._last_motion = frame
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
        self.spotify_play_pause_button.set_glyph("||" if is_playing else "▶")
        # The disc turns only while the track is actually playing.
        self.track_art.set_spinning(is_playing)
        if not title:
            self._spotify_has_track = False
            self.track_art.set_spinning(False)
            self.track_artist_label.setText("")
            self.track_title_label.setText("Nothing playing")
            self.track_progress.setValue(0)
            self.track_time_label.setText("0:00/0:00")
            return
        self._spotify_has_track = True
        self.track_artist_label.setText(artist)
        self.track_title_label.setText(title)
        self._spotify_playing = is_playing
        self._spotify_progress_ms = progress_ms
        self._spotify_duration_ms = duration_ms
        self._spotify_progress_ts = time.monotonic()
        self._update_track_progress_display()

    def _update_track_progress_display(self) -> None:
        # The Spotify poll only lands every couple of seconds; interpolate
        # locally off the wall clock in between so the time reads live
        # instead of visibly jumping once per poll.
        if not self._spotify_has_track or self._spotify_duration_ms <= 0:
            return
        elapsed_ms = 0.0
        if self._spotify_playing:
            elapsed_ms = (time.monotonic() - self._spotify_progress_ts) * 1000.0
        estimated_ms = min(self._spotify_progress_ms + elapsed_ms, self._spotify_duration_ms)
        self.track_progress.setValue(int(estimated_ms / self._spotify_duration_ms * 1000))
        self.track_time_label.setText(
            f"{_format_mmss(int(estimated_ms))}/{_format_mmss(self._spotify_duration_ms)}"
        )

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
        # Windows refuses to duplex-pair devices from different host APIs
        # (MME/DirectSound/WASAPI/WDM-KS) -- PaErrorCode -9993, "Illegal
        # combination of I/O devices" -- so among hint matches, prefer one
        # that shares the chosen input's host API before falling back to
        # whichever hint match comes first regardless of API.
        devices_by_index = {dev.index: dev for dev in list_devices()}
        input_dev = devices_by_index.get(self.input_box.currentData())
        input_hostapi = input_dev.hostapi if input_dev is not None else None

        def output_hostapi(i: int) -> int:
            dev = devices_by_index.get(self.output_box.itemData(i))
            return dev.hostapi if dev is not None else -1

        for hint in ("bose", "airpod", "headphone", "speaker"):
            for i in range(self.output_box.count()):
                if hint in self.output_box.itemText(i).lower() and (
                    output_hostapi(i) == input_hostapi
                ):
                    self.output_box.setCurrentIndex(i)
                    return
        # Nothing shares the input's host API, so rank instead of taking
        # whichever entry is listed first: on Windows that is always the
        # legacy MME duplicate, which resamples and drops Bluetooth output.
        api_names = hostapi_names()
        for hint in ("bose", "airpod", "headphone", "speaker"):
            matches = [
                i
                for i in range(self.output_box.count())
                if hint in self.output_box.itemText(i).lower()
            ]
            if matches:
                best = min(matches, key=lambda i: hostapi_rank(output_hostapi(i), api_names))
                self.output_box.setCurrentIndex(best)
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
            self.status.setText(routing.loopback_hint())

    def _volume_changed(self, value: int) -> None:
        db = value / 10.0
        self.engine.set_makeup_db(db)
        self.volume_readout.setText(f"+{db:.1f} dB")

    def _refresh(self) -> None:
        level = min(int(self.engine.output_level * 300), 100)
        self.level_bar.setValue(level if self.engine.running else 0)
        if self.engine.running:
            window = self.engine.latest_window()
            bars = bar_spectrum(window, self.engine.samplerate)
            self.spectrum.update_levels(bars)
            self._check_silence()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._match_transport_to_card()
        row = getattr(self, "_card_row", None)
        if row is not None:
            # Proportional rather than fixed, so the inset holds at any width.
            inset = round(self.width() * self._card_row_margin_fraction)
            row.setContentsMargins(inset, 0, inset, 0)
        grain = getattr(self, "_grain", None)
        if grain is not None and self.centralWidget() is not None:
            grain.setGeometry(self.centralWidget().rect())
            grain.raise_()

    def _relative_to_origin(self, frame: TouchFrame) -> TouchFrame:
        """Re-zero a frame against the calibrated pose.

        The firmware zeroes itself once, on connect. Anything after that -
        picking the pen up differently, or the gyro integrators drifting -
        leaves the rest pose reading as a tilt the EQ then applies. This lets
        the pose be re-declared at any time without dropping the connection.
        """
        origin = self._motion_origin
        if origin is None:
            return frame
        return TouchFrame(
            tilt=frame.tilt - origin.tilt,
            roll=frame.roll - origin.roll,
            energy=frame.energy,
            sway=frame.sway - origin.sway,
        )

    def _calibrate(self) -> None:
        """Take the pen's current pose as home and flatten the EQ.

        Safe mid-song: it only moves the reference the gains are measured
        from, it does not touch the audio stream.
        """
        self._motion_origin = self._latest_frame
        self._last_motion = None
        self._touch_gains = BandGains(0.0, 0.0, 0.0)
        for slider in self.sliders:
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        self._push_gains()
        if self._motion_origin is None:
            self.status.setText("EQ reset to flat; no pen frame yet to calibrate against")
        else:
            self.status.setText("EQ reset; this pen position is now home")

    def _match_transport_to_card(self) -> None:
        """Size the transport to the width the session card is allotted.

        The buttons are pinned to their artwork's aspect ratio, so width is
        the only free dimension and height follows. The target is computed
        from the window and the column stretches rather than read off the
        card: a fixed-size widget contributes to its column's minimum width,
        so measuring the card would let each resize feed the next and the
        column would ratchet wider every pass.
        """
        play = getattr(self, "spotify_play_pause_button", None)
        if play is None or self.width() <= 1:
            return
        # Derived from the window and the column stretches, never measured off
        # the card. A fixed-size child sets its column's minimum width, so
        # sizing these to the card's actual width let each resize widen the
        # column, which widened the card, which widened the buttons again.
        usable = self.width() * (1.0 - 2 * CARD_ROW_MARGIN_FRACTION)
        column = usable * CARD_STRETCHES[0] / sum(CARD_STRETCHES)
        width = int(min(max(column - SHADOW_WIDTH_COST, 120), CARD_MAX_WIDTH))
        # Capped to the column it sits in. A fixed-size child wider than its
        # column raises the whole row's minimum width, which widens the
        # window, which widens the column this is measured from: the button
        # would grow on every resize and never settle.
        play.set_width(int((column - SHADOW_WIDTH_COST) * PLAY_BUTTON_FRACTION))
        # Capped independently: the skips only grew because the column had
        # to widen for the play pill, and at full half-width they cost more
        # vertical space than the taller pill saved.
        half = min(max(1, (width - TRANSPORT_SPACING) // 2), SKIP_MAX_WIDTH)
        self.prev_button.set_width(half)
        self.next_button.set_width(half)
        # Each gap is the face-to-face gap minus the transparent room on
        # either side of it, which is usually negative: the neighbours
        # overlap where nothing is drawn.
        card_bottom_room = theme.dual_shadow_padding()[3]
        skip_top_room = theme.dual_shadow_padding(
            BUTTON_DARK_OFFSET, BUTTON_DARK_BLUR, BUTTON_LIGHT_OFFSET, BUTTON_LIGHT_BLUR
        )[1]
        self._left_column.set_gap(
            0,
            TRANSPORT_FACE_GAP
            - card_bottom_room
            - round(play.height() * PLAY_PILL_TOP_FRACTION),
        )
        self._transport_column.set_gap(
            0,
            TRANSPORT_FACE_GAP
            - skip_top_room
            - round(play.height() * PLAY_PILL_BOTTOM_ROOM_FRACTION),
        )

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
