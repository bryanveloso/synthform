from __future__ import annotations

from django.contrib import admin

from .models import Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = [
        "member",
        "unit",
        "lv",
        "atk",
        "mag",
        "spi",
        "hp",
        "gil",
        "collection",
        "wins",
        "updated_at",
    ]
    list_filter = [
        "season",
        "ascension",
        "preferedstat",
        "updated_at",
    ]
    search_fields = [
        "member__username",
        "member__display_name",
        "unit",
        "esper",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]

    fieldsets = [
        (
            None,
            {
                "fields": ["id", "member", "created_at", "updated_at"],
            },
        ),
        (
            "Core Stats",
            {
                "fields": [
                    "lv",
                    "atk",
                    "mag",
                    "spi",
                    "hp",
                    "exp",
                    "preferedstat",
                ],
            },
        ),
        (
            "Resources & Progress",
            {
                "fields": [
                    "gil",
                    "collection",
                    "ascension",
                    "wins",
                    "freehirecount",
                    "season",
                ],
            },
        ),
        (
            "Active Equipment",
            {
                "fields": [
                    "unit",
                    "esper",
                ],
            },
        ),
        (
            "Job System",
            {
                "fields": [
                    "jobap",
                    "m1",
                    "m2",
                    "m3",
                    "m4",
                    "m5",
                    "m6",
                    "m7",
                    "job_atk",
                    "job_mag",
                    "job_spi",
                    "job_hp",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Card System",
            {
                "fields": [
                    "card",
                    "card_collection",
                    "card_passive",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("member")