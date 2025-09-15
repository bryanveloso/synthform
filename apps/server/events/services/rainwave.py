from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from datetime import timezone
from typing import Dict
from typing import Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class RainwaveService:
    """Service for monitoring Rainwave game remix radio in real-time."""

    # Rainwave station IDs
    STATIONS = {
        "game": 1,  # Game music
        "remix": 2,  # OverClocked ReMix
        "covers": 3,  # Covers
        "chip": 4,  # Chiptune
        "all": 5,  # All stations
    }

    def __init__(self, station: str = "remix"):
        """Initialize Rainwave service.

        Args:
            station: Station to monitor ('game', 'remix', 'covers', 'chip', 'all')
        """
        from .music import music_service

        self.station_id = self.STATIONS.get(station, 2)  # Default to remix
        self.station_name = station
        self.base_url = "https://rainwave.cc/api4"
        self.music_service = music_service
        self.current_track: Optional[Dict] = None
        self.last_track_id: Optional[str] = None
        # Hardcoded API credentials as requested
        self.user_id = "53109"
        self.api_key = "vYyXHv30AT"

        # Error handling state
        self._consecutive_errors = 0
        self._last_error_time = 0
        self._error_backoff = 1  # Start with 1 second
        self._max_backoff = getattr(settings, "RAINWAVE_MAX_BACKOFF", 60)
        self._max_consecutive_errors = getattr(
            settings, "RAINWAVE_MAX_CONSECUTIVE_ERRORS", 10
        )

    def broadcast_update(self, track_info: Dict) -> None:
        """Broadcast music update via the central music service."""
        logger.info(
            f"🎵 Rainwave track update: {track_info.get('title')} by {track_info.get('artist')}"
        )
        # Use the central music service to broadcast
        self.music_service.process_rainwave_update(track_info)

    async def get_current_info(self) -> Optional[Dict]:
        """Fetch current track info from Rainwave API.

        Returns:
            Dict with track info or None if fetch fails or user not tuned in
        """
        # Check circuit breaker
        if self._consecutive_errors >= self._max_consecutive_errors:
            current_time = time.time()
            if current_time - self._last_error_time < self._error_backoff:
                logger.debug(
                    f"Circuit breaker open, waiting {self._error_backoff - (current_time - self._last_error_time):.1f}s"
                )
                return None
            # Try to reset circuit breaker
            logger.info("Attempting to reset Rainwave circuit breaker")

        try:
            async with httpx.AsyncClient() as client:
                # Include auth to get user tuned_in status
                response = await client.get(
                    f"{self.base_url}/info",
                    params={
                        "sid": self.station_id,
                        "user_id": self.user_id,
                        "key": self.api_key,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Check if user is actually tuned in
                user_info = data.get("user", {})
                if not user_info.get("tuned_in", False):
                    logger.debug("User not tuned in to Rainwave, skipping update")
                    return None

                if "sched_current" in data:
                    current = data["sched_current"]
                    song = current.get("songs", [{}])[0] if current.get("songs") else {}

                    # Get album info from albums array
                    albums = song.get("albums", [])
                    album_name = (
                        albums[0].get("name", "Unknown Album")
                        if albums
                        else "Unknown Album"
                    )
                    album_art = albums[0].get("art", "") if albums else ""

                    # Format track info
                    track_info = {
                        "id": f"rainwave_{song.get('id', 'unknown')}",
                        "title": song.get("title", "Unknown Title"),
                        "artist": self._format_artists(song.get("artists", [])),
                        "album": album_name,
                        "game": album_name,  # For game music, album is the game
                        "duration": song.get("length", 0),
                        "elapsed": current.get("sched_used", 0),
                        "artwork": f"https://rainwave.cc{album_art}_320.jpg"
                        if album_art
                        else None,
                        "source": "rainwave",
                        "station": self.station_name,
                        "url": song.get("url", ""),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    # Reset error state on successful fetch
                    if self._consecutive_errors > 0:
                        logger.info("Rainwave connection restored")
                        self._consecutive_errors = 0
                        self._error_backoff = 1

                    return track_info

        except httpx.HTTPError as e:
            await self._handle_error(f"HTTP error fetching Rainwave data: {e}")
        except Exception as e:
            await self._handle_error(f"Error fetching Rainwave data: {e}")

        return None

    async def _handle_error(self, error_msg: str) -> None:
        """Handle errors with circuit breaker pattern.

        Args:
            error_msg: Error message to log
        """
        logger.error(error_msg)
        self._consecutive_errors += 1
        self._last_error_time = time.time()

        if self._consecutive_errors >= self._max_consecutive_errors:
            # Circuit breaker tripped
            self._error_backoff = min(self._error_backoff * 2, self._max_backoff)
            logger.warning(
                f"Rainwave circuit breaker tripped after {self._consecutive_errors} errors. "
                f"Backing off for {self._error_backoff}s"
            )

    def _format_artists(self, artists: list) -> str:
        """Format artist list from Rainwave API.

        Args:
            artists: List of artist dictionaries

        Returns:
            Formatted artist string
        """
        if not artists:
            return "Unknown Artist"

        artist_names = [a.get("name", "") for a in artists if a.get("name")]
        return ", ".join(artist_names) if artist_names else "Unknown Artist"

    async def start_monitoring(self, interval: int = 10):
        """Start monitoring Rainwave for track changes.

        Note: Rainwave doesn't have a WebSocket API yet, so we poll.
        In the future, this could be replaced with WebSocket connection.

        Args:
            interval: Seconds between checks
        """
        logger.info(
            f"🎵 Starting Rainwave monitoring for station: {self.station_name} (ID: {self.station_id})"
        )

        was_tuned_in = False

        while True:
            try:
                track_info = await self.get_current_info()

                if track_info:
                    # User is tuned in and we have track info
                    if not was_tuned_in:
                        # Just tuned in, send current track
                        logger.info(f"🎵 User tuned in to Rainwave")
                        was_tuned_in = True
                        self.last_track_id = track_info["id"]
                        self.current_track = track_info
                        self.broadcast_update(track_info)
                    elif track_info["id"] != self.last_track_id:
                        # Track changed while tuned in
                        self.last_track_id = track_info["id"]
                        self.current_track = track_info
                        logger.info(
                            f"🎵 Rainwave track changed: {track_info['title']} by {track_info['artist']}"
                        )
                        self.broadcast_update(track_info)
                    else:
                        logger.debug(
                            f"Rainwave: Same track playing - {track_info['title']}"
                        )
                else:
                    # User not tuned in or failed to fetch
                    if was_tuned_in:
                        # User just tuned out, clear the music display
                        logger.info("🎵 User tuned out of Rainwave")
                        was_tuned_in = False
                        self.current_track = None
                        self.last_track_id = None
                        # Send a clear signal
                        clear_signal = {
                            "source": "rainwave",
                            "tuned_in": False,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        self.music_service.process_rainwave_update(clear_signal)

            except Exception as e:
                await self._handle_error(f"Error in Rainwave monitoring loop: {e}")

            # Use backoff if in error state
            sleep_time = interval
            if self._consecutive_errors > 0:
                sleep_time = min(interval * 2, self._max_backoff)
            await asyncio.sleep(sleep_time)


# Create singleton instance
rainwave_service = RainwaveService("game")
