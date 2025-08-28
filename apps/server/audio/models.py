from __future__ import annotations

import uuid

from django.db import models


class Session(models.Model):
    """Active session triggered by live/offline events."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Timeout management
    timeout_task_id = models.CharField(max_length=100, null=True, blank=True)
    timeout_started_at = models.DateTimeField(null=True, blank=True)

    # Configuration
    sample_rate = models.IntegerField(default=48000)
    channels = models.IntegerField(default=2)
    bit_depth = models.IntegerField(default=16)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_session",
            )
        ]

    def __str__(self):
        return f"Session {self.id}"


class Chunk(models.Model):
    """Raw chunk received from OBS."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="chunks"
    )
    timestamp = models.DateTimeField()
    source_id = models.CharField(max_length=100)
    source_name = models.CharField(max_length=200)
    data_size = models.IntegerField()

    # Audio format
    sample_rate = models.IntegerField()
    channels = models.IntegerField()
    bit_depth = models.IntegerField()

    # Processing status
    processed = models.BooleanField(default=False)
    processing_started = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["session", "timestamp"]),
            models.Index(fields=["processed"]),
        ]

    def __str__(self):
        return f"Chunk {self.id} ({self.source_id})"
