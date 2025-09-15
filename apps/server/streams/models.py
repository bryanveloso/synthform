from __future__ import annotations

import uuid

from django.db import models


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_date = models.DateField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def stream_session_id(self):
        """Generates the stream_YYYY_MM_DD format from the session_date."""
        return f"stream_{self.session_date.strftime('%Y_%m_%d')}"

    def __str__(self):
        return self.stream_session_id

    class Meta:
        ordering = ["-session_date"]


class Status(models.Model):
    """
    Singleton model for stream status.
    Only one Status record should exist at a time.
    """

    STATUS_CHOICES = [
        ("online", "Online"),
        ("away", "Away"),
        ("busy", "Busy"),
        ("brb", "Be Right Back"),
        ("focus", "Focus Mode"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="online")
    message = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom message to display with the status",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Ensure only one Status instance exists
        if not self.pk:
            # If creating new, delete any existing
            Status.objects.all().delete()
        super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        """Get or create the current status instance."""
        status, created = cls.objects.get_or_create(
            defaults={"status": "online", "message": ""}
        )
        return status

    def __str__(self):
        if self.message:
            return f"{self.get_status_display()}: {self.message}"
        return self.get_status_display()

    class Meta:
        verbose_name = "Stream Status"
        verbose_name_plural = "Stream Status"
