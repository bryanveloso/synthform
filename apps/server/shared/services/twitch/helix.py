"""Helix service for imperative Twitch API calls."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

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

    async def initialize(self) -> bool:
        """Initialize the Helix client with authentication."""
        async with self._init_lock:
            if self._initialized and self._client and self._broadcaster:
                return True

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
            return False

    async def get_reward_redemption_count(self, reward_id: str) -> int:
        """Get the count of pending redemptions for a specific channel points reward.

        Args:
            reward_id: The UUID of the channel points reward

        Returns:
            The number of pending redemptions in the queue
        """
        if not self._broadcaster:
            initialized = await self.initialize()
            if not initialized or not self._broadcaster:
                raise RuntimeError(
                    "Helix service failed to initialize - cannot fetch reward redemptions"
                )

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
            return count

        except Exception as e:
            logger.error(
                f"Error fetching reward redemption count for {reward_id}: {e}",
                exc_info=True,
            )
            raise  # Propagate the error for proper handling

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
