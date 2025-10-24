from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone

from events.models import Member


class Quote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Original quote number from elsydeon
    number = models.IntegerField(unique=True, db_index=True)

    # Quote content
    text = models.TextField()

    # Who said it (required - manual review ensures all Members exist)
    quotee = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="quotes_said"
    )

    # Who recorded/submitted it
    quoter = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="quotes_recorded"
    )

    # When it was said
    year = models.IntegerField()

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["quotee", "year"]),
            models.Index(fields=["year"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f'#{self.number}: "{preview}" - {self.quotee.display_name} ({self.year})'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
