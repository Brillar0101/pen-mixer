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


def unavailable_reason() -> str | None:
    """Why the poller cannot run, or None when it can.

    Worth distinguishing: a missing client id is a setup step the user has to
    do once, a missing spotipy is a broken install. "Not connected" told them
    neither.
    """
    if not CLIENT_ID:
        return "Set SPOTIFY_CLIENT_ID"
    try:
        import spotipy  # noqa: F401
    except ImportError:
        return "spotipy not installed"
    return None


def available() -> bool:
    return unavailable_reason() is None


class SpotifyPoller(QThread):
    """Polls playback state and exposes play/pause/skip for the UI."""

    # title, artist, is_playing, progress_ms, duration_ms
    track_changed = Signal(str, str, bool, int, int)
    art_changed = Signal(bytes)  # raw image bytes, only on a new album art URL
    status_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = False
        self._sp = None
        self._is_playing = False
        self._last_track_id: str | None = None
        self._last_art_url: str | None = None

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
            item = playback.get("item") if playback else None
            if item:
                self._is_playing = bool(playback.get("is_playing"))
                title = item["name"]
                artist = ", ".join(a["name"] for a in item["artists"])
                self.track_changed.emit(
                    title,
                    artist,
                    self._is_playing,
                    int(playback.get("progress_ms") or 0),
                    int(item.get("duration_ms") or 0),
                )
                self._last_track_id = item["id"]
                images = item.get("album", {}).get("images") or []
                # Spotify lists artwork largest first, so [0] is the 640px
                # version; [-1] is the 64px thumbnail, which visibly pixelated
                # once the disc grew past thumbnail size.
                self._maybe_fetch_art(images[0]["url"] if images else None)
            elif self._last_track_id is not None:
                self._is_playing = False
                self._last_track_id = None
                self.track_changed.emit("", "", False, 0, 0)
                self._maybe_fetch_art(None)
            self.msleep(int(POLL_SECONDS * 1000))

    def _maybe_fetch_art(self, url: str | None) -> None:
        if url == self._last_art_url:
            return
        self._last_art_url = url
        if url is None:
            self.art_changed.emit(b"")
            return
        try:
            import requests

            response = requests.get(url, timeout=5)
            response.raise_for_status()
            self.art_changed.emit(response.content)
        except Exception:  # noqa: BLE001 - a missing image is not worth surfacing
            self.art_changed.emit(b"")

    # ---- controls, called directly from the UI thread ------------------
    def play_pause(self) -> None:
        if self._sp is None:
            return
        try:
            if self._is_playing:
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
