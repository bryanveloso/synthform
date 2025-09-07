from __future__ import annotations

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "started_at",
        "ended_at",
        "is_active",
        "timeout_started_at",
        "duration",
    ]
    list_filter = ["is_active", "started_at"]
    search_fields = ["id"]
    readonly_fields = ["started_at", "duration"]

    def duration(self, obj):
        if obj.ended_at and obj.started_at:
            delta = obj.ended_at - obj.started_at
            return f"{delta.total_seconds():.1f}s"
        elif obj.is_active:
            delta = timezone.now() - obj.started_at
            return f"{delta.total_seconds():.1f}s (active)"
        return "-"


