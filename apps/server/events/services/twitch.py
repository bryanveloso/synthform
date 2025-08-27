from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import aiohttp
import redis
import twitchio
import twitchio.eventsub as eventsub
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone
from twitchio.web.starlette_adapter import StarletteAdapter

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
from events.models import Token  # noqa: E402

logger = logging.getLogger(__name__)


class DebugStarletteAdapter(StarletteAdapter):
    """StarletteAdapter with additional debugging."""

    async def oauth_callback(self, request):
        """Override oauth callback to add debugging."""
        try:
            logger.debug("Starting OAuth callback processing...")
            result = await super().oauth_callback(request)
            logger.debug(f"OAuth callback result: {result}")
            return result
        except Exception as e:
            logger.error(f"Exception in oauth_callback: {e}", exc_info=True)
            raise


class TwitchService(twitchio.Client):
    """Standalone TwitchIO service for handling EventSub events."""

    def __init__(self):
        super().__init__(
            client_id=settings.TWITCH_CLIENT_ID,
            client_secret=settings.TWITCH_CLIENT_SECRET,
            adapter=DebugStarletteAdapter(
                domain="twitch.avalonstar.dev",
                host="0.0.0.0",
                port=4343,
                eventsub_secret=settings.TWITCH_EVENTSUB_SECRET,
            ),
        )
        self._eventsub_connected = False
        self._redis_client = redis.Redis.from_url(
            settings.REDIS_URL or "redis://redis:6379/0"
        )

    async def event_ready(self):
        """Called when the client is ready."""
        user_info = f"User: {self.user.id if self.user else 'No user logged in'}"
        logger.info(f"TwitchIO client ready. {user_info}")

        # Load existing tokens from database
        await self._load_existing_tokens()

        # Only subscribe to events if user is logged in
        if self.user:
            await self._subscribe_to_events()
        else:
            logger.info("Waiting for OAuth authorization to subscribe to events")

    async def event_oauth_authorized(self, payload):
        """Handle OAuth authorization events."""
        try:
            logger.info(f"OAuth authorized for user: {payload.user_id}")

            # Add the user token to the client's token management
            try:
                logger.info("Adding user token to client...")
                await self.add_token(payload.access_token, payload.refresh_token)
                logger.info("User token added successfully")
            except Exception as token_error:
                logger.error(f"Error adding user token: {token_error}")

            # Fetch user info manually since TwitchIO client.user isn't being populated
            try:
                user_info = await self.fetch_users(ids=[payload.user_id])
                if user_info:
                    user = user_info[0]
                    logger.info(f"Fetched user info: {user.name} (ID: {user.id})")

                    # Subscribe to events now that we have user info and token
                    logger.info("User authorized, subscribing to EventSub events...")
                    await self._subscribe_to_events_for_user(str(user.id))
                else:
                    logger.error("Failed to fetch user info")
            except Exception as user_fetch_error:
                logger.error(f"Error fetching user info: {user_fetch_error}")

        except Exception as e:
            logger.error(f"Error in event_oauth_authorized: {e}", exc_info=True)

    async def event_token_refreshed(self, payload):
        """Handle token refresh events."""
        logger.info(f"Token refreshed for user: {payload.user_id}")
        # Update token in database
        await self._save_token_to_db(
            user_id=payload.user_id,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            expires_at=payload.expires_at,
            scopes=payload.scopes,
        )

    async def add_token(
        self, access_token, refresh_token=None, user_id=None, scopes=None
    ):
        """Override TwitchIO's add_token method to store in database."""
        # First call the parent method to maintain TwitchIO functionality
        result = await super().add_token(access_token, refresh_token)

        # Extract user_id from token if not provided
        if not user_id:
            try:
                # Validate token and get user info
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Client-ID": settings.TWITCH_CLIENT_ID,
                }
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.twitch.tv/helix/users", headers=headers
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"):
                                user_id = data["data"][0]["id"]
            except Exception as e:
                logger.error(f"Failed to extract user_id from token: {e}")
                return result

        # Save to database
        if user_id:
            await self._save_token_to_db(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                scopes=scopes or [],
            )

        return result

    async def _save_token_to_db(
        self, user_id, access_token, refresh_token=None, expires_at=None, scopes=None
    ):
        """Save or update token in database."""
        try:
            # Try to get existing token
            try:
                token = await sync_to_async(Token.objects.get)(
                    platform="twitch", user_id=user_id
                )
                # Update existing token
                token.access_token = access_token
                if refresh_token:
                    token.refresh_token = refresh_token
                if expires_at:
                    token.expires_at = expires_at
                if scopes is not None:
                    token.scopes = scopes
                await sync_to_async(token.save)()
                logger.info(f"Updated token for user {user_id} in database")
            except Token.DoesNotExist:
                # Create new token
                token = await sync_to_async(Token.objects.create)(
                    platform="twitch",
                    user_id=user_id,
                    access_token=access_token,
                    refresh_token=refresh_token or "",
                    expires_at=expires_at,
                    scopes=scopes or [],
                )
                logger.info(f"Created new token for user {user_id} in database")
        except Exception as e:
            logger.error(f"Error saving token to database: {e}")

    async def _load_existing_tokens(self):
        """Load existing tokens from database and add them to TwitchIO client."""
        try:
            tokens = await sync_to_async(list)(Token.objects.filter(platform="twitch"))

            for token in tokens:
                if not token.is_expired:
                    try:
                        # Add token to TwitchIO's internal storage
                        # Call parent's add_token method directly to avoid recursion
                        await super().add_token(token.access_token, token.refresh_token)
                        logger.info(
                            f"Loaded token for user {token.user_id} from database"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error loading token for user {token.user_id}: {e}"
                        )
                else:
                    logger.warning(
                        f"Token for user {token.user_id} has expired, skipping"
                    )

            logger.info(
                f"Loaded {len([t for t in tokens if not t.is_expired])} valid tokens from database"
            )

        except Exception as e:
            logger.error(f"Error loading tokens from database: {e}")

    async def _subscribe_to_events(self):
        """Subscribe to Twitch EventSub events."""
        try:
            if not self.user:
                logger.warning("No user logged in, cannot subscribe to events")
                return

            user_id = str(self.user.id)
            await self._subscribe_to_events_for_user(user_id)
        except Exception as e:
            logger.error(f"Error in _subscribe_to_events: {e}")

    async def _subscribe_to_events_for_user(self, user_id: str):
        """Subscribe to Twitch EventSub events for a specific user ID using subscription payload objects."""
        try:
            # Create subscription payload objects with the correct conditions
            subscriptions = [
                eventsub.ChannelFollowSubscription(
                    broadcaster_user_id=user_id, moderator_user_id=user_id
                ),
                eventsub.ChannelSubscribeSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelSubscriptionGiftSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelCheerSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelRaidSubscription(to_broadcaster_user_id=user_id),
                eventsub.StreamOnlineSubscription(broadcaster_user_id=user_id),
                eventsub.StreamOfflineSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelUpdateSubscription(broadcaster_user_id=user_id),
            ]

            for subscription in subscriptions:
                try:
                    await self.subscribe_websocket(subscription, token_for=user_id)
                    logger.info(
                        f"Successfully subscribed to {subscription.__class__.__name__}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to subscribe to {subscription.__class__.__name__}: {e}"
                    )

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
    # Setup logging with stdio debugging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Enable TwitchIO debugging
    logging.getLogger("twitchio").setLevel(logging.DEBUG)
    logging.getLogger("twitchio.web").setLevel(logging.DEBUG)
    logging.getLogger("twitchio.authentication").setLevel(logging.DEBUG)

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

        # Define required scopes
        scopes = [
            "bits:read",
            "channel:bot",
            "channel:edit:commercial",
            "channel:manage:ads",
            "channel:manage:redemptions",
            "channel:manage:videos",
            "channel:read:ads",
            "channel:read:charity",
            "channel:read:goals",
            "channel:read:guest_star",
            "channel:read:hype_train",
            "channel:read:polls",
            "channel:read:predictions",
            "channel:read:redemptions",
            "channel:read:subscriptions",
            "channel:read:vips",
            "chat:edit",
            "chat:read",
            "clips:edit",
            "moderator:manage:announcements",
            "moderator:read:chat_settings",
            "moderator:read:followers",
            "moderator:read:shoutouts",
            "user:bot",
            "user:read:chat",
            "user:write:chat",
        ]

        # Generate OAuth URL using twitchio.authentication.OAuth
        oauth = twitchio.authentication.OAuth(
            client_id=settings.TWITCH_CLIENT_ID,
            client_secret=settings.TWITCH_CLIENT_SECRET,
            redirect_uri="https://twitch.avalonstar.dev/oauth/callback",
            # redirect_uri="http://localhost:4343/oauth/callback",
            scopes=twitchio.Scopes(scopes),
        )
        oauth_url = oauth.get_authorization_url()

        logger.info("=" * 80)
        logger.info("TWITCH OAUTH AUTHORIZATION REQUIRED")
        logger.info("=" * 80)
        logger.info("To authorize this application, visit:")
        logger.info(f"{oauth_url}")
        logger.info("=" * 80)

        # Start the client
        await service.start()

    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in TwitchIO service: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
