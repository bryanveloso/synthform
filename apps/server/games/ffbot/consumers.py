from __future__ import annotations

import json
import logging
from datetime import datetime
from datetime import timezone

import redis.asyncio as redis
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)


class FFBotConsumer(AsyncWebsocketConsumer):
    """
    Receives FFBot events and forwards to Redis for real-time display.
    Updates FFBotPlayerStats cache whenever stats data is received.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Accept WebSocket connection from FFBot."""
        await self.accept()
        logger.info(f"FFBot connected from {self.scope['client']}")

        # Connect to Redis for publishing events
        self.redis = redis.from_url(settings.REDIS_URL)

    async def disconnect(self, close_code: int) -> None:
        """Clean up when FFBot disconnects."""
        logger.info(f"FFBot disconnected with code: {close_code}")

        if self.redis:
            await self.redis.close()

    async def receive(self, text_data: str) -> None:
        """Process incoming FFBot events."""
        try:
            data = json.loads(text_data)
            event_type = data.get("type")
            player_username = data.get("player")
            timestamp = data.get("timestamp", datetime.now(timezone.utc).timestamp())

            if not event_type or not player_username:
                logger.warning("Invalid FFBot event: missing type or player")
                return

            # Get or create Member
            member = await self._get_or_create_member(player_username)

            # Update PlayerStats cache for any event that contains stats data
            if event_type == "stats":
                await self._update_player_stats(member, data.get("data", {}))
            elif event_type == "hire":
                await self._update_after_hire(member, data.get("data", {}))
            elif event_type == "change":
                await self._update_after_change(member, data.get("data", {}))

            # Always forward to Redis for real-time overlay
            await self._publish_to_redis(event_type, member, data, timestamp)

            logger.debug(f"Processed FFBot {event_type} event from {player_username}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from FFBot: {e}")
        except Exception as e:
            logger.error(f"Error processing FFBot event: {e}", exc_info=True)

    async def _get_or_create_member(self, username: str):
        """Get or create Member by username."""
        from events.models import Member

        # Normalize username to lowercase for consistency
        username_lower = username.lower()

        member, created = await Member.objects.aget_or_create(
            username=username_lower, defaults={"display_name": username}
        )

        if created:
            logger.info(f"Created new Member for FFBot player: {username}")

        return member

    async def _update_player_stats(self, member, stats_data: dict) -> None:
        """Update PlayerStats with latest data from stats event."""
        from games.ffbot.models import Player

        stats, created = await Player.objects.aget_or_create(member=member)

        # Update all fields from stats event
        fields_to_update = []

        # Core stats
        for field in [
            "lv",
            "atk",
            "mag",
            "spi",
            "hp",
            "exp",
            "gil",
            "collection",
            "ascension",
            "wins",
            "freehirecount",
            "season",
            "esper",
        ]:
            if field in stats_data:
                setattr(stats, field, stats_data[field])
                fields_to_update.append(field)

        # Handle preference field name difference
        if "preference" in stats_data:
            stats.preferedstat = stats_data["preference"]
            fields_to_update.append("preferedstat")

        # Job fields
        for field in ["jobap", "job_atk", "job_mag", "job_spi", "job_hp"]:
            if field in stats_data:
                setattr(stats, field, stats_data[field])
                fields_to_update.append(field)

        # Handle job/mastery field
        if "job" in stats_data and stats_data["job"]:
            stats.m1 = stats_data["job"]
            fields_to_update.append("m1")

        # Card fields
        for field in ["card", "card_collection", "card_passive"]:
            if field in stats_data:
                setattr(stats, field, stats_data[field])
                fields_to_update.append(field)

        # Active unit (might not be in stats but could be elsewhere)
        if "unit" in stats_data:
            stats.unit = stats_data["unit"]
            fields_to_update.append("unit")

        if fields_to_update:
            fields_to_update.append("updated_at")
            await stats.asave(update_fields=fields_to_update)
            logger.debug(f"Updated Player for {member.display_name}")

    async def _update_after_hire(self, member, hire_data: dict) -> None:
        """Update PlayerStats after a hire event."""
        from games.ffbot.models import Player

        stats, _ = await Player.objects.aget_or_create(member=member)

        fields_to_update = []
        if "collection" in hire_data:
            stats.collection = hire_data["collection"]
            fields_to_update.append("collection")

        if "gil_remaining" in hire_data:
            stats.gil = hire_data["gil_remaining"]
            fields_to_update.append("gil")

        if fields_to_update:
            fields_to_update.append("updated_at")
            await stats.asave(update_fields=fields_to_update)

    async def _update_after_change(self, member, change_data: dict) -> None:
        """Update PlayerStats after a character change event."""
        from games.ffbot.models import Player

        stats, _ = await Player.objects.aget_or_create(member=member)

        if "to" in change_data:
            stats.unit = change_data["to"]
            await stats.asave(update_fields=["unit", "updated_at"])

    async def _publish_to_redis(
        self, event_type: str, member, data: dict, timestamp: float
    ) -> None:
        """Forward all events to Redis for real-time display."""
        redis_message = {
            "event_type": f"ffbot.{event_type}",
            "source": "ffbot",
            "timestamp": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
            "member": {
                "id": str(member.id),
                "username": member.username,
                "display_name": member.display_name,
            },
            "payload": data.get("data", {}),
            "player": data.get("player"),  # Keep original username for display
        }

        try:
            await self.redis.publish("events:games:ffbot", json.dumps(redis_message))
            logger.debug(
                f"Published FFBot {event_type} to Redis channel events:games:ffbot"
            )
        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")
