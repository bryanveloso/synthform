"""Campaign API endpoints."""

from __future__ import annotations

import json
import logging
from datetime import UTC
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.shortcuts import get_object_or_404
from ninja import Query
from ninja import Router

from .models import Campaign
from .models import Gift
from .models import Metric
from .models import Milestone
from .schemas import CampaignResponse
from .schemas import GiftLeaderboardResponse
from .schemas import MetricResponse
from .schemas import MilestoneResponse
from .services import campaign_service

logger = logging.getLogger(__name__)
router = Router(tags=["campaigns"])


@router.get("/active", response=CampaignResponse | None)
async def get_active_campaign(request) -> CampaignResponse | None:
    """Get the currently active campaign with its metrics and milestones."""
    campaign = await campaign_service.get_active_campaign()
    if not campaign:
        return None

    # Get metric
    try:
        metric = await Metric.objects.select_related("campaign").aget(campaign=campaign)
    except Metric.DoesNotExist:
        # Create metric if it doesn't exist
        metric = await Metric.objects.acreate(campaign=campaign)

    # Get milestones
    milestones = []
    async for milestone in Milestone.objects.filter(campaign=campaign).order_by(
        "threshold"
    ):
        milestones.append(
            MilestoneResponse(
                id=str(milestone.id),
                threshold=milestone.threshold,
                title=milestone.title,
                description=milestone.description,
                is_unlocked=milestone.is_unlocked,
                unlocked_at=milestone.unlocked_at,
                image_url=milestone.image_url,
            )
        )

    return CampaignResponse(
        id=str(campaign.id),
        name=campaign.name,
        slug=campaign.slug,
        description=campaign.description,
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        is_active=campaign.is_active,
        timer_mode=campaign.timer_mode,
        timer_initial_seconds=campaign.timer_initial_seconds,
        seconds_per_sub=campaign.seconds_per_sub,
        seconds_per_tier2=campaign.seconds_per_tier2,
        seconds_per_tier3=campaign.seconds_per_tier3,
        max_timer_seconds=campaign.max_timer_seconds,
        metric=MetricResponse(
            id=str(metric.id),
            total_subs=metric.total_subs,
            total_resubs=metric.total_resubs,
            total_bits=metric.total_bits,
            total_donations=float(metric.total_donations),
            timer_seconds_remaining=metric.timer_seconds_remaining,
            timer_started_at=metric.timer_started_at,
            timer_paused_at=metric.timer_paused_at,
            extra_data=metric.extra_data,
            updated_at=metric.updated_at,
        ),
        milestones=milestones,
    )


@router.get("/{campaign_id}/metrics", response=MetricResponse)
async def get_campaign_metrics(request, campaign_id: str) -> MetricResponse:
    """Get current metrics for a specific campaign."""
    campaign = await sync_to_async(get_object_or_404)(Campaign, id=campaign_id)

    try:
        metric = await Metric.objects.aget(campaign=campaign)
    except Metric.DoesNotExist:
        metric = await Metric.objects.acreate(campaign=campaign)

    return MetricResponse(
        id=str(metric.id),
        total_subs=metric.total_subs,
        total_resubs=metric.total_resubs,
        total_bits=metric.total_bits,
        total_donations=float(metric.total_donations),
        timer_seconds_remaining=metric.timer_seconds_remaining,
        timer_started_at=metric.timer_started_at,
        timer_paused_at=metric.timer_paused_at,
        extra_data=metric.extra_data,
        updated_at=metric.updated_at,
    )


@router.post("/timer/start", response=dict[str, Any])
async def start_timer(request) -> dict[str, Any]:
    """Start or restart the subathon timer for the active campaign."""
    campaign = await campaign_service.get_active_campaign()
    if not campaign:
        return {"error": "No active campaign"}

    result = await campaign_service.start_timer(campaign)

    # Publish timer start to Redis
    redis_client = None
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_message = {
            "event_type": "campaign:timer:started",
            "source": "campaign",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": result,
        }
        await redis_client.publish("events:campaign", json.dumps(redis_message))
    except Exception as e:
        logger.error(f"Failed to publish timer start: {e}")
    finally:
        if redis_client:
            await redis_client.close()

    return result


@router.post("/timer/pause", response=dict[str, Any])
async def pause_timer(request) -> dict[str, Any]:
    """Pause the subathon timer for the active campaign."""
    campaign = await campaign_service.get_active_campaign()
    if not campaign:
        return {"error": "No active campaign"}

    result = await campaign_service.pause_timer(campaign)

    # Publish timer pause to Redis
    redis_client = None
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_message = {
            "event_type": "campaign:timer:paused",
            "source": "campaign",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": result,
        }
        await redis_client.publish("events:campaign", json.dumps(redis_message))
    except Exception as e:
        logger.error(f"Failed to publish timer pause: {e}")
    finally:
        if redis_client:
            await redis_client.close()

    return result


@router.get("/active/gifts/leaderboard", response=list[GiftLeaderboardResponse])
async def get_active_campaign_gift_leaderboard(
    request, limit: int = Query(10, gt=0, le=100)
) -> list[GiftLeaderboardResponse]:
    """Get the top gift contributors for the active campaign.

    Args:
        limit: Number of results to return (1-100, default 10)
    """
    campaign = await campaign_service.get_active_campaign()
    if not campaign:
        return []

    leaderboard = await campaign_service.get_gift_leaderboard(campaign, limit)

    return [
        GiftLeaderboardResponse(
            member_id=entry["member_id"],
            display_name=entry["display_name"],
            username=entry["username"],
            tier1_count=entry["tier1_count"],
            tier2_count=entry["tier2_count"],
            tier3_count=entry["tier3_count"],
            total_count=entry["total_count"],
            first_gift_at=entry["first_gift_at"],
            last_gift_at=entry["last_gift_at"],
        )
        for entry in leaderboard
    ]


@router.get("/{campaign_id}/gifts/leaderboard", response=list[GiftLeaderboardResponse])
async def get_gift_leaderboard(
    request, campaign_id: str, limit: int = Query(10, gt=0, le=100)
) -> list[GiftLeaderboardResponse]:
    """Get the top gift contributors for a campaign.

    Args:
        campaign_id: The campaign ID
        limit: Number of results to return (1-100, default 10)
    """
    campaign = await sync_to_async(get_object_or_404)(Campaign, id=campaign_id)
    leaderboard = await campaign_service.get_gift_leaderboard(campaign, limit)

    return [
        GiftLeaderboardResponse(
            member_id=entry["member_id"],
            display_name=entry["display_name"],
            username=entry["username"],
            tier1_count=entry["tier1_count"],
            tier2_count=entry["tier2_count"],
            tier3_count=entry["tier3_count"],
            total_count=entry["total_count"],
            first_gift_at=entry["first_gift_at"],
            last_gift_at=entry["last_gift_at"],
        )
        for entry in leaderboard
    ]
