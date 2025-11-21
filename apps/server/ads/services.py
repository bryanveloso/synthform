from __future__ import annotations

import json
import logging
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx
import redis.asyncio as redis
from django.conf import settings
from django.utils import timezone

from authentication.models import Token

logger = logging.getLogger(__name__)

# Constants
AD_INTERVAL_MINUTES = 30
AD_DURATION_SECONDS = 90
AD_WARNING_SECONDS = 60
AD_RETRY_MINUTES = 5


class TwitchAdService:
    """Service for interacting with Twitch Ad APIs."""

    BASE_URL = "https://api.twitch.tv/helix"

    def __init__(self):
        self.client_id = settings.TWITCH_CLIENT_ID
        self.user_id = settings.TWITCH_USER_ID

    async def get_access_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        try:
            token = await Token.objects.aget(service="twitch", user_id=self.user_id)

            # Refresh if expired
            if token.is_expired:
                logger.info("Twitch token expired, refreshing...")
                token = await self.refresh_twitch_token(token)

            return token.access_token
        except Token.DoesNotExist:
            logger.error(f"No Twitch token found for user {self.user_id}")
            raise

    async def refresh_twitch_token(self, token: Token) -> Token:
        """Refresh an expired Twitch token."""
        url = "https://id.twitch.tv/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": self.client_id,
            "client_secret": settings.TWITCH_CLIENT_SECRET,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data)
                response.raise_for_status()

                token_data = response.json()

                # Update token
                token.access_token = token_data["access_token"]
                token.refresh_token = token_data.get(
                    "refresh_token", token.refresh_token
                )
                token.expires_in = token_data.get("expires_in", 3600)
                token.last_refreshed = timezone.now()
                await token.asave()

                logger.info("Successfully refreshed Twitch token")
                return token

            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to refresh token: {e.response.status_code}")
                raise

    async def start_commercial(self, duration_seconds: int = 90) -> dict[str, Any]:
        """
        Start a commercial on the channel.

        Args:
            duration_seconds: Ad duration (30, 60, 90, 120, 150, or 180)

        Returns:
            API response with commercial details
        """
        # Validate duration
        valid_durations = [30, 60, 90, 120, 150, 180]
        if duration_seconds not in valid_durations:
            duration_seconds = 90  # Default to 90 seconds
            logger.warning(f"Invalid ad duration, defaulting to {duration_seconds}s")

        access_token = await self.get_access_token()

        url = f"{self.BASE_URL}/channels/commercial"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
        }
        data = {"broadcaster_id": self.user_id, "length": duration_seconds}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()

                result = response.json()
                logger.info(f"Successfully started {duration_seconds}s commercial")
                return result

            except httpx.HTTPStatusError as e:
                error_msg = f"Failed to start commercial: {e.response.status_code} - {e.response.text}"
                logger.error(error_msg)
                raise


class AdScheduler:
    """Simple Redis-based ad scheduler for warning notifications."""

    def __init__(self):
        self.twitch_service = TwitchAdService()
        self.redis_url = settings.REDIS_URL
        self.redis: redis.Redis | None = None

    async def get_redis(self) -> redis.Redis:
        """Get Redis connection (singleton pattern)."""
        if self.redis is None:
            self.redis = redis.from_url(self.redis_url)
        return self.redis

    async def get_state(self) -> dict[str, Any]:
        """Get current ad state from Redis."""
        r = await self.get_redis()
        enabled = await r.get("ads:enabled")
        next_time = await r.get("ads:next_time")
        warning_active = await r.get("ads:warning_active")

        return {
            "enabled": enabled == b"true" if enabled else False,
            "next_time": next_time.decode() if next_time else None,
            "warning_active": warning_active == b"true" if warning_active else False,
        }

    async def set_next_ad_time(self, next_time: datetime | None = None) -> None:
        """Set the next ad time in Redis."""
        r = await self.get_redis()
        if next_time is None:
            # Default to AD_INTERVAL_MINUTES from now
            next_time = timezone.now() + timedelta(minutes=AD_INTERVAL_MINUTES)

        await r.set("ads:next_time", next_time.isoformat())
        logger.info(f"Next ad scheduled for {next_time}")

    async def enable(self) -> None:
        """Enable ad scheduling."""
        r = await self.get_redis()
        await r.set("ads:enabled", "true")
        await self.set_next_ad_time()
        logger.info("Ad scheduling enabled")

    async def disable(self) -> None:
        """Disable ad scheduling."""
        r = await self.get_redis()
        await r.set("ads:enabled", "false")
        await r.delete("ads:warning_active")
        await r.delete("ads:warning_lock")
        logger.info("Ad scheduling disabled")

    async def check_and_run_ad(self) -> bool:
        """
        Check if it's time to run an ad or send warnings.
        This runs every 10 seconds via Celery.
        """
        state = await self.get_state()

        if not state["enabled"]:
            return False

        # Check if stream is live
        r = await self.get_redis()
        stream_live = await r.get("stream:live")
        if stream_live != b"true":
            logger.debug("[Ads] Stream is not live, skipping ad check")
            return False

        # Check if ad has ended
        ad_end_time = await r.get("ads:end_time")
        if ad_end_time:
            end_time = datetime.fromisoformat(ad_end_time.decode())
            if end_time.tzinfo is None:
                logger.error(
                    f"Timezone-naive datetime found in ads:end_time: {ad_end_time}"
                )
                await r.delete("ads:end_time")
            elif timezone.now() >= end_time:
                # Ad has ended
                await r.publish("bot:ads", json.dumps({"type": "ad_ended"}))
                await r.delete("ads:end_time")
                logger.info("Ad ended notification sent")

        # Auto-initialize by scheduling first ad 5 minutes after stream goes live
        # This gives viewers time to join before running first ad to disable prerolls
        if not state["next_time"]:
            first_ad_time = timezone.now() + timedelta(minutes=5)
            await self.set_next_ad_time(first_ad_time)
            logger.info(
                "[Ads] Stream is live and ads enabled, first ad scheduled in 5 minutes"
            )
            return False

        next_time = datetime.fromisoformat(state["next_time"])

        # Validate timezone awareness
        if next_time.tzinfo is None:
            logger.error(
                f"Timezone-naive datetime found in Redis: {state['next_time']}"
            )
            await self.disable()
            return False

        now = timezone.now()
        seconds_until = (next_time - now).total_seconds()

        # Start warning at AD_WARNING_SECONDS with atomic lock
        if (
            seconds_until <= AD_WARNING_SECONDS
            and seconds_until > 0
            and not state["warning_active"]
        ):
            # Try to acquire lock to prevent race condition
            r = await self.get_redis()
            lock_acquired = await r.set("ads:warning_lock", "1", nx=True, ex=10)
            if lock_acquired:
                await self.start_warning()
                await r.delete("ads:warning_lock")
            else:
                logger.debug("Warning lock already held by another worker")
            return False

        # Update countdown if warning active
        if state["warning_active"] and seconds_until > 0:
            await self.broadcast_countdown(int(seconds_until))
            return False

        # Time to run the ad (with lock to prevent duplicate execution)
        if seconds_until <= 0:
            lock_acquired = await r.set("ads:run_lock", "1", nx=True, ex=120)
            if lock_acquired:
                await self.run_ad()
                return True
            else:
                logger.debug("[Ads] Ad run lock held by another worker, skipping")
                return False

        return False

    async def start_warning(self) -> None:
        """Start the warning countdown."""
        r = await self.get_redis()
        await r.set("ads:warning_active", "true")
        await self.broadcast_countdown(AD_WARNING_SECONDS)

        # Notify bot via Redis pub/sub
        await r.publish(
            "bot:ads",
            json.dumps({"type": "warning_start", "seconds": AD_WARNING_SECONDS}),
        )

        logger.info("Started ad warning countdown")

    async def broadcast_countdown(self, seconds: int) -> None:
        """Broadcast countdown to WebSocket clients."""
        r = await self.get_redis()
        message = {"type": "ads:warning", "payload": {"seconds": seconds}}

        # Broadcast to WebSocket consumers
        await r.publish("events:ads", json.dumps(message))

        # Also notify bot at key intervals
        if seconds in [60, 30, 10, 5]:
            await r.publish(
                "bot:ads", json.dumps({"type": "countdown", "seconds": seconds})
            )

    async def run_ad(self) -> None:
        """Run the ad and schedule the next one."""
        try:
            # Run the commercial
            await self.twitch_service.start_commercial(AD_DURATION_SECONDS)

            # Schedule next ad in AD_INTERVAL_MINUTES
            await self.set_next_ad_time()

            # Clear warning state and run lock
            r = await self.get_redis()
            await r.delete("ads:warning_active")
            await r.delete("ads:warning_lock")
            await r.delete("ads:run_lock")

            # Notify that ad is running
            message = {
                "type": "ads:running",
                "payload": {"duration": AD_DURATION_SECONDS},
            }
            await r.publish("events:ads", json.dumps(message))
            await r.publish(
                "bot:ads",
                json.dumps({"type": "ad_started", "duration": AD_DURATION_SECONDS}),
            )

            logger.info(f"Ad started, next ad in {AD_INTERVAL_MINUTES} minutes")

            # Store ad end time for notification
            ad_end_time = timezone.now() + timedelta(seconds=AD_DURATION_SECONDS)
            await r.set("ads:end_time", ad_end_time.isoformat())

        except Exception as e:
            logger.error(f"Failed to run ad: {e}")
            # Clear run lock on failure
            r = await self.get_redis()
            await r.delete("ads:run_lock")
            # Retry failed ad after AD_RETRY_MINUTES
            retry_time = timezone.now() + timedelta(minutes=AD_RETRY_MINUTES)
            await self.set_next_ad_time(retry_time)
            logger.info(
                f"Ad failed, retrying in {AD_RETRY_MINUTES} minutes at {retry_time}"
            )


# Singleton instances
twitch_ad_service = TwitchAdService()
ad_scheduler = AdScheduler()
