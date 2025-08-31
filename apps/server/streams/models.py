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
