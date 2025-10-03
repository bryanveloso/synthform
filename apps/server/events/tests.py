"""Tests for Twitch event handling, especially community gift aggregation."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TestCase

from events.services.twitch import TwitchEventHandler


class TestCommunityGiftAggregation(TestCase):
    """Test that community gift events are properly handled with IDs for aggregation."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = TwitchEventHandler()
        # Mock Redis client
        self.handler._redis_client = AsyncMock()
        # Mock the database operations
        self.member_mock = MagicMock(id=1, display_name="TestUser")
        self.event_mock = MagicMock(id=1)

    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    def test_community_sub_gift_extracts_id(
        self, mock_publish, mock_create_event, mock_get_member
    ):
        """Test that community_sub_gift events extract the community_gift_id."""
        mock_get_member.return_value = self.member_mock
        mock_create_event.return_value = self.event_mock

        # Create mock payload for community_sub_gift
        mock_payload = MagicMock()
        mock_payload.broadcaster.id = "123"
        mock_payload.broadcaster.name = "test_broadcaster"
        mock_payload.chatter.id = "456"
        mock_payload.chatter.name = "generous_gifter"
        mock_payload.chatter.display_name = "GenerousGifter"
        mock_payload.anonymous = False
        mock_payload.colour = "#FF0000"
        mock_payload.badges = []
        mock_payload.system_message = "GenerousGifter gifted 5 subs!"
        mock_payload.id = "msg_123"
        mock_payload.text = ""
        mock_payload.fragments = []
        mock_payload.notice_type = "community_sub_gift"

        # Mock community_sub_gift data
        mock_community_gift = MagicMock()
        mock_community_gift.id = "community_gift_abc123"
        mock_community_gift.total = 5
        mock_community_gift.tier = "1000"
        mock_community_gift.cumulative_total = 50
        # Ensure __slots__ returns expected attributes
        mock_community_gift.__slots__ = ["id", "total", "tier", "cumulative_total"]

        mock_payload.community_sub_gift = mock_community_gift
        # Set other notice fields to None
        mock_payload.sub = None
        mock_payload.resub = None
        mock_payload.sub_gift = None

        # Run the handler
        async_to_sync(self.handler._handle_chat_notification)(
            "channel.chat.notification", mock_payload
        )

        # Verify the published data includes community_gift_id
        mock_publish.assert_called_once()
        published_data = mock_publish.call_args[0][3]  # Fourth argument is payload_dict

        # Check that community_gift_id was extracted and added
        assert "community_gift_id" in published_data
        assert published_data["community_gift_id"] == "community_gift_abc123"
        assert published_data["tier"] == "1000"
        assert published_data["community_sub_gift"]["id"] == "community_gift_abc123"

    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    def test_sub_gift_with_community_id_skipped(
        self, mock_publish, mock_create_event, mock_get_member
    ):
        """Test that individual sub_gift events with community_gift_id are skipped."""
        mock_get_member.return_value = self.member_mock
        mock_create_event.return_value = self.event_mock

        # Create mock payload for individual sub_gift with community_gift_id
        individual_payload = MagicMock()
        individual_payload.broadcaster.id = "123"
        individual_payload.broadcaster.name = "test_broadcaster"
        individual_payload.chatter.id = "456"
        individual_payload.chatter.name = "generous_gifter"
        individual_payload.chatter.display_name = "GenerousGifter"
        individual_payload.anonymous = False
        individual_payload.colour = "#FF0000"
        individual_payload.badges = []
        individual_payload.system_message = (
            "GenerousGifter gifted a sub to lucky_viewer!"
        )
        individual_payload.id = "msg_124"
        individual_payload.text = ""
        individual_payload.fragments = []
        individual_payload.notice_type = "sub_gift"

        mock_sub_gift = MagicMock()
        mock_sub_gift.community_gift_id = "community_gift_abc123"
        mock_sub_gift.tier = "1000"
        mock_sub_gift.recipient_user_name = "lucky_viewer"
        mock_sub_gift.cumulative_total = 1
        mock_sub_gift.__slots__ = [
            "community_gift_id",
            "tier",
            "recipient_user_name",
            "cumulative_total",
        ]

        individual_payload.sub_gift = mock_sub_gift
        individual_payload.sub = None
        individual_payload.resub = None
        individual_payload.community_sub_gift = None

        # Process individual gift
        async_to_sync(self.handler._handle_chat_notification)(
            "channel.chat.notification", individual_payload
        )

        # Verify individual gift was NOT published (skipped to prevent spam)
        mock_publish.assert_not_called()

    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    def test_single_targeted_gift_publishes(
        self, mock_publish, mock_create_event, mock_get_member
    ):
        """Test that single targeted gifts (sub_gift without community_gift_id) publish normally."""
        mock_get_member.return_value = self.member_mock
        mock_create_event.return_value = self.event_mock

        # Create mock payload for single targeted gift (no community_gift_id)
        mock_payload = MagicMock()
        mock_payload.broadcaster.id = "123"
        mock_payload.broadcaster.name = "test_broadcaster"
        mock_payload.chatter.id = "456"
        mock_payload.chatter.name = "generous_gifter"
        mock_payload.chatter.display_name = "GenerousGifter"
        mock_payload.anonymous = False
        mock_payload.colour = "#FF0000"
        mock_payload.badges = []
        mock_payload.system_message = "GenerousGifter gifted a sub to lucky_viewer!"
        mock_payload.id = "msg_124"
        mock_payload.text = ""
        mock_payload.fragments = []
        mock_payload.notice_type = "sub_gift"

        # Mock sub_gift data WITHOUT community_gift_id (single targeted gift)
        mock_sub_gift = MagicMock()
        mock_sub_gift.tier = "1000"
        mock_sub_gift.recipient_user_name = "lucky_viewer"
        mock_sub_gift.cumulative_total = 1
        # No community_gift_id attribute
        mock_sub_gift.__slots__ = [
            "tier",
            "recipient_user_name",
            "cumulative_total",
        ]

        mock_payload.sub_gift = mock_sub_gift
        mock_payload.sub = None
        mock_payload.resub = None
        mock_payload.community_sub_gift = None

        # Run the handler
        async_to_sync(self.handler._handle_chat_notification)(
            "channel.chat.notification", mock_payload
        )

        # Verify the gift was published (not deduplicated)
        mock_publish.assert_called_once()
        published_data = mock_publish.call_args[0][3]

        # Check that it was treated as a normal gift
        assert "community_gift_id" not in published_data
        assert published_data["tier"] == "1000"

    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    def test_regular_sub_has_no_community_id(
        self, mock_publish, mock_create_event, mock_get_member
    ):
        """Test that regular sub events don't have community_gift_id."""
        mock_get_member.return_value = self.member_mock
        mock_create_event.return_value = self.event_mock

        # Create mock payload for regular sub
        mock_payload = MagicMock()
        mock_payload.broadcaster.id = "123"
        mock_payload.broadcaster.name = "test_broadcaster"
        mock_payload.chatter.id = "789"
        mock_payload.chatter.name = "new_subscriber"
        mock_payload.chatter.display_name = "NewSubscriber"
        mock_payload.anonymous = False
        mock_payload.colour = "#00FF00"
        mock_payload.badges = []
        mock_payload.system_message = "NewSubscriber subscribed!"
        mock_payload.id = "msg_125"
        mock_payload.text = ""
        mock_payload.fragments = []
        mock_payload.notice_type = "sub"

        # Mock sub data
        mock_sub = MagicMock()
        mock_sub.tier = "1000"
        mock_sub.is_prime = False
        mock_sub.duration_months = 1
        # Ensure __slots__ returns expected attributes
        mock_sub.__slots__ = ["tier", "is_prime", "duration_months"]

        mock_payload.sub = mock_sub
        # Set other notice fields to None
        mock_payload.resub = None
        mock_payload.sub_gift = None
        mock_payload.community_sub_gift = None

        # Run the handler
        async_to_sync(self.handler._handle_chat_notification)(
            "channel.chat.notification", mock_payload
        )

        # Verify the published data does NOT include community_gift_id
        mock_publish.assert_called_once()
        published_data = mock_publish.call_args[0][3]  # Fourth argument is payload_dict

        # Check that community_gift_id is not present for regular subs
        assert "community_gift_id" not in published_data
        assert published_data["tier"] == "1000"


class TestTierExtraction(TestCase):
    """Test that tier information is properly extracted from various event types."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = TwitchEventHandler()
        # Mock Redis client
        self.handler._redis_client = AsyncMock()
        # Mock the database operations
        self.member_mock = MagicMock(id=1, display_name="TestUser")
        self.event_mock = MagicMock(id=1)

    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    def test_tier_extracted_from_sub(
        self, mock_publish, mock_create_event, mock_get_member
    ):
        """Test that tier is extracted from sub events."""
        mock_get_member.return_value = self.member_mock
        mock_create_event.return_value = self.event_mock

        # Create mock payload
        mock_payload = MagicMock()
        mock_payload.broadcaster.id = "123"
        mock_payload.broadcaster.name = "test_broadcaster"
        mock_payload.chatter.id = "789"
        mock_payload.chatter.name = "subscriber"
        mock_payload.chatter.display_name = "Subscriber"
        mock_payload.anonymous = False
        mock_payload.colour = "#00FF00"
        mock_payload.badges = []
        mock_payload.system_message = "Subscriber subscribed at Tier 2!"
        mock_payload.id = "msg_126"
        mock_payload.text = ""
        mock_payload.fragments = []
        mock_payload.notice_type = "sub"

        # Mock sub data with tier 2
        mock_sub = MagicMock()
        mock_sub.tier = "2000"  # Tier 2
        mock_sub.is_prime = False
        mock_sub.duration_months = 1
        mock_sub.__slots__ = ["tier", "is_prime", "duration_months"]

        mock_payload.sub = mock_sub
        mock_payload.resub = None
        mock_payload.sub_gift = None
        mock_payload.community_sub_gift = None

        # Run the handler
        async_to_sync(self.handler._handle_chat_notification)(
            "channel.chat.notification", mock_payload
        )

        # Verify tier was extracted to top level
        mock_publish.assert_called_once()
        published_data = mock_publish.call_args[0][3]

        assert published_data["tier"] == "2000"
        assert published_data["sub"]["tier"] == "2000"
