"""Campaign tracking service for processing events and managing metrics."""

from __future__ import annotations

import json
import logging
from datetime import UTC
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from events.models import Member

from .models import Campaign
from .models import Gift
from .models import Metric
from .models import Milestone

logger = logging.getLogger(__name__)


class CampaignService:
    """Service for managing campaign metrics and milestones."""

    @staticmethod
    async def get_active_campaign() -> Campaign | None:
        """Get the currently active campaign."""
        try:
            return await Campaign.objects.filter(is_active=True).afirst()
        except Campaign.DoesNotExist:
            return None

    @staticmethod
    def _process_subscription_sync(
        campaign: Campaign, tier: int = 1
    ) -> tuple[Metric, int]:
        """Synchronous helper for process_subscription."""
        with transaction.atomic():
            # Use get_or_create with select_for_update to handle race conditions
            metric, created = Metric.objects.select_for_update().get_or_create(
                campaign=campaign, defaults={}
            )

            # Update sub count
            metric.total_subs = F("total_subs") + 1

            # Add timer seconds if timer mode is active
            timer_added = 0
            if campaign.timer_mode and metric.timer_started_at:
                if tier == 1:
                    timer_added = campaign.seconds_per_sub
                elif tier == 2:
                    timer_added = campaign.seconds_per_tier2
                elif tier == 3:
                    timer_added = campaign.seconds_per_tier3

                metric.timer_seconds_remaining = (
                    F("timer_seconds_remaining") + timer_added
                )

            metric.save()

            # Refresh to get actual values from F() expressions
            metric.refresh_from_db()

            # Apply cap if configured
            if (
                campaign.max_timer_seconds
                and metric.timer_seconds_remaining > campaign.max_timer_seconds
            ):
                metric.timer_seconds_remaining = campaign.max_timer_seconds
                metric.save(update_fields=["timer_seconds_remaining"])

            return metric, timer_added

    @staticmethod
    async def process_subscription(
        campaign: Campaign,
        tier: int = 1,
        is_gift: bool = False,
        gifter_id: str | None = None,
        gifter_name: str | None = None,
    ) -> dict[str, Any]:
        """Process a subscription or gift sub for the campaign.

        Args:
            campaign: The active campaign
            tier: Subscription tier (1, 2, or 3)
            is_gift: Whether this is a gift subscription
            gifter_id: Twitch ID of the gifter (for gift subs)
            gifter_name: Display name of the gifter (for gift subs)

        Returns:
            Dict containing any milestone unlocks and updated metrics
        """
        if not campaign:
            return {}

        # Use sync_to_async for transaction operations
        metric, timer_added = await sync_to_async(
            CampaignService._process_subscription_sync
        )(campaign, tier)

        # Track gift if this is a gift sub
        if is_gift and gifter_id:
            await CampaignService._track_gift(campaign, tier, gifter_id, gifter_name)

        # Check for milestone unlocks based on combined total (subs + resubs)
        combined_total = metric.total_subs + metric.total_resubs
        unlocked_milestone = await CampaignService._check_milestone_unlock(
            campaign, combined_total
        )

        result = {
            "campaign_id": str(campaign.id),
            "campaign_name": campaign.name,
            "total_subs": metric.total_subs,
            "timer_seconds_added": timer_added,
            "timer_seconds_remaining": metric.timer_seconds_remaining,
        }

        if unlocked_milestone:
            result["milestone_unlocked"] = {
                "id": str(unlocked_milestone.id),
                "threshold": unlocked_milestone.threshold,
                "title": unlocked_milestone.title,
                "description": unlocked_milestone.description,
            }
            logger.info(
                f"🎉 Milestone unlocked! {unlocked_milestone.threshold}: {unlocked_milestone.title}"
            )
            # Publish milestone unlock to Redis
            await CampaignService._publish_to_redis(
                "campaign:milestone", result["milestone_unlocked"]
            )

        # Publish metric update to Redis
        await CampaignService._publish_to_redis(
            "campaign:update",
            {
                "campaign_id": str(campaign.id),
                "total_subs": metric.total_subs,
                "total_resubs": metric.total_resubs,
                "total_bits": metric.total_bits,
                "timer_seconds_remaining": metric.timer_seconds_remaining,
                "timer_seconds_added": timer_added,
                "extra_data": metric.extra_data,
            },
        )

        return result

    @staticmethod
    def _process_resub_sync(campaign: Campaign) -> Metric:
        """Synchronous helper for process_resub."""
        with transaction.atomic():
            metric, created = Metric.objects.select_for_update().get_or_create(
                campaign=campaign, defaults={}
            )

            metric.total_resubs = F("total_resubs") + 1
            metric.save()
            metric.refresh_from_db()
            return metric

    @staticmethod
    async def process_resub(campaign: Campaign) -> dict[str, Any]:
        """Process a resub message for the campaign."""
        if not campaign:
            return {}

        metric = await sync_to_async(CampaignService._process_resub_sync)(campaign)

        # Check for milestone unlocks based on combined total (subs + resubs)
        combined_total = metric.total_subs + metric.total_resubs
        unlocked_milestone = await CampaignService._check_milestone_unlock(
            campaign, combined_total
        )

        result = {
            "campaign_id": str(campaign.id),
            "campaign_name": campaign.name,
            "total_resubs": metric.total_resubs,
            "combined_total": combined_total,
        }

        if unlocked_milestone:
            result["milestone_unlocked"] = {
                "id": str(unlocked_milestone.id),
                "threshold": unlocked_milestone.threshold,
                "title": unlocked_milestone.title,
                "description": unlocked_milestone.description,
            }
            logger.info(
                f"🎉 Milestone unlocked! {unlocked_milestone.threshold}: {unlocked_milestone.title}"
            )
            # Publish milestone unlock to Redis
            await CampaignService._publish_to_redis(
                "campaign:milestone", result["milestone_unlocked"]
            )

        # Publish metric update to Redis
        await CampaignService._publish_to_redis(
            "campaign:update",
            {
                "campaign_id": str(campaign.id),
                "total_subs": metric.total_subs,
                "total_resubs": metric.total_resubs,
                "total_bits": metric.total_bits,
                "extra_data": metric.extra_data,
            },
        )

        return result

    @staticmethod
    def _process_bits_sync(campaign: Campaign, bits: int) -> Metric:
        """Synchronous helper for process_bits."""
        with transaction.atomic():
            metric, created = Metric.objects.select_for_update().get_or_create(
                campaign=campaign, defaults={}
            )

            metric.total_bits = F("total_bits") + bits
            metric.save()
            metric.refresh_from_db()
            return metric

    @staticmethod
    async def process_bits(campaign: Campaign, bits: int) -> dict[str, Any]:
        """Process a bits cheer for the campaign."""
        if not campaign:
            return {}

        metric = await sync_to_async(CampaignService._process_bits_sync)(campaign, bits)

        return {
            "campaign_id": str(campaign.id),
            "campaign_name": campaign.name,
            "total_bits": metric.total_bits,
        }

    @staticmethod
    async def _check_milestone_unlock(
        campaign: Campaign, current_total: int
    ) -> Milestone | None:
        """Check if a milestone should be unlocked."""
        # Find the next locked milestone at or below current total
        milestone = (
            await Milestone.objects.filter(
                campaign=campaign, threshold__lte=current_total, is_unlocked=False
            )
            .order_by("-threshold")
            .afirst()
        )

        if milestone:
            milestone.is_unlocked = True
            milestone.unlocked_at = timezone.now()
            await milestone.asave()
            return milestone

        return None

    @staticmethod
    def _start_timer_sync(campaign: Campaign) -> Metric:
        """Synchronous helper for start_timer."""
        with transaction.atomic():
            metric, created = Metric.objects.select_for_update().get_or_create(
                campaign=campaign, defaults={}
            )

            # Initialize or add to timer
            if not metric.timer_started_at:
                metric.timer_seconds_remaining = campaign.timer_initial_seconds
            else:
                metric.timer_seconds_remaining = (
                    F("timer_seconds_remaining") + campaign.timer_initial_seconds
                )

            metric.timer_started_at = timezone.now()
            metric.timer_paused_at = None
            metric.save()
            metric.refresh_from_db()
            return metric

    @staticmethod
    async def start_timer(campaign: Campaign) -> dict[str, Any]:
        """Start or restart the subathon timer."""
        if not campaign or not campaign.timer_mode:
            return {"error": "Campaign does not have timer mode enabled"}

        metric = await sync_to_async(CampaignService._start_timer_sync)(campaign)

        return {
            "campaign_id": str(campaign.id),
            "timer_started": True,
            "timer_seconds_remaining": metric.timer_seconds_remaining,
        }

    @staticmethod
    def _pause_timer_sync(campaign: Campaign) -> Metric | None:
        """Synchronous helper for pause_timer."""
        with transaction.atomic():
            try:
                metric = Metric.objects.select_for_update().get(campaign=campaign)
                metric.timer_paused_at = timezone.now()
                metric.save()
                return metric
            except Metric.DoesNotExist:
                return None

    @staticmethod
    async def pause_timer(campaign: Campaign) -> dict[str, Any]:
        """Pause the subathon timer."""
        if not campaign or not campaign.timer_mode:
            return {"error": "Campaign does not have timer mode enabled"}

        metric = await sync_to_async(CampaignService._pause_timer_sync)(campaign)

        if metric:
            return {
                "campaign_id": str(campaign.id),
                "timer_paused": True,
                "timer_seconds_remaining": metric.timer_seconds_remaining,
            }

        return {"error": "No metric found for campaign"}

    @staticmethod
    def _update_vote_sync(campaign: Campaign, option: str, votes: int = 1) -> Metric:
        """Synchronous helper for update_vote."""
        with transaction.atomic():
            metric, created = Metric.objects.select_for_update().get_or_create(
                campaign=campaign, defaults={}
            )

            # Initialize voting data if not present
            if "ffxiv_votes" not in metric.extra_data:
                metric.extra_data["ffxiv_votes"] = {}

            # Update vote count
            current_votes = metric.extra_data["ffxiv_votes"].get(option, 0)
            metric.extra_data["ffxiv_votes"][option] = current_votes + votes

            metric.save()
            return metric

    @staticmethod
    async def update_vote(
        campaign: Campaign, option: str, votes: int = 1
    ) -> dict[str, Any]:
        """Update voting data in the campaign metric.

        Args:
            campaign: The active campaign
            option: The voting option (e.g., 'viera', 'lalafell')
            votes: Number of votes to add
        """
        if not campaign:
            return {}

        metric = await sync_to_async(CampaignService._update_vote_sync)(
            campaign, option, votes
        )

        return {
            "campaign_id": str(campaign.id),
            "voting_update": metric.extra_data["ffxiv_votes"],
        }

    @staticmethod
    def _track_gift_sync(
        campaign: Campaign, tier: int, twitch_id: str, display_name: str | None
    ) -> Gift:
        """Synchronous helper for tracking gift subscriptions."""
        with transaction.atomic():
            # Get or create the member
            member, created = Member.objects.get_or_create(
                twitch_id=twitch_id,
                defaults={"display_name": display_name or f"User{twitch_id}"},
            )

            # Update display name if it changed
            if not created and display_name and member.display_name != display_name:
                member.display_name = display_name
                member.save(update_fields=["display_name", "updated_at"])

            # Get or create the gift record
            gift, created = Gift.objects.select_for_update().get_or_create(
                member=member,
                campaign=campaign,
                defaults={},
            )

            # Update counts based on tier
            if tier == 1:
                gift.tier1_count = F("tier1_count") + 1
            elif tier == 2:
                gift.tier2_count = F("tier2_count") + 1
            elif tier == 3:
                gift.tier3_count = F("tier3_count") + 1

            gift.total_count = F("total_count") + 1

            # Update timestamps
            now = timezone.now()
            if created or not gift.first_gift_at:
                gift.first_gift_at = now
            gift.last_gift_at = now

            gift.save()
            gift.refresh_from_db()

            return gift

    @staticmethod
    async def _track_gift(
        campaign: Campaign, tier: int, twitch_id: str, display_name: str | None
    ) -> Gift:
        """Track a gift subscription from a member."""
        return await sync_to_async(CampaignService._track_gift_sync)(
            campaign, tier, twitch_id, display_name
        )

    @staticmethod
    async def get_gift_leaderboard(
        campaign: Campaign, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get the top gift contributors for a campaign.

        Args:
            campaign: The campaign to get leaderboard for
            limit: Maximum number of results (default 10)

        Returns:
            List of gift records with member info
        """
        # Exclude the broadcaster (Avalonstar) from the leaderboard
        gifts = await sync_to_async(list)(
            Gift.objects.filter(campaign=campaign)
            .exclude(member__display_name__iexact="Avalonstar")
            .select_related("member")
            .order_by("-total_count")[:limit]
        )

        return [
            {
                "member_id": str(gift.member.id),
                "display_name": gift.member.display_name,
                "username": gift.member.username,
                "tier1_count": gift.tier1_count,
                "tier2_count": gift.tier2_count,
                "tier3_count": gift.tier3_count,
                "total_count": gift.total_count,
                "first_gift_at": gift.first_gift_at.isoformat()
                if gift.first_gift_at
                else None,
                "last_gift_at": gift.last_gift_at.isoformat()
                if gift.last_gift_at
                else None,
            }
            for gift in gifts
        ]

    @staticmethod
    async def sync_campaign_state() -> None:
        """Trigger a full campaign state sync to all connected clients."""
        campaign = await CampaignService.get_active_campaign()
        if not campaign:
            logger.debug("No active campaign to sync")
            return

        try:
            # Get metric if it exists
            metric = await Metric.objects.filter(campaign=campaign).afirst()

            # Calculate current state
            current_session_start = await sync_to_async(
                campaign.get_current_session_start
            )()
            total_duration = await sync_to_async(campaign.calculate_total_duration)()

            # Build sync payload
            sync_data = {
                "campaign_id": str(campaign.id),
                "stream_started_at": current_session_start.isoformat()
                if current_session_start
                else None,
                "total_duration": total_duration,
            }

            # Add metric data if available
            if metric:
                sync_data.update(
                    {
                        "total_subs": metric.total_subs,
                        "total_resubs": metric.total_resubs,
                        "total_bits": metric.total_bits,
                        "timer_seconds_remaining": metric.timer_seconds_remaining,
                        "extra_data": metric.extra_data,
                    }
                )

            # Publish sync event
            await CampaignService._publish_to_redis("campaign:sync", sync_data)
            logger.info(
                f"Published campaign sync for {campaign.name}, stream_started_at: {current_session_start}"
            )

        except Exception as e:
            logger.error(f"Failed to sync campaign state: {e}")

    @staticmethod
    async def _publish_to_redis(event_type: str, data: dict) -> None:
        """Publish campaign events to Redis for real-time updates."""
        redis_client = None
        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_message = {
                "event_type": event_type,
                "source": "campaign",
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": data,
            }
            await redis_client.publish("events:campaign", json.dumps(redis_message))
            logger.debug(f"Published {event_type} to Redis")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")
        finally:
            if redis_client:
                await redis_client.close()


# Global instance
campaign_service = CampaignService()
