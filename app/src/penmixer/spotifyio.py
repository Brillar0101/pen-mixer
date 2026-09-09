"""Spotify now-playing and playback control, via the Web API.

Auth is PKCE (no client secret to keep safe in a distributed app): the first
poll opens a browser for login and spotipy catches the redirect with a
throwaway local server, then caches the refresh token on disk so later runs
skip the browser step. Requires SPOTIFY_CLIENT_ID in the environment; see
README for how to register an app and get one.
"""

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
SCOPE = "user-read-currently-playing user-read-playback-state user-modify-playback-state"
CACHE_PATH = Path.home() / ".cache" / "penmixer" / "spotify_token.json"
POLL_SECONDS = 2.0


def available() -> bool:
    if not CLIENT_ID:
        return False
    try:
        import spotipy  # noqa: F401
    except ImportError:
        return False
    return True


class SpotifyPoller(QThread):
    """Polls playback state and exposes play/pause/skip for the UI."""

    track_changed = Signal(str, str, bool)  # title, artist, is_playing
    status_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = False
        self._sp = None
        self._last = (None, None, None)

    def stop(self) -> None:
        self._stop = True

    def _client(self):
        import spotipy
        from spotipy.oauth2 import SpotifyPKCE

        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        auth_manager = SpotifyPKCE(
            client_id=CLIENT_ID,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=str(CACHE_PATH),
            open_browser=True,
        )
        return spotipy.Spotify(auth_manager=auth_manager)

    def run(self) -> None:
        self.status_changed.emit("Spotify: signing in...")
        try:
            self._sp = self._client()
        except Exception as exc:  # noqa: BLE001 - surfaced to the status line
            self.status_changed.emit(f"Spotify sign-in failed: {exc}")
            return
        self.status_changed.emit("Spotify: connected")
        while not self._stop:
            try:
                playback = self._sp.current_playback()
            except Exception as exc:  # noqa: BLE001 - one failed poll should not kill the loop
                self.status_changed.emit(f"Spotify error: {exc}")
                self.sleep(int(POLL_SECONDS))
                continue
            if playback and playback.get("item"):
                title = playback["item"]["name"]
                artist = ", ".join(a["name"] for a in playback["item"]["artists"])
                playing = bool(playback.get("is_playing"))
                current = (title, artist, playing)
                if current != self._last:
                    self._last = current
                    self.track_changed.emit(title, artist, playing)
            elif self._last != (None, None, None):
                self._last = (None, None, None)
                self.track_changed.emit("", "", False)
            self.msleep(int(POLL_SECONDS * 1000))

    # ---- controls, called directly from the UI thread ------------------
    def play_pause(self) -> None:
        if self._sp is None:
            return
        try:
            if self._last[2]:
                self._sp.pause_playback()
            else:
                self._sp.start_playback()
        except Exception as exc:  # noqa: BLE001 - surfaced to the status line
            self.status_changed.emit(f"Spotify error: {exc}")

    def next_track(self) -> None:
        if self._sp is None:
            return
        try:
            self._sp.next_track()
        except Exception as exc:  # noqa: BLE001 - surfaced to the status line
            self.status_changed.emit(f"Spotify error: {exc}")

    def previous_track(self) -> None:
        if self._sp is None:
            return
        try:
            self._sp.previous_track()
        except Exception as exc:  # noqa: BLE001 - surfaced to the status line
            self.status_changed.emit(f"Spotify error: {exc}")
