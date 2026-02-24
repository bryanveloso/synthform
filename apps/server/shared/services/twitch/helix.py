"""Simple Helix service that creates fresh connections per request."""

from __future__ import annotations

import logging

import redis.asyncio as redis
import twitchio
from django.conf import settings
from twitchio.exceptions import HTTPException, InvalidTokenException

logger = logging.getLogger(__name__)


class HelixService:
    """Service for making Twitch Helix API calls.

    Creates a fresh client for each request to avoid connection state issues.
    Uses Redis caching to minimize API calls.
    """

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis | None:
        """Get or create Redis connection for caching."""
        if not self._redis:
            try:
                self._redis = redis.from_url(settings.REDIS_URL)
                await self._redis.ping()
            except Exception as e:
                logger.warning(
                    f'[Helix] Could not connect to Redis for caching. error="{str(e)}"'
                )
                self._redis = None
        return self._redis

    async def _create_client(self) -> twitchio.Client | None:
        """Create a fresh TwitchIO client with authentication."""
        from authentication.services import AuthService

        try:
            # Get authentication service
            auth_service = AuthService("twitch")

            # Get the broadcaster's token
            tokens = await auth_service.get_all_tokens()
            if not tokens:
                logger.error("[Helix] No tokens available for Helix API.")
                return None

            # Create a new client
            client = twitchio.Client(
                client_id=settings.TWITCH_CLIENT_ID,
                client_secret=settings.TWITCH_CLIENT_SECRET,
            )

            # Load tokens from database
            for token in tokens:
                await client.add_token(
                    token["access_token"], token.get("refresh_token")
                )

            # Prevent TwitchIO from saving tokens (we handle that)
            async def save_tokens():
                pass

            client.save_tokens = save_tokens

            # Login to initialize the client
            await client.login()

            return client

        except InvalidTokenException as e:
            # TwitchIO wraps 429 in InvalidTokenException - check original cause
            original = getattr(e, "original", None)
            if isinstance(original, HTTPException) and getattr(original, "status", None) == 429:
                logger.warning("[Helix] Rate limited by Twitch API. Using cached fallback.")
                return None
            logger.error(
                f'[Helix] Invalid token error. error="{str(e)}"', exc_info=True
            )
            return None
        except HTTPException as e:
            # Handle rate limiting gracefully - don't treat as error
            if hasattr(e, "status") and e.status == 429:
                logger.warning("[Helix] Rate limited by Twitch API. Using cached fallback.")
                return None
            logger.error(
                f'[Helix] HTTP error creating Helix client. error="{str(e)}"', exc_info=True
            )
            return None
        except Exception as e:
            logger.error(
                f'[Helix] Error creating Helix client. error="{str(e)}"', exc_info=True
            )
            return None

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
                    logger.debug(
                        f"[Helix] Using cached redemption count. value={cached_value}"
                    )
                    return int(cached_value)
            except Exception as e:
                logger.warning(f'[Helix] Error reading from cache. error="{str(e)}"')

        # Create a fresh client for this request
        client = await self._create_client()
        if not client:
            # Return cached fallback if available
            if redis_conn:
                try:
                    cached_value = await redis_conn.get(f"{cache_key}:fallback")
                    if cached_value is not None:
                        logger.warning(
                            f"[Helix] Using fallback cached count. value={cached_value}"
                        )
                        return int(cached_value)
                except Exception:
                    pass
            return 0

        try:
            # Get the broadcaster ID from the first token
            from authentication.services import AuthService

            auth_service = AuthService("twitch")
            tokens = await auth_service.get_all_tokens()
            if not tokens:
                return 0

            broadcaster_id = tokens[0]["user_id"]

            # Fetch the broadcaster user
            users = await client.fetch_users(ids=[int(broadcaster_id)])
            if not users:
                logger.warning(
                    f"[Helix] Could not fetch broadcaster user. broadcaster_id={broadcaster_id}"
                )
                return 0

            broadcaster = users[0]

            # Fetch the custom reward
            rewards = await broadcaster.fetch_custom_rewards(ids=[reward_id])
            if not rewards:
                logger.warning(f"[Helix] Reward not found. reward_id={reward_id}")
                return 0

            reward = rewards[0]

            # Count unfulfilled redemptions
            count = 0
            async for _redemption in reward.fetch_redemptions(status="UNFULFILLED"):
                count += 1

            logger.debug(
                f"[Helix] Reward redemption count. reward_id={reward_id} count={count}"
            )

            # Cache the result
            if redis_conn:
                try:
                    cache_ttl = getattr(settings, "HELIX_CACHE_TTL", 30)
                    fallback_ttl = getattr(settings, "HELIX_CACHE_FALLBACK_TTL", 3600)
                    await redis_conn.set(cache_key, str(count), ex=cache_ttl)
                    await redis_conn.set(
                        f"{cache_key}:fallback", str(count), ex=fallback_ttl
                    )
                except Exception as e:
                    logger.warning(
                        f'[Helix] Error caching redemption count. error="{str(e)}"'
                    )

            return count

        except Exception as e:
            logger.error(
                f'[Helix] Error fetching reward redemption count. reward_id={reward_id} error="{str(e)}"',
                exc_info=True,
            )

            # Try to return cached fallback value on error
            if redis_conn:
                try:
                    cached_value = await redis_conn.get(f"{cache_key}:fallback")
                    if cached_value is not None:
                        logger.warning(
                            f"[Helix] API error, using fallback cached count. value={cached_value}"
                        )
                        return int(cached_value)
                except Exception:
                    pass

            return 0

        finally:
            # Always close the client
            try:
                await client.close()
            except Exception as e:
                logger.warning(
                    f'[Helix] Error closing TwitchIO client. error="{str(e)}"'
                )

    async def fulfill_redemptions(
        self, reward_id: str, count: int | None = None
    ) -> None:
        """Mark redemptions as fulfilled for a specific reward.

        Args:
            reward_id: The UUID of the channel points reward
            count: Number of redemptions to fulfill (None = all)
        """
        client = await self._create_client()
        if not client:
            logger.error("[Helix] Could not create Helix client.")
            return

        try:
            # Get the broadcaster ID
            from authentication.services import AuthService

            auth_service = AuthService("twitch")
            tokens = await auth_service.get_all_tokens()
            if not tokens:
                return

            broadcaster_id = tokens[0]["user_id"]

            # Fetch the broadcaster user
            users = await client.fetch_users(ids=[int(broadcaster_id)])
            if not users:
                logger.warning(
                    f"[Helix] Could not fetch broadcaster user. broadcaster_id={broadcaster_id}"
                )
                return

            broadcaster = users[0]

            # Fetch the custom reward
            rewards = await broadcaster.fetch_custom_rewards(ids=[reward_id])
            if not rewards:
                logger.warning(f"[Helix] Reward not found. reward_id={reward_id}")
                return

            reward = rewards[0]

            # Get unfulfilled redemptions and fulfill them
            processed = 0
            async for redemption in reward.fetch_redemptions(status="UNFULFILLED"):
                if count is not None and processed >= count:
                    break

                await redemption.fulfill()
                logger.debug(
                    f"[Helix] Redemption fulfilled. redemption_id={redemption.id}"
                )
                processed += 1

            if processed > 0:
                logger.info(
                    f"[Helix] Redemptions fulfilled. reward_id={reward_id} count={processed}"
                )
            else:
                logger.info(
                    f"[Helix] No unfulfilled redemptions. reward_id={reward_id}"
                )

        except Exception as e:
            logger.error(
                f'[Helix] Error fulfilling redemptions. error="{str(e)}"', exc_info=True
            )

        finally:
            # Always close the client
            try:
                await client.close()
            except Exception as e:
                logger.warning(
                    f'[Helix] Error closing TwitchIO client. error="{str(e)}"'
                )


# Global instance
helix_service = HelixService()
