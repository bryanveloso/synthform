from __future__ import annotations

import uuid

from django.db import models


class Campaign(models.Model):
    """A special streaming event (subathon, marathon, charity drive, etc.)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic info
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField()

    # Timing
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=False, db_index=True)

    # Subathon timer configuration
    timer_mode = models.BooleanField(default=False)
    timer_initial_seconds = models.IntegerField(default=3600)  # Start with 1 hour
    seconds_per_sub = models.IntegerField(default=180)  # 3 minutes per tier 1
    seconds_per_tier2 = models.IntegerField(default=360)  # 6 minutes for tier 2
    seconds_per_tier3 = models.IntegerField(default=900)  # 15 minutes for tier 3
    max_timer_seconds = models.IntegerField(null=True, blank=True)  # Optional cap

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.name


class Milestone(models.Model):
    """A goal within a campaign that unlocks at a certain threshold"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="milestones"
    )

    # Goal details
    threshold = models.IntegerField()  # 100 (subs)
    title = models.CharField(max_length=255)  # "UFO 50"
    description = models.TextField()  # "Bryan plays UFO 50"

    # Status
    is_unlocked = models.BooleanField(default=False, db_index=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)

    # Optional media
    image_url = models.URLField(blank=True)
    announcement_text = models.TextField(blank=True)  # Custom unlock message

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["threshold"]
        unique_together = ["campaign", "threshold"]

    def __str__(self):
        status = "✅" if self.is_unlocked else "🔒"
        return f"{status} {self.threshold}: {self.title}"


class Metric(models.Model):
    """Real-time tracking for a campaign"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    campaign = models.OneToOneField(
        Campaign, on_delete=models.CASCADE, related_name="metric"
    )

    # Cumulative tracking
    total_subs = models.IntegerField(default=0)  # New + gift subs
    total_resubs = models.IntegerField(default=0)  # Subscription messages
    total_bits = models.IntegerField(default=0)
    total_donations = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Timer tracking (for subathon mode)
    timer_seconds_remaining = models.IntegerField(default=0)
    timer_started_at = models.DateTimeField(null=True, blank=True)
    timer_paused_at = models.DateTimeField(null=True, blank=True)

    # Flexible JSON storage for special features
    extra_data = models.JSONField(default=dict)
    # Examples:
    # - FFXIV race votes: {"ffxiv_votes": {"viera": 125, "lalafell": 89}}
    # - Top contributors: {"top_gifters": [{"name": "user1", "count": 50}]}
    # - Daily stats: {"daily_subs": {"2025-09-28": 45, "2025-09-29": 67}}

    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Metrics"

    def __str__(self):
        return f"{self.campaign.name} - {self.total_subs} subs"
