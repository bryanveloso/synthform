from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import redis
import twitchio
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

# Add the app directory to Python path for Django imports
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "synthform.settings")
import django

django.setup()

from events.models import Event  # noqa: E402
from events.models import Member  # noqa: E402

logger = logging.getLogger(__name__)


class TwitchService(twitchio.Client):
    """Standalone TwitchIO service for handling EventSub events."""

    def __init__(self):
        super().__init__(
            client_id=settings.TWITCH_CLIENT_ID,
            client_secret=settings.TWITCH_CLIENT_SECRET,
            redirect_uri="http://localhost:4343/oauth/callback",
        )
        self._eventsub_connected = False
        self._redis_client = redis.Redis.from_url(
            settings.REDIS_URL or "redis://redis:6379/0"
        )

    async def event_ready(self):
        """Called when the client is ready."""
        user_info = f"User: {self.user.id if self.user else 'No user logged in'}"
        logger.info(f"TwitchIO client ready. {user_info}")

        # Subscribe to events we care about
        await self._subscribe_to_events()

    async def event_oauth_authorized(self, payload):
        """Handle OAuth authorization events."""
        logger.info(f"OAuth authorized for user: {payload.user_id}")

        # Store token (TwitchIO handles this automatically)
        await self.add_token(payload.access_token, payload.refresh_token)

        # If this is a new user authorization, we might want to subscribe to their events
        if payload.user_id and payload.user_id != getattr(self, "bot_id", None):
            logger.info(f"New user authorized: {payload.user_id}")

    async def event_token_refreshed(self, payload):
        """Handle token refresh events."""
        logger.info(f"Token refreshed for user: {payload.user_id}")

    async def _subscribe_to_events(self):
        """Subscribe to Twitch EventSub events."""
        try:
            if not self.user:
                logger.warning("No user logged in, cannot subscribe to events")
                return

            user_id = str(self.user.id)

            # Channel Follow events
            await self.subscribe_websocket(
                topic="channel.follow",
                version="2",
                condition={
                    "broadcaster_user_id": user_id,
                    "moderator_user_id": user_id,
                },
            )
            logger.info("Subscribed to channel.follow events")

            # Channel Subscribe events
            await self.subscribe_websocket(
                topic="channel.subscribe",
                version="1",
                condition={"broadcaster_user_id": user_id},
            )
            logger.info("Subscribed to channel.subscribe events")

            # Channel Subscription Gift events
            await self.subscribe_websocket(
                topic="channel.subscription.gift",
                version="1",
                condition={"broadcaster_user_id": user_id},
            )
            logger.info("Subscribed to channel.subscription.gift events")

            # Channel Cheer events
            await self.subscribe_websocket(
                topic="channel.cheer",
                version="1",
                condition={"broadcaster_user_id": user_id},
            )
            logger.info("Subscribed to channel.cheer events")

            # Channel Raid events
            await self.subscribe_websocket(
                topic="channel.raid",
                version="1",
                condition={"to_broadcaster_user_id": user_id},
            )
            logger.info("Subscribed to channel.raid events")

            # Stream Online/Offline events
            await self.subscribe_websocket(
                topic="stream.online",
                version="1",
                condition={"broadcaster_user_id": user_id},
            )
            await self.subscribe_websocket(
                topic="stream.offline",
                version="1",
                condition={"broadcaster_user_id": user_id},
            )
            logger.info("Subscribed to stream online/offline events")

            # Channel Update events
            await self.subscribe_websocket(
                topic="channel.update",
                version="2",
                condition={"broadcaster_user_id": user_id},
            )
            logger.info("Subscribed to channel.update events")

            self._eventsub_connected = True

        except Exception as e:
            logger.error(f"Error subscribing to EventSub events: {e}")

    async def event_follow(self, payload):
        """Handle channel follow events."""
        await self._create_event_from_payload("channel.follow", payload)

    async def event_subscription(self, payload):
        """Handle channel subscription events."""
        await self._create_event_from_payload("channel.subscribe", payload)

    async def event_subscription_gift(self, payload):
        """Handle channel subscription gift events."""
        await self._create_event_from_payload("channel.subscription.gift", payload)

    async def event_cheer(self, payload):
        """Handle channel cheer events."""
        await self._create_event_from_payload("channel.cheer", payload)

    async def event_raid(self, payload):
        """Handle channel raid events."""
        await self._create_event_from_payload("channel.raid", payload)

    async def event_stream_online(self, payload):
        """Handle stream online events."""
        await self._create_event_from_payload("stream.online", payload)

    async def event_stream_offline(self, payload):
        """Handle stream offline events."""
        await self._create_event_from_payload("stream.offline", payload)

    async def event_channel_update(self, payload):
        """Handle channel update events."""
        await self._create_event_from_payload("channel.update", payload)

    async def _create_event_from_payload(self, event_type: str, payload):
        """Create Event record and publish to Redis."""
        try:
            # Convert payload to dict for storage
            payload_dict = payload.__dict__.copy()

            # Extract user information for Member creation
            member = await self._get_or_create_member_from_payload(payload)

            # Create Event record in PostgreSQL
            event = await self._create_event(
                event_type=event_type,
                payload=payload_dict,
                member=member,
                source_id=getattr(payload, "id", None),
            )

            logger.info(
                f"Created event: {event_type} from {member.display_name if member else 'unknown'}"
            )

            # Publish to Redis for real-time delivery
            await self._publish_to_redis(event_type, event, member, payload_dict)

        except Exception as e:
            logger.error(f"Error creating event from {event_type} payload: {e}")

    async def _publish_to_redis(
        self,
        event_type: str,
        event: Event,
        member: Member | None,
        payload_dict: dict,
    ):
        """Publish event to Redis for real-time broadcasting."""
        try:
            redis_message = {
                "event_id": str(event.id),
                "event_type": event_type,
                "source": "twitch",
                "timestamp": event.timestamp.isoformat(),
                "member": {
                    "id": str(member.id),
                    "twitch_id": member.twitch_id,
                    "username": member.username,
                    "display_name": member.display_name,
                }
                if member
                else None,
                "payload": payload_dict,
            }

            # Publish to general events channel
            channel = "events:twitch"
            message_json = json.dumps(redis_message)

            # Use asyncio to run Redis publish in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._redis_client.publish, channel, message_json
            )

            logger.debug(f"Published {event_type} event to Redis channel: {channel}")

        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")

    async def _get_or_create_member_from_payload(self, payload) -> Member | None:
        """Extract Member information from EventSub payload."""
        # Try different user ID fields depending on event type
        twitch_id = (
            getattr(payload, "user_id", None)
            or getattr(payload, "from_broadcaster_user_id", None)
            or getattr(payload, "broadcaster_user_id", None)
        )

        username = (
            getattr(payload, "user_login", None)
            or getattr(payload, "from_broadcaster_user_login", None)
            or getattr(payload, "broadcaster_user_login", None)
        )

        display_name = (
            getattr(payload, "user_name", None)
            or getattr(payload, "from_broadcaster_user_name", None)
            or getattr(payload, "broadcaster_user_name", None)
        )

        if not twitch_id:
            return None

        try:
            # Try to get existing member
            member = await sync_to_async(Member.objects.get)(twitch_id=twitch_id)

            # Update display info if provided and different
            updated = False
            if display_name and member.display_name != display_name:
                member.display_name = display_name
                updated = True
            if username and member.username != username:
                member.username = username
                updated = True

            if updated:
                await sync_to_async(member.save)()

            return member

        except Member.DoesNotExist:
            # Create new member
            return await sync_to_async(Member.objects.create)(
                twitch_id=twitch_id,
                username=username or "",
                display_name=display_name or username or f"User_{twitch_id}",
            )

    async def _create_event(
        self,
        event_type: str,
        payload: dict,
        member: Member | None,
        source_id: str | None = None,
    ) -> Event:
        """Create Event record using sync_to_async."""
        return await sync_to_async(Event.objects.create)(
            source="twitch",
            source_id=source_id,
            event_type=event_type,
            member=member,
            payload=payload,
            timestamp=timezone.now(),
        )


async def main():
    """Main entry point for TwitchIO service."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting TwitchIO service...")

    # Check required settings
    if not settings.TWITCH_CLIENT_ID or not settings.TWITCH_CLIENT_SECRET:
        logger.error("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required")
        sys.exit(1)

    if not getattr(settings, "REDIS_URL", None):
        logger.error("REDIS_URL setting is required")
        sys.exit(1)

    try:
        # Create and start TwitchIO service
        service = TwitchService()
        logger.info("TwitchIO service created, starting client...")
        logger.info("Visit http://localhost:4343/oauth/callback to authorize")

        # Start the client (this will run indefinitely)
        await service.start()

    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in TwitchIO service: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
