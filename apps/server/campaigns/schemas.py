"""Pydantic schemas for campaign API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MilestoneResponse(BaseModel):
    """Response schema for a campaign milestone."""

    id: str
    threshold: int
    title: str
    description: str
    is_unlocked: bool
    unlocked_at: datetime | None
    image_url: str


class MetricResponse(BaseModel):
    """Response schema for campaign metrics."""

    id: str
    total_subs: int
    total_resubs: int
    total_bits: int
    total_donations: float
    timer_seconds_remaining: int
    timer_started_at: datetime | None
    timer_paused_at: datetime | None
    extra_data: dict[str, Any]
    updated_at: datetime


class CampaignResponse(BaseModel):
    """Response schema for a campaign with full details."""

    id: str
    name: str
    slug: str
    description: str
    start_date: datetime
    end_date: datetime
    is_active: bool

    # Timer configuration
    timer_mode: bool
    timer_initial_seconds: int
    seconds_per_sub: int
    seconds_per_tier2: int
    seconds_per_tier3: int
    max_timer_seconds: int | None

    # Related data
    metric: MetricResponse
    milestones: list[MilestoneResponse]


class GiftLeaderboardResponse(BaseModel):
    """Response schema for gift leaderboard entry."""

    member_id: str
    display_name: str
    username: str | None
    tier1_count: int
    tier2_count: int
    tier3_count: int
    total_count: int
    first_gift_at: str | None
    last_gift_at: str | None
