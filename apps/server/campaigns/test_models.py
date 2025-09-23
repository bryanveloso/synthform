"""Tests for campaign models."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from campaigns.models import Campaign
from campaigns.models import Metric
from campaigns.models import Milestone


class CampaignModelTest(TestCase):
    """Test Campaign model functionality."""

    def setUp(self):
        """Set up test data."""
        self.campaign = Campaign.objects.create(
            name="Test Subathon",
            slug="test-subathon",
            description="A test campaign",
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

    def test_campaign_creation(self):
        """Test creating a campaign with all fields."""
        self.assertEqual(self.campaign.name, "Test Subathon")
        self.assertEqual(self.campaign.slug, "test-subathon")
        self.assertTrue(self.campaign.is_active)
        self.assertTrue(self.campaign.timer_mode)
        self.assertEqual(self.campaign.timer_initial_seconds, 3600)
        self.assertIsNotNone(self.campaign.id)

    def test_campaign_string_representation(self):
        """Test campaign __str__ method."""
        self.assertEqual(str(self.campaign), "Test Subathon")

    def test_campaign_ordering(self):
        """Test campaigns are ordered by start_date descending."""
        older_campaign = Campaign.objects.create(
            name="Older Campaign",
            slug="older",
            description="An older campaign",
            start_date=timezone.now() - timedelta(days=30),
            end_date=timezone.now() - timedelta(days=23),
        )

        campaigns = list(Campaign.objects.all())
        self.assertEqual(campaigns[0], self.campaign)
        self.assertEqual(campaigns[1], older_campaign)

    def test_campaign_slug_uniqueness(self):
        """Test that campaign slugs must be unique."""
        with self.assertRaises(IntegrityError):
            Campaign.objects.create(
                name="Another Campaign",
                slug="test-subathon",  # Duplicate slug
                description="Another test",
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=1),
            )

    def test_campaign_defaults(self):
        """Test default values for campaign fields."""
        campaign = Campaign.objects.create(
            name="Default Campaign",
            slug="default",
            description="Testing defaults",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
        )

        self.assertFalse(campaign.is_active)
        self.assertFalse(campaign.timer_mode)
        self.assertEqual(campaign.timer_initial_seconds, 3600)
        self.assertEqual(campaign.seconds_per_sub, 180)
        self.assertEqual(campaign.seconds_per_tier2, 360)
        self.assertEqual(campaign.seconds_per_tier3, 900)
        self.assertIsNone(campaign.max_timer_seconds)

    def test_multiple_active_campaigns(self):
        """Test that multiple campaigns can be active simultaneously."""
        Campaign.objects.create(
            name="Second Active",
            slug="second-active",
            description="Another active campaign",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=3),
            is_active=True,
        )

        active_campaigns = Campaign.objects.filter(is_active=True)
        self.assertEqual(active_campaigns.count(), 2)

    def test_get_sessions(self):
        """Test getting sessions within campaign date range."""
        from streams.models import Session

        # Create sessions - some within range, some outside
        yesterday = timezone.now().date() - timedelta(days=1)
        today = timezone.now().date()
        next_week = timezone.now().date() + timedelta(days=8)

        # Within campaign range
        session1 = Session.objects.create(session_date=today)
        session2 = Session.objects.create(session_date=today + timedelta(days=3))

        # Outside campaign range
        Session.objects.create(session_date=yesterday)
        Session.objects.create(session_date=next_week)

        sessions = self.campaign.get_sessions()
        self.assertEqual(sessions.count(), 2)
        self.assertIn(session1, sessions)
        self.assertIn(session2, sessions)

    def test_calculate_total_duration_no_sessions(self):
        """Test calculating total duration with no sessions."""
        total = self.campaign.calculate_total_duration()
        self.assertEqual(total, 0)

    def test_calculate_total_duration_completed_sessions(self):
        """Test calculating total duration with completed sessions."""
        from streams.models import Session

        # Create completed sessions with durations
        today = timezone.now().date()
        session1 = Session.objects.create(
            session_date=today,
            started_at=timezone.now() - timedelta(hours=5),
            ended_at=timezone.now() - timedelta(hours=3),
            duration=7200,  # 2 hours
        )
        session2 = Session.objects.create(
            session_date=today + timedelta(days=1),
            started_at=timezone.now() - timedelta(hours=10),
            ended_at=timezone.now() - timedelta(hours=7),
            duration=10800,  # 3 hours
        )

        total = self.campaign.calculate_total_duration()
        self.assertEqual(total, 18000)  # 5 hours total

    def test_calculate_total_duration_with_live_session(self):
        """Test calculating total duration including a live session."""
        from streams.models import Session

        # Create a completed session within campaign range
        today = timezone.now().date()
        Session.objects.create(
            session_date=today,
            started_at=timezone.now() - timedelta(hours=5),
            ended_at=timezone.now() - timedelta(hours=3),
            duration=7200,  # 2 hours
        )

        # Create a live session (started 1 hour ago, not ended)
        tomorrow = today + timedelta(days=1)
        started = timezone.now() - timedelta(hours=1)
        Session.objects.create(
            session_date=tomorrow,
            started_at=started,
            ended_at=None,  # Still live
            duration=0,  # Not calculated yet
        )

        total = self.campaign.calculate_total_duration()
        # Should be roughly 2 hours + 1 hour = 10800 seconds
        self.assertGreaterEqual(total, 10700)  # Allow some margin for test execution
        self.assertLessEqual(total, 10900)

    def test_get_current_session_start_no_live(self):
        """Test getting current session start when not live."""
        start = self.campaign.get_current_session_start()
        self.assertIsNone(start)

    def test_get_current_session_start_with_live(self):
        """Test getting current session start when live."""
        from streams.models import Session

        # Create a live session
        now = timezone.now()
        today = now.date()
        started = now - timedelta(hours=2)

        session = Session.objects.create(
            session_date=today,
            started_at=started,
            ended_at=None,  # Still live
        )

        start = self.campaign.get_current_session_start()
        self.assertEqual(start, started)

    def test_get_current_session_start_ignores_ended(self):
        """Test that ended sessions are not considered current."""
        from streams.models import Session

        # Create an ended session today
        today = timezone.now().date()
        Session.objects.create(
            session_date=today,
            started_at=timezone.now() - timedelta(hours=4),
            ended_at=timezone.now() - timedelta(hours=2),  # Ended
            duration=7200,
        )

        start = self.campaign.get_current_session_start()
        self.assertIsNone(start)


class MilestoneModelTest(TestCase):
    """Test Milestone model functionality."""

    def setUp(self):
        """Set up test data."""
        self.campaign = Campaign.objects.create(
            name="Milestone Campaign",
            slug="milestone-campaign",
            description="Campaign with milestones",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
        )

        self.milestone = Milestone.objects.create(
            campaign=self.campaign,
            threshold=100,
            title="UFO 50",
            description="Bryan plays UFO 50",
            image_url="https://example.com/ufo50.jpg",
        )

    def test_milestone_creation(self):
        """Test creating a milestone with all fields."""
        self.assertEqual(self.milestone.campaign, self.campaign)
        self.assertEqual(self.milestone.threshold, 100)
        self.assertEqual(self.milestone.title, "UFO 50")
        self.assertFalse(self.milestone.is_unlocked)
        self.assertIsNone(self.milestone.unlocked_at)

    def test_milestone_string_representation(self):
        """Test milestone __str__ method."""
        self.assertEqual(str(self.milestone), "🔒 100: UFO 50")

        # Test unlocked milestone
        self.milestone.is_unlocked = True
        self.milestone.save()
        self.assertEqual(str(self.milestone), "✅ 100: UFO 50")

    def test_milestone_ordering(self):
        """Test milestones are ordered by threshold."""
        milestone2 = Milestone.objects.create(
            campaign=self.campaign,
            threshold=50,
            title="Earlier Milestone",
            description="Should come first",
        )

        milestone3 = Milestone.objects.create(
            campaign=self.campaign,
            threshold=200,
            title="Later Milestone",
            description="Should come last",
        )

        milestones = list(Milestone.objects.all())
        self.assertEqual(milestones[0], milestone2)
        self.assertEqual(milestones[1], self.milestone)
        self.assertEqual(milestones[2], milestone3)

    def test_milestone_unique_threshold_per_campaign(self):
        """Test that thresholds must be unique within a campaign."""
        with self.assertRaises(IntegrityError):
            Milestone.objects.create(
                campaign=self.campaign,
                threshold=100,  # Duplicate threshold
                title="Duplicate Threshold",
                description="This should fail",
            )

    def test_milestone_threshold_unique_across_campaigns(self):
        """Test that same threshold can exist in different campaigns."""
        other_campaign = Campaign.objects.create(
            name="Other Campaign",
            slug="other",
            description="Another campaign",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
        )

        # Should not raise an error
        milestone = Milestone.objects.create(
            campaign=other_campaign,
            threshold=100,  # Same threshold, different campaign
            title="Same Threshold",
            description="This should work",
        )

        self.assertEqual(milestone.threshold, 100)

    def test_milestone_unlock_tracking(self):
        """Test tracking milestone unlock status and timestamp."""
        self.assertFalse(self.milestone.is_unlocked)
        self.assertIsNone(self.milestone.unlocked_at)

        # Unlock the milestone
        unlock_time = timezone.now()
        self.milestone.is_unlocked = True
        self.milestone.unlocked_at = unlock_time
        self.milestone.save()

        self.milestone.refresh_from_db()
        self.assertTrue(self.milestone.is_unlocked)
        self.assertIsNotNone(self.milestone.unlocked_at)


class MetricModelTest(TestCase):
    """Test Metric model functionality."""

    def setUp(self):
        """Set up test data."""
        self.campaign = Campaign.objects.create(
            name="Metric Campaign",
            slug="metric-campaign",
            description="Campaign with metrics",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
        )

        self.metric = Metric.objects.create(
            campaign=self.campaign,
            total_subs=50,
            total_resubs=25,
            total_bits=10000,
            total_donations=Decimal("500.00"),
            timer_seconds_remaining=7200,
        )

    def test_metric_creation(self):
        """Test creating a metric with all fields."""
        self.assertEqual(self.metric.campaign, self.campaign)
        self.assertEqual(self.metric.total_subs, 50)
        self.assertEqual(self.metric.total_resubs, 25)
        self.assertEqual(self.metric.total_bits, 10000)
        self.assertEqual(self.metric.total_donations, Decimal("500.00"))
        self.assertEqual(self.metric.timer_seconds_remaining, 7200)

    def test_metric_string_representation(self):
        """Test metric __str__ method."""
        self.assertEqual(str(self.metric), "Metric Campaign - 50 subs")

    def test_metric_defaults(self):
        """Test default values for metric fields."""
        metric = Metric.objects.create(campaign=self.campaign)

        self.assertEqual(metric.total_subs, 0)
        self.assertEqual(metric.total_resubs, 0)
        self.assertEqual(metric.total_bits, 0)
        self.assertEqual(metric.total_donations, Decimal("0"))
        self.assertEqual(metric.timer_seconds_remaining, 0)
        self.assertIsNone(metric.timer_started_at)
        self.assertIsNone(metric.timer_paused_at)
        self.assertEqual(metric.extra_data, {})

    def test_metric_one_to_one_relationship(self):
        """Test that each campaign can only have one metric."""
        with self.assertRaises(IntegrityError):
            Metric.objects.create(campaign=self.campaign)

    def test_metric_json_field(self):
        """Test storing and retrieving data from the JSON field."""
        self.metric.extra_data = {
            "ffxiv_votes": {"viera": 125, "lalafell": 89},
            "top_gifters": [{"name": "user1", "count": 50}],
            "daily_subs": {"2025-09-28": 45, "2025-09-29": 67},
        }
        self.metric.save()

        self.metric.refresh_from_db()
        self.assertEqual(self.metric.extra_data["ffxiv_votes"]["viera"], 125)
        self.assertEqual(self.metric.extra_data["ffxiv_votes"]["lalafell"], 89)
        self.assertEqual(len(self.metric.extra_data["top_gifters"]), 1)
        self.assertEqual(self.metric.extra_data["daily_subs"]["2025-09-28"], 45)

    def test_metric_timer_fields(self):
        """Test timer-related fields."""
        now = timezone.now()
        self.metric.timer_started_at = now
        self.metric.timer_paused_at = now + timedelta(minutes=30)
        self.metric.save()

        self.metric.refresh_from_db()
        self.assertIsNotNone(self.metric.timer_started_at)
        self.assertIsNotNone(self.metric.timer_paused_at)

    def test_metric_auto_update_timestamp(self):
        """Test that updated_at is automatically updated."""
        original_updated = self.metric.updated_at

        # Wait a small amount and update
        import time

        time.sleep(0.01)

        self.metric.total_subs = 60
        self.metric.save()
        self.metric.refresh_from_db()

        self.assertGreater(self.metric.updated_at, original_updated)
