from __future__ import annotations

from django.contrib import admin

from .models import Quote


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "text_preview",
        "quotee",
        "quoter",
        "year",
        "created_at",
    )
    list_filter = ("year", "quotee", "quoter", "created_at")
    search_fields = ("text", "quotee__display_name", "quotee__username")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ["-number"]
    raw_id_fields = ("quotee", "quoter")

    def text_preview(self, obj):
        return obj.text[:75] + "..." if len(obj.text) > 75 else obj.text

    text_preview.short_description = "Text"
