from __future__ import annotations

import uuid

from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils import timezone

from streams.models import Session


class Transcription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Transcription content
    text = models.TextField()
    duration = models.FloatField(help_text="Duration in seconds")
    confidence = models.FloatField(
        null=True, blank=True, help_text="Transcription confidence score"
    )

    # Search capabilities
    search_vector = SearchVectorField(null=True, blank=True)

    # Session association (for date-based correlation)
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="transcriptions",
        null=True,
        blank=True,
    )

    # Source metadata
    source_file = models.CharField(max_length=255, null=True, blank=True)

    # Timing
    timestamp = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    # Optional correlation with events
    correlation_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["confidence"]),
            models.Index(fields=["correlation_id"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"Transcription: {preview} ({self.duration}s)"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
