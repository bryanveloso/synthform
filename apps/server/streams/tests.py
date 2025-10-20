"""Tests for stream models."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from streams.models import Session
from streams.models import Status


class SessionModelTest(TestCase):
    """Test Session model functionality."""

    def setUp(self):
        """Set up test data."""
        self.today = timezone.now().date()
        self.session = Session.objects.create(session_date=self.today)

    def test_session_creation(self):
        """Test creating a session with defaults."""
        self.assertIsNotNone(self.session.id)
        self.assertEqual(self.session.session_date, self.today)
        self.assertIsNone(self.session.started_at)
        self.assertIsNone(self.session.ended_at)
        self.assertEqual(self.session.duration, 0)

    def test_stream_session_id_property(self):
        """Test the stream_session_id property."""
        expected = f"stream_{self.today.strftime('%Y_%m_%d')}"
        self.assertEqual(self.session.stream_session_id, expected)

    def test_is_live_property_not_started(self):
        """Test is_live property when stream hasn't started."""
        self.assertFalse(self.session.is_live)

    def test_is_live_property_when_live(self):
        """Test is_live property when stream is live."""
        self.session.started_at = timezone.now()
        self.session.ended_at = None
        self.session.save()

        self.assertTrue(self.session.is_live)

    def test_is_live_property_when_ended(self):
        """Test is_live property when stream has ended."""
        self.session.started_at = timezone.now() - timedelta(hours=3)
        self.session.ended_at = timezone.now()
        self.session.save()

        self.assertFalse(self.session.is_live)

    def test_calculate_duration(self):
        """Test calculating duration from start/end times."""
        started = timezone.now() - timedelta(hours=4)
        ended = timezone.now() - timedelta(hours=1)

        self.session.started_at = started
        self.session.ended_at = ended
        duration = self.session.calculate_duration()

        self.assertEqual(duration, 10800)  # 3 hours in seconds
        self.assertEqual(self.session.duration, 10800)

    def test_calculate_duration_no_times(self):
        """Test calculating duration with no start/end times."""
        duration = self.session.calculate_duration()
        self.assertEqual(duration, 0)

    def test_calculate_duration_no_end_time(self):
        """Test calculating duration with only start time."""
        self.session.started_at = timezone.now()
        duration = self.session.calculate_duration()
        self.assertEqual(duration, 0)  # Can't calculate without end time

    def test_session_string_representation(self):
        """Test session __str__ method."""
        self.assertEqual(str(self.session), self.session.stream_session_id)

    def test_session_ordering(self):
        """Test sessions are ordered by date descending."""
        yesterday = self.today - timedelta(days=1)
        tomorrow = self.today + timedelta(days=1)

        older_session = Session.objects.create(session_date=yesterday)
        newer_session = Session.objects.create(session_date=tomorrow)

        sessions = list(Session.objects.all())
        self.assertEqual(sessions[0], newer_session)
        self.assertEqual(sessions[1], self.session)
        self.assertEqual(sessions[2], older_session)

    def test_session_date_uniqueness(self):
        """Test that session dates must be unique."""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Session.objects.create(session_date=self.today)

    def test_duration_tracking_full_cycle(self):
        """Test full cycle of stream duration tracking."""
        # Stream starts
        start_time = timezone.now()
        self.session.started_at = start_time
        self.session.save()

        self.assertTrue(self.session.is_live)
        self.assertEqual(self.session.duration, 0)

        # Stream ends after 2.5 hours
        end_time = start_time + timedelta(hours=2, minutes=30)
        self.session.ended_at = end_time
        self.session.duration = self.session.calculate_duration()
        self.session.save()

        self.assertFalse(self.session.is_live)
        self.assertEqual(self.session.duration, 9000)  # 2.5 hours in seconds


class StatusModelTest(TestCase):
    """Test Status model functionality."""

    def test_status_creation(self):
        """Test creating a status."""
        status = Status.objects.create(status="busy", message="Working on code")

        self.assertEqual(status.status, "busy")
        self.assertEqual(status.message, "Working on code")

    def test_status_singleton(self):
        """Test that only one Status instance exists."""
        Status.objects.create(status="online")
        Status.objects.create(status="away")

        # Should only have one status (the second one)
        self.assertEqual(Status.objects.count(), 1)
        self.assertEqual(Status.objects.first().status, "away")

    def test_get_current_status(self):
        """Test getting or creating current status."""
        status = Status.get_current()
        self.assertEqual(status.status, "online")
        self.assertEqual(status.message, "")

        # Getting again should return same instance
        status2 = Status.get_current()
        self.assertEqual(status.id, status2.id)

    def test_status_string_representation(self):
        """Test status __str__ method."""
        status = Status.objects.create(status="brb", message="Getting coffee")
        self.assertEqual(str(status), "Be Right Back: Getting coffee")

        status_no_message = Status.objects.create(status="focus")
        self.assertEqual(str(status_no_message), "Focus Mode")

    def test_status_choices(self):
        """Test that status choices are validated."""
        status = Status.objects.create(status="online")
        self.assertIn(status.status, ["online", "away", "busy", "brb", "focus"])
