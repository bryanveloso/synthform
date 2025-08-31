from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from datetime import timezone

import redis.asyncio as redis
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import DatabaseError

from .utils import cleanup_redis_connections

logger = logging.getLogger(__name__)


class OverlayConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for overlay communication."""

    # Timeline-worthy viewer interactions
    VIEWER_INTERACTIONS = [
        "channel.follow",
        "channel.subscribe",
        "channel.subscription.gift",
        "channel.subscription.message",
        "channel.cheer",
        "channel.channel_points_custom_reward_redemption",
        "channel.raid",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis: redis.Redis | None = None
        self.pubsub: redis.client.PubSub | None = None
        self.redis_task: asyncio.Task | None = None
        self.sequence: int = 0

    async def connect(self) -> None:
        """Accept WebSocket connection and initialize overlay state."""
        await self.accept()
        logger.info("Overlay client connected")

        # Connect to Redis for live events
        from django.conf import settings

        self.redis = redis.from_url(settings.REDIS_URL)
        self.pubsub = self.redis.pubsub()

        # Subscribe to live events
        await self.pubsub.subscribe("events:twitch")
        await self.pubsub.subscribe("events:obs")
        logger.info("Subscribed to Redis events:twitch and events:obs channels")

        # Start Redis message listener
        self.redis_task = asyncio.create_task(self._listen_to_redis())

        # Send initial state for all layers
        await self._send_initial_state()

    async def disconnect(self, close_code: int) -> None:
        """Clean up connections when overlay disconnects."""
        logger.info(f"Overlay client disconnected with code: {close_code}")

        await cleanup_redis_connections(self.redis, self.pubsub, self.redis_task)

    async def _listen_to_redis(self) -> None:
        """Listen for Redis pub/sub messages and route to overlay layers."""
        try:
            while True:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    try:
                        event_data = json.loads(message["data"])
                        await self._route_live_event(event_data)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Error processing Redis message: {e}")
                    except redis.RedisError as e:
                        logger.error(f"Redis error routing live event: {e}")
                        break

        except asyncio.CancelledError:
            logger.info("Redis listener task cancelled")
        except redis.RedisError as e:
            logger.error(f"Redis error in listener: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Redis listener: {e}")

    async def _route_live_event(self, event_data: dict) -> None:
        """Route live events to appropriate overlay layers."""
        event_type = event_data.get("event_type")
        source = event_data.get("source")

        if not event_type:
            return

        # Handle OBS events differently
        if source == "obs":
            # OBS events go to OBS state layer for real-time state updates
            await self._send_message("obs", "update", event_data)

            # Also broadcast scene changes to overlays that might need to adapt
            if event_type == "obs.scene.changed":
                await self._send_message("base", "obs_scene_changed", event_data)
        else:
            # Only route viewer interactions to timeline and base layers
            if event_type in self.VIEWER_INTERACTIONS:
                await self._send_message("timeline", "push", event_data)
                await self._send_message("base", "update", event_data)

            # Handle special event types for alerts/ticker
            if event_type in self.VIEWER_INTERACTIONS:
                # These are significant events that might trigger alerts or ticker updates
                await self._send_message("alerts", "push", event_data)

    async def _send_initial_state(self) -> None:
        """Send sync messages for all layers on connection."""
        # Base layer - latest event
        latest_event = await self._get_latest_event()
        if latest_event:
            await self._send_message("base", "sync", latest_event)

        # Timeline layer - recent events
        recent_events = await self._get_recent_events()
        if recent_events:
            await self._send_message("timeline", "sync", recent_events)

        # Ticker layer - initial ticker items
        ticker_items = await self._get_ticker_items()
        if ticker_items:
            await self._send_message("ticker", "sync", ticker_items)

        # OBS layer - current OBS state
        obs_state = await self._get_obs_state()
        if obs_state:
            await self._send_message("obs", "sync", obs_state)

        # Alert layer - starts with empty queue
        await self._send_message("alerts", "sync", [])

    async def _send_message(self, layer: str, verb: str, payload: dict | list) -> None:
        """Send formatted message to overlay client."""
        self.sequence += 1
        message = {
            "type": f"{layer}:{verb}",
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sequence": self.sequence,
        }

        await self.send(text_data=json.dumps(message))
        logger.debug(f"Sent {layer}:{verb} message to overlay client")

    async def _get_latest_event(self) -> dict | None:
        """Query database for latest viewer interaction."""
        from events.models import Event

        try:
            latest_event = (
                await Event.objects.select_related("member")
                .filter(event_type__in=self.VIEWER_INTERACTIONS)
                .afirst()
            )
            if latest_event:
                return {
                    "id": str(latest_event.id),
                    "type": f"{latest_event.source}.{latest_event.event_type}",
                    "data": {
                        "user_name": latest_event.username
                        or (
                            latest_event.member.display_name
                            if latest_event.member
                            else "Unknown"
                        ),
                        "timestamp": latest_event.timestamp.isoformat(),
                        "payload": latest_event.payload,
                    },
                }
            return None
        except DatabaseError as e:
            logger.error(f"Database error querying latest event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error querying latest event: {e}")
            return None

    async def _get_recent_events(self, limit: int = 10) -> list[dict]:
        """Query database for recent timeline-worthy events."""
        from events.models import Event

        try:
            events = []
            async for event in Event.objects.select_related("member").filter(
                event_type__in=self.VIEWER_INTERACTIONS
            )[:limit]:
                events.append(
                    {
                        "id": str(event.id),
                        "type": f"{event.source}.{event.event_type}",
                        "data": {
                            "user_name": event.username
                            or (
                                event.member.display_name if event.member else "Unknown"
                            ),
                            "timestamp": event.timestamp.isoformat(),
                            "payload": event.payload,
                        },
                    }
                )
            return events
        except DatabaseError as e:
            logger.error(f"Database error querying recent events: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying recent events: {e}")
            return []

    async def _get_ticker_items(self) -> list[dict]:
        """Get current ticker items based on show context."""
        # For now, return basic ticker items
        # TODO: Implement show context detection and dynamic queries
        return [
            {"type": "emote_stats", "data": await self._get_emote_stats()},
            {"type": "daily_stats", "data": await self._get_daily_stats()},
            {"type": "recent_follows", "data": await self._get_recent_follows()},
        ]

    async def _get_emote_stats(self) -> dict:
        """Get emote usage statistics."""
        # TODO: Implement actual emote statistics from events
        return {"message": "Emote stats coming soon"}

    async def _get_daily_stats(self) -> dict:
        """Get daily stream statistics."""
        from django.utils import timezone

        from events.models import Event

        try:
            today = timezone.now().date()
            today_start = timezone.datetime.combine(today, timezone.datetime.min.time())
            today_start = timezone.make_aware(today_start)

            # Count today's events by type
            follow_count = await Event.objects.filter(
                timestamp__gte=today_start, event_type="channel.follow"
            ).acount()

            subscribe_count = await Event.objects.filter(
                timestamp__gte=today_start, event_type="channel.subscribe"
            ).acount()

            return {
                "date": today.isoformat(),
                "follows": follow_count,
                "subscribers": subscribe_count,
            }
        except DatabaseError as e:
            logger.error(f"Database error querying daily stats: {e}")
            return {"message": "Daily stats unavailable"}
        except Exception as e:
            logger.error(f"Unexpected error querying daily stats: {e}")
            return {"message": "Daily stats unavailable"}

    async def _get_recent_follows(self) -> dict:
        """Get recent followers."""
        from events.models import Event

        try:
            follows = []
            async for event in Event.objects.filter(
                event_type="channel.follow"
            ).select_related("member")[:5]:
                follows.append(
                    {
                        "user_name": event.username
                        or (event.member.display_name if event.member else "Unknown"),
                        "followed_at": event.timestamp.isoformat(),
                    }
                )
            return {"recent_follows": follows}
        except DatabaseError as e:
            logger.error(f"Database error querying recent follows: {e}")
            return {"message": "Recent follows unavailable"}
        except Exception as e:
            logger.error(f"Unexpected error querying recent follows: {e}")
            return {"message": "Recent follows unavailable"}

    async def _get_obs_state(self) -> dict | None:
        """Get current OBS state from OBS service."""
        try:
            from streams.services.obs import obs_service

            return await obs_service.get_current_state()

        except Exception as e:
            logger.error(f"Error getting OBS state: {e}")
            return {"message": "OBS state unavailable", "connected": False}

    async def receive(self, text_data: str) -> None:
        """Handle messages from overlay clients (currently unused)."""
        try:
            data = json.loads(text_data)
            logger.debug(f"Received message from overlay client: {data}")
            # Overlays are read-only for now, but we can add controls later
        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON from overlay client: {text_data}")
