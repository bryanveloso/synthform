from __future__ import annotations

import json

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

    # Check Redis (if configured)
    try:
        import redis

        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        status["services"]["redis"] = "ok"
    except Exception as e:
        status["services"]["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"
        http_status = 503

    return JsonResponse(status, status=http_status)
