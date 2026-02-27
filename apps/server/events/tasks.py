"""Celery tasks for event processing and EventSub health monitoring."""

from __future__ import annotations

import logging
import time

from celery import shared_task

logger = logging.getLogger(__name__)

# Health check thresholds
EVENTSUB_MAX_SILENCE_SECONDS = 14400  # 4 hours without events = unhealthy
EVENTSUB_STALE_CONNECTION_SECONDS = (
    21600  # 6 hours since last restart = recommend refresh
)


@shared_task
def check_eventsub_health():
    """
    Periodically verify EventSub connection health.

    Checks:
    1. Redis health keys set by TwitchService
    2. Time since last event received
    3. Connection status flag

    If unhealthy, sets a Redis flag that triggers TwitchService restart.

    Note: Uses synchronous Redis client to avoid event loop conflicts with Celery.
    """
    redis_client = None
    try:
        import redis
        from django.conf import settings

        redis_client = redis.from_url(
            settings.REDIS_URL or "redis://redis:6379/0", decode_responses=True
        )

        # Check connection status
        eventsub_connected = redis_client.get("eventsub:connected")
        last_event_time = redis_client.get("eventsub:last_event_time")

        logger.info(
            f"[EventSub Health] Checking health. connected={eventsub_connected} "
            f"last_event_time={last_event_time}"
        )

        # If explicitly disconnected, request restart
        if eventsub_connected == "0":
            logger.warning(
                "[EventSub Health] ⚠️ EventSub marked as disconnected. Requesting restart."
            )
            _request_restart(redis_client, "eventsub_disconnected")
            return {"healthy": False, "reason": "disconnected"}

        # If no last event time, connection may be fresh or never received events
        if not last_event_time:
            logger.info(
                "[EventSub Health] No last_event_time recorded. Connection may be fresh."
            )
            return {"healthy": True, "reason": "no_baseline"}

        # Check time since last event
        try:
            last_event_timestamp = float(last_event_time)
            seconds_since_event = time.time() - last_event_timestamp
        except (ValueError, TypeError):
            logger.warning(
                f"[EventSub Health] Invalid last_event_time format. value={last_event_time}"
            )
            return {"healthy": True, "reason": "invalid_timestamp"}

        logger.info(
            f"[EventSub Health] Time since last event. seconds={int(seconds_since_event)}"
        )

        # If too long without events, request restart
        if seconds_since_event > EVENTSUB_MAX_SILENCE_SECONDS:
            logger.warning(
                f"[EventSub Health] ⚠️ No events for {int(seconds_since_event)}s "
                f"(threshold: {EVENTSUB_MAX_SILENCE_SECONDS}s). Requesting restart."
            )
            _request_restart(redis_client, "prolonged_silence")
            return {
                "healthy": False,
                "reason": "prolonged_silence",
                "seconds_since_event": int(seconds_since_event),
            }

        logger.info("[EventSub Health] ✅ EventSub appears healthy.")
        return {"healthy": True, "seconds_since_event": int(seconds_since_event)}

    except Exception as e:
        logger.error(f'[EventSub Health] ❌ Error checking health. error="{str(e)}"')
        return {"healthy": None, "error": str(e)}
    finally:
        if redis_client:
            redis_client.close()


def _request_restart(redis_client, reason: str):
    """Set Redis flag to request TwitchService restart."""
    import time

    redis_client.set("eventsub:restart_requested", reason)
    redis_client.set("eventsub:restart_requested_at", str(time.time()))
    # Flag expires after 10 minutes if not acted upon
    redis_client.expire("eventsub:restart_requested", 600)
    redis_client.expire("eventsub:restart_requested_at", 600)
    logger.info(f"[EventSub Health] Restart requested. reason={reason}")


@shared_task
def trigger_eventsub_health_check():
    """
    Trigger an immediate EventSub health check.

    Called by OBS service when stream starts to ensure EventSub is ready.
    """
    logger.info("[EventSub Health] Triggered immediate health check (stream starting).")
    return check_eventsub_health()
