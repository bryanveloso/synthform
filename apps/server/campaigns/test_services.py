"""Tests for campaign services."""

from __future__ import annotations

from datetime import timedelta

from asgiref.sync import async_to_sync
from django.test import TestCase
from django.test import TransactionTestCase
from django.utils import timezone

from campaigns.models import Campaign
from campaigns.models import Gift
from campaigns.models import Metric
from campaigns.models import Milestone
from campaigns.services import CampaignService
from events.models import Member


class CampaignServiceTest(TestCase):
    """Test CampaignService functionality with async methods."""

    def setUp(self):
        """Set up test data."""
        self.service = CampaignService()
        self.campaign = Campaign.objects.create(
            name="Test Campaign",
            slug="test-campaign",
            description="Campaign for testing",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            is_active=True,
            timer_mode=True,
            timer_initial_seconds=3600,
            seconds_per_sub=180,
            seconds_per_tier2=360,
            seconds_per_tier3=900,
            max_timer_seconds=86400,
        )

        # Create some milestones
        self.milestone_50 = Milestone.objects.create(
            campaign=self.campaign,
            threshold=50,
            title="First Goal",
            description="First milestone",
        )

        self.milestone_100 = Milestone.objects.create(
            campaign=self.campaign,
            threshold=100,
            title="Second Goal",
            description="Second milestone",
        )

    def test_get_active_campaign(self):
        """Test getting the active campaign."""
        result = async_to_sync(self.service.get_active_campaign)()
        self.assertEqual(result, self.campaign)

    def test_get_active_campaign_none(self):
        """Test when no active campaign exists."""
        self.campaign.is_active = False
        self.campaign.save()

        result = async_to_sync(self.service.get_active_campaign)()
        self.assertIsNone(result)

    def test_process_subscription_creates_metric(self):
        """Test that processing a subscription creates a metric if it doesn't exist."""
        result = async_to_sync(self.service.process_subscription)(self.campaign)

        self.assertEqual(result["campaign_id"], str(self.campaign.id))
        self.assertEqual(result["campaign_name"], "Test Campaign")
        self.assertEqual(result["total_subs"], 1)

        # Verify metric was created
        metric = Metric.objects.get(campaign=self.campaign)
        self.assertEqual(metric.total_subs, 1)

    def test_process_subscription_increments_count(self):
        """Test that subscriptions increment the count."""
        # Create initial metric
        Metric.objects.create(campaign=self.campaign, total_subs=10)

        result = async_to_sync(self.service.process_subscription)(self.campaign)
        self.assertEqual(result["total_subs"], 11)

        # Process another sub
        result = async_to_sync(self.service.process_subscription)(self.campaign)
        self.assertEqual(result["total_subs"], 12)

    def test_process_subscription_tier1_timer(self):
        """Test tier 1 subscription adds correct timer seconds."""
        # Start the timer first
        async_to_sync(self.service.start_timer)(self.campaign)

        result = async_to_sync(self.service.process_subscription)(self.campaign, tier=1)

        self.assertEqual(result["timer_seconds_added"], 180)
        self.assertGreaterEqual(result["timer_seconds_remaining"], 3780)  # 3600 + 180

    def test_process_subscription_tier2_timer(self):
        """Test tier 2 subscription adds correct timer seconds."""
        # Start the timer first
        async_to_sync(self.service.start_timer)(self.campaign)

        result = async_to_sync(self.service.process_subscription)(self.campaign, tier=2)

        self.assertEqual(result["timer_seconds_added"], 360)
        self.assertGreaterEqual(result["timer_seconds_remaining"], 3960)  # 3600 + 360

    def test_process_subscription_tier3_timer(self):
        """Test tier 3 subscription adds correct timer seconds."""
        # Start the timer first
        async_to_sync(self.service.start_timer)(self.campaign)

        result = async_to_sync(self.service.process_subscription)(self.campaign, tier=3)

        self.assertEqual(result["timer_seconds_added"], 900)
        self.assertGreaterEqual(result["timer_seconds_remaining"], 4500)  # 3600 + 900

    def test_process_subscription_no_timer_mode(self):
        """Test subscription processing when timer mode is disabled."""
        self.campaign.timer_mode = False
        self.campaign.save()

        result = async_to_sync(self.service.process_subscription)(self.campaign)

        self.assertEqual(result["timer_seconds_added"], 0)
        self.assertEqual(result["timer_seconds_remaining"], 0)

    def test_process_subscription_unlocks_milestone(self):
        """Test that hitting a milestone threshold unlocks it."""
        # Set initial subs to 49
        Metric.objects.create(campaign=self.campaign, total_subs=49)

        # Process a sub to hit 50
        result = async_to_sync(self.service.process_subscription)(self.campaign)

        self.assertEqual(result["total_subs"], 50)
        self.assertIn("milestone_unlocked", result)
        self.assertEqual(result["milestone_unlocked"]["threshold"], 50)
        self.assertEqual(result["milestone_unlocked"]["title"], "First Goal")

        # Verify milestone is unlocked in database
        self.milestone_50.refresh_from_db()
        self.assertTrue(self.milestone_50.is_unlocked)
        self.assertIsNotNone(self.milestone_50.unlocked_at)

    def test_process_subscription_skips_unlocked_milestone(self):
        """Test that already unlocked milestones are not re-unlocked."""
        # Unlock the first milestone
        self.milestone_50.is_unlocked = True
        self.milestone_50.save()

        # Set subs to 99
        Metric.objects.create(campaign=self.campaign, total_subs=99)

        # Process a sub to hit 100
        result = async_to_sync(self.service.process_subscription)(self.campaign)

        self.assertEqual(result["total_subs"], 100)
        self.assertIn("milestone_unlocked", result)
        # Should unlock the 100 milestone, not the 50
        self.assertEqual(result["milestone_unlocked"]["threshold"], 100)

    def test_process_subscription_no_campaign(self):
        """Test processing subscription with no campaign."""
        result = async_to_sync(self.service.process_subscription)(None)
        self.assertEqual(result, {})

    def test_process_resub(self):
        """Test processing a resub message."""
        result = async_to_sync(self.service.process_resub)(self.campaign)

        self.assertEqual(result["campaign_id"], str(self.campaign.id))
        self.assertEqual(result["total_resubs"], 1)

        # Process another resub
        result = async_to_sync(self.service.process_resub)(self.campaign)
        self.assertEqual(result["total_resubs"], 2)

    def test_process_resub_no_campaign(self):
        """Test processing resub with no campaign."""
        result = async_to_sync(self.service.process_resub)(None)
        self.assertEqual(result, {})

    def test_process_bits(self):
        """Test processing bits."""
        result = async_to_sync(self.service.process_bits)(self.campaign, 1000)

        self.assertEqual(result["campaign_id"], str(self.campaign.id))
        self.assertEqual(result["total_bits"], 1000)

        # Process more bits
        result = async_to_sync(self.service.process_bits)(self.campaign, 500)
        self.assertEqual(result["total_bits"], 1500)

    def test_process_bits_no_campaign(self):
        """Test processing bits with no campaign."""
        result = async_to_sync(self.service.process_bits)(None, 1000)
        self.assertEqual(result, {})

    def test_start_timer_initial(self):
        """Test starting the timer for the first time."""
        result = async_to_sync(self.service.start_timer)(self.campaign)

        self.assertTrue(result["timer_started"])
        self.assertEqual(result["timer_seconds_remaining"], 3600)

        # Verify in database
        metric = Metric.objects.get(campaign=self.campaign)
        self.assertIsNotNone(metric.timer_started_at)
        self.assertIsNone(metric.timer_paused_at)
        self.assertEqual(metric.timer_seconds_remaining, 3600)

    def test_start_timer_adds_to_existing(self):
        """Test starting timer when it already has time."""
        # Create metric with existing time
        Metric.objects.create(
            campaign=self.campaign,
            timer_seconds_remaining=1800,
            timer_started_at=timezone.now(),
        )

        result = async_to_sync(self.service.start_timer)(self.campaign)

        self.assertTrue(result["timer_started"])
        self.assertEqual(result["timer_seconds_remaining"], 5400)  # 1800 + 3600

    def test_start_timer_no_timer_mode(self):
        """Test starting timer when timer mode is disabled."""
        self.campaign.timer_mode = False
        self.campaign.save()

        result = async_to_sync(self.service.start_timer)(self.campaign)

        self.assertEqual(result["error"], "Campaign does not have timer mode enabled")

    def test_start_timer_no_campaign(self):
        """Test starting timer with no campaign."""
        result = async_to_sync(self.service.start_timer)(None)
        self.assertEqual(result["error"], "Campaign does not have timer mode enabled")

    def test_pause_timer(self):
        """Test pausing the timer."""
        # Start timer first
        async_to_sync(self.service.start_timer)(self.campaign)

        result = async_to_sync(self.service.pause_timer)(self.campaign)

        self.assertTrue(result["timer_paused"])
        self.assertEqual(result["timer_seconds_remaining"], 3600)

        # Verify in database
        metric = Metric.objects.get(campaign=self.campaign)
        self.assertIsNotNone(metric.timer_paused_at)

    def test_pause_timer_no_metric(self):
        """Test pausing timer when no metric exists."""
        result = async_to_sync(self.service.pause_timer)(self.campaign)
        self.assertEqual(result["error"], "No metric found for campaign")

    def test_pause_timer_no_timer_mode(self):
        """Test pausing timer when timer mode is disabled."""
        self.campaign.timer_mode = False
        self.campaign.save()

        result = async_to_sync(self.service.pause_timer)(self.campaign)
        self.assertEqual(result["error"], "Campaign does not have timer mode enabled")

    def test_update_vote_initializes(self):
        """Test that voting data is initialized properly."""
        result = async_to_sync(self.service.update_vote)(self.campaign, "viera", 5)

        self.assertEqual(result["voting_update"]["viera"], 5)

        # Verify in database
        metric = Metric.objects.get(campaign=self.campaign)
        self.assertEqual(metric.extra_data["ffxiv_votes"]["viera"], 5)

    def test_update_vote_accumulates(self):
        """Test that votes accumulate properly."""
        # First vote
        async_to_sync(self.service.update_vote)(self.campaign, "viera", 5)

        # Second vote
        result = async_to_sync(self.service.update_vote)(self.campaign, "viera", 3)
        self.assertEqual(result["voting_update"]["viera"], 8)

        # Add votes for different option
        result = async_to_sync(self.service.update_vote)(self.campaign, "lalafell", 10)
        self.assertEqual(result["voting_update"]["viera"], 8)
        self.assertEqual(result["voting_update"]["lalafell"], 10)

    def test_update_vote_no_campaign(self):
        """Test updating vote with no campaign."""
        result = async_to_sync(self.service.update_vote)(None, "viera", 5)
        self.assertEqual(result, {})

    def test_check_milestone_unlock(self):
        """Test the milestone unlock checking method."""
        # Create metric at 50 subs
        Metric.objects.create(campaign=self.campaign, total_subs=50)

        # Check milestone unlock
        milestone = async_to_sync(self.service._check_milestone_unlock)(
            self.campaign, 50
        )

        self.assertIsNotNone(milestone)
        self.assertEqual(milestone.threshold, 50)
        self.assertTrue(milestone.is_unlocked)

    def test_check_milestone_unlock_none_available(self):
        """Test milestone check when no milestones are available to unlock."""
        # Unlock all milestones
        self.milestone_50.is_unlocked = True
        self.milestone_50.save()
        self.milestone_100.is_unlocked = True
        self.milestone_100.save()

        milestone = async_to_sync(self.service._check_milestone_unlock)(
            self.campaign, 150
        )

        self.assertIsNone(milestone)

    def test_check_milestone_unlock_highest_available(self):
        """Test that the highest available milestone is unlocked."""
        # Jump straight to 100 subs
        milestone = async_to_sync(self.service._check_milestone_unlock)(
            self.campaign, 100
        )

        # Should unlock the 100 milestone, not the 50
        self.assertIsNotNone(milestone)
        self.assertEqual(milestone.threshold, 100)


class CampaignServiceConcurrencyTest(TransactionTestCase):
    """Test concurrent operations in CampaignService."""

    def setUp(self):
        """Set up test data."""
        self.service = CampaignService()
        self.campaign = Campaign.objects.create(
            name="Concurrent Campaign",
            slug="concurrent",
            description="Testing concurrency",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
            is_active=True,
        )

    def test_concurrent_subscription_processing(self):
        """Test that concurrent subscriptions are handled correctly."""
        from concurrent.futures import ThreadPoolExecutor

        def process_sub():
            return async_to_sync(self.service.process_subscription)(self.campaign)

        # Process 10 subscriptions concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_sub) for _ in range(10)]
            results = [f.result() for f in futures]

        # Check that we have exactly 10 subs
        metric = Metric.objects.get(campaign=self.campaign)
        self.assertEqual(metric.total_subs, 10)

        # All results should show incrementing totals
        totals = [r["total_subs"] for r in results]
        self.assertEqual(set(totals), set(range(1, 11)))

    def test_concurrent_vote_updates(self):
        """Test that concurrent vote updates work correctly."""
        from concurrent.futures import ThreadPoolExecutor

        def vote_viera():
            return async_to_sync(self.service.update_vote)(self.campaign, "viera", 1)

        def vote_lalafell():
            return async_to_sync(self.service.update_vote)(self.campaign, "lalafell", 1)

        # Process 20 votes concurrently (10 each)
        with ThreadPoolExecutor(max_workers=10) as executor:
            viera_futures = [executor.submit(vote_viera) for _ in range(10)]
            lalafell_futures = [executor.submit(vote_lalafell) for _ in range(10)]

            for f in viera_futures + lalafell_futures:
                f.result()

        # Check final vote counts
        metric = Metric.objects.get(campaign=self.campaign)
        self.assertEqual(metric.extra_data["ffxiv_votes"]["viera"], 10)
        self.assertEqual(metric.extra_data["ffxiv_votes"]["lalafell"], 10)

    def test_process_subscription_tracks_gift(self):
        """Test that gift subscriptions are tracked."""
        async_to_sync(self.service.process_subscription)(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id="gifter123",
            gifter_name="TestGifter",
        )

        # Check that gift was tracked
        member = Member.objects.get(twitch_id="gifter123")
        self.assertEqual(member.display_name, "TestGifter")

        gift = Gift.objects.get(member=member, campaign=self.campaign)
        self.assertEqual(gift.tier1_count, 1)
        self.assertEqual(gift.total_count, 1)
        self.assertIsNotNone(gift.first_gift_at)
        self.assertIsNotNone(gift.last_gift_at)

    def test_process_subscription_accumulates_gifts(self):
        """Test that multiple gift subs accumulate correctly."""
        # First gift
        async_to_sync(self.service.process_subscription)(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id="gifter123",
            gifter_name="TestGifter",
        )

        # Second gift (tier 2)
        async_to_sync(self.service.process_subscription)(
            self.campaign,
            tier=2,
            is_gift=True,
            gifter_id="gifter123",
            gifter_name="TestGifter",
        )

        # Third gift (tier 1 again)
        async_to_sync(self.service.process_subscription)(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id="gifter123",
            gifter_name="TestGifter",
        )

        gift = Gift.objects.get(member__twitch_id="gifter123")
        self.assertEqual(gift.tier1_count, 2)
        self.assertEqual(gift.tier2_count, 1)
        self.assertEqual(gift.tier3_count, 0)
        self.assertEqual(gift.total_count, 3)

    def test_process_subscription_no_gift_tracking_without_id(self):
        """Test that gifts aren't tracked without a gifter ID."""
        # Gift without gifter_id
        async_to_sync(self.service.process_subscription)(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id=None,
            gifter_name="TestGifter",
        )

        # Should not create any gift records
        self.assertEqual(Gift.objects.count(), 0)

    def test_get_gift_leaderboard(self):
        """Test getting the gift leaderboard."""
        # Create some members with gifts
        member1 = Member.objects.create(
            twitch_id="top_gifter",
            display_name="TopGifter",
            username="topgifter",
        )
        Gift.objects.create(
            member=member1,
            campaign=self.campaign,
            tier1_count=50,
            tier2_count=10,
            tier3_count=5,
            total_count=65,
        )

        member2 = Member.objects.create(
            twitch_id="mid_gifter",
            display_name="MidGifter",
            username="midgifter",
        )
        Gift.objects.create(
            member=member2,
            campaign=self.campaign,
            tier1_count=20,
            total_count=20,
        )

        member3 = Member.objects.create(
            twitch_id="small_gifter",
            display_name="SmallGifter",
            username="smallgifter",
        )
        Gift.objects.create(
            member=member3,
            campaign=self.campaign,
            tier1_count=5,
            total_count=5,
        )

        # Get leaderboard
        leaderboard = async_to_sync(self.service.get_gift_leaderboard)(
            self.campaign, limit=2
        )

        self.assertEqual(len(leaderboard), 2)
        self.assertEqual(leaderboard[0]["display_name"], "TopGifter")
        self.assertEqual(leaderboard[0]["total_count"], 65)
        self.assertEqual(leaderboard[1]["display_name"], "MidGifter")
        self.assertEqual(leaderboard[1]["total_count"], 20)

    def test_get_gift_leaderboard_empty(self):
        """Test getting leaderboard with no gifts."""
        leaderboard = async_to_sync(self.service.get_gift_leaderboard)(self.campaign)
        self.assertEqual(leaderboard, [])

    def test_gift_tracking_updates_display_name(self):
        """Test that display name is updated if it changes."""
        # First gift with initial name
        async_to_sync(self.service.process_subscription)(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id="gifter123",
            gifter_name="OldName",
        )

        member = Member.objects.get(twitch_id="gifter123")
        self.assertEqual(member.display_name, "OldName")

        # Second gift with new name
        async_to_sync(self.service.process_subscription)(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id="gifter123",
            gifter_name="NewName",
        )

        member.refresh_from_db()
        self.assertEqual(member.display_name, "NewName")
