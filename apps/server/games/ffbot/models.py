from __future__ import annotations

import uuid

from django.db import models


class Player(models.Model):
    """Cache current FFBot player state - updated whenever stats are received"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    member = models.OneToOneField(
        "events.Member", on_delete=models.CASCADE, related_name="ffbot_player"
    )

    # Core Stats
    lv = models.IntegerField(default=1)
    atk = models.IntegerField(default=0)
    mag = models.IntegerField(default=0)
    spi = models.IntegerField(default=0)
    hp = models.IntegerField(default=0)
    exp = models.IntegerField(default=0)
    preferedstat = models.CharField(max_length=10, default="none")

    # Resources
    gil = models.BigIntegerField(default=0)

    # Collection/Progress
    collection = models.IntegerField(default=0)
    ascension = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    freehirecount = models.IntegerField(default=0)
    season = models.IntegerField(default=4)

    # Active Character/Equipment
    unit = models.CharField(max_length=100, blank=True)
    esper = models.CharField(max_length=100, blank=True)

    # Job System
    jobap = models.IntegerField(default=0)
    m1 = models.CharField(max_length=50, blank=True)
    m2 = models.CharField(max_length=50, blank=True)
    m3 = models.CharField(max_length=50, blank=True)
    m4 = models.CharField(max_length=50, blank=True)
    m5 = models.CharField(max_length=50, blank=True)
    m6 = models.CharField(max_length=50, blank=True)
    m7 = models.CharField(max_length=50, blank=True)
    job_atk = models.IntegerField(default=0)
    job_mag = models.IntegerField(default=0)
    job_spi = models.IntegerField(default=0)
    job_hp = models.IntegerField(default=0)

    # Card System
    card = models.CharField(max_length=100, blank=True)
    card_collection = models.IntegerField(default=0)
    card_passive = models.CharField(max_length=200, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "games_ffbot_playerstats"
        indexes = [models.Index(fields=["member"])]
        verbose_name = "FFBot Player Stats"
        verbose_name_plural = "FFBot Player Stats"

    def __str__(self):
        return f"{self.member.display_name} - Lv.{self.lv}"
