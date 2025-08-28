from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone
from encrypted_fields import EncryptedTextField

from streams.models import Session


class Member(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Platform-specific member IDs
    twitch_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )
    youtube_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )
    discord_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )

    # Member display information
    display_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["twitch_id"]),
            models.Index(fields=["created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_name} ({self.username or 'no username'})"


class Event(models.Model):
    SOURCES = [
        ("twitch", "Twitch"),
        ("patreon", "Patreon"),
        ("discord", "Discord"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Event identification
    source = models.CharField(max_length=20, choices=SOURCES, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)

    # Member association (nullable for anonymous events)
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, null=True, blank=True, related_name="events"
    )

    # Session association (for date-based correlation)
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )

    # Event payload
    payload = models.JSONField(default=dict)

    # Timing
    timestamp = models.DateTimeField(db_index=True)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["source", "event_type"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["member", "timestamp"]),
        ]
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def amount(self):
        """Extract monetary amount from various event types."""
        if self.source == "twitch":
            return self.payload.get("bits", 0) or self.payload.get("amount", 0)
        elif self.source in ["patreon"]:
            return self.payload.get("amount", 0)
        return 0

    @property
    def message(self):
        """Extract message text from event payload."""
        return self.payload.get("message", "") or self.payload.get("text", "")

    @property
    def username(self):
        """Extract username from event payload."""
        return (
            self.payload.get("user_login")
            or self.payload.get("user_name")
            or self.payload.get("username", "")
        )

    def __str__(self):
        member_info = f" from {self.member.display_name}" if self.member else ""
        return f"{self.source}.{self.event_type}{member_info} at {self.timestamp}"


class Token(models.Model):
    PLATFORMS = [
        ("twitch", "Twitch"),
        ("youtube", "YouTube"),
        ("discord", "Discord"),
    ]

    # Platform and user identification
    platform = models.CharField(
        max_length=20, choices=PLATFORMS, default="twitch", db_index=True
    )
    user_id = models.CharField(max_length=255, db_index=True)  # Platform user ID

    # Token data (encrypted)
    access_token = EncryptedTextField()
    refresh_token = EncryptedTextField()
    expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("platform", "user_id")]
        indexes = [
            models.Index(fields=["platform", "user_id"]),
            models.Index(fields=["platform", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if the token is expired."""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.platform} token for user {self.user_id}"
