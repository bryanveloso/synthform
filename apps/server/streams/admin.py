from __future__ import annotations

from django.contrib import admin

from .models import Session
from .models import Status


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "stream_session_id",
        "session_date",
        "event_count",
        "transcription_count",
        "created_at",
    )
    list_filter = ("session_date", "created_at", "updated_at")
    search_fields = ("session_date",)
    readonly_fields = (
        "id",
        "stream_session_id",
        "created_at",
        "updated_at",
        "event_count",
        "transcription_count",
    )
    date_hierarchy = "session_date"
    ordering = ["-session_date"]

    def event_count(self, obj):
        return obj.events.count()

    event_count.short_description = "Events"

    def transcription_count(self, obj):
        return obj.transcriptions.count()

    transcription_count.short_description = "Transcriptions"


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("status", "message", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("message",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("status", "message")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
