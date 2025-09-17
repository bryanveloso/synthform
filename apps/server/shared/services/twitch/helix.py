"""Helix service for imperative Twitch API calls."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import redis.asyncio as redis
import twitchio
from django.conf import settings

logger = logging.getLogger(__name__)


class HelixService:
    """Service for making imperative Twitch Helix API calls.

    This service provides methods to interact with Twitch's Helix API
    for operations that need to be performed on-demand, such as fetching
    reward redemption counts for the limit-break feature.
    """

    def __init__(self) -> None:
        self._client: Optional[twitchio.Client] = None
        self._broadcaster: Optional[twitchio.User] = None
        self._broadcaster_id: Optional[str] = None
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._redis: Optional[redis.Redis] = None
        self._last_init_attempt = 0
        self._init_backoff = 1  # Start with 1 second backoff
        self._max_backoff = 60  # Max 60 seconds between retries

    async def _get_redis(self) -> Optional[redis.Redis]:
        """Get or create Redis connection for caching."""
        if not self._redis:
            try:
                self._redis = redis.from_url(settings.REDIS_URL)
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"Could not connect to Redis for caching: {e}")
                self._redis = None
        return self._redis

    async def initialize(self) -> bool:
        """Initialize the Helix client with authentication, with retry logic."""
        async with self._init_lock:
            if self._initialized and self._client and self._broadcaster:
                return True

            # Check if we should retry based on backoff
            current_time = time.time()
            if self._last_init_attempt > 0:
                time_since_last = current_time - self._last_init_attempt
                if time_since_last < self._init_backoff:
                    logger.debug(
                        f"Waiting {self._init_backoff - time_since_last:.1f}s before retry"
                    )
                    return False

            self._last_init_attempt = current_time

            if self._client:
                try:
                    await self._client.close()
                except Exception:
                    pass
                self._client = None

        from authentication.services import AuthService

        try:
            # Get authentication service
            auth_service = AuthService("twitch")

            # Get the broadcaster's token
            tokens = await auth_service.get_all_tokens()
            if not tokens:
                logger.error("No tokens available for Helix API")
                return False

            # Get the first token (should be the broadcaster's)
            token_data = tokens[0]
            self._broadcaster_id = token_data["user_id"]

            # Create a TwitchIO client
            self._client = twitchio.Client(
                client_id=settings.TWITCH_CLIENT_ID,
                client_secret=settings.TWITCH_CLIENT_SECRET,
            )

            # Override load_tokens to load tokens from our database
            async def load_tokens(path=None):
                """Load tokens from database into TwitchIO."""
                for token in tokens:
                    await self._client.add_token(
                        token["access_token"], token.get("refresh_token")
                    )

            # Override save_tokens to prevent double-saving
            async def save_tokens():
                """No-op to prevent saving tokens (main service handles this)."""
                pass

            # Replace the methods
            self._client.load_tokens = load_tokens
            self._client.save_tokens = save_tokens

            # Now login which will call load_tokens
            await self._client.login()

            # Fetch the broadcaster User object - this will use the authenticated token
            users = await self._client.fetch_users(ids=[int(self._broadcaster_id)])
            if not users:
                logger.error(f"Could not fetch broadcaster user {self._broadcaster_id}")
                return False

            self._broadcaster = users[0]
            self._initialized = True

            # Reset backoff on successful initialization
            self._init_backoff = 1

            logger.info(
                f"Helix service initialized for broadcaster: {self._broadcaster.name} (ID: {self._broadcaster_id})"
            )
            return True

        except Exception as e:
            logger.error(f"Error initializing Helix service: {e}", exc_info=True)
            if self._client:
                try:
                    await self._client.close()
                except Exception:
                    pass
                self._client = None
            self._initialized = False

            # Increase backoff for next retry (exponential backoff)
            self._init_backoff = min(self._init_backoff * 2, self._max_backoff)

            return False

    async def get_reward_redemption_count(self, reward_id: str) -> int:
        """Get the count of pending redemptions for a specific channel points reward.

        Args:
            reward_id: The UUID of the channel points reward

        Returns:
            The number of pending redemptions in the queue
        """
        # Try to get from cache first
        cache_key = f"limitbreak:count:{reward_id}"
        redis_conn = await self._get_redis()

        if redis_conn:
            try:
                cached_value = await redis_conn.get(cache_key)
                if cached_value is not None:
                    cached_count = int(cached_value)
                    logger.debug(f"Using cached redemption count: {cached_count}")
                    # Return cached value while we try to update in background
                    asyncio.create_task(
                        self._update_count_in_background(reward_id, cache_key)
                    )
                    return cached_count
            except Exception as e:
                logger.warning(f"Error reading from cache: {e}")

        # If not cached or cache failed, try to fetch from API
        if not self._broadcaster:
            initialized = await self.initialize()
            if not initialized or not self._broadcaster:
                # Can't initialize, try to return last known value from cache
                if redis_conn:
                    try:
                        cached_value = await redis_conn.get(f"{cache_key}:fallback")
                        if cached_value is not None:
                            fallback_count = int(cached_value)
                            logger.warning(
                                f"Using fallback cached count: {fallback_count}"
                            )
                            return fallback_count
                    except Exception:
                        pass

                # No cache available, return 0 as safe default
                logger.error("Helix service unavailable and no cached value")
                return 0

        try:
            # Fetch the custom reward using the User object's method
            rewards = await self._broadcaster.fetch_custom_rewards(ids=[reward_id])

            if not rewards:
                logger.warning(f"Reward {reward_id} not found")
                return 0  # This is a valid case - reward doesn't exist

            reward = rewards[0]

            # Get redemptions for this reward
            count = 0
            async for _redemption in reward.fetch_redemptions(status="UNFULFILLED"):
                count += 1

            logger.debug(f"Reward {reward_id} has {count} pending redemptions")

            # Cache the result
            if redis_conn:
                try:
                    # Cache for configured TTL
                    cache_ttl = getattr(settings, "HELIX_CACHE_TTL", 30)
                    fallback_ttl = getattr(settings, "HELIX_CACHE_FALLBACK_TTL", 3600)
                    await redis_conn.set(cache_key, str(count), ex=cache_ttl)
                    # Also set a longer-lived fallback cache
                    await redis_conn.set(
                        f"{cache_key}:fallback", str(count), ex=fallback_ttl
                    )
                except Exception as e:
                    logger.warning(f"Error caching redemption count: {e}")

            return count

        except Exception as e:
            logger.error(
                f"Error fetching reward redemption count for {reward_id}: {e}",
                exc_info=True,
            )

            # Try to return cached value on error
            if redis_conn:
                try:
                    cached_value = await redis_conn.get(f"{cache_key}:fallback")
                    if cached_value is not None:
                        fallback_count = int(cached_value)
                        logger.warning(
                            f"API error, using fallback cached count: {fallback_count}"
                        )
                        return fallback_count
                except Exception:
                    pass

            # Return 0 as safe default
            return 0

    async def _update_count_in_background(self, reward_id: str, cache_key: str) -> None:
        """Background task to update the redemption count."""
        try:
            # Check if we should skip this update due to rate limiting
            redis_conn = await self._get_redis()
            if redis_conn:
                # Use Redis to track last update time across all instances
                rate_limit_key = f"limitbreak:update_lock:{reward_id}"
                # Try to set the lock with a 5-second TTL (only succeeds if key doesn't exist)
                lock_acquired = await redis_conn.set(rate_limit_key, "1", nx=True, ex=5)
                if not lock_acquired:
                    logger.debug(
                        f"Skipping background update for {reward_id} - another update in progress"
                    )
                    return

            # Only update if we're initialized
            if not self._broadcaster:
                return

            # Fetch fresh count from API
            rewards = await self._broadcaster.fetch_custom_rewards(ids=[reward_id])
            if not rewards:
                return

            reward = rewards[0]
            count = 0
            async for _redemption in reward.fetch_redemptions(status="UNFULFILLED"):
                count += 1

            # Update cache
            if redis_conn:
                cache_ttl = getattr(settings, "HELIX_CACHE_TTL", 30)
                fallback_ttl = getattr(settings, "HELIX_CACHE_FALLBACK_TTL", 3600)
                await redis_conn.set(cache_key, str(count), ex=cache_ttl)
                await redis_conn.set(
                    f"{cache_key}:fallback", str(count), ex=fallback_ttl
                )

            logger.debug(
                f"Background update: Reward {reward_id} has {count} redemptions"
            )

        except Exception as e:
            logger.error(
                f"Background update failed for reward {reward_id}: {e}", exc_info=True
            )

    async def fulfill_redemptions(
        self, reward_id: str, count: Optional[int] = None
    ) -> None:
        """Mark redemptions as fulfilled for a specific reward.

        Args:
            reward_id: The UUID of the channel points reward
            count: Number of redemptions to fulfill (None = all)
        """
        if not self._broadcaster:
            await self.initialize()
            if not self._broadcaster:
                logger.error("Helix service not properly initialized")
                return

        try:
            # Fetch the custom reward using the User object's method
            rewards = await self._broadcaster.fetch_custom_rewards(ids=[reward_id])

            if not rewards:
                logger.warning(f"Reward {reward_id} not found")
                return

            reward = rewards[0]

            # Get unfulfilled redemptions
            processed = 0
            async for redemption in reward.fetch_redemptions(status="UNFULFILLED"):
                if count is not None and processed >= count:
                    break

                # Update redemption status to FULFILLED
                await redemption.fulfill()
                logger.debug(f"Fulfilled redemption {redemption.id}")
                processed += 1

            if processed > 0:
                logger.info(f"Fulfilled {processed} redemptions for reward {reward_id}")
            else:
                logger.info(f"No unfulfilled redemptions for reward {reward_id}")

        except Exception as e:
            logger.error(f"Error fulfilling redemptions: {e}")

    async def close(self) -> None:
        """Close the Helix client connection."""
        if self._client:
            try:
                # Close the TwitchIO client to properly clean up aiohttp ClientSession
                await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing TwitchIO client: {e}")
            finally:
                self._client = None
                self._broadcaster = None
                self._broadcaster_id = None
                self._initialized = False
                logger.info("Helix service closed")


# Global instance
helix_service = HelixService()
