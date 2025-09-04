from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone
from encrypted_fields import EncryptedTextField


class Token(models.Model):
    """OAuth token model for storing service authentication tokens."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Service identification (e.g., 'twitch', 'discord', 'youtube')
    service = models.CharField(max_length=50, default="twitch", db_index=True)

    # External service user ID
    user_id = models.CharField(max_length=255, db_index=True)

    # OAuth tokens
    access_token = EncryptedTextField()
    refresh_token = EncryptedTextField(null=True, blank=True)

    # Token metadata
    expires_in = models.IntegerField(default=3600)  # Expiration in seconds
    last_refreshed = models.DateTimeField(default=timezone.now)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["service", "user_id"]]
        indexes = [
            models.Index(fields=["service", "user_id"]),
            models.Index(fields=["last_refreshed"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired based on expires_in and last_refreshed."""
        if not self.expires_in:
            return False
        expiry_time = self.last_refreshed + timedelta(seconds=self.expires_in)
        return timezone.now() > expiry_time

    @property
    def expires_at(self):
        """Calculate expiration datetime based on last_refreshed and expires_in."""
        if not self.expires_in:
            return None
        return self.last_refreshed + timedelta(seconds=self.expires_in)

    def __str__(self):
        return f"{self.service}:{self.user_id} (expires: {self.expires_at})"
