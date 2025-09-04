from __future__ import annotations

import json

from django.contrib import admin
from django.utils.html import format_html

from .models import Event
from .models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "username",
        "twitch_id",
        "discord_id",
        "youtube_id",
        "created_at",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = (
        "display_name",
        "username",
        "twitch_id",
        "discord_id",
        "youtube_id",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ["-created_at"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "source",
        "event_type",
        "member_display",
        "session",
        "message_preview",
    )
    list_filter = ("source", "event_type", "timestamp", "session")
    search_fields = ("event_type", "member__display_name", "member__username")
    readonly_fields = ("id", "created_at", "updated_at", "formatted_payload")
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]
    raw_id_fields = ("member", "session")

    def member_display(self, obj):
        if obj.member:
            return f"{obj.member.display_name} ({obj.member.username})"
        return "Anonymous"

    member_display.short_description = "Member"

    def message_preview(self, obj):
        message = obj.message
        if message:
            return message[:50] + "..." if len(message) > 50 else message
        return "-"

    message_preview.short_description = "Message"

    def formatted_payload(self, obj):
        """Display JSON payload in a readable format"""
        try:
            formatted = json.dumps(obj.payload, indent=2, ensure_ascii=False)
            return format_html(
                '<pre style="white-space: pre-wrap; font-family: monospace; font-size: 11px;">{}</pre>',
                formatted,
            )
        except Exception:
            return str(obj.payload)

    formatted_payload.short_description = "Payload (formatted)"
