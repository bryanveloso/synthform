"""Tests for OBS performance monitoring."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone


class OBSPerformanceTest(TestCase):
    """Test OBS performance monitoring functionality."""

    def setUp(self):
        """Set up test data."""
        from streams.services.obs import OBSService

        self.service = OBSService()
        # Reset singleton state for testing
        self.service._running = False
        self.service._redis_client = None

    @patch("streams.services.obs.redis.from_url")
    async def test_reset_performance_metrics_success(self, mock_redis):
        """Test successful reset of performance metrics."""
        # Arrange
        mock_client = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        # Act
        await self.service.reset_performance_metrics()

        # Assert
        assert mock_client.delete.call_count == 3
        mock_client.delete.assert_any_call("obs:performance:prev_skipped")
        mock_client.delete.assert_any_call("obs:performance:prev_total")
        mock_client.delete.assert_any_call("obs:performance:warning_active")

    async def test_reset_performance_metrics_no_redis_client(self):
        """Test reset when Redis client is None."""
        # Arrange
        self.service._redis_client = None
        self.service._running = True

        # Act
        await self.service.reset_performance_metrics()

        # Assert - early return, no operations performed

    @patch("streams.services.obs.redis.from_url")
    async def test_reset_performance_metrics_redis_error(self, mock_redis):
        """Test reset handles Redis errors gracefully."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.delete.side_effect = Exception("Redis connection failed")
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        # Act - should not raise
        with self.assertLogs("streams.services.obs", level="ERROR") as cm:
            await self.service.reset_performance_metrics()

        # Assert - error logged
        self.assertIn("Redis connection failed", cm.output[0])
        self.assertIn("Error resetting performance metrics", cm.output[0])

    @override_settings(OBS_PERFORMANCE_MONITOR_ENABLED=False)
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_monitoring_disabled(self, mock_redis):
        """Test performance check returns False when monitoring disabled."""
        # Arrange
        mock_client = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        # Act
        result = await self.service.check_performance_and_alert()

        # Assert
        assert result is False

    @override_settings(OBS_PERFORMANCE_MONITOR_ENABLED=True)
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_obs_not_streaming(self, mock_redis):
        """Test performance check returns False when OBS not streaming."""
        # Arrange
        mock_client = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        with patch.object(self.service, "get_stream_performance", return_value=None):
            # Act
            result = await self.service.check_performance_and_alert()

            # Assert
            assert result is False

    @override_settings(
        OBS_PERFORMANCE_MONITOR_ENABLED=True,
        OBS_FRAME_DROP_THRESHOLD_TRIGGER=1.0,
        OBS_FRAME_DROP_THRESHOLD_CLEAR=0.5,
    )
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_first_poll_no_prev_values(self, mock_redis):
        """Test performance check handles first poll with no previous values."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get.return_value = None  # No previous values
        mock_client.publish = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        stats = {
            "output_active": True,
            "output_skipped_frames": 100,
            "output_total_frames": 10000,
        }

        with patch.object(self.service, "get_stream_performance", return_value=stats):
            # Act
            result = await self.service.check_performance_and_alert()

            # Assert - drop_rate = (100-0)/(10000-0)*100 = 1.0%, equals trigger threshold
            assert result is True  # Warning triggered at threshold
            # Verify warning was published
            mock_client.publish.assert_called_once()
            # Verify TTL was set
            assert (
                mock_client.set.call_count == 3
            )  # prev_skipped, prev_total, warning_active
            mock_client.set.assert_any_call(
                "obs:performance:prev_skipped", 100, ex=3600
            )
            mock_client.set.assert_any_call(
                "obs:performance:prev_total", 10000, ex=3600
            )

    @override_settings(
        OBS_PERFORMANCE_MONITOR_ENABLED=True,
        OBS_FRAME_DROP_THRESHOLD_TRIGGER=1.0,
        OBS_FRAME_DROP_THRESHOLD_CLEAR=0.5,
    )
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_byte_decoding(self, mock_redis):
        """Test performance check correctly decodes byte strings from Redis."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get.side_effect = [b"100", b"10000", None]  # prev values as bytes
        mock_client.publish = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        stats = {
            "output_active": True,
            "output_skipped_frames": 150,  # +50 skipped
            "output_total_frames": 15000,  # +5000 total
        }

        with patch.object(self.service, "get_stream_performance", return_value=stats):
            # Act
            result = await self.service.check_performance_and_alert()

            # Assert - drop_rate = (50 / 5000 * 100) = 1.0%
            assert result is True  # Warning triggered
            # Verify publish was called
            mock_client.publish.assert_called_once()
            call_args = mock_client.publish.call_args
            assert call_args[0][0] == "events:obs"

    @override_settings(
        OBS_PERFORMANCE_MONITOR_ENABLED=True,
        OBS_FRAME_DROP_THRESHOLD_TRIGGER=1.0,
        OBS_FRAME_DROP_THRESHOLD_CLEAR=0.5,
    )
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_trigger_warning(self, mock_redis):
        """Test performance check triggers warning when drop rate exceeds threshold."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            b"100",
            b"10000",
            None,
        ]  # No active warning
        mock_client.publish = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        stats = {
            "output_active": True,
            "output_skipped_frames": 200,  # +100 skipped
            "output_total_frames": 15000,  # +5000 total = 2.0% drop rate
        }

        with patch.object(self.service, "get_stream_performance", return_value=stats):
            # Act
            result = await self.service.check_performance_and_alert()

            # Assert
            assert result is True
            mock_client.set.assert_any_call("obs:performance:warning_active", "1")
            mock_client.publish.assert_called_once()

    @override_settings(
        OBS_PERFORMANCE_MONITOR_ENABLED=True,
        OBS_FRAME_DROP_THRESHOLD_TRIGGER=1.0,
        OBS_FRAME_DROP_THRESHOLD_CLEAR=0.5,
    )
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_clear_warning(self, mock_redis):
        """Test performance check clears warning when drop rate recovers."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            b"100",
            b"10000",
            b"1",
        ]  # Active warning
        mock_client.publish = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        stats = {
            "output_active": True,
            "output_skipped_frames": 105,  # +5 skipped
            "output_total_frames": 15000,  # +5000 total = 0.1% drop rate
        }

        with patch.object(self.service, "get_stream_performance", return_value=stats):
            # Act
            result = await self.service.check_performance_and_alert()

            # Assert
            assert result is True
            mock_client.delete.assert_called_with("obs:performance:warning_active")
            mock_client.publish.assert_called_once()

    @override_settings(
        OBS_PERFORMANCE_MONITOR_ENABLED=True,
        OBS_FRAME_DROP_THRESHOLD_TRIGGER=1.0,
        OBS_FRAME_DROP_THRESHOLD_CLEAR=0.5,
    )
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_hysteresis_no_retrigger(self, mock_redis):
        """Test hysteresis prevents re-triggering when warning already active."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            b"100",
            b"10000",
            b"1",
        ]  # Warning already active
        mock_client.publish = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        stats = {
            "output_active": True,
            "output_skipped_frames": 200,  # +100 skipped
            "output_total_frames": 15000,  # +5000 total = 2.0% drop rate
        }

        with patch.object(self.service, "get_stream_performance", return_value=stats):
            # Act
            result = await self.service.check_performance_and_alert()

            # Assert
            assert result is False  # No re-trigger
            mock_client.publish.assert_not_called()

    @override_settings(
        OBS_PERFORMANCE_MONITOR_ENABLED=True,
        OBS_FRAME_DROP_THRESHOLD_TRIGGER=1.0,
        OBS_FRAME_DROP_THRESHOLD_CLEAR=0.5,
    )
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_zero_division_protection(self, mock_redis):
        """Test performance check handles zero total_delta gracefully."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get.side_effect = [b"100", b"10000", None]
        mock_client.publish = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        stats = {
            "output_active": True,
            "output_skipped_frames": 100,  # No change
            "output_total_frames": 10000,  # No change
        }

        with patch.object(self.service, "get_stream_performance", return_value=stats):
            # Act
            result = await self.service.check_performance_and_alert()

            # Assert
            assert result is False  # drop_rate = 0.0, no warning

    @override_settings(
        OBS_PERFORMANCE_MONITOR_ENABLED=True,
        OBS_FRAME_DROP_THRESHOLD_TRIGGER=1.0,
        OBS_FRAME_DROP_THRESHOLD_CLEAR=0.5,
    )
    @patch("streams.services.obs.redis.from_url")
    async def test_check_performance_redis_ttl_set(self, mock_redis):
        """Test that Redis keys are set with 1-hour TTL."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get.side_effect = [b"100", b"10000", None]
        mock_client.publish = AsyncMock()
        mock_redis.return_value = mock_client
        self.service._redis_client = mock_client
        self.service._running = True

        stats = {
            "output_active": True,
            "output_skipped_frames": 110,
            "output_total_frames": 12000,
        }

        with patch.object(self.service, "get_stream_performance", return_value=stats):
            # Act
            await self.service.check_performance_and_alert()

            # Assert - verify ex=3600 parameter
            calls = mock_client.set.call_args_list
            assert len(calls) == 2
            for call in calls:
                assert call[1]["ex"] == 3600  # 1 hour in seconds


# Synchronous wrapper tests for Django test runner
class OBSPerformanceSyncTest(TestCase):
    """Synchronous test wrappers for async OBS performance tests."""

    def test_reset_performance_metrics_success(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_reset_performance_metrics_success)()

    def test_reset_performance_metrics_no_redis_client(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_reset_performance_metrics_no_redis_client)()

    def test_reset_performance_metrics_redis_error(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_reset_performance_metrics_redis_error)()

    def test_check_performance_monitoring_disabled(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_monitoring_disabled)()

    def test_check_performance_obs_not_streaming(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_obs_not_streaming)()

    def test_check_performance_first_poll_no_prev_values(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_first_poll_no_prev_values)()

    def test_check_performance_byte_decoding(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_byte_decoding)()

    def test_check_performance_trigger_warning(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_trigger_warning)()

    def test_check_performance_clear_warning(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_clear_warning)()

    def test_check_performance_hysteresis_no_retrigger(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_hysteresis_no_retrigger)()

    def test_check_performance_zero_division_protection(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_zero_division_protection)()

    def test_check_performance_redis_ttl_set(self):
        test = OBSPerformanceTest()
        test.setUp()
        async_to_sync(test.test_check_performance_redis_ttl_set)()
