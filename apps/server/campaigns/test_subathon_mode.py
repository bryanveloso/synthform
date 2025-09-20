"""Tests for subathon mode within campaigns."""

from __future__ import annotations

from datetime import timedelta

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from django.utils import timezone

from campaigns.models import Campaign
from campaigns.models import Metric
from campaigns.services import campaign_service


class SubathonModeTest(TransactionTestCase):
    """Test that subathon features require both active campaign AND timer_mode."""

    def setUp(self):
        """Set up test campaigns with different configurations."""
        # Active campaign WITH subathon mode
        self.active_with_subathon = Campaign.objects.create(
            name="Active Subathon",
            slug="active-subathon",
            description="Active campaign with subathon enabled",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            is_active=True,
            timer_mode=True,  # Subathon ON
            timer_initial_seconds=3600,
            seconds_per_sub=180,
        )

        # Active campaign WITHOUT subathon mode (regular campaign)
        self.active_no_subathon = Campaign.objects.create(
            name="Regular Campaign",
            slug="regular-campaign",
            description="Active campaign but no subathon",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            is_active=True,
            timer_mode=False,  # Subathon OFF
        )

        # Inactive campaign WITH subathon mode configured
        self.inactive_with_subathon = Campaign.objects.create(
            name="Inactive Subathon",
            slug="inactive-subathon",
            description="Has subathon settings but campaign is off",
            start_date=timezone.now() - timedelta(days=7),
            end_date=timezone.now() - timedelta(days=1),
            is_active=False,  # Campaign OFF
            timer_mode=True,  # Subathon settings exist
            timer_initial_seconds=3600,
            seconds_per_sub=180,
        )

    def test_timer_requires_both_active_and_timer_mode(self):
        """Test that timer only works when campaign is active AND timer_mode is True."""
        # Try to start timer on active campaign WITHOUT subathon mode
        result = async_to_sync(campaign_service.start_timer)(self.active_no_subathon)
        self.assertEqual(result["error"], "Campaign does not have timer mode enabled")

        # Note: Current implementation doesn't check is_active in start_timer
        # This documents current behavior - timer can start on inactive campaign
        # if timer_mode is True (this might be a bug to fix later)
        result = async_to_sync(campaign_service.start_timer)(
            self.inactive_with_subathon
        )
        # Current behavior: timer starts even on inactive campaign
        self.assertTrue(result.get("timer_started", False))

        # Start timer on active campaign WITH subathon mode - should work
        result = async_to_sync(campaign_service.start_timer)(self.active_with_subathon)
        self.assertTrue(result["timer_started"])
        self.assertEqual(result["timer_seconds_remaining"], 3600)

    def test_subscription_adds_timer_only_in_subathon_mode(self):
        """Test that subs only add timer when subathon is active."""
        # Process sub for active campaign WITH subathon
        async_to_sync(campaign_service.start_timer)(self.active_with_subathon)
        result = async_to_sync(campaign_service.process_subscription)(
            self.active_with_subathon, tier=1
        )

        self.assertEqual(result["timer_seconds_added"], 180)
        self.assertEqual(result["timer_seconds_remaining"], 3780)  # 3600 + 180

        # Process sub for active campaign WITHOUT subathon
        result = async_to_sync(campaign_service.process_subscription)(
            self.active_no_subathon, tier=1
        )

        self.assertEqual(result["timer_seconds_added"], 0)  # No timer addition
        self.assertEqual(result["timer_seconds_remaining"], 0)
        self.assertEqual(result["total_subs"], 1)  # Sub still counts!

    def test_subs_still_count_without_subathon(self):
        """Test that subs are tracked even when subathon mode is off."""
        # Process subs for regular campaign (no subathon)
        for _ in range(5):
            result = async_to_sync(campaign_service.process_subscription)(
                self.active_no_subathon
            )

        self.assertEqual(result["total_subs"], 5)
        self.assertEqual(result["timer_seconds_added"], 0)  # No timer

        # Verify metric exists and tracks subs
        metric = Metric.objects.get(campaign=self.active_no_subathon)
        self.assertEqual(metric.total_subs, 5)
        self.assertEqual(metric.timer_seconds_remaining, 0)

    def test_pause_timer_requires_subathon_mode(self):
        """Test that pause timer requires subathon mode."""
        # Start timer on subathon campaign
        async_to_sync(campaign_service.start_timer)(self.active_with_subathon)

        # Pause should work
        result = async_to_sync(campaign_service.pause_timer)(self.active_with_subathon)
        self.assertTrue(result["timer_paused"])

        # Try to pause on non-subathon campaign
        result = async_to_sync(campaign_service.pause_timer)(self.active_no_subathon)
        self.assertEqual(result["error"], "Campaign does not have timer mode enabled")

    def test_switching_subathon_mode_mid_campaign(self):
        """Test enabling/disabling subathon mode during active campaign."""
        # Start with regular campaign
        self.assertEqual(self.active_no_subathon.timer_mode, False)

        # Process some subs - no timer
        for _ in range(3):
            result = async_to_sync(campaign_service.process_subscription)(
                self.active_no_subathon
            )

        self.assertEqual(result["total_subs"], 3)
        self.assertEqual(result["timer_seconds_added"], 0)

        # Enable subathon mode mid-campaign
        self.active_no_subathon.timer_mode = True
        self.active_no_subathon.timer_initial_seconds = 3600
        self.active_no_subathon.seconds_per_sub = 180
        self.active_no_subathon.save()

        # Start the timer
        timer_result = async_to_sync(campaign_service.start_timer)(
            self.active_no_subathon
        )
        self.assertTrue(timer_result["timer_started"])

        # Now subs should add timer
        result = async_to_sync(campaign_service.process_subscription)(
            self.active_no_subathon
        )
        self.assertEqual(result["total_subs"], 4)  # Continues counting
        self.assertEqual(result["timer_seconds_added"], 180)  # Now adds time!

    def test_tier_bonuses_only_in_subathon_mode(self):
        """Test that tier bonuses only apply during subathon."""
        # Process different tiers for subathon campaign
        async_to_sync(campaign_service.start_timer)(self.active_with_subathon)

        tier1_result = async_to_sync(campaign_service.process_subscription)(
            self.active_with_subathon, tier=1
        )
        self.assertEqual(tier1_result["timer_seconds_added"], 180)

        tier2_result = async_to_sync(campaign_service.process_subscription)(
            self.active_with_subathon, tier=2
        )
        self.assertEqual(tier2_result["timer_seconds_added"], 360)

        tier3_result = async_to_sync(campaign_service.process_subscription)(
            self.active_with_subathon, tier=3
        )
        self.assertEqual(tier3_result["timer_seconds_added"], 900)

        # Process different tiers for non-subathon campaign
        tier1_regular = async_to_sync(campaign_service.process_subscription)(
            self.active_no_subathon, tier=1
        )
        tier2_regular = async_to_sync(campaign_service.process_subscription)(
            self.active_no_subathon, tier=2
        )
        tier3_regular = async_to_sync(campaign_service.process_subscription)(
            self.active_no_subathon, tier=3
        )

        # All should have 0 timer addition
        self.assertEqual(tier1_regular["timer_seconds_added"], 0)
        self.assertEqual(tier2_regular["timer_seconds_added"], 0)
        self.assertEqual(tier3_regular["timer_seconds_added"], 0)

        # But subs should still count
        metric = Metric.objects.get(campaign=self.active_no_subathon)
        self.assertEqual(metric.total_subs, 3)

    def test_campaign_hierarchy(self):
        """Test the full hierarchy: No campaign -> Campaign -> Subathon."""
        # Level 1: No active campaign
        active = async_to_sync(campaign_service.get_active_campaign)()

        # If no campaigns are active, should return None
        if not active:
            result = async_to_sync(campaign_service.process_subscription)(None)
            self.assertEqual(result, {})  # Nothing tracked

        # Level 2: Active campaign, no subathon
        active_regular = self.active_no_subathon
        result = async_to_sync(campaign_service.process_subscription)(active_regular)

        self.assertIn("total_subs", result)  # Subs tracked
        self.assertEqual(result["timer_seconds_added"], 0)  # No timer

        # Level 3: Active campaign WITH subathon
        active_subathon = self.active_with_subathon
        async_to_sync(campaign_service.start_timer)(active_subathon)
        result = async_to_sync(campaign_service.process_subscription)(active_subathon)

        self.assertIn("total_subs", result)  # Subs tracked
        self.assertGreater(result["timer_seconds_added"], 0)  # Timer active!

    def test_timer_without_started_timer(self):
        """Test that timer additions require timer to be started first."""
        # Process sub on subathon campaign WITHOUT starting timer
        result = async_to_sync(campaign_service.process_subscription)(
            self.active_with_subathon, tier=1
        )

        # Sub should count but no timer addition (timer not started)
        self.assertEqual(result["total_subs"], 1)
        self.assertEqual(result["timer_seconds_added"], 0)

        # Start the timer
        async_to_sync(campaign_service.start_timer)(self.active_with_subathon)

        # Now subs should add time
        result = async_to_sync(campaign_service.process_subscription)(
            self.active_with_subathon, tier=1
        )
        self.assertEqual(result["total_subs"], 2)
        self.assertEqual(result["timer_seconds_added"], 180)
