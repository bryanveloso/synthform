from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from datetime import timezone

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
        self.current_track: dict | None = None
        self.last_track_id: str | None = None
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

    def broadcast_update(self, track_info: dict) -> None:
        """Broadcast music update via the central music service."""
        logger.info(
            f'[Rainwave] 🎵 Track update. title="{track_info.get("title")}" artist="{track_info.get("artist")}"'
        )
        # Log if we have queue/history data
        if "upcoming" in track_info:
            logger.info(
                f"[Rainwave] Queue data retrieved. count={len(track_info['upcoming'])}"
            )
        if "history" in track_info:
            logger.info(
                f"[Rainwave] History data retrieved. count={len(track_info['history'])}"
            )
        # Use the central music service to broadcast
        self.music_service.process_rainwave_update(track_info)

    async def get_current_info(self) -> dict | None:
        """Fetch current track info from Rainwave API.

        Returns:
            Dict with track info or None if fetch fails or user not tuned in
        """
        # Check circuit breaker
        if self._consecutive_errors >= self._max_consecutive_errors:
            current_time = time.time()
            if current_time - self._last_error_time < self._error_backoff:
                logger.debug(
                    f"[Rainwave] Circuit breaker open. wait_time={self._error_backoff - (current_time - self._last_error_time):.1f}s"
                )
                return None
            # Try to reset circuit breaker
            logger.info("[Rainwave] Attempting circuit breaker reset.")

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0)
            ) as client:
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
                    logger.debug("[Rainwave] User not tuned in.")
                    return None

                # Process current track
                current_track = None
                if "sched_current" in data:
                    current = data["sched_current"]
                    current_track = self._format_schedule_event(
                        current, is_current=True
                    )

                # Process upcoming tracks (sched_next)
                upcoming = []
                if "sched_next" in data:
                    for event in data.get("sched_next", []):
                        formatted_event = self._format_schedule_event(event)
                        if formatted_event:
                            upcoming.append(formatted_event)

                # Process history (sched_history)
                history = []
                if "sched_history" in data:
                    for event in data.get("sched_history", []):
                        formatted_event = self._format_schedule_event(event)
                        if formatted_event:
                            history.append(formatted_event)

                # Build the complete track info
                if current_track:
                    track_info = current_track
                    track_info["upcoming"] = upcoming
                    track_info["history"] = history
                    track_info["timestamp"] = datetime.now(timezone.utc).isoformat()

                    # Log the enhanced data for debugging
                    logger.debug(
                        f"[Rainwave] Data fetched. has_current={bool(current_track)} upcoming_count={len(upcoming)} history_count={len(history)}"
                    )

                    # Reset error state on successful fetch
                    if self._consecutive_errors > 0:
                        logger.info("[Rainwave] ✅ Connection restored.")
                        self._consecutive_errors = 0
                        self._error_backoff = 1

                    return track_info
                else:
                    # No current track, might be between songs
                    return None

        except httpx.HTTPError as e:
            await self._handle_error(f'HTTP error fetching data. error="{str(e)}"')
        except Exception as e:
            await self._handle_error(f'Error fetching data. error="{str(e)}"')

        return None

    async def _handle_error(self, error_msg: str) -> None:
        """Handle errors with circuit breaker pattern.

        Args:
            error_msg: Error message to log (without [Rainwave] prefix)
        """
        self._consecutive_errors += 1
        self._last_error_time = time.time()

        if self._consecutive_errors >= self._max_consecutive_errors:
            # Circuit breaker tripped - log as error for Sentry
            self._error_backoff = min(self._error_backoff * 2, self._max_backoff)
            logger.error(
                f"[Rainwave] Circuit breaker tripped. consecutive_errors={self._consecutive_errors} backoff={self._error_backoff}s {error_msg}"
            )
        else:
            # Transient error - log as warning, don't spam Sentry
            logger.warning(f"[Rainwave] {error_msg}")

    def _format_schedule_event(
        self, event: dict, is_current: bool = False
    ) -> dict | None:
        """Format a schedule event (current, next, or history).

        Args:
            event: Schedule event from Rainwave API
            is_current: Whether this is the currently playing track

        Returns:
            Formatted event dictionary or None if no songs
        """
        if not event:
            return None

        # Get the song(s) from the event
        songs = event.get("songs", [])
        if not songs:
            return None

        # For elections (upcoming), there might be multiple songs
        # For current/history, there's usually just one
        if is_current or event.get("type") != "Election":
            # Single song event (current or past)
            song = songs[0]
            return self._format_song(song, event, is_current)
        else:
            # Election with multiple songs (for voting)
            return self._format_election(event)

    def _format_song(self, song: dict, event: dict, is_current: bool = False) -> dict:
        """Format a single song with metadata.

        Args:
            song: Song data from Rainwave
            event: Parent event data
            is_current: Whether this is currently playing

        Returns:
            Formatted song dictionary
        """
        # Get album info
        albums = song.get("albums", [])
        album_name = (
            albums[0].get("name", "Unknown Album") if albums else "Unknown Album"
        )
        album_art = albums[0].get("art", "") if albums else ""

        # Base song info
        song_info = {
            "id": f"rainwave_{song.get('id', 'unknown')}",
            "title": song.get("title", "Unknown Title"),
            "artist": self._format_artists(song.get("artists", [])),
            "album": album_name,
            "game": album_name,  # For game music, album is the game
            "duration": song.get("length", 0),
            "artwork": f"https://rainwave.cc{album_art}_320.jpg" if album_art else None,
            "source": "rainwave",
            "station": self.station_name,
            "url": song.get("url", ""),
        }

        # Add current-specific fields
        if is_current:
            song_info["elapsed"] = event.get("sched_used", 0)

        # Add requester info if available
        if song.get("elec_request_username"):
            song_info["requested_by"] = song.get("elec_request_username")
            song_info["requested_by_id"] = song.get("elec_request_user_id")

            # Check if requester is a Crusader (community member)
            song_info["is_crusader"] = self._check_is_crusader(
                song.get("elec_request_username")
            )

        # Add event metadata
        song_info["event_id"] = event.get("id")
        song_info["event_type"] = event.get("type", "OneUp")  # OneUp, Election, etc.

        return song_info

    def _format_election(self, event: dict) -> dict:
        """Format an election (voting) event with multiple songs.

        Args:
            event: Election event from Rainwave

        Returns:
            Formatted election dictionary
        """
        songs = event.get("songs", [])

        # Format all song options for voting
        song_options = []
        for song in songs:
            song_data = self._format_song(song, event, is_current=False)
            # Add voting-specific data
            song_data["votes"] = song.get("elec_votes", 0)
            song_data["is_request"] = bool(song.get("elec_request_username"))

            # Check if requester is a Crusader for election songs too
            if song.get("elec_request_username"):
                song_data["is_crusader"] = self._check_is_crusader(
                    song.get("elec_request_username")
                )

            song_options.append(song_data)

        return {
            "event_id": event.get("id"),
            "event_type": "Election",
            "voting_allowed": event.get("voting_allowed", False),
            "songs": song_options,
        }

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

    def _check_is_crusader(self, username: str) -> bool:
        """Check if a username belongs to a community member (Crusader).

        Args:
            username: Rainwave username to check

        Returns:
            True if the user is in our Member database
        """
        if not username:
            return False

        try:
            # Import here to avoid circular dependencies
            from django.db.models import Q

            from events.models import Member

            # Check if username matches any member's username or display_name
            # Case-insensitive match
            return Member.objects.filter(
                Q(username__iexact=username) | Q(display_name__iexact=username)
            ).exists()
        except Exception as e:
            logger.debug(
                f'[Rainwave] Failed to check crusader status. username={username} error="{str(e)}"'
            )
            return False

    async def start_monitoring(self, interval: int = 10):
        """Start monitoring Rainwave for track changes.

        Note: Rainwave doesn't have a WebSocket API yet, so we poll.
        In the future, this could be replaced with WebSocket connection.

        Args:
            interval: Seconds between checks
        """
        logger.info(
            f"[Rainwave] 🎵 Monitoring started. station={self.station_name} station_id={self.station_id}"
        )

        was_tuned_in = False

        while True:
            try:
                track_info = await self.get_current_info()

                if track_info:
                    # User is tuned in and we have track info
                    if not was_tuned_in:
                        # Just tuned in, send current track
                        logger.info("[Rainwave] 🎵 User tuned in.")
                        was_tuned_in = True
                        self.last_track_id = track_info["id"]
                        self.current_track = track_info
                        self.broadcast_update(track_info)
                    elif track_info["id"] != self.last_track_id:
                        # Track changed while tuned in
                        self.last_track_id = track_info["id"]
                        self.current_track = track_info
                        logger.info(
                            f'[Rainwave] 🎵 Track changed. title="{track_info["title"]}" artist="{track_info["artist"]}"'
                        )
                        self.broadcast_update(track_info)
                else:
                    # User not tuned in or failed to fetch
                    if was_tuned_in:
                        # User just tuned out, clear the music display
                        logger.info("[Rainwave] 🎵 User tuned out.")
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
                await self._handle_error(f'Error in monitoring loop. error="{str(e)}"')

            # Use backoff if in error state
            sleep_time = interval
            if self._consecutive_errors > 0:
                sleep_time = min(interval * 2, self._max_backoff)
            await asyncio.sleep(sleep_time)


# Create singleton instance
rainwave_service = RainwaveService("game")
