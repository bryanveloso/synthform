from __future__ import annotations

import time

from django.conf import settings
from django.db import connection
from django.http import HttpRequest
from django.http import JsonResponse


def health_check(request: HttpRequest) -> JsonResponse:
    """Basic health check endpoint for monitoring."""
    status = {"status": "ok", "services": {}}
    http_status = 200

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status["services"]["database"] = "ok"
    except Exception as e:
        status["services"]["database"] = f"error: {str(e)}"
        status["status"] = "degraded"
        http_status = 503

    # Create Redis client once for all Redis checks
    try:
        import redis

        r = redis.Redis.from_url(settings.REDIS_URL)

        # Check Redis connectivity
        r.ping()
        status["services"]["redis"] = "ok"

        # Check EventSub health using same Redis client
        eventsub_connected = r.get("eventsub:connected")
        last_event_time = r.get("eventsub:last_event_time")

        # Decode Redis bytes to string
        is_connected_str = (
            eventsub_connected.decode("utf-8") if eventsub_connected else None
        )

        if is_connected_str == "1":
            # Check if we've received events recently (within 15 minutes)
            if last_event_time:
                try:
                    last_time = float(last_event_time.decode("utf-8"))
                    time_since_event = time.time() - last_time
                    minutes_since = int(time_since_event / 60)
                except (ValueError, AttributeError) as conv_err:
                    # Invalid timestamp in Redis
                    status["services"]["eventsub"] = (
                        f"error: invalid timestamp ({conv_err})"
                    )
                    status["status"] = "degraded"
                    http_status = 503
                    return JsonResponse(status, status=http_status)

                if time_since_event < settings.EVENTSUB_STALENESS_THRESHOLD_SECONDS:
                    status["services"]["eventsub"] = (
                        f"ok (last event {minutes_since}m ago)"
                    )
                else:
                    status["services"]["eventsub"] = (
                        f"stale (no events for {minutes_since}m)"
                    )
                    status["status"] = "degraded"
                    http_status = 503
            else:
                status["services"]["eventsub"] = "connected (no events yet)"
        else:
            status["services"]["eventsub"] = "disconnected"
            status["status"] = "degraded"
            http_status = 503

    except Exception as e:
        # Redis connection failed - mark both services as error
        status["services"]["redis"] = f"error: {str(e)}"
        status["services"]["eventsub"] = "error: unable to check (Redis unavailable)"
        status["status"] = "degraded"
        http_status = 503

    return JsonResponse(status, status=http_status)
