"""Authentication service for managing OAuth tokens."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from asgiref.sync import sync_to_async
from django.utils import timezone

from .models import Token

logger = logging.getLogger(__name__)


class AuthService:
    """Service for managing OAuth tokens across different platforms."""

    def __init__(self, service_name: str = "twitch"):
        """Initialize auth service for a specific platform.

        Args:
            service_name: Name of the service (e.g., 'twitch', 'discord')
        """
        self.service_name = service_name

    async def save_token(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str | None = None,
        expires_in: int = 3600,
    ) -> Token:
        """Save or update a token for a user.

        Args:
            user_id: External service user ID
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_in: Token expiration time in seconds

        Returns:
            Token: The saved token object
        """
        try:
            token, created = await sync_to_async(Token.objects.update_or_create)(
                service=self.service_name,
                user_id=user_id,
                defaults={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": expires_in,
                    "last_refreshed": timezone.now(),
                },
            )

            action = "created" if created else "updated"
            logger.info(f"Token {action} for {self.service_name}:{user_id}")
            return token

        except Exception as e:
            logger.error(f"Error saving token for {self.service_name}:{user_id}: {e}")
            raise

    async def get_token(self, user_id: str) -> Token | None:
        """Get a token for a specific user.

        Args:
            user_id: External service user ID

        Returns:
            Token or None if not found
        """
        try:
            return await sync_to_async(Token.objects.get)(
                service=self.service_name, user_id=user_id
            )
        except Token.DoesNotExist:
            logger.debug(f"No token found for {self.service_name}:{user_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting token for {self.service_name}:{user_id}: {e}")
            return None

    async def get_all_tokens(self) -> list[dict[str, Any]]:
        """Get all tokens for this service.

        Returns:
            List of token dictionaries
        """
        try:
            tokens = await sync_to_async(list)(
                Token.objects.filter(service=self.service_name).values(
                    "user_id",
                    "access_token",
                    "refresh_token",
                    "expires_in",
                    "last_refreshed",
                )
            )
            logger.info(f"Retrieved {len(tokens)} tokens for {self.service_name}")
            return tokens
        except Exception as e:
            logger.error(f"Error getting all tokens for {self.service_name}: {e}")
            return []

    async def update_token(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str | None = None,
        expires_in: int | None = None,
    ) -> bool:
        """Update an existing token.

        Args:
            user_id: External service user ID
            access_token: New access token
            refresh_token: New refresh token (optional)
            expires_in: Token expiration time in seconds (optional)

        Returns:
            bool: True if updated successfully
        """
        try:
            update_data = {
                "access_token": access_token,
                "last_refreshed": timezone.now(),
            }

            if refresh_token is not None:
                update_data["refresh_token"] = refresh_token
            if expires_in is not None:
                update_data["expires_in"] = expires_in

            updated_count = await sync_to_async(
                Token.objects.filter(service=self.service_name, user_id=user_id).update
            )(**update_data)

            if updated_count > 0:
                logger.info(f"Token updated for {self.service_name}:{user_id}")
                return True
            else:
                logger.warning(
                    f"No token found to update for {self.service_name}:{user_id}"
                )
                return False

        except Exception as e:
            logger.error(f"Error updating token for {self.service_name}:{user_id}: {e}")
            return False

    async def delete_token(self, user_id: str) -> bool:
        """Delete a token for a user.

        Args:
            user_id: External service user ID

        Returns:
            bool: True if deleted successfully
        """
        try:
            deleted_count, _ = await sync_to_async(
                Token.objects.filter(service=self.service_name, user_id=user_id).delete
            )()

            if deleted_count > 0:
                logger.info(f"Token deleted for {self.service_name}:{user_id}")
                return True
            else:
                logger.warning(
                    f"No token found to delete for {self.service_name}:{user_id}"
                )
                return False

        except Exception as e:
            logger.error(f"Error deleting token for {self.service_name}:{user_id}: {e}")
            return False

    async def get_active_tokens(self) -> list[dict[str, Any]]:
        """Get all non-expired tokens for this service.

        Returns:
            List of active token dictionaries
        """
        try:
            all_tokens = await self.get_all_tokens()
            active_tokens = []

            for token_data in all_tokens:
                # Check if token is likely still valid
                last_refreshed = token_data.get("last_refreshed")
                expires_in = token_data.get("expires_in", 3600)

                if last_refreshed:
                    expiry_time = last_refreshed + timedelta(seconds=expires_in)
                    if timezone.now() < expiry_time:
                        active_tokens.append(token_data)

            logger.info(
                f"Found {len(active_tokens)} active tokens for {self.service_name}"
            )
            return active_tokens

        except Exception as e:
            logger.error(f"Error getting active tokens for {self.service_name}: {e}")
            return []
