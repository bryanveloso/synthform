"""Tests for stream event handling with OBS integration."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TestCase
from django.utils import timezone


class StreamEventOBSIntegrationTest(TestCase):
    """Test stream events trigger OBS performance metrics reset."""

    @patch("events.services.twitch.redis.Redis.from_url")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.obs_service.reset_performance_metrics")
    @patch("events.services.twitch.campaign_service.sync_campaign_state")
    async def test_stream_online_resets_obs_metrics(
        self,
        mock_sync_campaign,
        mock_reset_obs,
        mock_get_member,
        mock_create_event,
        mock_publish,
        mock_redis_from_url,
    ):
        """Test that stream.online event triggers OBS metrics reset."""
        # Arrange
        from events.services.twitch import TwitchEventHandler

        mock_redis_client = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_client

        mock_member = MagicMock(
            id="test-member-1",
            twitch_id="38981465",
            username="avalonstar",
            display_name="Avalonstar",
        )
        mock_get_member.return_value = mock_member

        handler = TwitchEventHandler()

        # Create mock payload
        payload = MagicMock()
        payload.id = "stream-123"
        payload.broadcaster.id = "38981465"
        payload.broadcaster.name = "avalonstar"
        payload.type = "live"
        payload.started_at = timezone.now()

        # Act
        await handler._handle_stream_online("stream.online", payload)

        # Assert
        mock_reset_obs.assert_called_once()

    @patch("events.services.twitch.redis.Redis.from_url")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.obs_service.reset_performance_metrics")
    @patch("events.services.twitch.campaign_service.sync_campaign_state")
    async def test_stream_offline_resets_obs_metrics(
        self,
        mock_sync_campaign,
        mock_reset_obs,
        mock_get_member,
        mock_create_event,
        mock_publish,
        mock_redis_from_url,
    ):
        """Test that stream.offline event triggers OBS metrics reset."""
        # Arrange
        from events.services.twitch import TwitchEventHandler

        mock_redis_client = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_client

        mock_member = MagicMock(
            id="test-member-1",
            twitch_id="38981465",
            username="avalonstar",
            display_name="Avalonstar",
        )
        mock_get_member.return_value = mock_member

        handler = TwitchEventHandler()

        # Create mock payload
        payload = MagicMock()
        payload.broadcaster.id = "38981465"
        payload.broadcaster.name = "avalonstar"

        # Act
        await handler._handle_stream_offline("stream.offline", payload)

        # Assert
        mock_reset_obs.assert_called_once()

    @patch("events.services.twitch.redis.Redis.from_url")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.obs_service.reset_performance_metrics")
    @patch("events.services.twitch.campaign_service.sync_campaign_state")
    async def test_stream_online_obs_error_isolated(
        self,
        mock_sync_campaign,
        mock_reset_obs,
        mock_get_member,
        mock_create_event,
        mock_publish,
        mock_redis_from_url,
    ):
        """Test that OBS reset errors don't break stream.online processing."""
        # Arrange
        from events.services.twitch import TwitchEventHandler

        mock_redis_client = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_client

        mock_member = MagicMock(
            id="test-member-1",
            twitch_id="38981465",
            username="avalonstar",
            display_name="Avalonstar",
        )
        mock_get_member.return_value = mock_member

        mock_reset_obs.side_effect = Exception("OBS service unavailable")

        handler = TwitchEventHandler()

        # Create mock payload
        payload = MagicMock()
        payload.id = "stream-123"
        payload.broadcaster.id = "38981465"
        payload.broadcaster.name = "avalonstar"
        payload.type = "live"
        payload.started_at = timezone.now()

        # Act - should not raise
        await handler._handle_stream_online("stream.online", payload)

        # Assert
        mock_reset_obs.assert_called_once()

    @patch("events.services.twitch.redis.Redis.from_url")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.obs_service.reset_performance_metrics")
    @patch("events.services.twitch.campaign_service.sync_campaign_state")
    async def test_stream_offline_obs_error_isolated(
        self,
        mock_sync_campaign,
        mock_reset_obs,
        mock_get_member,
        mock_create_event,
        mock_publish,
        mock_redis_from_url,
    ):
        """Test that OBS reset errors don't break stream.offline processing."""
        # Arrange
        from events.services.twitch import TwitchEventHandler

        mock_redis_client = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_client

        mock_member = MagicMock(
            id="test-member-1",
            twitch_id="38981465",
            username="avalonstar",
            display_name="Avalonstar",
        )
        mock_get_member.return_value = mock_member

        mock_reset_obs.side_effect = Exception("OBS service unavailable")

        handler = TwitchEventHandler()

        # Create mock payload
        payload = MagicMock()
        payload.broadcaster.id = "38981465"
        payload.broadcaster.name = "avalonstar"

        # Act - should not raise
        await handler._handle_stream_offline("stream.offline", payload)

        # Assert
        mock_reset_obs.assert_called_once()

    @patch("events.services.twitch.redis.Redis.from_url")
    @patch("events.services.twitch.TwitchEventHandler._publish_to_redis")
    @patch("events.services.twitch.TwitchEventHandler._create_event")
    @patch(
        "events.services.twitch.TwitchEventHandler._get_or_create_member_from_payload"
    )
    @patch("events.services.twitch.obs_service.reset_performance_metrics")
    @patch("events.services.twitch.campaign_service.sync_campaign_state")
    async def test_stream_online_campaign_error_still_resets_obs(
        self,
        mock_sync_campaign,
        mock_reset_obs,
        mock_get_member,
        mock_create_event,
        mock_publish,
        mock_redis_from_url,
    ):
        """Test that campaign errors don't prevent OBS metrics reset."""
        # Arrange
        from events.services.twitch import TwitchEventHandler

        mock_redis_client = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_client

        mock_member = MagicMock(
            id="test-member-1",
            twitch_id="38981465",
            username="avalonstar",
            display_name="Avalonstar",
        )
        mock_get_member.return_value = mock_member

        mock_sync_campaign.side_effect = Exception("Campaign service error")

        handler = TwitchEventHandler()

        # Create mock payload
        payload = MagicMock()
        payload.id = "stream-123"
        payload.broadcaster.id = "38981465"
        payload.broadcaster.name = "avalonstar"
        payload.type = "live"
        payload.started_at = timezone.now()

        # Act
        await handler._handle_stream_online("stream.online", payload)

        # Assert - OBS reset still called after campaign error
        mock_reset_obs.assert_called_once()


# Synchronous wrapper tests for Django test runner
class StreamEventOBSIntegrationSyncTest(TestCase):
    """Synchronous test wrappers for async stream event tests."""

    def test_stream_online_resets_obs_metrics(self):
        test = StreamEventOBSIntegrationTest()
        async_to_sync(test.test_stream_online_resets_obs_metrics)()

    def test_stream_offline_resets_obs_metrics(self):
        test = StreamEventOBSIntegrationTest()
        async_to_sync(test.test_stream_offline_resets_obs_metrics)()

    def test_stream_online_obs_error_isolated(self):
        test = StreamEventOBSIntegrationTest()
        async_to_sync(test.test_stream_online_obs_error_isolated)()

    def test_stream_offline_obs_error_isolated(self):
        test = StreamEventOBSIntegrationTest()
        async_to_sync(test.test_stream_offline_obs_error_isolated)()

    def test_stream_online_campaign_error_still_resets_obs(self):
        test = StreamEventOBSIntegrationTest()
        async_to_sync(test.test_stream_online_campaign_error_still_resets_obs)()
