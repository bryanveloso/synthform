"""Campaign tracking service for processing events and managing metrics."""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import F
from django.utils import timezone

from .models import Campaign
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
    async def process_subscription(
        campaign: Campaign, tier: int = 1, is_gift: bool = False
    ) -> dict[str, Any]:
        """Process a subscription or gift sub for the campaign.

        Returns:
            Dict containing any milestone unlocks and updated metrics
        """
        if not campaign:
            return {}

        try:
            metric = await Metric.objects.select_for_update().aget(campaign=campaign)
        except Metric.DoesNotExist:
            # Create metric if it doesn't exist
            metric = await Metric.objects.acreate(campaign=campaign)

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

            metric.timer_seconds_remaining = F("timer_seconds_remaining") + timer_added

            # Apply cap if configured
            if campaign.max_timer_seconds:
                # This needs to be done in a separate query after save
                pass

        await metric.asave()

        # Refresh to get actual values
        await metric.arefresh_from_db()

        # Check for milestone unlocks
        unlocked_milestone = await CampaignService._check_milestone_unlock(
            campaign, metric.total_subs
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
                "announcement_text": unlocked_milestone.announcement_text,
            }
            logger.info(
                f"🎉 Milestone unlocked! {unlocked_milestone.threshold}: {unlocked_milestone.title}"
            )

            # Publish milestone unlock event
            from synthform.websocket import publish_to_overlay

            await publish_to_overlay("campaign:milestone", result["milestone_unlocked"])

        # Publish metric update
        from synthform.websocket import publish_to_overlay

        await publish_to_overlay(
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
    async def process_resub(campaign: Campaign) -> dict[str, Any]:
        """Process a resub message for the campaign."""
        if not campaign:
            return {}

        try:
            metric = await Metric.objects.select_for_update().aget(campaign=campaign)
        except Metric.DoesNotExist:
            metric = await Metric.objects.acreate(campaign=campaign)

        metric.total_resubs = F("total_resubs") + 1
        await metric.asave()
        await metric.arefresh_from_db()

        return {
            "campaign_id": str(campaign.id),
            "campaign_name": campaign.name,
            "total_resubs": metric.total_resubs,
        }

    @staticmethod
    async def process_bits(campaign: Campaign, bits: int) -> dict[str, Any]:
        """Process a bits cheer for the campaign."""
        if not campaign:
            return {}

        try:
            metric = await Metric.objects.select_for_update().aget(campaign=campaign)
        except Metric.DoesNotExist:
            metric = await Metric.objects.acreate(campaign=campaign)

        metric.total_bits = F("total_bits") + bits
        await metric.asave()
        await metric.arefresh_from_db()

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
    async def start_timer(campaign: Campaign) -> dict[str, Any]:
        """Start or restart the subathon timer."""
        if not campaign or not campaign.timer_mode:
            return {"error": "Campaign does not have timer mode enabled"}

        try:
            metric = await Metric.objects.select_for_update().aget(campaign=campaign)
        except Metric.DoesNotExist:
            metric = await Metric.objects.acreate(campaign=campaign)

        # Initialize or add to timer
        if not metric.timer_started_at:
            metric.timer_seconds_remaining = campaign.timer_initial_seconds
        else:
            metric.timer_seconds_remaining = (
                F("timer_seconds_remaining") + campaign.timer_initial_seconds
            )

        metric.timer_started_at = timezone.now()
        metric.timer_paused_at = None
        await metric.asave()
        await metric.arefresh_from_db()

        return {
            "campaign_id": str(campaign.id),
            "timer_started": True,
            "timer_seconds_remaining": metric.timer_seconds_remaining,
        }

    @staticmethod
    async def pause_timer(campaign: Campaign) -> dict[str, Any]:
        """Pause the subathon timer."""
        if not campaign or not campaign.timer_mode:
            return {"error": "Campaign does not have timer mode enabled"}

        try:
            metric = await Metric.objects.aget(campaign=campaign)
            metric.timer_paused_at = timezone.now()
            await metric.asave()

            return {
                "campaign_id": str(campaign.id),
                "timer_paused": True,
                "timer_seconds_remaining": metric.timer_seconds_remaining,
            }
        except Metric.DoesNotExist:
            return {"error": "No metric found for campaign"}

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

        try:
            metric = await Metric.objects.select_for_update().aget(campaign=campaign)
        except Metric.DoesNotExist:
            metric = await Metric.objects.acreate(campaign=campaign)

        # Initialize voting data if not present
        if "ffxiv_votes" not in metric.extra_data:
            metric.extra_data["ffxiv_votes"] = {}

        # Update vote count
        current_votes = metric.extra_data["ffxiv_votes"].get(option, 0)
        metric.extra_data["ffxiv_votes"][option] = current_votes + votes

        await metric.asave()

        return {
            "campaign_id": str(campaign.id),
            "voting_update": metric.extra_data["ffxiv_votes"],
        }


# Global instance
campaign_service = CampaignService()
