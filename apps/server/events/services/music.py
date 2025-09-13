from __future__ import annotations

import json
import logging
from datetime import datetime
from datetime import timezone

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


class MusicService:
    """Service for handling music updates from various sources."""

    def __init__(self):
        # Use sync Redis since this is called from sync context
        self.redis = redis.from_url(settings.REDIS_URL)

    def broadcast_update(self, data: dict, is_sync: bool = False) -> None:
        """Broadcast music update to WebSocket clients via Redis."""
        # Send appropriate event type
        event_type = "music.sync" if is_sync else "music.update"
        event_data = {
            "event_type": event_type,
            "source": "music",
            "data": data,
        }
        result = self.redis.publish("events:music", json.dumps(event_data))
        logger.info(f"📡 Redis {event_type} publish result (subscribers): {result}")

    def process_apple_music_update(self, data: dict) -> dict:
        """Process Apple Music update data."""
        # Add timestamp if not present
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Add source field
        data["source"] = "apple"

        # Broadcast to clients
        self.broadcast_update(data)

        logger.info(
            f"Apple Music update: {data.get('title', 'No track')} by {data.get('artist', 'Unknown')}"
        )

        return data

    def process_rainwave_update(self, data: dict) -> dict:
        """Process Rainwave update data."""
        # Add timestamp if not present
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Add source field
        data["source"] = "rainwave"

        # Broadcast to clients
        self.broadcast_update(data)

        logger.info(
            f"Rainwave update: {data.get('title', 'No track')} by {data.get('artist', 'Unknown')}"
        )

        return data


# Create singleton instance
music_service = MusicService()
