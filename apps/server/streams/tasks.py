from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def monitor_obs_performance():
    """
    Monitor OBS encoder performance every 5 seconds.
    Checks frame drop rate and triggers alerts when threshold exceeded.

    Note: Uses synchronous Redis client to avoid event loop conflicts with Celery.
    The OBS service runs in the ASGI server's event loop, so we can't reuse its async client.
    """
    redis_client = None
    try:
        import redis
        from django.conf import settings

        from .services.obs import obs_service

        # Use synchronous Redis client (Celery doesn't play well with async)
        redis_client = redis.from_url(
            settings.REDIS_URL or "redis://redis:6379/0", decode_responses=True
        )

        # Check if monitoring is enabled
        if not settings.OBS_PERFORMANCE_MONITOR_ENABLED:
            return False

        # Check if OBS client is connected
        if not obs_service._client_req:
            return False

        # Get current performance stats (both are synchronous OBS API calls)
        try:
            stream_status = obs_service._client_req.get_stream_status()
            stats = obs_service._client_req.get_stats()
        except Exception as e:
            # OBS not running, disconnected, or timeout - expected, don't spam Sentry
            logger.debug(
                f"[Streams] OBS not available for performance monitoring. error={e.__class__.__name__}: {e}"
            )
            return False

        if not stream_status or not stats:
            return False

        # Check if output is active (streaming)
        # Use getattr for safety in case obsws-python API changes
        if not getattr(stream_status, "output_active", False):
            return False

        # Extract frame data (output frames from stream_status, render frames from stats)
        # Use getattr for safety in case obsws-python API changes
        output_skipped = getattr(stream_status, "output_skipped_frames", 0)
        output_total = getattr(stream_status, "output_total_frames", 0)
        render_skipped = getattr(stats, "render_skipped_frames", 0)
        render_total = getattr(stats, "render_total_frames", 0)

        # Bail out if we don't have valid frame counts
        if output_total == 0 and render_total == 0:
            return False

        # Get previous values from Redis
        prev_output_skipped = int(
            redis_client.get("obs:performance:prev_output_skipped") or 0
        )
        prev_output_total = int(
            redis_client.get("obs:performance:prev_output_total") or 0
        )
        prev_render_skipped = int(
            redis_client.get("obs:performance:prev_render_skipped") or 0
        )
        prev_render_total = int(
            redis_client.get("obs:performance:prev_render_total") or 0
        )

        # Calculate deltas
        output_skipped_delta = output_skipped - prev_output_skipped
        output_total_delta = output_total - prev_output_total
        render_skipped_delta = render_skipped - prev_render_skipped
        render_total_delta = render_total - prev_render_total

        # Calculate drop rates
        output_drop_rate = (
            (output_skipped_delta / output_total_delta * 100)
            if output_total_delta > 0
            else 0.0
        )
        render_drop_rate = (
            (render_skipped_delta / render_total_delta * 100)
            if render_total_delta > 0
            else 0.0
        )

        # Store current values for next check (expire after 1 hour)
        redis_client.setex(
            "obs:performance:prev_output_skipped", 3600, str(output_skipped)
        )
        redis_client.setex("obs:performance:prev_output_total", 3600, str(output_total))
        redis_client.setex(
            "obs:performance:prev_render_skipped", 3600, str(render_skipped)
        )
        redis_client.setex("obs:performance:prev_render_total", 3600, str(render_total))

        # Check thresholds
        warning_active = redis_client.get("obs:performance:warning_active")
        trigger_threshold = settings.OBS_FRAME_DROP_THRESHOLD_TRIGGER
        clear_threshold = settings.OBS_FRAME_DROP_THRESHOLD_CLEAR
        max_drop_rate = max(render_drop_rate, output_drop_rate)

        logger.debug(
            f"[Streams] Performance check. render_drop={render_drop_rate:.2f}% output_drop={output_drop_rate:.2f}%"
        )

        # Trigger warning if threshold exceeded (warning expires after 5 minutes)
        result = False
        if max_drop_rate >= trigger_threshold and not warning_active:
            logger.warning(
                f"[Streams] ⚠️ OBS performance issue detected. render_drop={render_drop_rate:.2f}% output_drop={output_drop_rate:.2f}%"
            )
            redis_client.setex("obs:performance:warning_active", 300, "1")
            result = True
        elif max_drop_rate < clear_threshold and warning_active:
            logger.info("[Streams] ✅ OBS performance recovered.")
            redis_client.delete("obs:performance:warning_active")

        return result

    except Exception as e:
        logger.error(
            f'[Streams] ❌ Error in monitor_obs_performance task. error="{str(e)}"'
        )
        return False
    finally:
        if redis_client:
            redis_client.close()
