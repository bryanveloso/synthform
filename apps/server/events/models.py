from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


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
        db_table = "members"
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
    source_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)

    # Member association (nullable for anonymous events)
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, null=True, blank=True, related_name="events"
    )

    # Event payload
    payload = models.JSONField(default=dict)

    # Timing
    timestamp = models.DateTimeField(db_index=True)
    correlation_id = models.UUIDField(null=True, blank=True, db_index=True)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "events"
        indexes = [
            models.Index(fields=["source", "event_type"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["member", "timestamp"]),
            models.Index(fields=["correlation_id"]),
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
