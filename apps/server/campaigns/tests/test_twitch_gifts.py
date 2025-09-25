"""Tests for Twitch gift subscription event handling."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.utils import timezone

from campaigns.models import Campaign
from campaigns.models import Gift
from campaigns.models import Metric
from campaigns.models import Milestone
from campaigns.services import campaign_service
from events.models import Member


@pytest.mark.django_db(transaction=True)
class TestGiftSubscriptionHandling(TestCase):
    """Test gift subscription handling in campaigns."""

    def setUp(self):
        """Set up test data."""
        self.campaign = Campaign.objects.create(
            name="Test Campaign",
            slug="test-campaign",
            description="Test campaign for gift tracking",
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=7),
            is_active=True,
            timer_mode=True,
            timer_initial_seconds=3600,
            seconds_per_sub=180,
            seconds_per_tier2=360,
            seconds_per_tier3=900,
        )

        # Create a metric for the campaign
        self.metric = Metric.objects.create(campaign=self.campaign)

        # Create a milestone
        self.milestone = Milestone.objects.create(
            campaign=self.campaign,
            threshold=10,
            title="Test Milestone",
            description="Test milestone description",
        )

    @pytest.mark.asyncio
    async def test_process_single_gift_subscription(self):
        """Test processing a single gift subscription."""
        result = await campaign_service.process_subscription(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id="123456",
            gifter_name="TestGifter",
        )

        # Check campaign tracking
        assert result["campaign_id"] == str(self.campaign.id)
        assert result["total_subs"] == 1
        assert result["timer_seconds_added"] == 180  # tier 1 adds 180 seconds
        assert result["timer_seconds_remaining"] == 180

        # Check gift tracking
        gift = await Gift.objects.select_related("member").aget(
            member__twitch_id="123456", campaign=self.campaign
        )
        assert gift.tier1_count == 1
        assert gift.total_count == 1
        assert gift.member.display_name == "TestGifter"

    @pytest.mark.asyncio
    async def test_process_multiple_gift_subscriptions(self):
        """Test processing multiple gift subscriptions from same user."""
        # Process first batch of gifts
        for i in range(5):
            await campaign_service.process_subscription(
                self.campaign,
                tier=1,
                is_gift=True,
                gifter_id="123456",
                gifter_name="TestGifter",
            )

        # Process tier 2 gifts
        for i in range(3):
            await campaign_service.process_subscription(
                self.campaign,
                tier=2,
                is_gift=True,
                gifter_id="123456",
                gifter_name="TestGifter",
            )

        # Check gift tracking
        gift = await Gift.objects.aget(
            member__twitch_id="123456", campaign=self.campaign
        )
        assert gift.tier1_count == 5
        assert gift.tier2_count == 3
        assert gift.total_count == 8

    @pytest.mark.asyncio
    async def test_gift_milestone_unlock(self):
        """Test that gift subscriptions can unlock milestones."""
        # Process gifts to reach milestone
        for i in range(10):
            result = await campaign_service.process_subscription(
                self.campaign,
                tier=1,
                is_gift=True,
                gifter_id=f"user{i}",
                gifter_name=f"User{i}",
            )

        # Last gift should unlock the milestone
        assert "milestone_unlocked" in result
        assert result["milestone_unlocked"]["threshold"] == 10
        assert result["milestone_unlocked"]["title"] == "Test Milestone"

        # Check milestone is marked as unlocked
        milestone = await Milestone.objects.aget(id=self.milestone.id)
        assert milestone.is_unlocked is True
        assert milestone.unlocked_at is not None

    @pytest.mark.asyncio
    async def test_anonymous_gift_handling(self):
        """Test handling of anonymous gift subscriptions."""
        result = await campaign_service.process_subscription(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id=None,
            gifter_name=None,
        )

        # Should still track the subscription for campaign metrics
        assert result["total_subs"] == 1
        assert result["timer_seconds_added"] == 180

        # No gift record should be created for anonymous gifts
        gift_count = await Gift.objects.filter(campaign=self.campaign).acount()
        assert gift_count == 0

    @pytest.mark.asyncio
    async def test_gift_leaderboard(self):
        """Test gift leaderboard generation."""
        # Create gifts from multiple users
        test_gifts = [
            ("user1", "TopGifter", 50, 5, 1),
            ("user2", "MidGifter", 20, 2, 0),
            ("user3", "SmallGifter", 5, 0, 0),
        ]

        for twitch_id, name, tier1, tier2, tier3 in test_gifts:
            member, _ = await Member.objects.aget_or_create(
                twitch_id=twitch_id, defaults={"display_name": name}
            )
            await Gift.objects.acreate(
                member=member,
                campaign=self.campaign,
                tier1_count=tier1,
                tier2_count=tier2,
                tier3_count=tier3,
                total_count=tier1 + tier2 + tier3,
                first_gift_at=timezone.now(),
                last_gift_at=timezone.now(),
            )

        # Get leaderboard
        leaderboard = await campaign_service.get_gift_leaderboard(
            self.campaign, limit=10
        )

        assert len(leaderboard) == 3
        assert leaderboard[0]["display_name"] == "TopGifter"
        assert leaderboard[0]["total_count"] == 56
        assert leaderboard[1]["display_name"] == "MidGifter"
        assert leaderboard[1]["total_count"] == 22
        assert leaderboard[2]["display_name"] == "SmallGifter"
        assert leaderboard[2]["total_count"] == 5

    @pytest.mark.asyncio
    async def test_gift_tracking_race_condition(self):
        """Test that gift tracking handles race conditions properly."""
        # Simulate concurrent gift processing
        tasks = []
        for i in range(10):
            tasks.append(
                campaign_service.process_subscription(
                    self.campaign,
                    tier=1,
                    is_gift=True,
                    gifter_id="123456",
                    gifter_name="TestGifter",
                )
            )

        # Process all gifts
        import asyncio

        await asyncio.gather(*tasks)

        # Check final count is correct
        gift = await Gift.objects.aget(
            member__twitch_id="123456", campaign=self.campaign
        )
        assert gift.total_count == 10
        assert gift.tier1_count == 10

    @pytest.mark.asyncio
    async def test_gift_with_different_tiers(self):
        """Test tracking gifts of different tiers."""
        # Process tier 1 gift
        await campaign_service.process_subscription(
            self.campaign,
            tier=1,
            is_gift=True,
            gifter_id="123456",
            gifter_name="TestGifter",
        )

        # Process tier 2 gift
        await campaign_service.process_subscription(
            self.campaign,
            tier=2,
            is_gift=True,
            gifter_id="123456",
            gifter_name="TestGifter",
        )

        # Process tier 3 gift
        await campaign_service.process_subscription(
            self.campaign,
            tier=3,
            is_gift=True,
            gifter_id="123456",
            gifter_name="TestGifter",
        )

        gift = await Gift.objects.aget(
            member__twitch_id="123456", campaign=self.campaign
        )
        assert gift.tier1_count == 1
        assert gift.tier2_count == 1
        assert gift.tier3_count == 1
        assert gift.total_count == 3

        # Check timer seconds added correctly
        metric = await Metric.objects.aget(campaign=self.campaign)
        expected_seconds = 180 + 360 + 900  # tier1 + tier2 + tier3
        assert metric.timer_seconds_remaining == expected_seconds


@pytest.mark.django_db(transaction=True)
class TestTwitchEventIntegration(TestCase):
    """Test integration with Twitch event handler."""

    def setUp(self):
        """Set up test data."""
        self.campaign = Campaign.objects.create(
            name="Test Campaign",
            slug="test-campaign",
            description="Test campaign",
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=7),
            is_active=True,
        )

    @pytest.mark.asyncio
    @patch("events.services.twitch.campaign_service")
    async def test_twitch_gift_event_processing(self, mock_campaign_service):
        """Test that Twitch gift events are processed correctly."""
        # Mock the campaign service
        mock_campaign_service.get_active_campaign.return_value = self.campaign
        mock_campaign_service.process_subscription.return_value = {
            "campaign_id": str(self.campaign.id),
            "total_subs": 1,
            "timer_seconds_added": 180,
            "timer_seconds_remaining": 180,
        }

        # Import the handler after setting up mocks
        from events.services.twitch import TwitchEventHandler

        handler = TwitchEventHandler()

        # Create a mock gift payload
        mock_payload = MagicMock()
        mock_payload.user.id = "123456"
        mock_payload.user.name = "testgifter"
        mock_payload.user.display_name = "TestGifter"
        mock_payload.broadcaster.id = "789"
        mock_payload.broadcaster.name = "streamer"
        mock_payload.broadcaster.display_name = "Streamer"
        mock_payload.total = 5
        mock_payload.tier = 1
        mock_payload.cumulative_total = 10
        mock_payload.anonymous = False

        # Process the gift event
        await handler._handle_channel_subscription_gift(
            "channel.subscription.gift", mock_payload
        )

        # Verify campaign service was called correctly
        assert (
            mock_campaign_service.process_subscription.call_count == 5
        )  # One per gift
        for call in mock_campaign_service.process_subscription.call_args_list:
            args, kwargs = call
            assert args[0] == self.campaign
            assert kwargs["tier"] == 1
            assert kwargs["is_gift"] is True
            assert kwargs["gifter_id"] == "123456"
            assert kwargs["gifter_name"] == "TestGifter"
