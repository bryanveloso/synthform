from __future__ import annotations

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Chunk
from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "started_at",
        "ended_at",
        "is_active",
        "timeout_started_at",
        "chunk_count",
        "duration",
    ]
    list_filter = ["is_active", "started_at"]
    search_fields = ["id"]
    readonly_fields = ["started_at", "chunk_count", "duration"]

    def chunk_count(self, obj):
        return obj.chunks.count()

    chunk_count.short_description = "Chunks"

    def duration(self, obj):
        if obj.ended_at and obj.started_at:
            delta = obj.ended_at - obj.started_at
            return f"{delta.total_seconds():.1f}s"
        elif obj.is_active:
            delta = timezone.now() - obj.started_at
            return f"{delta.total_seconds():.1f}s (active)"
        return "-"


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "session",
        "timestamp",
        "source_name",
        "data_size_kb",
        "format_info",
        "processed_status",
    ]
    list_filter = ["processed", "sample_rate", "channels", "session__is_active"]
    search_fields = ["source_id", "source_name", "session__id"]
    readonly_fields = ["timestamp", "data_size_kb", "format_info"]
    date_hierarchy = "timestamp"

    def data_size_kb(self, obj):
        return f"{obj.data_size / 1024:.1f} KB"

    data_size_kb.short_description = "Size"

    def format_info(self, obj):
        return f"{obj.sample_rate}Hz, {obj.channels}ch, {obj.bit_depth}bit"

    format_info.short_description = "Format"

    def processed_status(self, obj):
        if obj.processed:
            return format_html('<span style="color: green;">✓ Processed</span>')
        elif obj.processing_started:
            return format_html('<span style="color: orange;">⏳ Processing</span>')
        else:
            return format_html('<span style="color: red;">⏸ Pending</span>')

    processed_status.short_description = "Status"
