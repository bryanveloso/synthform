from __future__ import annotations

from django.contrib import admin

from .models import Transcription


@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "text_preview",
        "duration",
        "confidence",
        "session",
        "source_file",
    )
    list_filter = ("timestamp", "confidence", "session", "created_at")
    search_fields = ("text", "source_file", "legacy_stream_session_id")
    readonly_fields = ("id", "search_vector", "created_at", "updated_at")
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]
    raw_id_fields = ("session",)

    def text_preview(self, obj):
        if obj.text:
            return obj.text[:75] + "..." if len(obj.text) > 75 else obj.text
        return "-"

    text_preview.short_description = "Text Preview"
