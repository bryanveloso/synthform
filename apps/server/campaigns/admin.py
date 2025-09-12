from __future__ import annotations

from django.contrib import admin

from .models import Campaign
from .models import Metric
from .models import Milestone


class MilestoneInline(admin.TabularInline):
    """Inline admin for managing milestones within a campaign."""

    model = Milestone
    extra = 1
    fields = ["threshold", "title", "description", "is_unlocked", "unlocked_at"]
    readonly_fields = ["unlocked_at"]
    ordering = ["threshold"]


class MetricInline(admin.StackedInline):
    """Inline admin for viewing campaign metrics."""

    model = Metric
    extra = 0
    max_num = 1
    fields = [
        "total_subs",
        "total_resubs",
        "total_bits",
        "total_donations",
        "timer_seconds_remaining",
        "timer_started_at",
        "timer_paused_at",
        "extra_data",
        "updated_at",
    ]
    readonly_fields = ["updated_at"]


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Admin interface for campaigns."""

    list_display = ["name", "slug", "is_active", "start_date", "end_date", "timer_mode"]
    list_filter = ["is_active", "timer_mode", "start_date"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = (
        ("Basic Information", {"fields": ("name", "slug", "description")}),
        ("Schedule", {"fields": ("start_date", "end_date", "is_active")}),
        (
            "Timer Configuration",
            {
                "fields": (
                    "timer_mode",
                    "timer_initial_seconds",
                    "seconds_per_sub",
                    "seconds_per_tier2",
                    "seconds_per_tier3",
                    "max_timer_seconds",
                ),
                "classes": ("collapse",),
                "description": "Configure timer settings for subathon mode",
            },
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["created_at", "updated_at"]
    inlines = [MetricInline, MilestoneInline]

    actions = ["activate_campaign", "deactivate_campaign"]

    def activate_campaign(self, request, queryset):
        """Activate selected campaigns."""
        # Deactivate all other campaigns first
        Campaign.objects.filter(is_active=True).update(is_active=False)
        # Activate selected campaigns
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} campaign(s) activated.")

    activate_campaign.short_description = "Activate selected campaigns"

    def deactivate_campaign(self, request, queryset):
        """Deactivate selected campaigns."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} campaign(s) deactivated.")

    deactivate_campaign.short_description = "Deactivate selected campaigns"


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    """Admin interface for milestones."""

    list_display = ["threshold", "title", "campaign", "is_unlocked", "unlocked_at"]
    list_filter = ["is_unlocked", "campaign"]
    search_fields = ["title", "description"]
    ordering = ["campaign", "threshold"]

    fieldsets = (
        ("Campaign", {"fields": ("campaign",)}),
        ("Goal Details", {"fields": ("threshold", "title", "description")}),
        ("Status", {"fields": ("is_unlocked", "unlocked_at")}),
        (
            "Media",
            {"fields": ("image_url", "announcement_text"), "classes": ("collapse",)},
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["created_at", "updated_at", "unlocked_at"]

    actions = ["mark_as_unlocked", "mark_as_locked"]

    def mark_as_unlocked(self, request, queryset):
        """Mark selected milestones as unlocked."""
        from django.utils import timezone

        updated = queryset.update(is_unlocked=True, unlocked_at=timezone.now())
        self.message_user(request, f"{updated} milestone(s) marked as unlocked.")

    mark_as_unlocked.short_description = "Mark as unlocked"

    def mark_as_locked(self, request, queryset):
        """Mark selected milestones as locked."""
        updated = queryset.update(is_unlocked=False, unlocked_at=None)
        self.message_user(request, f"{updated} milestone(s) marked as locked.")

    mark_as_locked.short_description = "Mark as locked"


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    """Admin interface for campaign metrics."""

    list_display = [
        "campaign",
        "total_subs",
        "total_resubs",
        "total_bits",
        "updated_at",
    ]
    list_filter = ["campaign"]

    fieldsets = (
        ("Campaign", {"fields": ("campaign",)}),
        (
            "Cumulative Tracking",
            {"fields": ("total_subs", "total_resubs", "total_bits", "total_donations")},
        ),
        (
            "Timer Tracking",
            {
                "fields": (
                    "timer_seconds_remaining",
                    "timer_started_at",
                    "timer_paused_at",
                )
            },
        ),
        (
            "Extra Data",
            {
                "fields": ("extra_data",),
                "description": "JSON field for flexible data storage (voting, stats, etc.)",
            },
        ),
        ("Metadata", {"fields": ("updated_at",)}),
    )

    readonly_fields = ["updated_at"]
