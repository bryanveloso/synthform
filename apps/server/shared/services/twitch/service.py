"""Lean TwitchIO adapter service for OAuth and EventSub routing."""

from __future__ import annotations

import asyncio
import logging
import os
import time

# Setup Django for standalone execution
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "synthform.settings")

import django

django.setup()

import sentry_sdk  # noqa: E402
import twitchio  # noqa: E402
from django.conf import settings  # noqa: E402
from twitchio import eventsub  # noqa: E402
from twitchio.exceptions import HTTPException  # noqa: E402
from twitchio.exceptions import InvalidTokenException  # noqa: E402
from twitchio.web.starlette_adapter import StarletteAdapter  # noqa: E402

from authentication.services import AuthService  # noqa: E402
from events.services.twitch import TwitchEventHandler  # noqa: E402

logger = logging.getLogger(__name__)


# Filter to suppress expected duplicate subscription errors during reconnection
class TwitchIODuplicateSubscriptionFilter(logging.Filter):
    """Suppress 'Disregarding HTTPException' errors that occur during EventSub reconnection."""

    def filter(self, record):
        # Allow all non-error messages through
        if record.levelno < logging.ERROR:
            return True
        # Suppress the specific duplicate subscription error
        if "Disregarding HTTPException in subscribe" in record.getMessage():
            return False
        # Allow all other errors through
        return True


# Configure TwitchIO logging to reduce noise
logging.getLogger("twitchio.authentication.tokens").setLevel(logging.WARNING)
logging.getLogger("twitchio.eventsub.websockets").setLevel(logging.WARNING)
# Filter out duplicate subscription errors (expected during reconnection)
logging.getLogger("twitchio.client").addFilter(TwitchIODuplicateSubscriptionFilter())


class TwitchService(twitchio.Client):
    """Lean TwitchIO adapter for OAuth callbacks and EventSub delegation."""

    def __init__(self):
        """Initialize TwitchIO client with StarletteAdapter."""
        super().__init__(
            client_id=settings.TWITCH_CLIENT_ID,
            client_secret=settings.TWITCH_CLIENT_SECRET,
            adapter=StarletteAdapter(
                domain=settings.EVENTSUB_DOMAIN,
                host="0.0.0.0",
                port=4343,
                eventsub_secret=settings.TWITCH_EVENTSUB_SECRET,
            ),
        )
        self._eventsub_connected = False
        self._event_handler = TwitchEventHandler()
        self._auth_service = AuthService("twitch")
        self._reconnect_attempts = 0
        self._reconnect_delay = 1  # Start with 1 second
        self._max_reconnect_delay = 300  # Max 5 minutes
        self._active_subscriptions = {}  # Track active subscriptions
        self._last_event_time = None  # Track last event received for health monitoring
        self._reconnecting = False  # Prevent concurrent reconnection attempts
        self._broadcaster_user_id = None  # Store broadcaster ID for reconnections
        self._background_tasks = set()  # Track background tasks
        self._processed_event_ids = set()  # Track recently processed event IDs for deduplication
        self._event_id_max_size = 1000  # Maximum event IDs to track

        # Redis client for health status tracking
        import redis.asyncio as redis

        self._redis = redis.Redis.from_url(settings.REDIS_URL or "redis://redis:6379/0")

        logger.info("[TwitchIO] Service initialized.")

    async def event_ready(self):
        """Called when the client is ready."""
        logger.info("[TwitchIO] Client ready.")

        # Load existing tokens from database and subscribe to events
        # Note: _load_existing_tokens() handles subscription, no need for separate call
        await self._load_existing_tokens()

        self._eventsub_connected = True
        self._reconnect_attempts = 0  # Reset on successful connection
        self._reconnect_delay = 1

        # Verify Redis connection and update health status
        try:
            await self._redis.ping()
            logger.info("[Redis] Connected to Redis.")
            await self._redis.set("eventsub:connected", "1")
            await self._redis.set("eventsub:reconnect_attempts", "0")
        except Exception as e:
            logger.error(f'[Redis] Failed to update health status. error="{str(e)}"')
            sentry_sdk.capture_exception(e)

        logger.info("[TwitchIO] EventSub connected and subscribed.")

        # Start heartbeat monitoring
        self._create_background_task(self._heartbeat_monitor())

        # Start daily reconnection scheduler
        self._create_background_task(self._daily_reconnection_scheduler())

    def _create_background_task(self, coro):
        """Create a background task with proper exception handling."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _heartbeat_monitor(self):
        """Monitor EventSub health and trigger reconnection if no events received."""
        # Wait 5 minutes before starting monitoring (allow initial setup)
        await asyncio.sleep(300)

        # Check every 2 minutes
        check_interval = 120
        # Reconnect if no events for 10 minutes (stream might be offline)
        max_silence = 600

        while True:
            try:
                await asyncio.sleep(check_interval)

                if not self._eventsub_connected:
                    continue

                if self._last_event_time is None:
                    # No events received yet, update timestamp
                    self._last_event_time = time.time()
                    continue

                time_since_last_event = time.time() - self._last_event_time

                # Log heartbeat status
                logger.debug(
                    f"[TwitchIO] Heartbeat check. seconds_since_last_event={int(time_since_last_event)}"
                )

                # Update heartbeat status in Redis for monitoring
                try:
                    await self._redis.set(
                        "eventsub:last_event_time", int(self._last_event_time), ex=3600
                    )
                    await self._redis.set(
                        "eventsub:seconds_since_last_event",
                        int(time_since_last_event),
                        ex=3600,
                    )
                except Exception as e:
                    logger.debug(
                        f'[Redis] Failed to update heartbeat. error="{str(e)}"'
                    )

                if time_since_last_event > max_silence:
                    # Only check during potential streaming hours (7am+ Pacific)
                    # This prevents false alarms overnight while still catching failures
                    from datetime import datetime
                    from zoneinfo import ZoneInfo

                    pacific_tz = ZoneInfo("America/Los_Angeles")
                    now_pacific = datetime.now(pacific_tz)

                    if now_pacific.hour < 7:
                        logger.debug(
                            f"[TwitchIO] No EventSub events, but it's {now_pacific.hour}:00 Pacific (before 7am). Skipping check."
                        )
                        # Update last_event_time to prevent repeated checks
                        self._last_event_time = time.time()
                        continue

                    logger.warning(
                        f"[TwitchIO] 🟡 No EventSub events received for {int(time_since_last_event)}s during streaming hours. Container restart recommended."
                    )

                    # Alert to Sentry
                    sentry_sdk.capture_message(
                        "EventSub silent failure detected - no events received",
                        level="warning",
                        extras={
                            "seconds_since_last_event": int(time_since_last_event),
                            "max_silence": max_silence,
                            "hour_pacific": now_pacific.hour,
                        },
                    )

                    # Mark as disconnected but don't auto-reconnect (prevents duplicate connections)
                    self._eventsub_connected = False
                    await self._redis.set("eventsub:connected", "0")
                    # Daily restart at 7am will handle recovery

            except asyncio.CancelledError:
                logger.info("[TwitchIO] Heartbeat monitor cancelled.")
                break
            except Exception as e:
                logger.error(
                    f'[TwitchIO] ❌ Error in heartbeat monitor. error="{str(e)}"'
                )
                sentry_sdk.capture_exception(e)
                # Continue monitoring despite errors
                await asyncio.sleep(check_interval)

    async def _daily_reconnection_scheduler(self):
        """Exit process daily at 7am Pacific to trigger container restart for fresh EventSub connection."""
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        import sys

        pacific_tz = ZoneInfo("America/Los_Angeles")

        while True:
            try:
                now = datetime.now(pacific_tz)

                # Calculate next 7am Pacific
                next_restart = now.replace(hour=7, minute=0, second=0, microsecond=0)
                if now >= next_restart:
                    # Already past 7am today, schedule for tomorrow
                    next_restart += timedelta(days=1)

                seconds_until_restart = (next_restart - now).total_seconds()
                logger.info(
                    f"[TwitchIO] Daily restart scheduled for {next_restart.strftime('%Y-%m-%d %H:%M %Z')} ({int(seconds_until_restart / 3600)}h {int((seconds_until_restart % 3600) / 60)}m)"
                )

                # Sleep until 7am Pacific
                await asyncio.sleep(seconds_until_restart)

                # Exit to trigger container restart
                logger.info("[TwitchIO] Daily scheduled restart at 7am Pacific. Exiting to restart container.")
                await self._redis.set("eventsub:connected", "0")
                sys.exit(0)

            except asyncio.CancelledError:
                logger.info("[TwitchIO] Daily restart scheduler cancelled.")
                break
            except Exception as e:
                logger.error(
                    f'[TwitchIO] ❌ Error in daily restart scheduler. error="{str(e)}"'
                )
                sentry_sdk.capture_exception(e)
                # Retry in 1 hour if error
                await asyncio.sleep(3600)

    async def event_oauth_authorized(
        self, payload: twitchio.OAuthAuthorizedPayload
    ) -> twitchio.ResponsePayload | None:
        """Handle OAuth authorization callbacks."""
        logger.info(f"[TwitchIO] OAuth authorized. user_id={payload.user_id}")

        try:
            # Save token to database through auth service
            await self._auth_service.save_token(
                user_id=payload.user_id,
                access_token=payload.access_token,
                refresh_token=payload.refresh_token,
                expires_in=payload.expires_in,
            )

            # Subscribe to events for this user
            await self._subscribe_to_events_for_user(payload.user_id)

            return twitchio.ResponsePayload(
                status=200,
                title="Authorization Successful",
                message="Your Twitch account has been connected successfully!",
            )
        except Exception as e:
            logger.error(f'[TwitchIO] OAuth authorization failed. error="{str(e)}"')
            return twitchio.ResponsePayload(
                status=500,
                title="Authorization Failed",
                message=f"Failed to save authorization: {str(e)}",
            )

    async def event_token_refreshed(self, payload: twitchio.TokenRefreshedPayload):
        """Handle token refresh events."""
        logger.info(f"[TwitchIO] Token refreshed. user_id={payload.user_id}")

        try:
            # Update token in database through auth service
            await self._auth_service.update_token(
                user_id=payload.user_id,
                access_token=payload.token,
                refresh_token=payload.refresh_token,
                expires_in=payload.expires_in,
            )
        except Exception as e:
            logger.error(
                f'[TwitchIO] Failed to update refreshed token. user_id={payload.user_id} error="{str(e)}"'
            )

    async def add_token(
        self,
        access_token,
        refresh_token=None,
        user_id=None,
        scopes=None,
        expires_at=None,
    ):
        """Override TwitchIO's add_token method to store in database."""
        # First call the parent method to maintain TwitchIO functionality
        result = await super().add_token(access_token, refresh_token)

        # Extract user_id using TwitchIO's fetch_users method if needed
        if not user_id:
            try:
                # Use TwitchIO's fetch_users to get current user info from the token
                users = await self.fetch_users()
                if users:
                    user_id = str(users[0].id)
                    # TwitchIO doesn't expose scopes/expires_at easily,
                    # so we'll rely on defaults for now
            except InvalidTokenException as token_error:
                logger.error(
                    f'[TwitchIO] Invalid token when fetching user. error="{str(token_error)}"'
                )
                return result
            except HTTPException as http_error:
                logger.error(
                    f'[TwitchIO] HTTP error fetching user. error="{str(http_error)}"'
                )
                return result
            except Exception as e:
                logger.error(f'[TwitchIO] Failed to fetch user info. error="{str(e)}"')
                return result

        # Save to database
        if user_id:
            # Save token using AuthService
            await self._auth_service.save_token(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=3600,  # Default expires_in
            )

        return result

    async def _load_existing_tokens(self):
        """Load existing tokens from database on startup."""
        try:
            tokens = await self._auth_service.get_all_tokens()

            valid_tokens = []
            for token_data in tokens:
                logger.info(
                    f"[TwitchIO] Loading token. user_id={token_data['user_id']}"
                )
                try:
                    # Call parent's add_token method directly - only takes access and refresh
                    await super().add_token(
                        token_data["access_token"], token_data["refresh_token"]
                    )
                    valid_tokens.append(token_data)
                    logger.info(
                        f"[TwitchIO] Loaded token from database. user_id={token_data['user_id']}"
                    )
                except Exception as e:
                    logger.error(
                        f'[TwitchIO] Failed to load token. user_id={token_data["user_id"]} error="{str(e)}"'
                    )

            # If we have valid tokens, automatically subscribe to events
            if valid_tokens:
                primary_token = valid_tokens[0]  # Use first valid token
                logger.info(
                    f"[TwitchIO] Subscribing to EventSub. user_id={primary_token['user_id']}"
                )
                await self._subscribe_to_events_for_user(str(primary_token["user_id"]))

            if tokens:
                logger.info(
                    f"[TwitchIO] Loaded valid tokens from database. count={len(valid_tokens)}"
                )
            else:
                logger.info("[TwitchIO] No existing tokens found.")

        except Exception as e:
            logger.error(f'[TwitchIO] Failed to load existing tokens. error="{str(e)}"')

    async def _subscribe_to_events(self):
        """Subscribe to EventSub events for authenticated users."""
        try:
            # This method is called after event_ready, check if we have a user
            if not self.user:
                logger.debug(
                    "[TwitchIO] No user context in client - subscriptions handled via loaded tokens."
                )
                return

            user_id = str(self.user.id)
            await self._subscribe_to_events_for_user(user_id)

        except Exception as e:
            logger.error(f'[TwitchIO] Failed to subscribe to events. error="{str(e)}"')

    async def _subscribe_to_events_for_user(self, user_id: str):
        """Subscribe to Twitch EventSub events for a specific user ID using subscription payload objects."""
        try:
            # Store broadcaster ID for reconnections
            self._broadcaster_user_id = user_id

            # Create subscription payload objects with the correct conditions
            subscriptions = [
                # Stream events
                eventsub.StreamOnlineSubscription(broadcaster_user_id=user_id),
                eventsub.StreamOfflineSubscription(broadcaster_user_id=user_id),
                # Channel information updates
                eventsub.ChannelUpdateSubscription(broadcaster_user_id=user_id),
                # Follow events
                eventsub.ChannelFollowSubscription(
                    broadcaster_user_id=user_id, moderator_user_id=user_id
                ),
                # Subscription events
                eventsub.ChannelSubscribeSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelSubscriptionEndSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelSubscriptionGiftSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelSubscribeMessageSubscription(
                    broadcaster_user_id=user_id
                ),
                # Bits/Cheer events
                eventsub.ChannelCheerSubscription(broadcaster_user_id=user_id),
                # Raid events
                eventsub.ChannelRaidSubscription(to_broadcaster_user_id=user_id),
                # Chat events
                eventsub.ChatClearSubscription(
                    broadcaster_user_id=user_id, user_id=user_id
                ),
                eventsub.ChatClearUserMessagesSubscription(
                    broadcaster_user_id=user_id, user_id=user_id
                ),
                eventsub.ChatMessageSubscription(
                    broadcaster_user_id=user_id, user_id=user_id
                ),
                eventsub.ChatNotificationSubscription(
                    broadcaster_user_id=user_id, user_id=user_id
                ),
                # Channel Points events
                eventsub.ChannelPointsRewardAddSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPointsRewardUpdateSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPointsRewardRemoveSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPointsRedeemAddSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPointsRedeemUpdateSubscription(
                    broadcaster_user_id=user_id
                ),
                # Poll events
                eventsub.ChannelPollBeginSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelPollProgressSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelPollEndSubscription(broadcaster_user_id=user_id),
                # Prediction events
                eventsub.ChannelPredictionBeginSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPredictionProgressSubscription(
                    broadcaster_user_id=user_id
                ),
                eventsub.ChannelPredictionLockSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelPredictionEndSubscription(broadcaster_user_id=user_id),
                # Charity events
                eventsub.CharityDonationSubscription(broadcaster_user_id=user_id),
                # Hype Train events - DISABLED: TwitchIO bug crashes on null shared_train_participants
                # TODO: Re-enable when TwitchIO fixes iteration over None in BaseHypeTrain.__init__
                # eventsub.HypeTrainBeginSubscription(broadcaster_user_id=user_id),
                # eventsub.HypeTrainProgressSubscription(broadcaster_user_id=user_id),
                # eventsub.HypeTrainEndSubscription(broadcaster_user_id=user_id),
                # Goal events
                eventsub.GoalBeginSubscription(broadcaster_user_id=user_id),
                eventsub.GoalProgressSubscription(broadcaster_user_id=user_id),
                eventsub.GoalEndSubscription(broadcaster_user_id=user_id),
                # Shoutout events
                eventsub.ShoutoutCreateSubscription(
                    broadcaster_user_id=user_id, moderator_user_id=user_id
                ),
                # VIP events
                eventsub.ChannelVIPAddSubscription(broadcaster_user_id=user_id),
                eventsub.ChannelVIPRemoveSubscription(broadcaster_user_id=user_id),
                # Ad break events
                eventsub.AdBreakBeginSubscription(broadcaster_user_id=user_id),
            ]

            for subscription in subscriptions:
                try:
                    sub_id = await self.subscribe_websocket(
                        subscription, token_for=user_id
                    )
                    # Track active subscription for reconnection
                    self._active_subscriptions[subscription.__class__.__name__] = {
                        "subscription": subscription,
                        "user_id": user_id,
                        "id": sub_id,
                    }
                    logger.info(
                        f"[TwitchIO] Subscribed to event. type={subscription.__class__.__name__}"
                    )
                    # Proactive rate limiting: small delay between subscriptions
                    await asyncio.sleep(0.15)
                except InvalidTokenException as token_error:
                    logger.error(
                        f'[TwitchIO] Invalid token when subscribing. type={subscription.__class__.__name__} error="{str(token_error)}"'
                    )
                except HTTPException as http_error:
                    error_message = str(http_error)

                    # Check for dead WebSocket session (happens during network outages)
                    if (
                        hasattr(http_error, "status")
                        and http_error.status == 400
                        and "websocket transport session does not exist"
                        in error_message
                    ):
                        logger.warning(
                            f"[TwitchIO] 🟡 WebSocket session expired during subscription. type={subscription.__class__.__name__}"
                        )
                        # Mark as disconnected to trigger reconnection
                        self._eventsub_connected = False
                        break  # Stop trying to subscribe with dead session
                    # Check for rate limiting
                    elif hasattr(http_error, "status") and http_error.status == 429:
                        logger.warning(
                            "[TwitchIO] 🟡 Rate limited, waiting before next subscription."
                        )
                        await asyncio.sleep(2)
                    else:
                        # Log other HTTP errors as actual errors
                        logger.error(
                            f'[TwitchIO] HTTP error when subscribing. type={subscription.__class__.__name__} error="{error_message}"'
                        )
                except Exception as e:
                    logger.error(
                        f'[TwitchIO] Failed to subscribe to event. type={subscription.__class__.__name__} error="{str(e)}"'
                    )

            self._eventsub_connected = True

        except Exception as e:
            logger.error(
                f'[TwitchIO] Failed to subscribe to events. user_id={user_id} error="{str(e)}"'
            )

    async def event_eventsub_notification_subscription_revoked(self, payload):
        """Handle EventSub subscription revocation."""
        logger.warning(f"[TwitchIO] EventSub subscription revoked. Container restart required. payload={payload}")

        # Alert to Sentry
        sentry_sdk.capture_message(
            "EventSub subscription revoked - container restart required",
            level="warning",
            extras={"payload": str(payload)},
        )

        # Mark as disconnected
        self._eventsub_connected = False

        # Update health status in Redis
        try:
            await self._redis.set("eventsub:connected", "0")
        except Exception as e:
            logger.error(
                f'[Redis] Failed to update health status. context=subscription_revoked error="{str(e)}"'
            )
            sentry_sdk.capture_exception(e)

    async def event_eventsub_notification_websocket_disconnect(self, payload):
        """Handle EventSub WebSocket disconnection."""
        logger.warning(f"[TwitchIO] EventSub WebSocket disconnected. Container restart required. payload={payload}")

        # Alert to Sentry on disconnect
        sentry_sdk.capture_message(
            "EventSub WebSocket disconnected - container restart required",
            level="warning",
            extras={"payload": str(payload)},
        )

        self._eventsub_connected = False

        # Update health status in Redis
        try:
            await self._redis.set("eventsub:connected", "0")
        except Exception as e:
            logger.error(
                f'[Redis] Failed to update health status. context=websocket_disconnect error="{str(e)}"'
            )
            sentry_sdk.capture_exception(e)

    async def event_eventsub_error(self, error):
        """Handle EventSub errors including 429 rate limit."""
        logger.error(f'[TwitchIO] ❌ EventSub error received. error="{str(error)}"')

        # Report to Sentry
        sentry_sdk.capture_message(
            f"EventSub error: {error}",
            level="error",
            extras={"error_details": str(error)},
        )

        # Check for rate limit or bad request errors
        if "429" in str(error) or "400" in str(error):
            logger.warning(
                "[TwitchIO] 🟡 EventSub connection issue detected. Container restart required."
            )
            self._eventsub_connected = False

    async def cleanup_subscriptions(self):
        """Clean up EventSub subscriptions on shutdown."""
        logger.info("[TwitchIO] Cleaning up EventSub subscriptions.")
        try:
            # Clear tracked subscriptions
            self._active_subscriptions.clear()
            self._eventsub_connected = False
            logger.info("[TwitchIO] EventSub subscriptions cleaned up.")
        except Exception as e:
            logger.error(
                f'[TwitchIO] Failed to clean up subscriptions. error="{str(e)}"'
            )

    async def _handle_reconnection(self):
        """Handle EventSub reconnection with exponential backoff."""
        # Prevent concurrent reconnection attempts
        if self._reconnecting:
            logger.debug("[TwitchIO] Reconnection already in progress, skipping.")
            return

        self._reconnecting = True
        self._reconnect_attempts += 1
        wait_time = min(self._reconnect_delay, self._max_reconnect_delay)

        # Update reconnect attempts in Redis
        try:
            await self._redis.set(
                "eventsub:reconnect_attempts", str(self._reconnect_attempts)
            )
        except Exception as e:
            logger.error(
                f'[Redis] Failed to update reconnect attempts. error="{str(e)}"'
            )
            sentry_sdk.capture_exception(e)

        logger.warning(
            f"[TwitchIO] 🟡 EventSub disconnected, attempting reconnection. attempt={self._reconnect_attempts} delay={wait_time}s"
        )

        # Alert to Sentry on attempt 3 and every 10 attempts after
        if self._reconnect_attempts == 3 or self._reconnect_attempts % 10 == 0:
            sentry_sdk.capture_message(
                f"EventSub reconnection attempt #{self._reconnect_attempts}",
                level="warning",
                extras={
                    "reconnect_attempts": self._reconnect_attempts,
                    "wait_time": wait_time,
                    "broadcaster_id": self._broadcaster_user_id,
                },
            )

        await asyncio.sleep(wait_time)
        self._reconnect_delay = min(
            self._reconnect_delay * 2, self._max_reconnect_delay
        )

        try:
            if not self._broadcaster_user_id:
                logger.error(
                    "[TwitchIO] ❌ No broadcaster ID stored, cannot reconnect."
                )
                self._reconnecting = False
                return

            logger.info("[TwitchIO] Closing existing EventSub WebSocket connections.")

            # Close existing EventSub websocket connections
            # TwitchIO manages these internally, we need to trigger cleanup
            if hasattr(self, "_eventsub") and self._eventsub:
                try:
                    # Access TwitchIO's internal EventSub websocket manager
                    if hasattr(self._eventsub, "_websockets"):
                        for ws in list(self._eventsub._websockets.values()):
                            try:
                                await ws.close()
                            except Exception:
                                pass
                except Exception as e:
                    logger.debug(
                        f'[TwitchIO] Error closing websockets. error="{str(e)}"'
                    )

            # Clear tracked subscriptions (will be recreated)
            self._active_subscriptions.clear()

            # Small delay to ensure cleanup completes
            await asyncio.sleep(1)

            logger.info("[TwitchIO] Re-subscribing to EventSub events.")
            # Re-subscribe to events - this will create a new WebSocket connection
            await self._subscribe_to_events_for_user(self._broadcaster_user_id)

            self._eventsub_connected = True
            self._reconnect_attempts = 0
            self._reconnect_delay = 1
            self._reconnecting = False

            # Update health status in Redis
            try:
                await self._redis.set("eventsub:connected", "1")
                await self._redis.set("eventsub:reconnect_attempts", "0")
            except Exception as e:
                logger.error(
                    f'[Redis] Failed to update health status. context=reconnection_success error="{str(e)}"'
                )
                sentry_sdk.capture_exception(e)

            logger.info("[TwitchIO] ✅ EventSub reconnected.")

        except Exception as e:
            logger.error(
                f'[TwitchIO] ❌ EventSub reconnection failed. error="{str(e)}"'
            )
            self._reconnecting = False

            # Alert Sentry on failure
            sentry_sdk.capture_exception(
                e,
                extras={
                    "reconnect_attempts": self._reconnect_attempts,
                    "broadcaster_id": self._broadcaster_user_id,
                },
            )

            # Schedule another reconnection attempt
            self._create_background_task(self._handle_reconnection())

    async def _safe_delegate(self, handler_method, payload, event_name: str):
        """Safely delegate events to handler with error handling."""
        try:
            # Deduplicate events by ID (handles multiple WebSocket connections)
            event_id = getattr(payload, 'id', None)
            if event_id:
                if event_id in self._processed_event_ids:
                    logger.debug(f"[TwitchIO] Duplicate event detected, skipping. event_id={event_id} type={event_name}")
                    return

                # Add to processed set
                self._processed_event_ids.add(event_id)

                # Limit set size to prevent memory growth
                if len(self._processed_event_ids) > self._event_id_max_size:
                    # Remove oldest half of events (FIFO approximation)
                    self._processed_event_ids = set(list(self._processed_event_ids)[self._event_id_max_size // 2:])

            # Track that we received an event (for health monitoring)
            self._last_event_time = time.time()

            # Update last event time in Redis
            try:
                await self._redis.set(
                    "eventsub:last_event_time", str(self._last_event_time)
                )
            except Exception as redis_err:
                logger.error(
                    f'[Redis] Failed to update last event time. error="{str(redis_err)}"'
                )
                # Don't capture to Sentry on every event - would be too noisy

            await handler_method(payload)
        except AttributeError as e:
            logger.error(
                f'[TwitchIO] Handler method not found. event={event_name} error="{str(e)}"'
            )
        except Exception as e:
            logger.error(
                f'[TwitchIO] Failed to handle event. event={event_name} error="{str(e)}"',
                exc_info=True,
            )
            # Don't re-raise to prevent breaking the event loop

    # EventSub event delegation methods with error handling
    async def event_follow(self, payload):
        """Delegate follow events to handler."""
        await self._safe_delegate(self._event_handler.event_follow, payload, "follow")

    async def event_subscription(self, payload):
        """Delegate subscription events to handler."""
        await self._safe_delegate(
            self._event_handler.event_subscription, payload, "subscription"
        )

    async def event_subscription_gift(self, payload):
        """Delegate subscription gift events to handler."""
        await self._safe_delegate(
            self._event_handler.event_subscription_gift, payload, "subscription_gift"
        )

    async def event_subscription_message(self, payload):
        """Delegate subscription message events to handler."""
        await self._safe_delegate(
            self._event_handler.event_subscription_message,
            payload,
            "subscription_message",
        )

    async def event_cheer(self, payload):
        """Delegate cheer events to handler."""
        await self._safe_delegate(self._event_handler.event_cheer, payload, "cheer")

    async def event_raid(self, payload):
        """Delegate raid events to handler."""
        await self._safe_delegate(self._event_handler.event_raid, payload, "raid")

    async def event_ban(self, payload):
        """Delegate ban events to handler."""
        await self._safe_delegate(self._event_handler.event_ban, payload, "ban")

    async def event_unban(self, payload):
        """Delegate unban events to handler."""
        await self._safe_delegate(self._event_handler.event_unban, payload, "unban")

    async def event_stream_online(self, payload):
        """Delegate stream online events to handler."""
        await self._safe_delegate(
            self._event_handler.event_stream_online, payload, "stream_online"
        )

    async def event_stream_offline(self, payload):
        """Delegate stream offline events to handler."""
        await self._safe_delegate(
            self._event_handler.event_stream_offline, payload, "stream_offline"
        )

    async def event_channel_update(self, payload):
        """Delegate channel update events to handler."""
        await self._safe_delegate(
            self._event_handler.event_channel_update, payload, "channel_update"
        )

    async def event_subscription_end(self, payload):
        """Delegate subscription end events to handler."""
        await self._safe_delegate(
            self._event_handler.event_subscription_end, payload, "subscription_end"
        )

    # Chat event delegation methods
    async def event_message(self, payload):
        """Delegate chat message events to handler."""
        await self._safe_delegate(
            self._event_handler.event_message, payload, "chat_message"
        )

    async def event_message_delete(self, payload):
        """Delegate message delete events to handler."""
        await self._safe_delegate(
            self._event_handler.event_message_delete,
            payload,
            "chat_message_delete",
        )

    async def event_chat_notification(self, payload):
        """Delegate chat notification events to handler."""
        await self._safe_delegate(
            self._event_handler.event_chat_notification, payload, "chat_notification"
        )

    async def event_chat_clear(self, payload):
        """Delegate chat clear events to handler."""
        await self._safe_delegate(
            self._event_handler.event_chat_clear, payload, "chat_clear"
        )

    async def event_chat_clear_user(self, payload):
        """Delegate chat clear user events to handler."""
        await self._safe_delegate(
            self._event_handler.event_chat_clear_user, payload, "chat_clear_user"
        )

    # Channel Points event delegation
    async def event_custom_reward_add(self, payload):
        """Delegate custom reward add events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_reward_add, payload, "custom_reward_add"
        )

    async def event_custom_reward_update(self, payload):
        """Delegate custom reward update events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_reward_update,
            payload,
            "custom_reward_update",
        )

    async def event_custom_reward_remove(self, payload):
        """Delegate custom reward remove events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_reward_remove,
            payload,
            "custom_reward_remove",
        )

    async def event_custom_redemption_add(self, payload):
        """Delegate custom redemption add events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_redemption_add,
            payload,
            "custom_redemption_add",
        )

    async def event_custom_redemption_update(self, payload):
        """Delegate custom redemption update events to handler."""
        await self._safe_delegate(
            self._event_handler.event_custom_redemption_update,
            payload,
            "custom_redemption_update",
        )

    # Poll event delegation
    async def event_poll_begin(self, payload):
        """Delegate poll begin events to handler."""
        await self._safe_delegate(
            self._event_handler.event_poll_begin, payload, "poll_begin"
        )

    async def event_poll_progress(self, payload):
        """Delegate poll progress events to handler."""
        await self._safe_delegate(
            self._event_handler.event_poll_progress, payload, "poll_progress"
        )

    async def event_poll_end(self, payload):
        """Delegate poll end events to handler."""
        await self._safe_delegate(
            self._event_handler.event_poll_end, payload, "poll_end"
        )

    # Prediction event delegation
    async def event_prediction_begin(self, payload):
        """Delegate prediction begin events to handler."""
        await self._safe_delegate(
            self._event_handler.event_prediction_begin, payload, "prediction_begin"
        )

    async def event_prediction_progress(self, payload):
        """Delegate prediction progress events to handler."""
        await self._safe_delegate(
            self._event_handler.event_prediction_progress,
            payload,
            "prediction_progress",
        )

    async def event_prediction_lock(self, payload):
        """Delegate prediction lock events to handler."""
        await self._safe_delegate(
            self._event_handler.event_prediction_lock, payload, "prediction_lock"
        )

    async def event_prediction_end(self, payload):
        """Delegate prediction end events to handler."""
        await self._safe_delegate(
            self._event_handler.event_prediction_end, payload, "prediction_end"
        )

    # Hype Train event delegation
    async def event_hype_train(self, payload):
        """Delegate hype train begin events to handler."""
        await self._safe_delegate(
            self._event_handler.event_hype_train_begin, payload, "hype_train_begin"
        )

    async def event_hype_train_progress(self, payload):
        """Delegate hype train progress events to handler."""
        await self._safe_delegate(
            self._event_handler.event_hype_train_progress,
            payload,
            "hype_train_progress",
        )

    async def event_hype_train_end(self, payload):
        """Delegate hype train end events to handler."""
        await self._safe_delegate(
            self._event_handler.event_hype_train_end, payload, "hype_train_end"
        )

    # Goal event delegation
    async def event_goal_begin(self, payload):
        """Delegate goal begin events to handler."""
        await self._safe_delegate(
            self._event_handler.event_goal_begin, payload, "goal_begin"
        )

    async def event_goal_progress(self, payload):
        """Delegate goal progress events to handler."""
        await self._safe_delegate(
            self._event_handler.event_goal_progress, payload, "goal_progress"
        )

    async def event_goal_end(self, payload):
        """Delegate goal end events to handler."""
        await self._safe_delegate(
            self._event_handler.event_goal_end, payload, "goal_end"
        )

    # Charity event delegation
    async def event_charity_campaign_donate(self, payload):
        """Delegate charity donation events to handler."""
        await self._safe_delegate(
            self._event_handler.event_charity_donation, payload, "charity_donation"
        )

    # Shoutout event delegation
    async def event_shoutout_create(self, payload):
        """Delegate shoutout create events to handler."""
        await self._safe_delegate(
            self._event_handler.event_shoutout_create, payload, "shoutout_create"
        )

    async def event_shoutout_receive(self, payload):
        """Delegate shoutout receive events to handler."""
        await self._safe_delegate(
            self._event_handler.event_shoutout_receive, payload, "shoutout_receive"
        )

    # VIP event delegation
    async def event_vip_add(self, payload):
        """Delegate VIP add events to handler."""
        await self._safe_delegate(self._event_handler.event_vip_add, payload, "vip_add")

    async def event_vip_remove(self, payload):
        """Delegate VIP remove events to handler."""
        await self._safe_delegate(
            self._event_handler.event_vip_remove, payload, "vip_remove"
        )

    # Ad break event delegation
    async def event_ad_break(self, payload):
        """Delegate ad break events to handler."""
        await self._safe_delegate(
            self._event_handler.event_ad_break, payload, "ad_break"
        )


async def main():
    """Run the TwitchIO adapter service."""
    service = TwitchService()

    try:
        logger.info("[TwitchIO] Service starting. port=4343")
        await service.start()
    except KeyboardInterrupt:
        logger.info("[TwitchIO] Received interrupt signal, shutting down.")
        await service.cleanup_subscriptions()
    except Exception as e:
        logger.error(f'[TwitchIO] ❌ Service error. error="{str(e)}"')
        await service.cleanup_subscriptions()
    finally:
        await service.close()
        logger.info("[TwitchIO] Service stopped.")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Enable TwitchIO debugging
    logging.getLogger("twitchio").setLevel(logging.DEBUG)
    logging.getLogger("twitchio.web").setLevel(logging.DEBUG)

    # Run the service
    asyncio.run(main())
