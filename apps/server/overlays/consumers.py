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
    # Now we only use channel.chat.notification for the timeline to avoid duplicates
    TIMELINE_EVENTS = [
        "channel.chat.notification",  # Consolidated event that includes subs, raids, etc.
        "channel.follow",  # Still separate as it doesn't appear in chat.notification
        "channel.cheer",  # Still separate as it doesn't appear in chat.notification
    ]

    # Keep the old list for other uses (like base layer)
    VIEWER_INTERACTIONS = [
        "channel.chat.notification",
        "channel.follow",
        "channel.subscribe",
        "channel.subscription.gift",
        "channel.subscription.message",
        "channel.cheer",
        "channel.raid",
    ]

    # Notice types from channel.chat.notification that we want in timeline
    # Excludes: announcement, unraid, shared_chat_* variants, etc.
    TIMELINE_NOTICE_TYPES = [
        "sub",  # New subscription
        "resub",  # Resubscription
        "sub_gift",  # Single gift subscription
        "community_sub_gift",  # Community gift subscriptions
        "gift_paid_upgrade",  # Gift sub converted to paid
        "prime_paid_upgrade",  # Prime sub converted to paid
        "pay_it_forward",  # Pay it forward gift
        "raid",  # Channel raid
        "bits_badge_tier",  # Bits badge earned
        "charity_donation",  # Charity donation
    ]

    # Notice types to exclude from timeline
    EXCLUDED_NOTICE_TYPES = [
        "announcement",  # Channel announcements
        "unraid",  # Raid cancelled (our stream status)
        # Shared chat events (for merged chat rooms)
        "shared_chat_sub",
        "shared_chat_resub",
        "shared_chat_sub_gift",
        "shared_chat_community_sub_gift",
        "shared_chat_gift_paid_upgrade",
        "shared_chat_prime_paid_upgrade",
        "shared_chat_pay_it_forward",
        "shared_chat_raid",
        "shared_chat_unraid",
        "shared_chat_announcement",
        "shared_chat_bits_badge_tier",
        "shared_chat_charity_donation",
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
        await self.pubsub.subscribe("events:limitbreak")
        await self.pubsub.subscribe("events:music")
        await self.pubsub.subscribe("events:status")
        await self.pubsub.subscribe("events:chat")
        await self.pubsub.subscribe("events:games:ffbot")
        # Future game channels can be added here:
        # await self.pubsub.subscribe("events:games:ironmon")
        # await self.pubsub.subscribe("events:games:ff14")
        logger.info(
            "Subscribed to Redis channels: events:twitch, events:obs, events:limitbreak, events:music, events:status, events:chat, and events:games:ffbot"
        )

        # Start Redis message listener
        self.redis_task = asyncio.create_task(self._listen_to_redis())

        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self._heartbeat())

        # Send initial state for all layers
        await self._send_initial_state()

        # Test Redis connection
        logger.info("🧪 Testing Redis pub/sub...")
        test_channel = f"test:{datetime.now(timezone.utc).timestamp()}"
        await self.redis.publish(test_channel, "test")
        logger.info("✅ Redis test publish successful")

    async def _heartbeat(self) -> None:
        """Send periodic heartbeat to detect connection issues."""
        heartbeat_interval = 30  # seconds
        try:
            while True:
                await asyncio.sleep(heartbeat_interval)
                await self._send_message(
                    "base",
                    "heartbeat",
                    {"timestamp": datetime.now(timezone.utc).isoformat()},
                )
                logger.debug("💓 Heartbeat sent")
        except asyncio.CancelledError:
            logger.info("Heartbeat task cancelled")
        except Exception as e:
            logger.error(f"❌ Heartbeat error: {e}")

    async def disconnect(self, close_code: int) -> None:
        """Clean up connections when overlay disconnects."""
        logger.info(f"Overlay client disconnected with code: {close_code}")

        # Cancel heartbeat if it exists
        if hasattr(self, "heartbeat_task"):
            self.heartbeat_task.cancel()

        await cleanup_redis_connections(self.redis, self.pubsub, self.redis_task)

    async def _listen_to_redis(self) -> None:
        """Listen for Redis pub/sub messages and route to overlay layers."""
        try:
            while True:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message.get("type") == "message":
                    try:
                        logger.info(
                            f"📨 Received Redis message on channel: {message.get('channel')}"
                        )
                        event_data = json.loads(message["data"])
                        logger.info(
                            f"📨 Event type: {event_data.get('event_type')}, Source: {event_data.get('source')}"
                        )
                        # Debug log the entire event_data structure for chat notifications
                        if event_data.get("event_type") == "channel.chat.notification":
                            logger.info(f"📨 FULL event_data keys: {event_data.keys()}")
                            payload = event_data.get("payload")
                            if payload:
                                logger.info(f"📨 Payload type: {type(payload)}")
                                if isinstance(payload, dict):
                                    logger.info(f"📨 Payload keys: {payload.keys()}")
                                    logger.info(
                                        f"📨 chatter_display_name: {payload.get('chatter_display_name')}"
                                    )
                                    logger.info(
                                        f"📨 notice_type: {payload.get('notice_type')}"
                                    )
                                    if payload.get("notice_type") == "resub":
                                        logger.info(
                                            f"📨 resub data: {payload.get('resub')}"
                                        )
                                else:
                                    logger.info(
                                        f"📨 Payload is STRING: {payload[:100]}..."
                                    )
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

        # Handle limit break events
        if event_type == "limitbreak.update":
            logger.info(
                f"🎯 WebSocket: Sending limitbreak:update to overlay - {event_data.get('data', {})}"
            )
            await self._send_message("limitbreak", "update", event_data.get("data", {}))
            return
        elif event_type == "limitbreak.executed":
            logger.info(
                f"🔊 WebSocket: Sending limitbreak:executed to overlay - {event_data.get('data', {})}"
            )
            await self._send_message(
                "limitbreak", "executed", event_data.get("data", {})
            )
            return

        # Handle music events
        if event_type == "music.update":
            logger.info(
                f"🎵 WebSocket: Sending music:update to overlay - {event_data.get('data', {})}"
            )
            await self._send_message("music", "update", event_data.get("data", {}))
            return
        elif event_type == "music.sync":
            logger.info(
                f"🎵 WebSocket: Sending music:sync to overlay - {event_data.get('data', {})}"
            )
            await self._send_message("music", "sync", event_data.get("data", {}))
            return

        # Handle status events
        if event_type == "status.update":
            logger.info(
                f"📍 WebSocket: Sending status:update to overlay - {event_data.get('data', {})}"
            )
            await self._send_message("status", "update", event_data.get("data", {}))
            return

        # Handle chat messages for emote rain
        if event_type == "channel.chat.message":
            logger.info("💬 WebSocket: Sending chat:message to overlay")
            await self._send_message("chat", "message", event_data.get("data", {}))
            # Don't return - let it continue to other handlers if needed

        # Handle game events from FFBot
        if source == "ffbot":
            # Extract the event subtype (stats, hire, change, save)
            game_event_type = event_type.replace("ffbot.", "")

            # Build appropriate payload based on event type
            payload = {}
            if game_event_type == "stats":
                payload = {
                    "player": event_data.get("player"),
                    "member": event_data.get("member"),
                    "data": event_data.get("payload", {}),
                    "timestamp": event_data.get("timestamp"),
                }
            elif game_event_type == "hire":
                game_payload = event_data.get("payload", {})
                payload = {
                    "player": event_data.get("player"),
                    "member": event_data.get("member"),
                    "character": game_payload.get("character"),
                    "cost": game_payload.get("cost", 0),
                    "data": game_payload.get("stats", {}),  # Include enriched stats
                    "timestamp": event_data.get("timestamp"),
                }
            elif game_event_type == "change":
                game_payload = event_data.get("payload", {})
                payload = {
                    "player": event_data.get("player"),
                    "member": event_data.get("member"),
                    "from": game_payload.get("from", ""),
                    "to": game_payload.get("to", ""),
                    "data": game_payload.get("stats", {}),  # Include enriched stats
                    "timestamp": event_data.get("timestamp"),
                }
            elif game_event_type == "save":
                game_payload = event_data.get("payload", {})
                payload = {
                    "player_count": game_payload.get("player_count", 0),
                    "metadata": game_payload.get("metadata"),
                    "timestamp": event_data.get("timestamp"),
                }
            else:
                # Unknown event type, skip
                logger.warning(f"Unknown FFBot event type: {event_type}")
                return

            # Send with specific message type
            logger.info(f"🎮 WebSocket: Sending ffbot:{game_event_type} to overlay")
            await self._send_message("ffbot", game_event_type, payload)
            return

        # Handle OBS events differently
        if source == "obs":
            # OBS events go to OBS state layer for real-time state updates
            await self._send_message("obs", "update", event_data)

            # Also broadcast scene changes to overlays that might need to adapt
            if event_type == "obs.scene.changed":
                await self._send_message("base", "obs_scene_changed", event_data)
        else:
            # Send timeline-worthy events to timeline
            if event_type in [
                "channel.chat.notification",
                "channel.follow",
                "channel.cheer",
            ]:
                # For chat.notification, check if it's a timeline-worthy notice type
                if event_type == "channel.chat.notification":
                    payload = event_data.get("payload", {})
                    # Parse payload if it's a string (shouldn't happen, but just in case)
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                            logger.warning(
                                f"Had to parse payload from string for {event_type}"
                            )
                        except json.JSONDecodeError:
                            logger.error(
                                f"Failed to parse payload string for {event_type}"
                            )
                            payload = {}
                    notice_type = payload.get("notice_type", "")
                    logger.info(
                        f"📺 Chat notification received - notice_type: {notice_type}, "
                        f"is_timeline_worthy: {notice_type in self.TIMELINE_NOTICE_TYPES}"
                    )
                    logger.info(
                        f"📺 Payload type: {type(payload)}, "
                        f"chatter_user_name: {payload.get('chatter_user_name') if isinstance(payload, dict) else 'N/A - payload is not dict'}"
                    )
                    if notice_type in self.TIMELINE_NOTICE_TYPES:
                        # Format event for timeline with proper structure
                        timeline_event = {
                            "id": event_data.get("event_id"),
                            "type": f"{event_data.get('source', 'twitch')}.{event_type}",
                            "data": {
                                "timestamp": event_data.get("timestamp"),
                                "payload": payload,  # Use the parsed payload
                                "user_name": payload.get(
                                    "chatter_user_name", "Unknown"
                                ),
                            },
                        }
                        logger.info(f"📺 Sending {notice_type} to timeline:push")
                        await self._send_message("timeline", "push", timeline_event)
                else:
                    # Follow and cheer events always go to timeline
                    # Format event for timeline with proper structure
                    timeline_event = {
                        "id": event_data.get("event_id"),
                        "type": f"{event_data.get('source', 'twitch')}.{event_type}",
                        "data": {
                            "timestamp": event_data.get("timestamp"),
                            "payload": event_data.get("payload", {}),
                            "user_name": event_data.get("payload", {}).get(
                                "user_name", "Unknown"
                            ),
                        },
                    }
                    await self._send_message("timeline", "push", timeline_event)

            # All viewer interactions still go to base and alerts for other uses
            if event_type in self.VIEWER_INTERACTIONS:
                # Format event for base and alerts with proper structure
                formatted_event = {
                    "id": event_data.get("event_id"),
                    "type": f"{event_data.get('source', 'twitch')}.{event_type}",
                    "data": {
                        "timestamp": event_data.get("timestamp"),
                        "payload": event_data.get("payload", {}),
                        "user_name": event_data.get("member", {}).get("display_name")
                        or event_data.get("member", {}).get("username")
                        or event_data.get("payload", {}).get("user_name")
                        or event_data.get("payload", {}).get("chatter_user_name")
                        or "Unknown",
                    },
                }
                await self._send_message("base", "update", formatted_event)
                await self._send_message("alerts", "push", formatted_event)

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

        # Limit break layer - get current state
        limit_break_state = await self._get_limit_break_state()
        # Always send sync message, even if state is empty
        await self._send_message(
            "limitbreak",
            "sync",
            limit_break_state
            or {"count": 0, "bar1": 0, "bar2": 0, "bar3": 0, "isMaxed": False},
        )

        # Music layer - get current music state from Redis
        music_state = await self._get_music_state()
        if music_state:
            await self._send_message("music", "sync", music_state)

        # Status layer - get current status
        status_state = await self._get_status_state()
        if status_state:
            await self._send_message("status", "sync", status_state)

    async def _send_message(self, layer: str, verb: str, payload: dict | list) -> None:
        """Send formatted message to overlay client."""
        self.sequence += 1
        message = {
            "type": f"{layer}:{verb}",
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sequence": self.sequence,
        }

        try:
            await self.send(text_data=json.dumps(message))
            logger.info(f"📤 Sent {layer}:{verb} to overlay (seq: {self.sequence})")
        except Exception as e:
            logger.error(f"❌ Failed to send {layer}:{verb}: {e}")

    async def _get_latest_event(self) -> dict | None:
        """Query database for latest viewer interaction."""
        from events.models import Event

        try:
            latest_event = (
                await Event.objects.select_related("member")
                .filter(event_type__in=self.VIEWER_INTERACTIONS)
                .order_by("-timestamp")
                .afirst()
            )
            if latest_event:
                # Parse payload if it's a string (from older events)
                payload = latest_event.payload
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse payload for event {latest_event.id}"
                        )
                        payload = {}

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
                        "payload": payload,
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

            # Fetch events using TIMELINE_EVENTS to avoid duplicates
            # We now only show channel.chat.notification, follow, and cheer events
            async for event in (
                Event.objects.select_related("member")
                .filter(event_type__in=self.TIMELINE_EVENTS)
                .order_by("-timestamp")[
                    : limit * 2
                ]  # Fetch extra to account for filtered events
            ):
                # For channel.chat.notification, filter by notice_type
                if event.event_type == "channel.chat.notification":
                    notice_type = event.payload.get("notice_type", "")

                    # Skip if not a timeline-worthy notice type
                    if notice_type not in self.TIMELINE_NOTICE_TYPES:
                        continue

                # Add event to the list
                try:
                    # Parse payload if it's a string (from older events)
                    payload = event.payload
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Failed to parse payload for event {event.id}"
                            )
                            payload = {}

                    events.append(
                        {
                            "id": str(event.id),
                            "type": f"{event.source}.{event.event_type}",
                            "data": {
                                "user_name": event.username
                                or (
                                    event.member.display_name
                                    if event.member
                                    else "Unknown"
                                ),
                                "timestamp": event.timestamp.isoformat(),
                                "payload": payload,
                            },
                        }
                    )

                    # Stop once we have enough events
                    if len(events) >= limit:
                        break

                except Exception as e:
                    logger.error(
                        f"Error processing event {event.id} ({event.event_type}): {e}"
                    )
                    continue

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

    async def _get_limit_break_state(self) -> dict | None:
        """Get current limit break state using the helix service."""
        from shared.services.twitch.helix import helix_service

        try:
            logger.info("Fetching limit break state using helix service...")

            # Get the current redemption count directly from helix service
            count = await helix_service.get_reward_redemption_count(
                "5685d03e-80c2-4640-ba06-566fb8bbc4ce"
            )
            logger.info(f"Limit break queue count from helix service: {count}")

            # Calculate bar states based on breakpoints at 33/66/100
            bar1 = min(count / 33, 1.0)
            bar2 = min(max(count - 33, 0) / 33, 1.0)
            bar3 = min(max(count - 66, 0) / 34, 1.0)
            is_maxed = count >= 100

            result = {
                "count": count,
                "bar1": bar1,
                "bar2": bar2,
                "bar3": bar3,
                "isMaxed": is_maxed,
            }
            logger.info(f"Limit break state calculated: {result}")
            return result

        except Exception as e:
            logger.error(f"Error getting limit break state: {e}")
            # Return a fallback state instead of None to ensure the message is sent
            return {"count": 0, "bar1": 0, "bar2": 0, "bar3": 0, "isMaxed": False}

    async def _get_music_state(self) -> dict | None:
        """Get current music state from Rainwave service."""
        try:
            from events.services.rainwave import rainwave_service

            # Get the current track from the service
            if rainwave_service.current_track:
                logger.info(
                    f"Sending initial music state: {rainwave_service.current_track.get('title')}"
                )
                return rainwave_service.current_track
            else:
                logger.info("No current track in Rainwave service")
                return None

        except Exception as e:
            logger.error(f"Error getting music state: {e}")
            return None

    async def _get_status_state(self) -> dict | None:
        """Get current stream status."""
        from asgiref.sync import sync_to_async

        from streams.models import Status

        try:
            # Use the singleton pattern to get current status
            status = await sync_to_async(Status.get_current)()
            return {
                "status": status.status,
                "message": status.message,
                "updated_at": status.updated_at.isoformat()
                if status.updated_at
                else None,
            }
        except Exception as e:
            logger.error(f"Error getting status state: {e}")
            return {
                "status": "online",
                "message": "",
                "updated_at": None,
            }

    async def receive(self, text_data: str) -> None:
        """Handle messages from overlay clients (currently unused)."""
        try:
            data = json.loads(text_data)
            logger.debug(f"Received message from overlay client: {data}")
            # Overlays are read-only for now, but we can add controls later
        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON from overlay client: {text_data}")
